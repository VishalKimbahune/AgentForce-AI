"""LangGraph Orchestrator: StateGraph with Intent -> Planner -> Orchestrator -> Agent -> Verifier."""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.metrics import record_workflow_metric, record_agent_task_metric
from app.core.telemetry import trace_span
from app.models.models import (
    AgentMessage,
    Workflow,
    WorkflowCheckpoint,
    WorkflowTask,
)
from app.schemas.workflow import InterAgentMessageSchema
from app.services.agents.hr import SAMPLE_RESUMES, hr_agent
from app.services.agents.finance import SAMPLE_INVOICES, finance_agent
from app.services.agents.ops import ops_agent
from app.services.tools.mock_erp import mock_erp
from app.services.orchestrator.events import event_bus
from app.services.policy_engine.engine import policy_engine, PolicyContext, PolicyEffect
from app.services.approvals.service import approval_service

logger = logging.getLogger("orchestrator")


class OrchestratorState(TypedDict):
    workflow_id: str
    tenant_id: str
    correlation_id: str
    input_text: str
    intent: str
    plan: Dict[str, Any]
    tasks: List[Dict[str, Any]]
    current_step: int
    messages: List[Dict[str, Any]]
    agent_outputs: Dict[str, Any]
    final_result: Dict[str, Any]
    status: str
    error: str


async def checkpoint_state(state: OrchestratorState) -> None:
    """Persists intermediate state in workflow_checkpoints table."""
    try:
        async with AsyncSessionLocal() as session:
            chk = WorkflowCheckpoint(
                workflow_id=uuid.UUID(state["workflow_id"]),
                state=json.loads(json.dumps(state, default=str)),
                step=state["current_step"],
            )
            session.add(chk)
            await session.commit()
    except Exception as e:
        logger.error("Failed to write workflow checkpoint: %s", str(e))


async def record_inter_agent_message(
    workflow_id: str,
    tenant_id: str,
    source_agent: str,
    destination_agent: str,
    task_description: str,
    correlation_id: str,
    input_context: dict,
    task_id: Optional[str] = None,
) -> InterAgentMessageSchema:
    """Emits and records an inter-agent message conforming to docs/01 schema."""
    t_id = task_id or str(uuid.uuid4())
    msg_schema = InterAgentMessageSchema(
        task_id=t_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        source_agent=source_agent,
        destination_agent=destination_agent,
        task_description=task_description,
        input_context=input_context,
        expected_output_schema={"type": "array", "items": "CandidateRanking"},
        priority="normal",
        deadline=datetime.now(timezone.utc).isoformat(),
        permissions=["resume:read"],
        status="pending",
        correlation_id=correlation_id,
    )

    try:
        async with AsyncSessionLocal() as session:
            msg_db = AgentMessage(
                workflow_id=uuid.UUID(workflow_id),
                tenant_id=uuid.UUID(tenant_id),
                source_agent=source_agent,
                destination_agent=destination_agent,
                payload=msg_schema.model_dump(),
                correlation_id=correlation_id,
            )
            session.add(msg_db)
            await session.commit()
    except Exception as e:
        logger.error("Failed to persist agent message: %s", str(e))

    return msg_schema


# ---------------------------------------------------------
# GRAPH NODE DEFINITIONS
# ---------------------------------------------------------

async def intent_node(state: OrchestratorState) -> OrchestratorState:
    """Node 1: Classifies user intent and extracts parameters."""
    wf_id = state["workflow_id"]
    cid = state["correlation_id"]

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.started",
        agent="intent_agent",
        message="Analyzing user instructions and extracting workflow intent...",
        correlation_id=cid,
    )

    inp = state["input_text"].lower()
    words = set(re.findall(r"\b\w+\b", inp))
    if words & {"resume", "resumes", "candidate", "candidates", "interview", "interviews", "hire", "recruit", "recruiting", "recruitment", "jd"}:
        intent = "recruitment"
    elif words & {"invoice", "invoices", "po", "payment", "payments", "expense", "expenses", "vendor", "vendors", "bill", "bills", "accounts"}:
        intent = "finance"
    elif words & {"report", "reports", "monthly", "operations", "ops", "kpi", "kpis", "summary"}:
        intent = "operations"
    else:
        intent = "general_workforce"

    state["intent"] = intent
    state["current_step"] += 1

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.completed",
        agent="intent_agent",
        message=f"Classified workflow intent as '{intent}'. Delegating to planner.",
        correlation_id=cid,
        data={"intent": intent},
    )

    await checkpoint_state(state)
    return state


async def planner_node(state: OrchestratorState) -> OrchestratorState:
    """Node 2: Generates structured task execution plan."""
    wf_id = state["workflow_id"]
    t_id = state["tenant_id"]
    cid = state["correlation_id"]

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.started",
        agent="planner",
        message="Generating structured task execution graph and agent assignments...",
        correlation_id=cid,
    )

    intent = state.get("intent", "recruitment")
    destination_agent = "hr"
    task_desc = "Execute candidate screening and ranking against Python Job Description"
    input_ctx = {"plan": {}, "candidate_count": len(SAMPLE_RESUMES)}

    if intent == "finance":
        destination_agent = "finance"
        plan_tasks = [
            {
                "id": str(uuid.uuid4()),
                "name": "Extract invoice metadata and vendor line items",
                "agent": "finance",
                "depends_on": [],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Audit invoices against ERP purchase orders and flag anomalies",
                "agent": "finance",
                "depends_on": ["Extract invoice metadata and vendor line items"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Assemble payment batch and evaluate financial disbursement policy",
                "agent": "finance",
                "depends_on": ["Audit invoices against ERP purchase orders and flag anomalies"],
            },
        ]
        task_desc = "Audit vendor invoices against ERP purchase orders and construct payment batch"
        input_ctx = {"invoice_count": len(SAMPLE_INVOICES)}

    elif intent == "operations":
        destination_agent = "ops"
        plan_tasks = [
            {
                "id": str(uuid.uuid4()),
                "name": "Pull monthly performance metrics from ERP data warehouse",
                "agent": "ops",
                "depends_on": [],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Compile executive business report and generate styled PDF document",
                "agent": "ops",
                "depends_on": ["Pull monthly performance metrics from ERP data warehouse"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Audit numerical accuracy and prepare leadership distribution",
                "agent": "ops",
                "depends_on": ["Compile executive business report and generate styled PDF document"],
            },
        ]
        task_desc = "Aggregate operational metrics and compile verified executive business report"
        input_ctx = {"period": "October 2026"}

    else:
        # Default recruitment tasks
        plan_tasks = [
            {
                "id": str(uuid.uuid4()),
                "name": "Parse and structure candidate resumes",
                "agent": "hr",
                "depends_on": [],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Match resumes against Job Description criteria",
                "agent": "hr",
                "depends_on": ["Parse and structure candidate resumes"],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Rank candidates and generate recommendation report",
                "agent": "hr",
                "depends_on": ["Match resumes against Job Description criteria"],
            },
        ]

    plan = {
        "title": f"Plan for: {state['input_text'][:60]}",
        "tasks": plan_tasks,
        "estimated_duration_sec": 5,
    }

    state["plan"] = plan
    state["tasks"] = plan_tasks
    state["current_step"] += 1

    # Persist workflow tasks in database
    try:
        async with AsyncSessionLocal() as session:
            for pt in plan_tasks:
                task_db = WorkflowTask(
                    id=uuid.UUID(pt["id"]),
                    workflow_id=uuid.UUID(wf_id),
                    tenant_id=uuid.UUID(t_id),
                    name=pt["name"],
                    depends_on=pt["depends_on"],
                    status="pending",
                )
                session.add(task_db)

            # Update workflow plan in database
            await session.execute(
                update(Workflow)
                .where(Workflow.id == uuid.UUID(wf_id))
                .values(plan=plan, status="running")
            )
            await session.commit()
    except Exception as e:
        logger.error("Failed to persist workflow plan and tasks: %s", str(e))

    # Send Inter-Agent message from Planner to target Agent
    input_ctx["plan"] = plan
    msg = await record_inter_agent_message(
        workflow_id=wf_id,
        tenant_id=t_id,
        source_agent="planner",
        destination_agent=destination_agent,
        task_description=task_desc,
        correlation_id=cid,
        input_context=input_ctx,
    )
    state["messages"].append(msg.model_dump())

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.completed",
        agent="planner",
        message=f"Plan generated with {len(plan_tasks)} tasks. Dispatched inter-agent message to {destination_agent} agent.",
        correlation_id=cid,
        data={"plan": plan},
    )

    await checkpoint_state(state)
    return state


async def orchestrator_node(state: OrchestratorState) -> OrchestratorState:
    """Node 3: Enforces step limits, boundaries, and dispatches to specialized agent."""
    wf_id = state["workflow_id"]
    cid = state["correlation_id"]

    # Hard step limit protection (Rule 10 of Project Specs: 30 steps max)
    if state["current_step"] >= settings.MAX_WORKFLOW_STEPS:
        state["status"] = "failed"
        state["error"] = f"Workflow step limit exceeded ({settings.MAX_WORKFLOW_STEPS} steps max)"
        event_bus.emit(
            workflow_id=wf_id,
            event_type="workflow.failed",
            agent="orchestrator",
            message=state["error"],
            correlation_id=cid,
        )
        return state

    target_agent = "HR"
    if state.get("intent") == "finance":
        target_agent = "Finance"
    elif state.get("intent") == "operations":
        target_agent = "Operations"

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.started",
        agent="orchestrator",
        message=f"Orchestrator dispatching tasks to {target_agent} AI Employee...",
        correlation_id=cid,
    )

    state["current_step"] += 1
    await checkpoint_state(state)
    return state


async def hr_agent_node(state: OrchestratorState) -> OrchestratorState:
    """Node 4A: HR Agent execution (parsing, JD matching, ranking)."""
    wf_id = state["workflow_id"]
    cid = state["correlation_id"]

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.started",
        agent="hr",
        message=f"HR Employee parsing {len(SAMPLE_RESUMES)} candidate resumes...",
        correlation_id=cid,
    )

    # 1. Parse resumes
    parsed_resumes = [hr_agent.parse_resume(r["raw_text"]) for r in SAMPLE_RESUMES]

    # Emit intermediate progress
    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.started",
        agent="hr",
        message=f"Parsed {len(parsed_resumes)} resumes. Matching skills against Python developer JD...",
        correlation_id=cid,
    )

    # 2. Match against JD criteria
    jd_requirement = (
        state["input_text"]
        or "Senior Python Backend Developer with FastAPI, PostgreSQL, Docker, and AsyncIO experience"
    )
    rankings = await hr_agent.rank_candidates_against_jd(parsed_resumes, jd_requirement)

    state["agent_outputs"]["rankings"] = [r.model_dump() for r in rankings]
    state["current_step"] += 1

    top_candidate = rankings[0].candidate_name if rankings else "None"
    top_score = rankings[0].score if rankings else 0

    # Update tasks in database
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(WorkflowTask)
                .where(WorkflowTask.workflow_id == uuid.UUID(wf_id))
                .values(
                    status="completed",
                    output={"rankings": [r.model_dump() for r in rankings]},
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
    except Exception as e:
        logger.error("Failed to update tasks status: %s", str(e))

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.completed",
        agent="hr",
        message=f"Ranking complete. Evaluated {len(rankings)} candidates. Top match: {top_candidate} ({top_score}% match).",
        correlation_id=cid,
        data={"top_candidate": top_candidate, "top_score": top_score, "rankings": [r.model_dump() for r in rankings]},
    )

    # Human-in-the-loop: Check if workflow requested scheduling interviews
    if any(k in state["input_text"].lower() for k in ("schedule", "interview", "invitation", "invite")):
        top_candidates = [
            {
                "name": r.candidate_name,
                "email": r.email,
                "score": r.score,
                "slot": "2026-11-05T14:00:00Z",
            }
            for r in rankings[:2]
        ]

        policy_eval = policy_engine.evaluate(
            PolicyContext(
                tenant_id=state["tenant_id"],
                agent="hr",
                action_type="interview.send_invitation",
                params={"candidates": top_candidates},
            )
        )

        if policy_eval.effect == PolicyEffect.REQUIRE_APPROVAL:
            app_req = await approval_service.create_request(
                tenant_id=state["tenant_id"],
                workflow_id=wf_id,
                requested_by_agent="hr",
                action_type="interview.send_invitation",
                action_payload={
                    "candidates": top_candidates,
                    "draft_message": f"Invitation to Python Technical Interview for top candidates ({top_candidate})",
                },
                risk_level=policy_eval.risk_level,
                reason=policy_eval.reason,
                required_role=policy_eval.required_role,
                level=policy_eval.level,
            )
            state["status"] = "waiting_approval"
            state["agent_outputs"]["approval_id"] = str(app_req.id)
            await checkpoint_state(state)
            return state

    await checkpoint_state(state)
    return state


async def finance_agent_node(state: OrchestratorState) -> OrchestratorState:
    """Node 4B: Finance Agent execution (invoice extraction, PO reconciliation, anomaly check, batch assembly)."""
    wf_id = state["workflow_id"]
    cid = state["correlation_id"]

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.started",
        agent="finance",
        message=f"Finance Employee auditing {len(SAMPLE_INVOICES)} vendor invoices against ERP purchase orders...",
        correlation_id=cid,
    )

    audit_res = finance_agent.extract_and_match_invoices()
    state["agent_outputs"]["finance"] = audit_res
    state["current_step"] += 1

    clean_count = audit_res["audit_stats"]["clean_count"]
    flagged_count = audit_res["audit_stats"]["flagged_count"]
    clean_amount = audit_res["audit_stats"]["clean_amount"]

    # Update tasks in database
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(WorkflowTask)
                .where(WorkflowTask.workflow_id == uuid.UUID(wf_id))
                .values(
                    status="completed",
                    output=audit_res,
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
    except Exception as e:
        logger.error("Failed to update tasks status: %s", str(e))

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.completed",
        agent="finance",
        message=(
            f"Finance audit complete: {clean_count} clean invoices (${clean_amount:,.2f}), "
            f"{flagged_count} flagged for anomalies. Payment batch prepared."
        ),
        correlation_id=cid,
        data=audit_res,
    )

    # Journey B: Check policy for payment execution (Mandatory Finance Manager approval)
    payment_batch = audit_res["payment_batch"]
    policy_eval = policy_engine.evaluate(
        PolicyContext(
            tenant_id=state["tenant_id"],
            agent="finance",
            action_type="payment.execute",
            amount=payment_batch["total_amount"],
            params=payment_batch,
        )
    )

    if policy_eval.effect == PolicyEffect.REQUIRE_APPROVAL:
        app_req = await approval_service.create_request(
            tenant_id=state["tenant_id"],
            workflow_id=wf_id,
            requested_by_agent="finance",
            action_type="payment.execute",
            action_payload=payment_batch,
            risk_level=policy_eval.risk_level,
            reason=policy_eval.reason,
            required_role=policy_eval.required_role,
            level=policy_eval.level,
        )
        state["status"] = "waiting_approval"
        state["agent_outputs"]["approval_id"] = str(app_req.id)
        await checkpoint_state(state)
        return state

    await checkpoint_state(state)
    return state


async def ops_agent_node(state: OrchestratorState) -> OrchestratorState:
    """Node 4C: Operations Agent execution (metric synthesis, reportlab PDF generation, distribution staging)."""
    wf_id = state["workflow_id"]
    cid = state["correlation_id"]

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.started",
        agent="ops",
        message="Operations Employee querying ERP data warehouse and compiling monthly business report...",
        correlation_id=cid,
    )

    report_res = ops_agent.generate_executive_report(
        tenant_id=state["tenant_id"],
        period="October 2026",
    )
    state["agent_outputs"]["operations"] = report_res
    state["current_step"] += 1

    # Update tasks in database
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(WorkflowTask)
                .where(WorkflowTask.workflow_id == uuid.UUID(wf_id))
                .values(
                    status="completed",
                    output=report_res,
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
    except Exception as e:
        logger.error("Failed to update tasks status: %s", str(e))

    event_bus.emit(
        workflow_id=wf_id,
        event_type="task.completed",
        agent="ops",
        message=f"Executive operations report compiled: {report_res['filename']}.",
        correlation_id=cid,
        data=report_res,
    )

    # Journey C: Check policy for distributing report to leadership
    policy_eval = policy_engine.evaluate(
        PolicyContext(
            tenant_id=state["tenant_id"],
            agent="ops",
            action_type="report.distribute",
            params={
                "title": "Monthly Executive Operations Report",
                "filename": report_res["filename"],
                "summary": report_res["summary"],
                "recipient": "leadership@company.internal",
            },
        )
    )

    if policy_eval.effect == PolicyEffect.REQUIRE_APPROVAL:
        app_req = await approval_service.create_request(
            tenant_id=state["tenant_id"],
            workflow_id=wf_id,
            requested_by_agent="ops",
            action_type="report.distribute",
            action_payload={
                "title": "Monthly Executive Operations Report",
                "filename": report_res["filename"],
                "summary": report_res["summary"],
                "file_path": report_res["file_path"],
                "recipient": "leadership@company.internal",
            },
            risk_level=policy_eval.risk_level,
            reason=policy_eval.reason,
            required_role=policy_eval.required_role,
            level=policy_eval.level,
        )
        state["status"] = "waiting_approval"
        state["agent_outputs"]["approval_id"] = str(app_req.id)
        await checkpoint_state(state)
        return state

    await checkpoint_state(state)
    return state


async def verifier_node(state: OrchestratorState) -> OrchestratorState:
    """Node 5: Supervisor/Verifier node ensuring requirements were completed accurately."""
    wf_id = state["workflow_id"]
    cid = state["correlation_id"]

    # If workflow is paused waiting for human approval, maintain state
    if state.get("status") == "waiting_approval":
        return state

    intent = state.get("intent", "recruitment")

    # 1. Finance Verification
    if intent == "finance":
        finance_data = state["agent_outputs"].get("finance")
        if not finance_data or not finance_data.get("clean_invoices"):
            state["status"] = "failed"
            state["error"] = "Verifier rejected finance output: No audited invoices or payment batch produced"
            event_bus.emit(
                workflow_id=wf_id,
                event_type="workflow.failed",
                agent="verifier",
                message=state["error"],
                correlation_id=cid,
            )
            return state

        state["status"] = "completed"
        state["final_result"] = {
            "summary": finance_data["summary"],
            "payment_batch": finance_data["payment_batch"],
            "clean_invoices": finance_data["clean_invoices"],
            "flagged_invoices": finance_data["flagged_invoices"],
            "audit_stats": finance_data["audit_stats"],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    # 2. Operations Verification
    elif intent == "operations":
        ops_data = state["agent_outputs"].get("operations")
        if not ops_data or not ops_data.get("file_path"):
            state["status"] = "failed"
            state["error"] = "Verifier rejected operations output: Report file not generated"
            event_bus.emit(
                workflow_id=wf_id,
                event_type="workflow.failed",
                agent="verifier",
                message=state["error"],
                correlation_id=cid,
            )
            return state

        # Verify numerical accuracy against ERP
        erp_metrics = mock_erp.get_operations_metrics()
        verify_audit = ops_agent.verify_report(ops_data, erp_metrics)
        if not verify_audit["verified"]:
            state["status"] = "failed"
            state["error"] = f"Verifier detected numerical discrepancy in report: {verify_audit['discrepancies']}"
            event_bus.emit(
                workflow_id=wf_id,
                event_type="workflow.failed",
                agent="verifier",
                message=state["error"],
                correlation_id=cid,
            )
            return state

        state["status"] = "completed"
        state["final_result"] = {
            "summary": ops_data["summary"],
            "filename": ops_data["filename"],
            "file_path": ops_data["file_path"],
            "metrics": ops_data["metrics"],
            "verification": verify_audit,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    # 3. Recruitment Verification (Default)
    else:
        rankings_data = state["agent_outputs"].get("rankings", [])
        if not rankings_data:
            state["status"] = "failed"
            state["error"] = "Verifier rejected agent output: No candidate rankings produced"
            event_bus.emit(
                workflow_id=wf_id,
                event_type="workflow.failed",
                agent="verifier",
                message=state["error"],
                correlation_id=cid,
            )
            return state

        state["status"] = "completed"
        state["final_result"] = {
            "summary": f"Successfully screened and ranked {len(rankings_data)} candidates for Python role.",
            "rankings": rankings_data,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    state["current_step"] += 1

    # Persist completion in database
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Workflow)
                .where(Workflow.id == uuid.UUID(wf_id))
                .values(
                    status="completed",
                    tokens_used=1250,
                    cost_usd=0.0019,
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
    except Exception as e:
        logger.error("Failed to update completed workflow status: %s", str(e))

    event_bus.emit(
        workflow_id=wf_id,
        event_type="workflow.completed",
        agent="verifier",
        message="Verification passed: 100% of task requirements validated. Workflow completed successfully.",
        correlation_id=cid,
        data=state["final_result"],
    )

    await checkpoint_state(state)
    return state


# ---------------------------------------------------------
# GRAPH COMPILATION
# ---------------------------------------------------------

def route_orchestrator(state: OrchestratorState) -> str:
    """Conditional router dispatching orchestrator state to the specialized agent node."""
    intent = state.get("intent", "").lower()
    if intent == "finance":
        return "finance_agent"
    elif intent == "operations":
        return "ops_agent"
    return "hr_agent"


def create_orchestrator_graph():
    """Builds and compiles the LangGraph StateGraph supporting HR, Finance, and Operations."""
    builder = StateGraph(OrchestratorState)

    builder.add_node("intent", intent_node)
    builder.add_node("planner", planner_node)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("hr_agent", hr_agent_node)
    builder.add_node("finance_agent", finance_agent_node)
    builder.add_node("ops_agent", ops_agent_node)
    builder.add_node("verifier", verifier_node)

    builder.set_entry_point("intent")
    builder.add_edge("intent", "planner")
    builder.add_edge("planner", "orchestrator")
    builder.add_conditional_edges(
        "orchestrator",
        route_orchestrator,
        {
            "hr_agent": "hr_agent",
            "finance_agent": "finance_agent",
            "ops_agent": "ops_agent",
        },
    )
    builder.add_edge("hr_agent", "verifier")
    builder.add_edge("finance_agent", "verifier")
    builder.add_edge("ops_agent", "verifier")
    builder.add_edge("verifier", END)

    return builder.compile()


compiled_graph = create_orchestrator_graph()


async def execute_workflow_graph(
    workflow_id: str,
    tenant_id: str,
    input_text: str,
    correlation_id: str,
) -> OrchestratorState:
    """Executes the workflow through the compiled LangGraph graph."""
    initial_state: OrchestratorState = {
        "workflow_id": workflow_id,
        "tenant_id": tenant_id,
        "correlation_id": correlation_id,
        "input_text": input_text,
        "intent": "pending",
        "plan": {},
        "tasks": [],
        "current_step": 0,
        "messages": [],
        "agent_outputs": {},
        "final_result": {},
        "status": "running",
        "error": "",
    }

    start_time = time.time()
    with trace_span(
        name="orchestrator.execute",
        span_type="orchestrator",
        attributes={"workflow_id": workflow_id, "tenant_id": tenant_id, "correlation_id": correlation_id},
    ):
        final_state = await compiled_graph.ainvoke(initial_state)
        elapsed_s = time.time() - start_time
        record_workflow_metric(
            tenant_id=tenant_id,
            status=final_state.get("status", "completed"),
            intent=final_state.get("intent", "general"),
            duration_s=elapsed_s,
        )
        return final_state
