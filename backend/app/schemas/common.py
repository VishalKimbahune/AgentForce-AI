"""Common Pydantic schemas across the API."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    correlation_id: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    environment: str = "development"
    correlation_id: Optional[str] = None


class DependencyStatus(BaseModel):
    database: str
    redis: str
    qdrant: str
    rabbitmq: str


class ReadinessResponse(BaseModel):
    status: str
    dependencies: DependencyStatus
    correlation_id: Optional[str] = None

