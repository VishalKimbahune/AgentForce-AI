"""AIOps API Router: incident management, automated anomaly detection, and governed remediation."""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_tenant_context
from app.models.models import AIOpsIncident
from app.services.agents.aiops import aiops_agent

router = APIRouter(prefix="/aiops", tags=["aiops"])


class IncidentResponse(BaseModel):
    id: str
    tenant_id: str
    severity: str
    summary: str
    root_cause_hypothesis: Optional[str]
    recommendation: Optional[str]
    status: str
    created_at: str
    resolved_at: Optional[str] = None


class SimulateFailureRequest(BaseModel):
    agent_name: str = Field("recruitment", description="Agent to simulate failure on")
    error_reason: str = Field(
        "ATS mock integration at http://localhost:8101 connection timed out after 30s",
        description="Simulated failure message",
    )


@router.get("/incidents", response_model=List[IncidentResponse])
async def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Lists AIOps incidents strictly filtered by tenant."""
    query = select(AIOpsIncident).where(AIOpsIncident.tenant_id == ctx.tenant_id)
    if status_filter:
        query = query.where(AIOpsIncident.status == status_filter)

    query = query.order_by(AIOpsIncident.created_at.desc())
    res = await db.execute(query)
    incidents = res.scalars().all()

    return [
        IncidentResponse(
            id=str(inc.id),
            tenant_id=str(inc.tenant_id),
            severity=inc.severity,
            summary=inc.summary,
            root_cause_hypothesis=inc.root_cause_hypothesis,
            recommendation=inc.recommendation,
            status=inc.status,
            created_at=inc.created_at.isoformat() if inc.created_at else "",
            resolved_at=inc.resolved_at.isoformat() if inc.resolved_at else None,
        )
        for inc in incidents
    ]


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Fetches single incident details ensuring tenant isolation."""
    try:
        inc_uuid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid incident ID format")

    inc = await db.get(AIOpsIncident, inc_uuid)
    if not inc or inc.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    return IncidentResponse(
        id=str(inc.id),
        tenant_id=str(inc.tenant_id),
        severity=inc.severity,
        summary=inc.summary,
        root_cause_hypothesis=inc.root_cause_hypothesis,
        recommendation=inc.recommendation,
        status=inc.status,
        created_at=inc.created_at.isoformat() if inc.created_at else "",
        resolved_at=inc.resolved_at.isoformat() if inc.resolved_at else None,
    )


@router.post("/scan", response_model=List[IncidentResponse])
async def trigger_anomaly_scan(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Triggers an autonomous AIOps anomaly scan over recent workforce telemetry."""
    new_incidents = await aiops_agent.scan_anomalies(tenant_id=str(ctx.tenant_id), db=db)
    return [
        IncidentResponse(
            id=str(inc.id),
            tenant_id=str(inc.tenant_id),
            severity=inc.severity,
            summary=inc.summary,
            root_cause_hypothesis=inc.root_cause_hypothesis,
            recommendation=inc.recommendation,
            status=inc.status,
            created_at=inc.created_at.isoformat() if inc.created_at else "",
            resolved_at=inc.resolved_at.isoformat() if inc.resolved_at else None,
        )
        for inc in new_incidents
    ]


@router.post("/simulate-failure", status_code=status.HTTP_201_CREATED, response_model=IncidentResponse)
async def simulate_failure_and_diagnose(
    req: SimulateFailureRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Forces an agent failure to verify incident detection and root-cause hypothesis generation (Done When condition)."""
    incident = await aiops_agent.simulate_forced_failure(
        tenant_id=str(ctx.tenant_id),
        agent_name=req.agent_name,
        error_reason=req.error_reason,
        db=db,
    )
    return IncidentResponse(
        id=str(incident.id),
        tenant_id=str(incident.tenant_id),
        severity=incident.severity,
        summary=incident.summary,
        root_cause_hypothesis=incident.root_cause_hypothesis,
        recommendation=incident.recommendation,
        status=incident.status,
        created_at=incident.created_at.isoformat() if incident.created_at else "",
        resolved_at=incident.resolved_at.isoformat() if incident.resolved_at else None,
    )


@router.post("/incidents/{incident_id}/remediate")
async def remediate_incident(
    incident_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Creates a Human-in-the-Loop approval request before applying remediation."""
    if not ctx.has_role(["owner", "manager"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AIOps remediation requires manager or owner permissions",
        )

    try:
        app_req = await aiops_agent.request_remediation(
            incident_id=incident_id,
            tenant_id=str(ctx.tenant_id),
            user_role=ctx.role,
            user_id=str(ctx.user.id),
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    return {
        "status": "remediation_requested",
        "incident_id": incident_id,
        "approval_request_id": str(app_req.id),
        "message": "Remediation submitted to Approval Center for human verification.",
    }


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Marks an incident as resolved."""
    if not ctx.has_role(["owner", "manager"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resolving incidents requires manager or owner permissions",
        )

    incident = await aiops_agent.resolve_incident(
        incident_id=incident_id,
        tenant_id=str(ctx.tenant_id),
        db=db,
    )
    return {
        "status": "resolved",
        "incident_id": str(incident.id),
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else "",
    }

