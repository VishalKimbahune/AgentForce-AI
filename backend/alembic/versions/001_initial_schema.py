"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-31 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.models.types import GUID


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        "organizations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="starter"),
        sa.Column("daily_token_budget", sa.Integer(), nullable=False, server_default="500000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. users (id matches Supabase auth.users.id)
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # 3. memberships
    op.create_table(
        "memberships",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
    )
    op.create_index("ix_memberships_tenant_id", "memberships", ["tenant_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])

    # 4. api_keys
    op.create_table(
        "api_keys",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])

    # 5. agents
    op.create_table(
        "agents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("model_policy", sa.JSON(), nullable=True),
        sa.Column("allowed_tools", sa.JSON(), nullable=False),
        sa.Column("knowledge_scopes", sa.JSON(), nullable=False),
        sa.Column("approval_rules", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("template_id", GUID(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agents_tenant_id", "agents", ["tenant_id"])

    # 6. agent_templates
    op.create_table(
        "agent_templates",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("default_config", sa.JSON(), nullable=True),
        sa.Column("required_integrations", sa.JSON(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # 7. workflows
    op.create_table(
        "workflows",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("input_source", sa.String(20), nullable=False, server_default="text"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("plan", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("trace_id", sa.String(255), nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflows_tenant_id", "workflows", ["tenant_id"])
    op.create_index("ix_workflows_status", "workflows", ["status"])
    op.create_index("ix_workflows_idempotency_key", "workflows", ["idempotency_key"])
    op.create_index("ix_workflows_tenant_status_created", "workflows", ["tenant_id", "status", "created_at"])

    # 8. workflow_tasks
    op.create_table(
        "workflow_tasks",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("workflow_id", GUID(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", GUID(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("depends_on", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflow_tasks_workflow_id", "workflow_tasks", ["workflow_id"])
    op.create_index("ix_workflow_tasks_tenant_id", "workflow_tasks", ["tenant_id"])

    # 9. workflow_checkpoints
    op.create_table(
        "workflow_checkpoints",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("workflow_id", GUID(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_checkpoints_workflow_id", "workflow_checkpoints", ["workflow_id"])

    # 10. agent_messages
    op.create_table(
        "agent_messages",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("workflow_id", GUID(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_agent", sa.String(100), nullable=False),
        sa.Column("destination_agent", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_messages_workflow_id", "agent_messages", ["workflow_id"])
    op.create_index("ix_agent_messages_tenant_id", "agent_messages", ["tenant_id"])

    # 11. approval_requests
    op.create_table(
        "approval_requests",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", GUID(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", GUID(), nullable=True),
        sa.Column("requested_by_agent", sa.String(100), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("action_payload", sa.JSON(), nullable=False),
        sa.Column("risk_level", sa.String(30), nullable=False, server_default="medium"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("required_role", sa.String(30), nullable=False, server_default="manager"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"])
    op.create_index("ix_approval_requests_workflow_id", "approval_requests", ["workflow_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
    op.create_index("ix_approvals_tenant_status_created", "approval_requests", ["tenant_id", "status", "created_at"])

    # 12. policy_rules
    op.create_table(
        "policy_rules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=True),
        sa.Column("effect", sa.String(30), nullable=False),
    )
    op.create_index("ix_policy_rules_tenant_id", "policy_rules", ["tenant_id"])

    # 13. integrations
    op.create_table(
        "integrations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("connected_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_integrations_tenant_id", "integrations", ["tenant_id"])

    # 14. tool_executions
    op.create_table(
        "tool_executions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", GUID(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", GUID(), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("params_redacted", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("response_redacted", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tool_executions_tenant_id", "tool_executions", ["tenant_id"])
    op.create_index("ix_tool_executions_workflow_id", "tool_executions", ["workflow_id"])
    op.create_index("ix_tool_executions_idempotency_key", "tool_executions", ["idempotency_key"])

    # 15. documents
    op.create_table(
        "documents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="processing"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("allowed_roles", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("uploaded_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])

    # 16. document_chunks
    op.create_table(
        "document_chunks",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("qdrant_point_id", sa.String(255), nullable=True),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_tenant_id", "document_chunks", ["tenant_id"])

    # 17. llm_requests
    op.create_table(
        "llm_requests",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", GUID(), nullable=True),
        sa.Column("task_id", GUID(), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False, server_default="v1"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="success"),
        sa.Column("fallback_from", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_llm_requests_tenant_id", "llm_requests", ["tenant_id"])
    op.create_index("ix_llm_requests_workflow_id", "llm_requests", ["workflow_id"])

    # 18. audit_logs (append-only)
    op.create_table(
        "audit_logs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_type", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details_redacted", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])

    # 19. outbox_events
    op.create_table(
        "outbox_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_outbox_events_tenant_id", "outbox_events", ["tenant_id"])

    # 20. aiops_incidents
    op.create_table(
        "aiops_incidents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("root_cause_hypothesis", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_aiops_incidents_tenant_id", "aiops_incidents", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("aiops_incidents")
    op.drop_table("outbox_events")
    op.drop_table("audit_logs")
    op.drop_table("llm_requests")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("tool_executions")
    op.drop_table("integrations")
    op.drop_table("policy_rules")
    op.drop_table("approval_requests")
    op.drop_table("agent_messages")
    op.drop_table("workflow_checkpoints")
    op.drop_table("workflow_tasks")
    op.drop_table("workflows")
    op.drop_table("agent_templates")
    op.drop_table("agents")
    op.drop_table("api_keys")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")

