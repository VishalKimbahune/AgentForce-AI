"""Workflow API router: lifecycle management, inter-agent traces, and SSE live events."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.correlation import get_correlation_id
from app.core.database import get_db
from app.core.dependencies import TenantContext, get_tenant_context
from app.core.security import verify_supabase_token
from app.models.models import AgentMessage, Workflow, WorkflowTask
from app.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowResponse,
)
from app.services.orchestrator.events import event_bus
from app.services.orchestrator.graph import execute_workflow_graph
from app.services.guardrails import prompt_injection_guard, security_logger

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_workflow(
    req: WorkflowCreateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Submits a new workflow instruction with optional idempotency, prompt injection guard, and triggers orchestrator."""
    # 1. Guardrail Check: Prompt Injection Detection
    injection_check = prompt_injection_guard.scan(req.input)
    if injection_check.is_injection:
        corr_id = get_correlation_id()
        security_logger.record_incident(
            event_type="security.prompt_injection",
            threat_category=injection_check.category,
            risk_level=injection_check.risk_level,
            detail=injection_check.detail,
            tenant_id=str(ctx.tenant_id),
            user_id=str(ctx.user.id),
            correlation_id=corr_id,
            payload_sample={"input": req.input[:120]},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prompt injection detected. Request rejected by security guardrails: {injection_check.detail}",
        )

    # 2. Check idempotency
    if idempotency_key:
        stmt = select(Workflow).where(
            Workflow.tenant_id == ctx.tenant_id,
            Workflow.idempotency_key == idempotency_key,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "workflow_id": str(existing.id),
                    "status": existing.status,
                    "idempotent_replay": True,
                },
            )

    corr_id = get_correlation_id()
    wf_id = uuid.uuid4()
    wf = Workflow(
        id=wf_id,
        tenant_id=ctx.tenant_id,
        created_by=str(ctx.user.id),
        input_text=req.input,
        input_source="text",
        status="pending",
        idempotency_key=idempotency_key,
        correlation_id=corr_id,
        cost_usd=0.0,
        tokens_used=0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    # Trigger orchestrator execution asynchronously in background
    asyncio.create_task(
        execute_workflow_graph(
            workflow_id=str(wf.id),
            tenant_id=str(ctx.tenant_id),
            input_text=req.input,
            correlation_id=corr_id,
        )
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"workflow_id": str(wf.id), "status": "pending"},
    )


@router.get("", response_model=List[WorkflowResponse])
async def list_workflows(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Lists workflows strictly isolated to the caller's tenant."""
    query = (
        select(Workflow)
        .where(Workflow.tenant_id == ctx.tenant_id)
        .order_by(Workflow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter:
        query = query.where(Workflow.status == status_filter)

    result = await db.execute(query)
    workflows = result.scalars().all()
    return workflows


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves workflow status, plan, tasks, cost, and tokens."""
    query = select(Workflow).where(
        Workflow.id == workflow_id,
        Workflow.tenant_id == ctx.tenant_id,
    )
    result = await db.execute(query)
    wf = result.scalar_one_or_none()
    if not wf:
        leak_stmt = select(Workflow.tenant_id).where(Workflow.id == workflow_id)
        leak_res = await db.execute(leak_stmt)
        other_tenant = leak_res.scalar_one_or_none()
        if other_tenant and other_tenant != ctx.tenant_id:
            security_logger.record_incident(
                event_type="security.cross_tenant_access_attempt",
                threat_category="multi_tenant_boundary_violation",
                risk_level="critical",
                detail=f"Tenant {ctx.tenant_id} attempted unauthorized access to workflow {workflow_id} owned by tenant {other_tenant}",
                tenant_id=str(ctx.tenant_id),
                user_id=str(ctx.user.id),
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    return wf


@router.get("/{workflow_id}/messages")
async def get_workflow_messages(
    workflow_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Returns inter-agent message trace for the workflow."""
    # Verify workflow exists for tenant
    wf_res = await db.execute(
        select(Workflow.id).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == ctx.tenant_id,
        )
    )
    if not wf_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    stmt = (
        select(AgentMessage)
        .where(
            AgentMessage.workflow_id == workflow_id,
            AgentMessage.tenant_id == ctx.tenant_id,
        )
        .order_by(AgentMessage.created_at.asc())
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "workflow_id": str(m.workflow_id),
            "tenant_id": str(m.tenant_id),
            "source_agent": m.source_agent,
            "destination_agent": m.destination_agent,
            "payload": m.payload,
            "correlation_id": m.correlation_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


@router.get("/{workflow_id}/events")
async def stream_workflow_events(
    workflow_id: uuid.UUID,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Server-Sent Events (SSE) live timeline stream."""
    raw_token = token or (authorization.split(" ", 1)[1] if authorization and " " in authorization else authorization)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials for event stream",
        )

    # Verify user token
    claims = verify_supabase_token(raw_token)

    # Verify workflow exists
    wf_query = select(Workflow).where(Workflow.id == workflow_id)
    wf_res = await db.execute(wf_query)
    wf = wf_res.scalar_one_or_none()
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    return StreamingResponse(
        event_bus.subscribe(str(workflow_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(
    workflow_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Cancels a pending or running workflow."""
    query = select(Workflow).where(
        Workflow.id == workflow_id,
        Workflow.tenant_id == ctx.tenant_id,
    )
    result = await db.execute(query)
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    wf.status = "cancelled"
    wf.finished_at = datetime.now(timezone.utc)
    await db.commit()

    event_bus.emit(
        workflow_id=str(wf.id),
        event_type="workflow.failed",
        agent="orchestrator",
        message="Workflow was cancelled by user.",
        correlation_id=wf.correlation_id or str(uuid.uuid4()),
    )

    return {"workflow_id": str(wf.id), "status": "cancelled"}
