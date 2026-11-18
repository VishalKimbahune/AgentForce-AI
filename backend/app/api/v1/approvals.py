"""Approvals API router: listing, reviewing, approving, rejecting, and delegating human-in-the-loop actions."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_tenant_context
from app.models.models import ApprovalRequest
from app.schemas.approval import (
    ApprovalDecisionRequest,
    ApprovalDelegateRequest,
    ApprovalResponse,
)
from app.services.approvals.service import approval_service
from app.services.guardrails import security_logger

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=List[ApprovalResponse])
async def list_approvals(
    status_filter: Optional[str] = Query(None, alias="status"),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Lists approval requests isolated to caller's tenant."""
    query = (
        select(ApprovalRequest)
        .where(ApprovalRequest.tenant_id == ctx.tenant_id)
        .order_by(ApprovalRequest.created_at.desc())
    )
    if status_filter:
        query = query.where(ApprovalRequest.status == status_filter)

    res = await db.execute(query)
    approvals = res.scalars().all()
    return approvals


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves approval details with action payload and justification."""
    query = select(ApprovalRequest).where(
        ApprovalRequest.id == approval_id,
        ApprovalRequest.tenant_id == ctx.tenant_id,
    )
    res = await db.execute(query)
    req = res.scalar_one_or_none()
    if not req:
        leak_stmt = select(ApprovalRequest.tenant_id).where(ApprovalRequest.id == approval_id)
        leak_res = await db.execute(leak_stmt)
        other_tenant = leak_res.scalar_one_or_none()
        if other_tenant and other_tenant != ctx.tenant_id:
            security_logger.record_incident(
                event_type="security.cross_tenant_access_attempt",
                threat_category="multi_tenant_boundary_violation",
                risk_level="critical",
                detail=f"Tenant {ctx.tenant_id} attempted unauthorized access to approval {approval_id} owned by tenant {other_tenant}",
                tenant_id=str(ctx.tenant_id),
                user_id=str(ctx.user.id),
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found",
        )
    return req


@router.post("/{approval_id}/approve")
async def approve_request(
    approval_id: uuid.UUID,
    body: Optional[ApprovalDecisionRequest] = None,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Approves request, revalidates permissions, and resumes workflow execution."""
    note = body.note if body else ""
    try:
        result = await approval_service.approve(
            approval_id=str(approval_id),
            user_id=str(ctx.user.id),
            user_role=ctx.role,
            note=note,
            db=db,
        )
        return result
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/{approval_id}/reject")
async def reject_request(
    approval_id: uuid.UUID,
    body: Optional[ApprovalDecisionRequest] = None,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Rejects request and resumes workflow with rejected state (sends no external side-effects)."""
    note = body.note if body else ""
    try:
        result = await approval_service.reject(
            approval_id=str(approval_id),
            user_id=str(ctx.user.id),
            user_role=ctx.role,
            note=note,
            db=db,
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/{approval_id}/delegate")
async def delegate_request(
    approval_id: uuid.UUID,
    body: ApprovalDelegateRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Delegates approval to another authorized team member."""
    stmt = select(ApprovalRequest).where(
        ApprovalRequest.id == approval_id,
        ApprovalRequest.tenant_id == ctx.tenant_id,
    )
    res = await db.execute(stmt)
    req = res.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")

    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot delegate resolved request ({req.status})")

    req.decision_note = f"Delegated to user {body.to_user_id} by {ctx.user.id}"
    await db.commit()

    return {"delegated": True, "approval_id": str(approval_id), "to_user_id": body.to_user_id}

