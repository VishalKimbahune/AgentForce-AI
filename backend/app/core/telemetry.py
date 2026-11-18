"""OpenTelemetry distributed tracing for AgentForce AI platform.

Provides trace context, span management, and in-memory trace buffers across API,
orchestrator, agent, LLM gateway, and tool execution layers.
"""

import functools
import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Generator, List, Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

from app.core.config import settings

logger = logging.getLogger("core.telemetry")

# Initialize OpenTelemetry TracerProvider
resource = Resource.create(
    {
        "service.name": "agentforce-ai",
        "service.version": "1.0.0",
        "deployment.environment": settings.APP_ENV,
    }
)

_provider = TracerProvider(resource=resource)

# Optional OTLP exporter if endpoint is active
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        otlp_exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
        _provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
except Exception as e:
    logger.debug("OTLP exporter not initialized (%s). Using in-memory trace tracking.", e)

trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("agentforce-ai", "1.0.0")

# In-memory ring buffer for live dashboard inspection (Screen 13 & 14)
MAX_IN_MEMORY_SPANS = 200
_in_memory_spans: List[Dict[str, Any]] = []


class SpanRecord:
    """Represents a simplified trace span for analytics and UI inspection."""

    def __init__(
        self,
        name: str,
        span_type: str,
        attributes: Dict[str, Any],
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        parent_id: Optional[str] = None,
    ):
        self.trace_id = trace_id or uuid.uuid4().hex
        self.span_id = span_id or uuid.uuid4().hex[:16]
        self.parent_id = parent_id
        self.name = name
        self.span_type = span_type  # api, orchestrator, agent, llm, tool
        self.attributes = attributes
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self.duration_ms: float = 0.0
        self.status: str = "ok"
        self.error_message: Optional[str] = None

    def finish(self, status: str = "ok", error: Optional[str] = None) -> "SpanRecord":
        self.end_time = datetime.now(timezone.utc)
        self.duration_ms = round((self.end_time - self.start_time).total_seconds() * 1000, 2)
        self.status = status
        self.error_message = error

        # Append to buffer
        payload = self.to_dict()
        _in_memory_spans.append(payload)
        if len(_in_memory_spans) > MAX_IN_MEMORY_SPANS:
            _in_memory_spans.pop(0)

        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "span_type": self.span_type,
            "attributes": self.attributes,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error_message": self.error_message,
        }


@contextmanager
def trace_span(
    name: str,
    span_type: str = "internal",
    attributes: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Generator[SpanRecord, None, None]:
    """Context manager for tracing an operation across OpenTelemetry and internal telemetry."""
    attrs = attributes or {}
    record = SpanRecord(name=name, span_type=span_type, attributes=attrs, trace_id=trace_id)

    with tracer.start_as_current_span(name) as otel_span:
        for k, v in attrs.items():
            if isinstance(v, (str, bool, int, float)):
                otel_span.set_attribute(k, v)

        try:
            yield record
            record.finish(status="ok")
            otel_span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            record.finish(status="error", error=str(exc))
            otel_span.set_status(Status(StatusCode.ERROR, str(exc)))
            otel_span.record_exception(exc)
            raise


def trace_agent(agent_name: str) -> Callable:
    """Decorator to automatically trace AI Employee execution steps."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            attrs = {"agent": agent_name, "function": func.__name__}
            with trace_span(name=f"agent.{agent_name}", span_type="agent", attributes=attrs):
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            attrs = {"agent": agent_name, "function": func.__name__}
            with trace_span(name=f"agent.{agent_name}", span_type="agent", attributes=attrs):
                return func(*args, **kwargs)

        return async_wrapper if asyncio_is_coroutine_function(func) else sync_wrapper

    return decorator


def asyncio_is_coroutine_function(func: Any) -> bool:
    import asyncio

    return asyncio.iscoroutinefunction(func)


def get_recent_spans(
    span_type: Optional[str] = None,
    tenant_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Retrieves recent trace spans from the in-memory ring buffer with optional filtering."""
    results = _in_memory_spans.copy()
    if span_type:
        results = [s for s in results if s.get("span_type") == span_type]
    if tenant_id:
        results = [s for s in results if s.get("attributes", {}).get("tenant_id") == tenant_id]
    return results[-limit:]


def clear_spans() -> None:
    """Clears in-memory spans (primarily for testing)."""
    _in_memory_spans.clear()

