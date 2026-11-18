"""Audit Logs API Router: immutable audit trail inspection and compliance CSV export."""

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_tenant_context, require_role
from app.models.models import AuditLog

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


class AuditLogResponse(BaseModel):
    id: str
    tenant_id: str
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details_redacted: Optional[Dict[str, Any]]
    ip: Optional[str]
    correlation_id: Optional[str]
    created_at: str


class CreateAuditLogRequest(BaseModel):
    actor_type: str = Field(..., description="user|agent|system")
    action: str = Field(..., description="Action performed, e.g. approval.decide")
    resource_type: str = Field(..., description="Target resource type")
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@router.get("")
async def list_or_export_audit_logs(
    actor_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    export: Optional[str] = Query(None, description="Set to 'csv' to download as CSV"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves audit trail entries strictly filtered by tenant with optional CSV export (Screen 15)."""
    query = select(AuditLog).where(AuditLog.tenant_id == ctx.tenant_id)

    if actor_type:
        query = query.where(AuditLog.actor_type == actor_type)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)

    query = query.order_by(AuditLog.created_at.desc())

    if export != "csv":
        query = query.limit(limit).offset(offset)

    res = await db.execute(query)
    logs = res.scalars().all()

    # CSV Export format for compliance auditors
    if export == "csv":
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        # Header
        writer.writerow(
            [
                "Audit ID",
                "Timestamp (UTC)",
                "Actor Type",
                "Actor ID",
                "Action",
                "Resource Type",
                "Resource ID",
                "Correlation ID",
                "IP Address",
            ]
        )
        for log in logs:
            writer.writerow(
                [
                    str(log.id),
                    log.created_at.isoformat() if log.created_at else "",
                    log.actor_type,
                    log.actor_id,
                    log.action,
                    log.resource_type,
                    log.resource_id or "",
                    log.correlation_id or "",
                    log.ip or "",
                ]
            )

        csv_content = output.getvalue()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="audit_logs.csv"'},
        )

    return [
        AuditLogResponse(
            id=str(log.id),
            tenant_id=str(log.tenant_id),
            actor_type=log.actor_type,
            actor_id=log.actor_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details_redacted=log.details_redacted,
            ip=log.ip,
            correlation_id=log.correlation_id,
            created_at=log.created_at.isoformat() if log.created_at else "",
        )
        for log in logs
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AuditLogResponse)
async def record_audit_log(
    req: CreateAuditLogRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Appends an immutable audit log record for the tenant."""
    log_entry = AuditLog(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        actor_type=req.actor_type,
        actor_id=str(ctx.user.id),
        action=req.action,
        resource_type=req.resource_type,
        resource_id=req.resource_id,
        details_redacted=req.details,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)

    return AuditLogResponse(
        id=str(log_entry.id),
        tenant_id=str(log_entry.tenant_id),
        actor_type=log_entry.actor_type,
        actor_id=log_entry.actor_id,
        action=log_entry.action,
        resource_type=log_entry.resource_type,
        resource_id=log_entry.resource_id,
        details_redacted=log_entry.details_redacted,
        ip=log_entry.ip,
        correlation_id=log_entry.correlation_id,
        created_at=log_entry.created_at.isoformat() if log_entry.created_at else "",
    )

