"""SQLAlchemy database models for AgentForce AI.
Conforms strictly to docs/06_DATABASE_AND_API_SPEC.md.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.types import GUID


def utcnow():
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="starter", nullable=False)
    daily_token_budget = Column(Integer, default=500000, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    memberships = relationship("Membership", back_populates="organization", cascade="all, delete-orphan", lazy="selectin")
    agents = relationship("Agent", back_populates="organization", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    """User profile referencing Supabase Auth user id."""
    __tablename__ = "users"

    # id matches Supabase auth.users.id; no local password hash
    id = Column(String(64), primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan", lazy="selectin")


class Membership(Base):
    """Organization membership with RBAC role."""
    __tablename__ = "memberships"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(30), nullable=False)  # owner|manager|approver|member|auditor

    organization = relationship("Organization", back_populates="memberships", lazy="selectin")
    user = relationship("User", back_populates="memberships", lazy="selectin")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False)
    scopes = Column(JSON, default=list, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class Agent(Base):
    __tablename__ = "agents"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # hr, finance, support, ops, compliance, knowledge, notification, aiops
    system_prompt = Column(Text, nullable=False)
    model_policy = Column(JSON, nullable=True)
    allowed_tools = Column(JSON, default=list, nullable=False)
    knowledge_scopes = Column(JSON, default=list, nullable=False)
    approval_rules = Column(JSON, nullable=True)
    status = Column(String(30), default="active", nullable=False)
    template_id = Column(GUID, nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    organization = relationship("Organization", back_populates="agents")


class AgentTemplate(Base):
    __tablename__ = "agent_templates"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    default_config = Column(JSON, nullable=True)
    required_integrations = Column(JSON, default=list, nullable=False)
    published = Column(Boolean, default=True, nullable=False)


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(String(64), nullable=True)
    input_text = Column(Text, nullable=False)
    input_source = Column(String(20), default="text", nullable=False)  # text|voice|api
    status = Column(String(30), default="pending", nullable=False, index=True)
    plan = Column(JSON, nullable=True)
    idempotency_key = Column(String(255), nullable=True, index=True)
    trace_id = Column(String(255), nullable=True)
    correlation_id = Column(String(255), nullable=True)
    cost_usd = Column(Float, default=0.0, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    organization = relationship("Organization", back_populates="workflows")
    tasks = relationship("WorkflowTask", back_populates="workflow", cascade="all, delete-orphan", lazy="selectin")
    checkpoints = relationship("WorkflowCheckpoint", back_populates="workflow", cascade="all, delete-orphan", lazy="selectin")
    messages = relationship("AgentMessage", back_populates="workflow", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        Index("ix_workflows_tenant_status_created", "tenant_id", "status", "created_at"),
    )


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    workflow_id = Column(GUID, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(GUID, nullable=True)
    name = Column(String(255), nullable=False)
    depends_on = Column(JSON, default=list, nullable=False)
    status = Column(String(30), default="pending", nullable=False)
    input = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    workflow = relationship("Workflow", back_populates="tasks")


class WorkflowCheckpoint(Base):
    __tablename__ = "workflow_checkpoints"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    workflow_id = Column(GUID, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    state = Column(JSON, nullable=False)
    step = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    workflow = relationship("Workflow", back_populates="checkpoints")


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    workflow_id = Column(GUID, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_agent = Column(String(100), nullable=False)
    destination_agent = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    correlation_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    workflow = relationship("Workflow", back_populates="messages")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(GUID, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(GUID, nullable=True)
    requested_by_agent = Column(String(100), nullable=False)
    action_type = Column(String(100), nullable=False)
    action_payload = Column(JSON, nullable=False)
    risk_level = Column(String(30), default="medium", nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(30), default="pending", nullable=False, index=True)  # pending|approved|rejected|expired|cancelled
    required_role = Column(String(30), default="manager", nullable=False)
    level = Column(Integer, default=1, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(String(64), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_approvals_tenant_status_created", "tenant_id", "status", "created_at"),
    )


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)
    conditions = Column(JSON, nullable=True)
    effect = Column(String(30), nullable=False)  # allow|require_approval|deny


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(100), nullable=False)
    status = Column(String(30), default="active", nullable=False)
    config = Column(JSON, nullable=True)
    connected_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(GUID, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(GUID, nullable=True)
    tool_name = Column(String(100), nullable=False)
    params_redacted = Column(JSON, nullable=True)
    idempotency_key = Column(String(255), nullable=True, index=True)
    status = Column(String(30), nullable=False)
    response_redacted = Column(JSON, nullable=True)
    duration_ms = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    storage_key = Column(String(512), nullable=False)
    mime_type = Column(String(100), nullable=False)
    status = Column(String(30), default="processing", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    allowed_roles = Column(JSON, default=list, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    uploaded_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy="selectin")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    qdrant_point_id = Column(String(255), nullable=True)

    document = relationship("Document", back_populates="chunks")


class LLMRequest(Base):
    __tablename__ = "llm_requests"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(GUID, nullable=True, index=True)
    task_id = Column(GUID, nullable=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    prompt_version = Column(String(50), default="v1", nullable=False)
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    status = Column(String(30), default="success", nullable=False)
    fallback_from = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    """Immutable audit trail. Append-only."""
    __tablename__ = "audit_logs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_type = Column(String(30), nullable=False)  # user|agent|system
    actor_id = Column(String(64), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(255), nullable=True)
    details_redacted = Column(JSON, nullable=True)
    ip = Column(String(45), nullable=True)
    correlation_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    topic = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class AIOpsIncident(Base):
    __tablename__ = "aiops_incidents"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    severity = Column(String(30), nullable=False)  # low|medium|high|critical
    summary = Column(String(255), nullable=False)
    root_cause_hypothesis = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    status = Column(String(30), default="open", nullable=False)  # open|remediating|resolved
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

