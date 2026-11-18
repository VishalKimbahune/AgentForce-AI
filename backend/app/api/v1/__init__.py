"""API v1 router bundle."""

from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.org import router as org_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.documents import router as documents_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.voice import router as voice_router
from app.api.v1.aiops import router as aiops_router
from app.api.v1.marketplace import router as marketplace_router
from app.api.v1.audit_logs import router as audit_logs_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(org_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(workflows_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(knowledge_router)
api_v1_router.include_router(approvals_router)
api_v1_router.include_router(integrations_router)
api_v1_router.include_router(voice_router)
api_v1_router.include_router(aiops_router)
api_v1_router.include_router(marketplace_router)
api_v1_router.include_router(audit_logs_router)
