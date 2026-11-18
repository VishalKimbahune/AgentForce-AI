"""Prometheus metrics registry and telemetry collectors for AgentForce AI."""

import time
from typing import Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Custom registry so we have clean metrics isolation
metrics_registry = CollectorRegistry(auto_describe=True)

# 1. Workflows
WORKFLOWS_TOTAL = Counter(
    "agentforce_workflows_total",
    "Total workflows created in AgentForce",
    ["tenant_id", "status", "intent", "input_source"],
    registry=metrics_registry,
)

WORKFLOW_DURATION_SECONDS = Histogram(
    "agentforce_workflow_duration_seconds",
    "End-to-end workflow execution duration in seconds",
    ["tenant_id", "intent"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
    registry=metrics_registry,
)

ACTIVE_WORKFLOWS = Gauge(
    "agentforce_active_workflows",
    "Currently running or planning workflows",
    ["tenant_id"],
    registry=metrics_registry,
)

# 2. LLM Gateway & Telemetry
LLM_REQUESTS_TOTAL = Counter(
    "agentforce_llm_requests_total",
    "Total LLM Gateway requests dispatched",
    ["tenant_id", "provider", "model", "status"],
    registry=metrics_registry,
)

LLM_TOKENS_TOTAL = Counter(
    "agentforce_llm_tokens_total",
    "Total LLM tokens consumed",
    ["tenant_id", "model", "token_type"],  # prompt, completion
    registry=metrics_registry,
)

LLM_COST_USD_TOTAL = Counter(
    "agentforce_llm_cost_usd_total",
    "Total LLM cost accrued in USD",
    ["tenant_id", "model"],
    registry=metrics_registry,
)

# 3. Agent Tasks & Failures
AGENT_TASKS_TOTAL = Counter(
    "agentforce_agent_tasks_total",
    "Total tasks executed by AI Employees",
    ["tenant_id", "agent", "status"],
    registry=metrics_registry,
)

AGENT_FAILURES_TOTAL = Counter(
    "agentforce_agent_failures_total",
    "Total failures encountered by AI Employees",
    ["tenant_id", "agent", "error_type"],
    registry=metrics_registry,
)

# 4. Tool Execution
TOOL_EXECUTIONS_TOTAL = Counter(
    "agentforce_tool_executions_total",
    "Total tool invocations via Tool Registry",
    ["tenant_id", "tool", "status"],
    registry=metrics_registry,
)

# 5. AIOps Incidents
AIOPS_INCIDENTS_TOTAL = Counter(
    "agentforce_aiops_incidents_total",
    "Total AIOps anomaly incidents detected",
    ["tenant_id", "severity", "status"],
    registry=metrics_registry,
)


def record_workflow_metric(
    tenant_id: str,
    status: str,
    intent: str = "general",
    input_source: str = "text",
    duration_s: Optional[float] = None,
) -> None:
    """Records workflow execution metrics."""
    t_id = str(tenant_id)
    WORKFLOWS_TOTAL.labels(
        tenant_id=t_id,
        status=status,
        intent=intent,
        input_source=input_source,
    ).inc()

    if duration_s is not None:
        WORKFLOW_DURATION_SECONDS.labels(tenant_id=t_id, intent=intent).observe(duration_s)


def record_llm_metric(
    tenant_id: str,
    provider: str,
    model: str,
    status: str,
    cost_usd: float = 0.0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Records LLM gateway request telemetry."""
    t_id = str(tenant_id)
    LLM_REQUESTS_TOTAL.labels(
        tenant_id=t_id,
        provider=provider,
        model=model,
        status=status,
    ).inc()

    if prompt_tokens > 0:
        LLM_TOKENS_TOTAL.labels(tenant_id=t_id, model=model, token_type="prompt").inc(prompt_tokens)
    if completion_tokens > 0:
        LLM_TOKENS_TOTAL.labels(tenant_id=t_id, model=model, token_type="completion").inc(completion_tokens)
    if cost_usd > 0.0:
        LLM_COST_USD_TOTAL.labels(tenant_id=t_id, model=model).inc(cost_usd)


def record_agent_task_metric(
    tenant_id: str,
    agent: str,
    status: str,
    error_type: Optional[str] = None,
) -> None:
    """Records an AI Employee task outcome."""
    t_id = str(tenant_id)
    AGENT_TASKS_TOTAL.labels(tenant_id=t_id, agent=agent, status=status).inc()
    if status == "failed" and error_type:
        AGENT_FAILURES_TOTAL.labels(tenant_id=t_id, agent=agent, error_type=error_type).inc()


def record_tool_metric(tenant_id: str, tool: str, status: str) -> None:
    """Records a tool execution invocation."""
    TOOL_EXECUTIONS_TOTAL.labels(tenant_id=str(tenant_id), tool=tool, status=status).inc()


def record_incident_metric(tenant_id: str, severity: str, status: str) -> None:
    """Records an AIOps incident detection."""
    AIOPS_INCIDENTS_TOTAL.labels(tenant_id=str(tenant_id), severity=severity, status=status).inc()


def export_prometheus_metrics() -> str:
    """Exports all current metrics in standard Prometheus text exposition format."""
    return generate_latest(metrics_registry).decode("utf-8")

