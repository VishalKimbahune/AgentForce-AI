"""Pydantic schemas for workflows, inter-agent messages, tasks, and realtime events."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class InterAgentMessageSchema(BaseModel):
    """Inter-agent message schema conforming strictly to docs/01_PROJECT_OVERVIEW_AND_ARCHITECTURE.md."""

    task_id: str
    workflow_id: str
    tenant_id: str
    source_agent: str
    destination_agent: str
    task_description: str
    input_context: Dict[str, Any] = Field(default_factory=dict)
    expected_output_schema: Dict[str, Any] = Field(default_factory=dict)
    priority: str = "normal"
    deadline: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    status: str = "pending"
    correlation_id: str


class WorkflowEventSchema(BaseModel):
    """Realtime SSE event payload conforming to docs/06_DATABASE_AND_API_SPEC.md section 6."""

    type: str  # task.started | task.completed | task.failed | approval.requested | workflow.completed | workflow.failed
    workflow_id: str
    task_id: Optional[str] = None
    agent: str
    message: str
    timestamp: str
    correlation_id: str
    data: Optional[Dict[str, Any]] = None


class WorkflowCreateRequest(BaseModel):
    input: str = Field(..., description="Task description or work instructions")
    attachments: List[str] = Field(default_factory=list, description="List of file paths or document IDs")
    agent_ids: List[str] = Field(default_factory=list, description="Optional target agent IDs")


class WorkflowTaskResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    agent_id: Optional[uuid.UUID] = None
    name: str
    depends_on: List[Any] = Field(default_factory=list)
    status: str
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by: Optional[str] = None
    input_text: str
    input_source: str
    status: str
    plan: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    cost_usd: float
    tokens_used: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    tasks: List[WorkflowTaskResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class CandidateRanking(BaseModel):
    candidate_name: str
    email: Optional[str] = None
    score: int = Field(..., ge=0, le=100, description="Match score from 0 to 100%")
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    experience_years: Optional[float] = None
    summary: str
    rationale: str

