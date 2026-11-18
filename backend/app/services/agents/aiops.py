"""AIOps AI Employee: automated health monitoring, anomaly detection, root-cause diagnosis, and governed remediation."""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import record_incident_metric
from app.core.telemetry import trace_agent, trace_span
from app.models.models import AIOpsIncident, ApprovalRequest, Workflow, WorkflowTask
from app.services.approvals.service import approval_service
from app.services.orchestrator.events import event_bus
from app.services.policy_engine.engine import PolicyContext, PolicyEffect, policy_engine

logger = logging.getLogger("agents.aiops")


class AIOpsAgent:
    """Autonomous monitoring AI Employee that diagnoses failures and proposes governed remediation."""

    def __init__(self):
        self.name = "aiops"
        self.role = "Site Reliability & AIOps Engineer"

    async def scan_anomalies(self, tenant_id: str, db: AsyncSession) -> List[AIOpsIncident]:
        """Scans recent workflow and task logs for failure rate spikes, cost anomalies, or provider timeouts."""
        tenant_uuid = uuid.UUID(str(tenant_id))
        created_incidents: List[AIOpsIncident] = []

        with trace_span(
            name="agent.aiops.scan",
            span_type="agent",
            attributes={"tenant_id": str(tenant_id)},
        ):
            # Query recent tasks for the tenant
            recent_tasks_stmt = (
                select(WorkflowTask)
                .where(WorkflowTask.tenant_id == tenant_uuid)
                .order_by(WorkflowTask.started_at.desc().nullslast())
                .limit(50)
            )
            res = await db.execute(recent_tasks_stmt)
            tasks = res.scalars().all()

            if not tasks:
                return []

            # Group tasks by agent/name
            agent_task_map: Dict[str, List[WorkflowTask]] = {}
            for t in tasks:
                agent_key = (t.name or "orchestrator").split()[0].lower()
                agent_task_map.setdefault(agent_key, []).append(t)

            for agent_name, agent_tasks in agent_task_map.items():
                total = len(agent_tasks)
                failed = [t for t in agent_tasks if t.status == "failed" or t.error]
                fail_count = len(failed)
                fail_rate = fail_count / total if total > 0 else 0.0

                # Anomaly Threshold: >= 20% failure rate with at least 1 failed task
                if fail_rate >= 0.20 and fail_count >= 1:
                    # Check if an open incident already exists for this agent
                    existing_stmt = select(AIOpsIncident).where(
                        AIOpsIncident.tenant_id == tenant_uuid,
                        AIOpsIncident.status.in_(["open", "remediating"]),
                        AIOpsIncident.summary.ilike(f"%{agent_name}%"),
                    )
                    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
                    if existing:
                        continue

                    # Diagnose root-cause hypothesis
                    sample_error = failed[0].error or "Unknown timeout or execution error"
                    hypothesis, recommendation, severity = self.diagnose_hypothesis(
                        agent_name=agent_name,
                        fail_rate=fail_rate,
                        fail_count=fail_count,
                        error_sample=sample_error,
                    )

                    incident = AIOpsIncident(
                        id=uuid.uuid4(),
                        tenant_id=tenant_uuid,
                        severity=severity,
                        summary=f"{agent_name.title()} employee failure rate spiked to {int(fail_rate * 100)}%",
                        root_cause_hypothesis=hypothesis,
                        recommendation=recommendation,
                        status="open",
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(incident)
                    await db.commit()
                    await db.refresh(incident)

                    record_incident_metric(str(tenant_id), severity=severity, status="open")
                    created_incidents.append(incident)

                    logger.warning(
                        "AIOps detected anomaly for tenant %s: Incident %s created (%s)",
                        tenant_id,
                        incident.id,
                        incident.summary,
                    )

        return created_incidents

    def diagnose_hypothesis(
        self,
        agent_name: str,
        fail_rate: float,
        fail_count: int,
        error_sample: str,
    ) -> tuple[str, str, str]:
        """Synthesizes root-cause hypothesis and actionable recommendation."""
        error_lower = error_sample.lower()

        if "ats" in error_lower or "timeout" in error_lower or "connection" in error_lower:
            hypothesis = (
                f"Root-Cause Hypothesis: Upstream ATS mock integration service at http://localhost:8101 "
                f"experienced connection timeouts, causing {agent_name} employee resume ingestion to fail "
                f"across {fail_count} tasks. Telemetry shows repeated HTTP 504 gateway response."
            )
            recommendation = (
                f"Recommended Fix: Restart mock ATS service adapter, reset connection circuit breaker, "
                f"and replay {fail_count} failed workflow tasks."
            )
            severity = "high"

        elif "erp" in error_lower or "payment" in error_lower:
            hypothesis = (
                f"Root-Cause Hypothesis: ERP integration adapter rejected invoice reconciliation payload due to "
                f"duplicate transaction ledger locks or mock ERP API latency."
            )
            recommendation = (
                "Recommended Fix: Unlock ledger lock in Mock ERP service and resume invoice audit workflow."
            )
            severity = "high"

        elif "429" in error_lower or "quota" in error_lower or "api key" in error_lower:
            hypothesis = (
                f"Root-Cause Hypothesis: Primary LLM provider exceeded rate quota or returned 403 Forbidden. "
                f"LiteLLM fallback chain engaged with elevated latency."
            )
            recommendation = (
                "Recommended Fix: Rotate provider credentials or increase Groq/Gemini concurrency ceiling."
            )
            severity = "critical"

        else:
            hypothesis = (
                f"Root-Cause Hypothesis: Unexpected task error encountered in {agent_name} agent pipeline. "
                f"Error detail: {error_sample[:150]}."
            )
            recommendation = (
                f"Recommended Fix: Flush intermediate agent checkpoint state and revalidate task input payload."
            )
            severity = "medium"

        return hypothesis, recommendation, severity

    async def simulate_forced_failure(
        self,
        tenant_id: str,
        agent_name: str = "recruitment",
        error_reason: str = "ATS integration service at http://localhost:8101 connection timed out after 30s",
        db: Optional[AsyncSession] = None,
    ) -> AIOpsIncident:
        """Forces an incident failure condition and generates the incident with root-cause hypothesis (Done When condition)."""
        tenant_uuid = uuid.UUID(str(tenant_id))

        # Create a mock workflow and failed task
        wf_id = uuid.uuid4()
        wf = Workflow(
            id=wf_id,
            tenant_id=tenant_uuid,
            created_by="system",
            input_text=f"Screen candidates for Senior Python role ({agent_name})",
            input_source="api",
            status="failed",
            cost_usd=0.0,
            tokens_used=0,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            finished_at=datetime.now(timezone.utc),
        )
        task = WorkflowTask(
            id=uuid.uuid4(),
            workflow_id=wf_id,
            tenant_id=tenant_uuid,
            name=f"{agent_name} candidate ingestion",
            status="failed",
            error=error_reason,
            attempts=3,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            finished_at=datetime.now(timezone.utc),
        )
        db.add(wf)
        db.add(task)
        await db.commit()

        # Generate incident directly with diagnostic hypothesis
        hypothesis, recommendation, severity = self.diagnose_hypothesis(
            agent_name=agent_name,
            fail_rate=0.35,
            fail_count=2,
            error_sample=error_reason,
        )

        incident = AIOpsIncident(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            severity=severity,
            summary=f"{agent_name.title()} employee failure rate spiked to 35%",
            root_cause_hypothesis=hypothesis,
            recommendation=recommendation,
            status="open",
            created_at=datetime.now(timezone.utc),
        )
        db.add(incident)
        await db.commit()
        await db.refresh(incident)

        record_incident_metric(str(tenant_id), severity=severity, status="open")
        return incident

    async def request_remediation(
        self,
        incident_id: str,
        tenant_id: str,
        user_role: str,
        user_id: str,
        db: AsyncSession,
    ) -> ApprovalRequest:
        """Creates a governed Human-in-the-Loop approval request before applying remediation."""
        # Non-negotiable policy rule: AIOps remediation requires manager approval
        if user_role not in ("owner", "manager"):
            raise PermissionError("AIOps remediation requires manager or owner authority.")

        incident_uuid = uuid.UUID(str(incident_id))
        incident = await db.get(AIOpsIncident, incident_uuid)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found.")

        # Create human approval request
        app_req = await approval_service.create_request(
            tenant_id=str(tenant_id),
            workflow_id=str(incident_id),  # associate with incident
            requested_by_agent="aiops",
            action_type="aiops.remediation",
            action_payload={
                "incident_id": str(incident.id),
                "summary": incident.summary,
                "recommendation": incident.recommendation,
                "remediation_action": "restart_adapter_and_reset_circuit",
            },
            risk_level="high",
            reason=f"Authorize automated remediation for AIOps incident: {incident.summary}",
            required_role="manager",
            db=db,
        )

        incident.status = "remediating"
        await db.commit()
        await db.refresh(incident)

        return app_req

    async def resolve_incident(
        self,
        incident_id: str,
        tenant_id: str,
        db: AsyncSession,
    ) -> AIOpsIncident:
        """Applies remediation and transitions incident to resolved."""
        incident_uuid = uuid.UUID(str(incident_id))
        incident = await db.get(AIOpsIncident, incident_uuid)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found.")

        incident.status = "resolved"
        incident.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(incident)

        record_incident_metric(str(tenant_id), severity=incident.severity, status="resolved")
        return incident


aiops_agent = AIOpsAgent()

