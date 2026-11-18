"""Correlation ID context and HTTP middleware for FastAPI."""

import uuid
from contextvars import ContextVar
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id_ctx", default=None)


class CorrelationId:
    """Helper providing get() and set() matching standard correlation ID API."""

    @staticmethod
    def get() -> Optional[str]:
        return _correlation_id_ctx.get()

    @staticmethod
    def set(value: Optional[str]) -> None:
        _correlation_id_ctx.set(value)


correlation_id = CorrelationId()


def get_correlation_id() -> str:
    """Returns current correlation ID from context or generates a new one."""
    cid = correlation_id.get()
    return cid or str(uuid.uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware extracting or generating correlation ID for every request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        header_cid = request.headers.get("x-correlation-id")
        cid = header_cid if header_cid else str(uuid.uuid4())
        correlation_id.set(cid)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response
