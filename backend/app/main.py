"""Main FastAPI application entry point for AgentForce AI."""

import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from app.core.correlation import correlation_id, CorrelationIdMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.metrics import export_prometheus_metrics
from app.api.v1 import api_v1_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import health_check, readiness_check
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start up and shut down hooks."""
    setup_logging(log_level="INFO" if not settings.is_production else "WARNING")
    logger.info("AgentForce AI Backend starting up [Env: %s]", settings.APP_ENV)
    yield
    logger.info("AgentForce AI Backend shutting down")


app = FastAPI(
    title="AgentForce AI",
    description="The Operating System for AI Employees",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    correlation_id.set(cid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response

# CORS middleware for Next.js frontend
allowed_origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    cid = correlation_id.get()
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "correlation_id": cid,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    cid = correlation_id.get()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": str(exc.errors()),
                "correlation_id": cid,
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    cid = correlation_id.get()
    logger.exception("Unhandled exception during request processing")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact support.",
                "correlation_id": cid,
            }
        },
    )


# Top-level health endpoints as required by spec / infra
@app.get("/health", tags=["Health"], include_in_schema=True)
async def top_level_health():
    return await health_check()


@app.get("/ready", tags=["Health"], include_in_schema=True)
async def top_level_ready():
    return await readiness_check()


@app.get("/metrics", response_class=PlainTextResponse, tags=["Observability"], include_in_schema=True)
async def prometheus_metrics():
    """Prometheus exposition endpoint for scraping AgentForce operational metrics."""
    return export_prometheus_metrics()


# Instrument FastAPI with OpenTelemetry distributed tracing
FastAPIInstrumentor.instrument_app(app)

# Mount API v1 router and aliases
app.include_router(api_v1_router)
app.include_router(auth_router)  # Supports /me and /auth/complete-profile directly

# Mount marketplace and audit logs aliases at root for spec compliance
from app.api.v1.marketplace import router as marketplace_router
from app.api.v1.audit_logs import router as audit_logs_router
app.include_router(marketplace_router)
app.include_router(audit_logs_router)
