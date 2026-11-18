"""Pydantic schemas for approvals and human-in-the-loop workflows."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ApprovalDecisionRequest(BaseModel):
    note: Optional[str] = Field(default="", description="Reviewer decision note or rationale")


class ApprovalDelegateRequest(BaseModel):
    to_user_id: str = Field(..., description="Target user ID to delegate approval responsibility to")


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    workflow_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    requested_by_agent: str
    action_type: str
    action_payload: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str
    reason: str
    status: str
    required_role: str
    level: int
    expires_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

