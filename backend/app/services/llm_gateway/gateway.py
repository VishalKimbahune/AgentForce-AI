"""LiteLLM Gateway service: multi-model routing, fallback chains, circuit breakers, and telemetry."""

import asyncio
import logging
import os
import random
import time
import uuid
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel

import litellm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import LLMRequest
from app.services.llm_gateway.circuit_breaker import CircuitBreakerRegistry
from app.services.llm_gateway.pii import mask_pii
from app.core.metrics import record_llm_metric
from app.core.telemetry import trace_span

# Initialize optional Langfuse tracer
_langfuse_client = None
if getattr(settings, "LANGFUSE_PUBLIC_KEY", None) and getattr(settings, "LANGFUSE_SECRET_KEY", None):
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_BASE_URL or settings.LANGFUSE_HOST,
        )
    except Exception as _e:
        pass

# Suppress noisy LiteLLM telemetry and cost map network calls
litellm.telemetry = False
litellm.suppress_debug_info = True

logger = logging.getLogger("llm_gateway")


class TaskType(str, Enum):
    INTENT = "intent"          # Intent classification, simple extraction
    PLANNING = "planning"      # Long context reasoning, planning, complex schemas
    SENSITIVE = "sensitive"    # Confidential data (strictly local model)
    GENERAL = "general"        # Standard agent tasks


class ModelRoute(BaseModel):
    provider: str
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    timeout: float = 30.0


class LLMResponse(BaseModel):
    content: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    fallback_from: Optional[str] = None


class LLMGateway:
    """Enterprise LLM Gateway with routing, fallbacks, circuit breaking, and telemetry."""

    def __init__(self):
        self.circuit_registry = CircuitBreakerRegistry(
            failure_threshold=3,
            recovery_time_seconds=30.0,
        )
        self._mock_handler: Optional[Callable[..., Any]] = None

    def set_mock_handler(self, handler: Optional[Callable[..., Any]]) -> None:
        """Allows test suites to mock external provider completions deterministically."""
        self._mock_handler = handler

    def get_route_chain(self, task_type: TaskType) -> List[ModelRoute]:
        """Returns the ordered model fallback chain for a given task type."""
        gemini_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
        groq_key = settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
        ollama_base = settings.OLLAMA_BASE_URL or "http://localhost:11434"

        gemini_flash = ModelRoute(
            provider="gemini",
            model="gemini/gemini-1.5-flash",
            api_key=gemini_key,
        )
        gemini_pro = ModelRoute(
            provider="gemini",
            model="gemini/gemini-1.5-pro",
            api_key=gemini_key,
        )
        groq_small = ModelRoute(
            provider="groq",
            model="groq/llama-3.1-8b-instant",
            api_key=groq_key,
        )
        groq_large = ModelRoute(
            provider="groq",
            model="groq/llama-3.3-70b-versatile",
            api_key=groq_key,
        )
        ollama_local = ModelRoute(
            provider="ollama",
            model="ollama/llama3.1",
            api_base=ollama_base,
        )

        if task_type == TaskType.SENSITIVE:
            # Sensitive tasks strictly run locally to prevent tenant data leakage
            return [ollama_local]

        if task_type == TaskType.INTENT:
            # Small and fast tier
            return [groq_small, gemini_flash, ollama_local]

        if task_type == TaskType.PLANNING:
            # High reasoning capability tier
            return [gemini_pro, gemini_flash, groq_large, ollama_local]

        # General / default fallback chain: Gemini -> Groq -> Ollama
        return [gemini_flash, groq_small, ollama_local]

    async def complete(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        tenant_id: Optional[uuid.UUID] = None,
        workflow_id: Optional[uuid.UUID] = None,
        task_id: Optional[uuid.UUID] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
        db: Optional[AsyncSession] = None,
    ) -> LLMResponse:
        """Executes LLM completion across the fallback chain with bounded retries and logging."""
        routes = self.get_route_chain(task_type)
        if not routes:
            raise RuntimeError(f"No available model routes configured for task type: {task_type}")

        fallback_from: Optional[str] = None
        last_exception: Optional[Exception] = None

        # Redact PII in prompt before any logging or storage
        redacted_prompt = mask_pii(prompt)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": mask_pii(system_prompt)})
        messages.append({"role": "user", "content": prompt})

        for route in routes:
            model_key = f"{route.provider}:{route.model}"
            breaker = self.circuit_registry.get_breaker(model_key)

            if not breaker.can_execute():
                logger.warning("Circuit breaker OPEN for %s, skipping to next route", model_key)
                if not fallback_from:
                    fallback_from = route.model
                continue

            # Bounded retries with exponential backoff and jitter
            max_retries = min(settings.MAX_RETRIES, 2)
            for attempt in range(max_retries + 1):
                start_time = time.time()
                try:
                    if self._mock_handler:
                        # Test suite simulation
                        content, tokens_in, tokens_out, cost = await self._mock_handler(
                            route=route,
                            prompt=prompt,
                            attempt=attempt,
                        )
                    else:
                        # LiteLLM execution
                        kwargs: Dict[str, Any] = {
                            "model": route.model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            "timeout": route.timeout,
                        }
                        if route.api_key:
                            kwargs["api_key"] = route.api_key
                        if route.api_base:
                            kwargs["api_base"] = route.api_base

                        response = await litellm.acompletion(**kwargs)
                        content = response.choices[0].message.content or ""
                        usage = getattr(response, "usage", None)
                        tokens_in = getattr(usage, "prompt_tokens", len(prompt) // 4)
                        tokens_out = getattr(usage, "completion_tokens", len(content) // 4)
                        cost = 0.0
                        try:
                            cost = litellm.completion_cost(completion_response=response)
                        except Exception:
                            cost = (tokens_in * 0.0000005) + (tokens_out * 0.0000015)

                    duration_ms = int((time.time() - start_time) * 1000)
                    breaker.record_success()

                    # Telemetry logging to database
                    if db and tenant_id:
                        await self._log_telemetry(
                            db=db,
                            tenant_id=tenant_id,
                            workflow_id=workflow_id,
                            task_id=task_id,
                            provider=route.provider,
                            model=route.model,
                            input_tokens=tokens_in,
                            output_tokens=tokens_out,
                            cost_usd=cost,
                            latency_ms=duration_ms,
                            status="success",
                            fallback_from=fallback_from,
                        )

                    return LLMResponse(
                        content=content,
                        provider=route.provider,
                        model=route.model,
                        input_tokens=tokens_in,
                        output_tokens=tokens_out,
                        cost_usd=cost,
                        latency_ms=duration_ms,
                        fallback_from=fallback_from,
                    )

                except Exception as exc:
                    duration_ms = int((time.time() - start_time) * 1000)
                    last_exception = exc
                    logger.warning(
                        "Route %s failed (attempt %d/%d): %s",
                        model_key,
                        attempt + 1,
                        max_retries + 1,
                        str(exc),
                    )

                    if attempt < max_retries:
                        # Exponential backoff with jitter
                        delay = (0.2 * (2**attempt)) + (random.uniform(0.05, 0.2))
                        await asyncio.sleep(delay)
                    else:
                        breaker.record_failure()
                        if not fallback_from:
                            fallback_from = route.model

        # If all routes in fallback chain failed
        if db and tenant_id:
            await self._log_telemetry(
                db=db,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                task_id=task_id,
                provider="none",
                model=routes[0].model,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=0,
                status="failed",
                fallback_from=fallback_from,
            )

        raise RuntimeError(
            f"All LLM routes exhausted for task {task_type}. Last error: {str(last_exception)}"
        ) from last_exception

    async def _log_telemetry(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        workflow_id: Optional[uuid.UUID],
        task_id: Optional[uuid.UUID],
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: int,
        status: str,
        fallback_from: Optional[str],
    ) -> None:
        """Asynchronously inserts an execution record into the llm_requests table."""
        # Record Prometheus metric
        try:
            record_llm_metric(
                tenant_id=str(tenant_id),
                provider=provider,
                model=model,
                status=status,
                cost_usd=cost_usd,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
            )
        except Exception:
            pass

        # Record to Langfuse if configured
        if _langfuse_client:
            try:
                _langfuse_client.generation(
                    name=f"llm.{model}",
                    model=model,
                    usage={"input": input_tokens, "output": output_tokens, "total": input_tokens + output_tokens},
                    metadata={"provider": provider, "status": status, "fallback_from": fallback_from},
                )
            except Exception:
                pass

        try:
            req = LLMRequest(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                task_id=task_id,
                provider=provider,
                model=model,
                prompt_version="v1",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                status=status,
                fallback_from=fallback_from,
            )
            db.add(req)
            await db.commit()
        except Exception as e:
            logger.error("Failed to log LLM telemetry to database: %s", str(e))
            await db.rollback()


# Global singleton instance
gateway = LLMGateway()

