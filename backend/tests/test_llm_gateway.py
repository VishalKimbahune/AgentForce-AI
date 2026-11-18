"""Tests for Phase 2: LLM Gateway, routing, fallbacks, circuit breakers, and telemetry."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal
from app.core.security import create_token
from app.services.llm_gateway.circuit_breaker import CircuitBreaker, CircuitState
from app.services.llm_gateway.gateway import LLMGateway, ModelRoute, TaskType, gateway
from app.services.llm_gateway.pii import mask_pii


def test_pii_masking():
    raw_text = (
        "User Priya (email: priya.sharma@example.com, phone: +1-555-839-2910) "
        "with SSN 123-45-6789 and Card 4111-2222-3333-4444 submitted API key "
        "sk-999998888877777666665555544444."
    )
    masked = mask_pii(raw_text)
    assert "[EMAIL_REDACTED]" in masked
    assert "priya.sharma@example.com" not in masked
    assert "[PHONE_REDACTED]" in masked
    assert "+1-555-839-2910" not in masked
    assert "[SSN_REDACTED]" in masked
    assert "123-45-6789" not in masked
    assert "[CARD_REDACTED]" in masked
    assert "4111-2222-3333-4444" not in masked
    assert "[KEY_REDACTED]" in masked
    assert "sk-999998888877777666665555544444" not in masked


def test_task_type_routing_chains():
    gw = LLMGateway()

    # 1. SENSITIVE tasks must strictly route locally to Ollama
    sensitive_routes = gw.get_route_chain(TaskType.SENSITIVE)
    assert len(sensitive_routes) == 1
    assert sensitive_routes[0].provider == "ollama"

    # 2. INTENT tasks prioritize small/fast models (Groq 8B)
    intent_routes = gw.get_route_chain(TaskType.INTENT)
    assert intent_routes[0].provider == "groq"
    assert "8b" in intent_routes[0].model

    # 3. PLANNING tasks prioritize reasoning models (Gemini Pro)
    planning_routes = gw.get_route_chain(TaskType.PLANNING)
    assert planning_routes[0].provider == "gemini"
    assert "pro" in planning_routes[0].model

    # 4. GENERAL tasks follow default chain (Gemini -> Groq -> Ollama)
    general_routes = gw.get_route_chain(TaskType.GENERAL)
    providers = [r.provider for r in general_routes]
    assert providers == ["gemini", "groq", "ollama"]


def test_circuit_breaker_trip_and_cooldown():
    breaker = CircuitBreaker(failure_threshold=3, recovery_time_seconds=1.0)
    assert breaker.can_execute() is True
    assert breaker.state == CircuitState.CLOSED

    # Record 2 failures - should still be CLOSED
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.can_execute() is True
    assert breaker.state == CircuitState.CLOSED

    # 3rd failure trips the breaker to OPEN
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    assert breaker.can_execute() is False

    # After cooldown, resets to HALF_OPEN
    breaker.last_failure_time -= 2.0  # simulate time passing
    assert breaker.can_execute() is True
    assert breaker.state == CircuitState.HALF_OPEN

    # Success restores to CLOSED
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_fallback_when_provider_key_fails():
    """Done when: killing one provider key still returns a response through fallback."""
    gw = LLMGateway()
    tenant_id = uuid.uuid4()

    # Simulate Gemini failing (e.g. invalid key or 429), then Groq succeeding
    call_history = []

    async def mock_router(route: ModelRoute, prompt: str, attempt: int):
        call_history.append(route.model)
        if route.provider == "gemini":
            raise RuntimeError("Gemini API key rejected: Invalid API Key (HTTP 403)")
        # Fallback provider succeeds
        return f"Response from {route.model} for: {prompt}", 120, 45, 0.00015

    gw.set_mock_handler(mock_router)

    async with AsyncSessionLocal() as session:
        response = await gw.complete(
            prompt="Plan interview schedule for Python developer",
            task_type=TaskType.GENERAL,
            tenant_id=tenant_id,
            db=session,
        )

    # Gemini failed and fallback to Groq succeeded
    assert response.provider == "groq"
    assert "llama-3.1-8b-instant" in response.model
    assert response.fallback_from == "gemini/gemini-1.5-flash"
    assert "Response from groq" in response.content
    assert response.input_tokens == 120
    assert response.output_tokens == 45
    print("[PASS] Killing Gemini provider key successfully fell back to Groq")


@pytest.mark.asyncio
async def test_analytics_llm_endpoint():
    """Verifies GET /api/v1/analytics/llm returns telemetry metrics and enforces tenant isolation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create Org A with Priya
        user_a_id = str(uuid.uuid4())
        token_a = create_token(sub=user_a_id, email=f"priya_llm_{user_a_id[:8]}@acme.com")
        res_a = await client.post(
            "/api/v1/auth/complete-profile",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"name": "Priya LLM", "organization_name": "Acme AI Corp"},
        )
        org_a_id = uuid.UUID(res_a.json()["organization"]["id"])

        # Execute 2 completions for Tenant A through gateway
        gw = LLMGateway()

        async def mock_handler(route: ModelRoute, prompt: str, attempt: int):
            return f"Answer from {route.model}", 100, 50, 0.0002

        gw.set_mock_handler(mock_handler)

        async with AsyncSessionLocal() as session:
            await gw.complete(
                prompt="Task 1",
                task_type=TaskType.GENERAL,
                tenant_id=org_a_id,
                db=session,
            )
            await gw.complete(
                prompt="Task 2",
                task_type=TaskType.GENERAL,
                tenant_id=org_a_id,
                db=session,
            )

        # Query /analytics/llm for Tenant A
        res_analytics = await client.get(
            "/api/v1/analytics/llm",
            headers={"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(org_a_id)},
        )
        assert res_analytics.status_code == 200
        data = res_analytics.json()
        assert data["total_requests"] >= 2
        assert data["total_tokens"] >= 300
        assert len(data["models"]) >= 1
        model_stat = data["models"][0]
        assert model_stat["provider"] == "gemini"
        assert model_stat["total_requests"] >= 2
        print("[PASS] LLM analytics endpoint successfully aggregated telemetry data")

