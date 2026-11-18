"""Pydantic schemas for LLM analytics and observability dashboards."""

from typing import List, Optional
from pydantic import BaseModel


class ModelAnalytics(BaseModel):
    model: str
    provider: str
    total_requests: int
    avg_latency_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    total_cost_usd: float
    fallback_count: int


class LLMAnalyticsResponse(BaseModel):
    models: List[ModelAnalytics]
    total_requests: int
    total_cost_usd: float
    total_tokens: int


class OverviewAnalyticsResponse(BaseModel):
    running_workflows: int
    pending_approvals: int
    hours_saved: float
    cost_usd: float
    total_workflows: int
    success_rate: float


class AgentHealthAnalytics(BaseModel):
    agent: str
    role: str
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    success_rate: float
    avg_latency_ms: float
    status: str  # healthy | degraded | failing


