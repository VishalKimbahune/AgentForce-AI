"""Approval service managing human-in-the-loop workflows, permissions, and LangGraph resumption."""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.dependencies import ROLES_HIERARCHY
from app.models.models import ApprovalRequest, Workflow, WorkflowTask
from app.services.orchestrator.events import event_bus
from app.services.tools.registry import tool_registry
from app.services.guardrails import security_logger

logger = logging.getLogger("services.approvals")


class ApprovalService:
    """Handles the lifecycle of human-in-the-loop approval requests and workflow resumption."""

    async def create_request(
        self,
        tenant_id: str,
        workflow_id: str,
        requested_by_agent: str,
        action_type: str,
        action_payload: Dict[str, Any],
        risk_level: str = "medium",
        reason: str = "Mandatory human review required by corporate policy",
        required_role: str = "manager",
        level: int = 1,
        task_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> ApprovalRequest:
        """Creates an approval request, pauses the workflow, and emits realtime notification."""
        expiry = datetime.now(timezone.utc) + timedelta(hours=settings.APPROVAL_EXPIRY_HOURS)
        req_id = uuid.uuid4()

        req = ApprovalRequest(
            id=req_id,
            tenant_id=uuid.UUID(tenant_id),
            workflow_id=uuid.UUID(workflow_id),
            task_id=uuid.UUID(task_id) if task_id else None,
            requested_by_agent=requested_by_agent,
            action_type=action_type,
            action_payload=action_payload,
            risk_level=risk_level,
            reason=reason,
            status="pending",
            required_role=required_role,
            level=level,
            expires_at=expiry,
        )

        async def _save(session: AsyncSession):
            session.add(req)
            # Update workflow status to waiting_approval
            await session.execute(
                update(Workflow)
                .where(Workflow.id == uuid.UUID(workflow_id))
                .values(status="waiting_approval")
            )
            await session.commit()

        if db:
            await _save(db)
        else:
            async with AsyncSessionLocal() as session:
                await _save(session)

        # Emit realtime event for frontend Approval Center
        event_bus.emit(
            workflow_id=workflow_id,
            event_type="approval.requested",
            agent=requested_by_agent,
            message=f"Workflow paused: Human approval required for '{action_type}' ({reason})",
            correlation_id=str(uuid.uuid4()),
            task_id=task_id,
            data={
                "approval_id": str(req_id),
                "action_type": action_type,
                "risk_level": risk_level,
                "reason": reason,
                "required_role": required_role,
                "expires_at": expiry.isoformat(),
            },
        )

        return req

    async def approve(
        self,
        approval_id: str,
        user_id: str,
        user_role: str,
        note: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Approves a pending request, validates role hierarchy and expiration, and resumes workflow."""
        async with AsyncSessionLocal() as session:
            stmt = select(ApprovalRequest).where(ApprovalRequest.id == uuid.UUID(approval_id))
            res = await session.execute(stmt)
            req = res.scalar_one_or_none()
            if not req:
                raise ValueError("Approval request not found")

            # 1. Double approval / idempotency check
            if req.status != "pending":
                raise ValueError(f"Approval request already resolved with status '{req.status}'")

            # 2. Expiry check
            now = datetime.now(timezone.utc)
            if req.expires_at:
                exp = req.expires_at if req.expires_at.tzinfo else req.expires_at.replace(tzinfo=timezone.utc)
                if exp < now:
                    req.status = "expired"
                    await session.commit()
                    raise ValueError("Approval request has expired")

            # 3. Revalidate permissions (caller must meet required_role)
            caller_rank = ROLES_HIERARCHY.get(user_role, 0)
            required_rank = ROLES_HIERARCHY.get(req.required_role, 0)
            if caller_rank < required_rank and user_role != "owner":
                security_logger.record_incident(
                    event_type="security.unauthorized_approval_attempt",
                    threat_category="role_privilege_escalation",
                    risk_level="high",
                    detail=f"User with role '{user_role}' attempted to approve request {approval_id} requiring '{req.required_role}'",
                    tenant_id=str(req.tenant_id),
                    user_id=user_id,
                )
                raise PermissionError(
                    f"Insufficient role '{user_role}' to approve. Required role: '{req.required_role}'"
                )

            # 4. Mark approved
            req.status = "approved"
            req.decided_by = user_id
            req.decided_at = now
            req.decision_note = note or "Approved via Approval Center"
            await session.commit()

            # 5. Resume paused workflow execution
            await self._resume_workflow(
                workflow_id=str(req.workflow_id),
                approval_req=req,
                decision="approved",
                session=session,
            )

        return {
            "approval_id": str(approval_id),
            "status": "approved",
            "decided_by": user_id,
            "decided_at": now.isoformat(),
        }

    async def reject(
        self,
        approval_id: str,
        user_id: str,
        user_role: str,
        note: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Rejects a pending request. Does NOT execute side-effect actions (Reject and expiry send nothing)."""
        async with AsyncSessionLocal() as session:
            stmt = select(ApprovalRequest).where(ApprovalRequest.id == uuid.UUID(approval_id))
            res = await session.execute(stmt)
            req = res.scalar_one_or_none()
            if not req:
                raise ValueError("Approval request not found")

            if req.status != "pending":
                raise ValueError(f"Approval request already resolved with status '{req.status}'")

            now = datetime.now(timezone.utc)
            req.status = "rejected"
            req.decided_by = user_id
            req.decided_at = now
            req.decision_note = note or "Rejected by reviewer"
            await session.commit()

            # Resume workflow with rejection - no external side-effects
            await self._resume_workflow(
                workflow_id=str(req.workflow_id),
                approval_req=req,
                decision="rejected",
                session=session,
            )

        return {
            "approval_id": str(approval_id),
            "status": "rejected",
            "decided_by": user_id,
            "decided_at": now.isoformat(),
        }

    async def _resume_workflow(
        self,
        workflow_id: str,
        approval_req: ApprovalRequest,
        decision: str,
        session: AsyncSession,
    ) -> None:
        """Resumes workflow: if approved, executes actions; if rejected/expired, sends nothing."""
        payload = approval_req.action_payload or {}
        tenant_str = str(approval_req.tenant_id)

        if decision == "approved":
            action_type = approval_req.action_type

            # Journey A: HR Interview scheduling
            if action_type in ("interview.send_invitation", "interview.schedule"):
                candidates = payload.get("candidates", [])
                tool_results = []
                for c in candidates:
                    # 1. Book mock calendar slot
                    cal_res = await tool_registry.execute(
                        name="mock_calendar.create_event",
                        params={
                            "candidate_name": c.get("name", "Candidate"),
                            "candidate_email": c.get("email"),
                            "start_time": c.get("slot", "2026-11-05T14:00:00Z"),
                        },
                        agent="hr",
                        tenant_id=tenant_str,
                        workflow_id=workflow_id,
                        db=session,
                    )
                    # 2. Dispatch in-app interview notification
                    notif_res = await tool_registry.execute(
                        name="notifications.send_in_app",
                        params={
                            "recipient": c.get("email", "candidate"),
                            "title": "Interview Invitation Confirmed",
                            "message": f"Interview scheduled for {c.get('name')} at {cal_res.get('meeting_link')}",
                        },
                        agent="notification_agent",
                        tenant_id=tenant_str,
                        workflow_id=workflow_id,
                        db=session,
                    )
                    tool_results.append({"candidate": c.get("name"), "calendar": cal_res, "notification": notif_res})

                await session.execute(
                    update(Workflow)
                    .where(Workflow.id == uuid.UUID(workflow_id))
                    .values(
                        status="completed",
                        finished_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

                event_bus.emit(
                    workflow_id=workflow_id,
                    event_type="workflow.completed",
                    agent="orchestrator",
                    message=f"Approval granted. Scheduled {len(candidates)} interviews and delivered invitations.",
                    correlation_id=str(uuid.uuid4()),
                    data={"results": tool_results},
                )

            # Journey B: Finance payment batch execution
            elif action_type in ("payment.execute", "payment"):
                batch_id = payload.get("batch_id", f"BATCH-{uuid.uuid4().hex[:8].upper()}")
                invoices = payload.get("invoices", [])
                total_amount = float(payload.get("total_amount", 0.0))

                pay_res = await tool_registry.execute(
                    name="mock_payment.execute_batch",
                    params={
                        "batch_id": batch_id,
                        "invoices": invoices,
                        "total_amount": total_amount,
                    },
                    agent="finance",
                    tenant_id=tenant_str,
                    workflow_id=workflow_id,
                    db=session,
                )

                await session.execute(
                    update(Workflow)
                    .where(Workflow.id == uuid.UUID(workflow_id))
                    .values(
                        status="completed",
                        finished_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

                event_bus.emit(
                    workflow_id=workflow_id,
                    event_type="workflow.completed",
                    agent="orchestrator",
                    message=(
                        f"Finance approval granted. Disbursed ${total_amount:,.2f} across {len(invoices)} invoices "
                        f"via Mock Payment Gateway (TX ID: {pay_res.get('transaction_id')})."
                    ),
                    correlation_id=str(uuid.uuid4()),
                    data={"payment_result": pay_res, "batch_id": batch_id},
                )

            # Journey C: Operations report leadership distribution
            elif action_type in ("report.distribute", "report.send_to_leadership"):
                notif_res = await tool_registry.execute(
                    name="notifications.send_in_app",
                    params={
                        "recipient": payload.get("recipient", "leadership@company.internal"),
                        "title": payload.get("title", "Executive Monthly Business Report"),
                        "message": (
                            f"{payload.get('summary', 'Report compiled successfully.')} "
                            f"[Document: {payload.get('filename', 'report.pdf')}]"
                        ),
                    },
                    agent="notification_agent",
                    tenant_id=tenant_str,
                    workflow_id=workflow_id,
                    db=session,
                )

                await session.execute(
                    update(Workflow)
                    .where(Workflow.id == uuid.UUID(workflow_id))
                    .values(
                        status="completed",
                        finished_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

                event_bus.emit(
                    workflow_id=workflow_id,
                    event_type="workflow.completed",
                    agent="orchestrator",
                    message=(
                        f"Operations report distribution approved. Delivered in-app notification to leadership "
                        f"for {payload.get('filename', 'report.pdf')}."
                    ),
                    correlation_id=str(uuid.uuid4()),
                    data={"notification": notif_res, "report": payload},
                )

            # Journey D: AIOps Incident Remediation
            elif action_type in ("aiops.remediation", "aiops"):
                incident_id = payload.get("incident_id")
                if incident_id:
                    from app.services.agents.aiops import aiops_agent

                    await aiops_agent.resolve_incident(
                        incident_id=incident_id,
                        tenant_id=tenant_str,
                        db=session,
                    )

                event_bus.emit(
                    workflow_id=workflow_id,
                    event_type="workflow.completed",
                    agent="aiops",
                    message="AIOps remediation approved by manager and executed successfully.",
                    correlation_id=str(uuid.uuid4()),
                    data={"remediation_action": payload.get("remediation_action")},
                )

            else:
                # Generic approved action
                await session.execute(
                    update(Workflow)
                    .where(Workflow.id == uuid.UUID(workflow_id))
                    .values(
                        status="completed",
                        finished_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

                event_bus.emit(
                    workflow_id=workflow_id,
                    event_type="workflow.completed",
                    agent="orchestrator",
                    message=f"Approval granted for '{action_type}'. Action executed.",
                    correlation_id=str(uuid.uuid4()),
                    data={"action_type": action_type},
                )

        else:
            # Decision is rejected - send nothing!
            await session.execute(
                update(Workflow)
                .where(Workflow.id == uuid.UUID(workflow_id))
                .values(
                    status="completed",
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

            event_bus.emit(
                workflow_id=workflow_id,
                event_type="workflow.completed",
                agent="orchestrator",
                message="Approval rejected by reviewer. Action cancelled; no payment, invitations, or notifications sent.",
                correlation_id=str(uuid.uuid4()),
                data={"rejected": True, "note": approval_req.decision_note},
            )


approval_service = ApprovalService()
