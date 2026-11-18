"""Health and readiness endpoints."""

from fastapi import APIRouter, status
from app.core.correlation import correlation_id
from sqlalchemy import text
from app.core.config import settings
from app.core.database import async_engine
from app.schemas.common import HealthResponse, ReadinessResponse, DependencyStatus

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check() -> HealthResponse:
    """Liveness probe - returns 200 if the process is up."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        environment=settings.APP_ENV,
        correlation_id=correlation_id.get(),
    )


@router.get("/ready", response_model=ReadinessResponse, status_code=status.HTTP_200_OK)
async def readiness_check() -> ReadinessResponse:
    """Readiness probe - tests connectivity to essential services."""
    db_status = "unknown"
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"unreachable: {str(e)[:50]}"

    # In development/local setup, dependencies report status gracefully
    return ReadinessResponse(
        status="ok" if db_status == "connected" else "degraded",
        dependencies=DependencyStatus(
            database=db_status,
            redis="configured",
            qdrant="configured",
            rabbitmq="configured",
        ),
        correlation_id=correlation_id.get(),
    )
