"""Marketplace & AI Employees API Router: templates, installation, and agent management."""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_tenant_context, require_role
from app.models.models import Agent, AgentTemplate

router = APIRouter(tags=["marketplace"])

# Standard catalog of pre-configured AI Employees
DEFAULT_TEMPLATES = [
    {
        "name": "HR Talent Recruiter",
        "type": "hr",
        "description": "Parses incoming candidate resumes (PDF/DOCX), matches skills against job descriptions with embeddings, and proposes interview calendar slots.",
        "default_config": {
            "model_policy": {"task": "recruitment", "preferred_model": "gemini/gemini-1.5-flash"},
            "allowed_tools": ["mock_ats.get_candidate", "mock_calendar.create_event", "notifications.send_in_app"],
            "knowledge_scopes": ["hiring_policy", "recruitment_rubric"],
        },
        "required_integrations": ["ats", "calendar"],
    },
    {
        "name": "Finance & Invoice Auditor",
        "type": "finance",
        "description": "Extracts invoice line items, matches against ERP purchase orders, flags duplicate invoices and price anomalies, and stages payment batches.",
        "default_config": {
            "model_policy": {"task": "finance", "preferred_model": "groq/llama-3.3-70b-versatile"},
            "allowed_tools": ["mock_erp.get_purchase_order", "mock_payment.execute_batch"],
            "knowledge_scopes": ["expense_policy", "procurement_approval_matrix"],
        },
        "required_integrations": ["erp", "payment_gateway"],
    },
    {
        "name": "Operations Executive Reporter",
        "type": "ops",
        "description": "Compiles 30-day KPI and operations metrics from ERP, validates calculations deterministically, and generates executive business reports.",
        "default_config": {
            "model_policy": {"task": "operations", "preferred_model": "gemini/gemini-1.5-pro"},
            "allowed_tools": ["mock_erp.get_metrics", "notifications.send_in_app"],
            "knowledge_scopes": ["operational_standards", "kpi_definitions"],
        },
        "required_integrations": ["erp"],
    },
    {
        "name": "Corporate Knowledge Officer",
        "type": "knowledge",
        "description": "Performs hybrid retrieval-augmented generation (RAG) over company policies, employee handbooks, and compliance documents with citations.",
        "default_config": {
            "model_policy": {"task": "knowledge", "preferred_model": "gemini/gemini-1.5-flash"},
            "allowed_tools": ["qdrant.search"],
            "knowledge_scopes": ["all"],
        },
        "required_integrations": ["qdrant_vector_store"],
    },
    {
        "name": "AIOps Site Reliability Engineer",
        "type": "aiops",
        "description": "Monitors workforce telemetry, detects failure and cost spikes, hypothesizes root causes from error traces, and proposes governed remediation.",
        "default_config": {
            "model_policy": {"task": "aiops", "preferred_model": "gemini/gemini-1.5-flash"},
            "allowed_tools": ["circuit_breaker.reset", "integrations.restart"],
            "knowledge_scopes": ["infrastructure_runbooks"],
        },
        "required_integrations": ["prometheus", "opentelemetry"],
    },
    {
        "name": "Customer Support Dispatcher",
        "type": "support",
        "description": "Classifies incoming customer inquiry tickets, extracts urgency, searches knowledge base, and drafts resolution recommendations.",
        "default_config": {
            "model_policy": {"task": "support", "preferred_model": "groq/llama-3.1-8b-instant"},
            "allowed_tools": ["notifications.send_in_app"],
            "knowledge_scopes": ["support_faq", "product_documentation"],
        },
        "required_integrations": ["crm"],
    },
]


class TemplateResponse(BaseModel):
    id: str
    name: str
    type: str
    description: str
    default_config: Optional[Dict[str, Any]] = None
    required_integrations: List[str] = []
    published: bool = True


class AgentResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    type: str
    system_prompt: str
    model_policy: Optional[Dict[str, Any]] = None
    allowed_tools: List[str] = []
    status: str
    template_id: Optional[str] = None
    created_at: str


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    system_prompt: Optional[str] = None


@router.get("/marketplace/templates", response_model=List[TemplateResponse])
async def list_marketplace_templates(
    db: AsyncSession = Depends(get_db),
):
    """Lists published AI Employee templates from the catalog. Seeds default templates if none exist."""
    res = await db.execute(select(AgentTemplate).where(AgentTemplate.published == True))
    templates = res.scalars().all()

    if not templates:
        # Seed standard templates
        for tpl_data in DEFAULT_TEMPLATES:
            tpl = AgentTemplate(
                id=uuid.uuid4(),
                name=tpl_data["name"],
                type=tpl_data["type"],
                description=tpl_data["description"],
                default_config=tpl_data["default_config"],
                required_integrations=tpl_data["required_integrations"],
                published=True,
            )
            db.add(tpl)
        await db.commit()
        res = await db.execute(select(AgentTemplate).where(AgentTemplate.published == True))
        templates = res.scalars().all()

    return [
        TemplateResponse(
            id=str(t.id),
            name=t.name,
            type=t.type,
            description=t.description,
            default_config=t.default_config,
            required_integrations=t.required_integrations or [],
            published=t.published,
        )
        for t in templates
    ]


@router.post("/marketplace/templates/{template_id}/install", response_model=AgentResponse)
async def install_template(
    template_id: str,
    ctx: TenantContext = Depends(require_role(["owner", "manager"])),
    db: AsyncSession = Depends(get_db),
):
    """Installs an AI Employee template into the caller's tenant workspace."""
    try:
        tpl_uuid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid template ID")

    tpl = await db.get(AgentTemplate, tpl_uuid)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    cfg = tpl.default_config or {}
    agent_id = uuid.uuid4()
    agent = Agent(
        id=agent_id,
        tenant_id=ctx.tenant_id,
        name=tpl.name,
        type=tpl.type,
        system_prompt=f"You are the {tpl.name} for the organization. Execute tasks accurately according to enterprise policy.",
        model_policy=cfg.get("model_policy"),
        allowed_tools=cfg.get("allowed_tools", []),
        knowledge_scopes=cfg.get("knowledge_scopes", []),
        status="active",
        template_id=tpl.id,
        created_by=str(ctx.user.id),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return AgentResponse(
        id=str(agent.id),
        tenant_id=str(agent.tenant_id),
        name=agent.name,
        type=agent.type,
        system_prompt=agent.system_prompt,
        model_policy=agent.model_policy,
        allowed_tools=agent.allowed_tools or [],
        status=agent.status,
        template_id=str(agent.template_id) if agent.template_id else None,
        created_at=agent.created_at.isoformat() if agent.created_at else "",
    )


@router.get("/agents", response_model=List[AgentResponse])
async def list_agents(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Lists installed AI Employees strictly filtered by tenant."""
    res = await db.execute(
        select(Agent).where(Agent.tenant_id == ctx.tenant_id).order_by(Agent.created_at.asc())
    )
    agents = res.scalars().all()

    return [
        AgentResponse(
            id=str(a.id),
            tenant_id=str(a.tenant_id),
            name=a.name,
            type=a.type,
            system_prompt=a.system_prompt,
            model_policy=a.model_policy,
            allowed_tools=a.allowed_tools or [],
            status=a.status,
            template_id=str(a.template_id) if a.template_id else None,
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a in agents
    ]


@router.patch("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    req: UpdateAgentRequest,
    ctx: TenantContext = Depends(require_role(["owner", "manager"])),
    db: AsyncSession = Depends(get_db),
):
    """Updates configuration or status for an installed AI Employee."""
    try:
        a_uuid = uuid.UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID")

    agent = await db.get(Agent, a_uuid)
    if not agent or agent.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if req.name is not None:
        agent.name = req.name
    if req.status is not None:
        agent.status = req.status
    if req.system_prompt is not None:
        agent.system_prompt = req.system_prompt

    await db.commit()
    await db.refresh(agent)

    return AgentResponse(
        id=str(agent.id),
        tenant_id=str(agent.tenant_id),
        name=agent.name,
        type=agent.type,
        system_prompt=agent.system_prompt,
        model_policy=agent.model_policy,
        allowed_tools=agent.allowed_tools or [],
        status=agent.status,
        template_id=str(agent.template_id) if agent.template_id else None,
        created_at=agent.created_at.isoformat() if agent.created_at else "",
    )

