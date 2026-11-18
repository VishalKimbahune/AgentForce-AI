"""Tool registry, mock business adapters, and execution engine with idempotency and audit logging."""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.models import ToolExecution
from app.services.llm_gateway.pii import mask_pii
from app.services.tools.mock_erp import mock_erp
from app.services.guardrails import tool_guard, security_logger

logger = logging.getLogger("services.tools")


class ToolDefinition(BaseModel):
    """Tool metadata and contract conforming to docs/06 Section 7."""

    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    side_effect: str = "write"  # read | write
    requires_approval_default: bool = False
    allowed_agents: List[str] = Field(default_factory=list)
    rate_limit_per_min: int = 30
    idempotent: bool = True


# In-memory storage for mock business tools
MOCK_CALENDAR_EVENTS: List[Dict[str, Any]] = []
MOCK_NOTIFICATIONS: List[Dict[str, Any]] = []
MOCK_ATS_RECORDS: List[Dict[str, Any]] = []


# -------------------------------------------------------------
# MOCK TOOL IMPLEMENTATIONS
# -------------------------------------------------------------

async def mock_calendar_create_event(params: Dict[str, Any]) -> Dict[str, Any]:
    """Books an interview slot in the local mock calendar service."""
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "title": params.get("title", f"Interview: {params.get('candidate_name', 'Candidate')}"),
        "candidate_name": params.get("candidate_name"),
        "candidate_email": params.get("candidate_email"),
        "start_time": params.get("start_time", "2026-11-05T14:00:00Z"),
        "duration_minutes": params.get("duration_minutes", 45),
        "interviewer": params.get("interviewer", "Priya Sharma (HR Lead)"),
        "meeting_link": f"https://meet.local.company/{event_id[:8]}",
        "status": "confirmed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    MOCK_CALENDAR_EVENTS.append(event)
    logger.info("Mock Calendar Event Created: %s for %s", event_id, event["candidate_name"])
    return event


async def mock_notifications_send_in_app(params: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatches an internal in-app workforce notification."""
    notif_id = str(uuid.uuid4())
    notif = {
        "notification_id": notif_id,
        "recipient": params.get("recipient", "team"),
        "title": params.get("title", "Workforce Notification"),
        "message": params.get("message", ""),
        "channel": "in_app",
        "delivered": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    MOCK_NOTIFICATIONS.append(notif)
    logger.info("Mock Notification Sent: %s -> %s", notif_id, notif["recipient"])
    return notif


async def mock_ats_update_candidate(params: Dict[str, Any]) -> Dict[str, Any]:
    """Updates candidate status in mock ATS."""
    candidate_id = params.get("candidate_id", str(uuid.uuid4()))
    record = {
        "candidate_id": candidate_id,
        "candidate_name": params.get("candidate_name"),
        "stage": params.get("stage", "interview_scheduled"),
        "notes": params.get("notes", "Automated interview invitation staged"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    MOCK_ATS_RECORDS.append(record)
    return record


async def mock_erp_get_purchase_order(params: Dict[str, Any]) -> Dict[str, Any]:
    """Fetches PO details from Mock ERP."""
    po_num = params.get("po_number", "")
    res = mock_erp.get_purchase_order(po_num)
    if res:
        return {"found": True, "po": res}
    return {"found": False, "error": f"PO {po_num} not found"}


async def mock_erp_get_metrics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves operational KPIs and departmental metrics from Mock ERP."""
    period = params.get("period")
    return mock_erp.get_operations_metrics(period)


async def mock_payment_execute_batch(params: Dict[str, Any]) -> Dict[str, Any]:
    """Executes vendor payment batch via Mock Payment Gateway."""
    batch_id = params.get("batch_id", f"BATCH-{uuid.uuid4().hex[:8].upper()}")
    invoices = params.get("invoices", [])
    total_amount = float(params.get("total_amount", 0.0))
    return mock_erp.execute_payment_batch(batch_id=batch_id, invoices=invoices, total_amount=total_amount)


# -------------------------------------------------------------
# TOOL REGISTRY
# -------------------------------------------------------------

class ToolRegistry:
    """Central registry and policy-controlled executor for workforce tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        # 1. Mock Calendar Tool
        self.register(
            ToolDefinition(
                name="mock_calendar.create_event",
                description="Create an interview event in the local mock calendar service",
                input_schema={
                    "type": "object",
                    "properties": {
                        "candidate_name": {"type": "string"},
                        "candidate_email": {"type": "string"},
                        "start_time": {"type": "string"},
                    },
                    "required": ["candidate_name"],
                },
                output_schema={"type": "object", "properties": {"event_id": {"type": "string"}}},
                side_effect="write",
                requires_approval_default=True,
                allowed_agents=["hr", "orchestrator"],
                rate_limit_per_min=30,
                idempotent=True,
            ),
            mock_calendar_create_event,
        )

        # 2. In-App Notification Tool
        self.register(
            ToolDefinition(
                name="notifications.send_in_app",
                description="Deliver an internal in-app workforce alert or invitation",
                input_schema={
                    "type": "object",
                    "properties": {
                        "recipient": {"type": "string"},
                        "title": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["title", "message"],
                },
                side_effect="write",
                requires_approval_default=False,
                allowed_agents=["hr", "finance", "ops", "orchestrator", "notification_agent"],
                rate_limit_per_min=60,
                idempotent=True,
            ),
            mock_notifications_send_in_app,
        )

        # 3. Mock ATS Tool
        self.register(
            ToolDefinition(
                name="mock_ats.update_candidate",
                description="Update candidate lifecycle stage in internal ATS",
                side_effect="write",
                requires_approval_default=False,
                allowed_agents=["hr", "orchestrator"],
                rate_limit_per_min=60,
                idempotent=True,
            ),
            mock_ats_update_candidate,
        )

        # 4. Mock ERP Get PO Tool
        self.register(
            ToolDefinition(
                name="mock_erp.get_purchase_order",
                description="Lookup purchase order records in mock ERP",
                input_schema={
                    "type": "object",
                    "properties": {"po_number": {"type": "string"}},
                    "required": ["po_number"],
                },
                side_effect="read",
                requires_approval_default=False,
                allowed_agents=["finance", "orchestrator"],
                rate_limit_per_min=120,
                idempotent=True,
            ),
            mock_erp_get_purchase_order,
        )

        # 5. Mock ERP Get Metrics Tool
        self.register(
            ToolDefinition(
                name="mock_erp.get_metrics",
                description="Fetch enterprise operational KPIs and departmental budgets",
                side_effect="read",
                requires_approval_default=False,
                allowed_agents=["ops", "finance", "orchestrator"],
                rate_limit_per_min=120,
                idempotent=True,
            ),
            mock_erp_get_metrics,
        )

        # 6. Mock Payment Execute Batch Tool
        self.register(
            ToolDefinition(
                name="mock_payment.execute_batch",
                description="Disburse approved vendor invoice batch through mock payment gateway",
                input_schema={
                    "type": "object",
                    "properties": {
                        "batch_id": {"type": "string"},
                        "invoices": {"type": "array"},
                        "total_amount": {"type": "number"},
                    },
                    "required": ["invoices", "total_amount"],
                },
                side_effect="write",
                requires_approval_default=True,
                allowed_agents=["finance", "orchestrator"],
                rate_limit_per_min=20,
                idempotent=True,
            ),
            mock_payment_execute_batch,
        )

    def register(self, definition: ToolDefinition, handler: Callable):
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    async def execute(
        self,
        name: str,
        params: Dict[str, Any],
        agent: str,
        tenant_id: str,
        workflow_id: str,
        task_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Executes a tool with agent permission checking, idempotency, and audit logging."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' is not registered")

        # 1. Check agent permission
        if agent not in tool.allowed_agents and "orchestrator" not in agent:
            raise PermissionError(f"Agent '{agent}' is not authorized to call tool '{name}'. Allowed: {tool.allowed_agents}")

        # 2. Guardrail Check: Validate tool parameters against path traversal, command injection, and bounds
        is_valid, err_msg = tool_guard.validate_parameters(name, params)
        if not is_valid:
            security_logger.record_incident(
                event_type="security.tool_parameter_violation",
                threat_category="parameter_tampering",
                risk_level="high",
                detail=err_msg or "Invalid tool parameters",
                tenant_id=tenant_id,
                payload_sample={"tool": name, "params": {k: str(v)[:60] for k, v in params.items()}},
            )
            raise ValueError(f"Tool parameter validation error: {err_msg}")

        # 3. Check idempotency in database
        actual_idem_key = idempotency_key or f"{workflow_id}:{name}:{hash(str(sorted(params.items())))}"
        async def _check_cache(s: AsyncSession):
            stmt = select(ToolExecution).where(
                ToolExecution.tenant_id == uuid.UUID(tenant_id),
                ToolExecution.idempotency_key == actual_idem_key,
            )
            res = await s.execute(stmt)
            return res.scalar_one_or_none()

        cached_rec = None
        if db:
            cached_rec = await _check_cache(db)
        else:
            async with AsyncSessionLocal() as s:
                cached_rec = await _check_cache(s)

        if cached_rec and cached_rec.status == "success":
            logger.info("Idempotent replay for tool '%s' (key: %s)", name, actual_idem_key)
            return cached_rec.response_redacted or {}

        # 3. Execute tool
        handler = self._handlers[name]
        start_time = time.time()
        status_code = "success"
        response: Dict[str, Any] = {}

        try:
            response = await handler(params)
        except Exception as e:
            status_code = "failed"
            response = {"error": str(e)}
            raise e
        finally:
            duration_ms = int((time.time() - start_time) * 1000)

            # Redact sensitive parameters and response
            redacted_params = {k: mask_pii(str(v)) if isinstance(v, str) else v for k, v in params.items()}
            redacted_resp = {k: mask_pii(str(v)) if isinstance(v, str) else v for k, v in response.items()}

            # 4. Audit log to tool_executions
            te = ToolExecution(
                tenant_id=uuid.UUID(tenant_id),
                workflow_id=uuid.UUID(workflow_id),
                task_id=uuid.UUID(task_id) if task_id else None,
                tool_name=name,
                params_redacted=redacted_params,
                idempotency_key=actual_idem_key,
                status=status_code,
                response_redacted=redacted_resp,
                duration_ms=duration_ms,
            )

            try:
                if db:
                    db.add(te)
                    await db.commit()
                else:
                    async with AsyncSessionLocal() as session:
                        session.add(te)
                        await session.commit()
            except Exception as log_err:
                logger.error("Failed to write tool execution log: %s", str(log_err))

        return response


# Global tool registry singleton
tool_registry = ToolRegistry()
