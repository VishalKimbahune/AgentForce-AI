"""Circuit breaker implementation for LLM providers."""

import time
from enum import Enum
from typing import Dict


class CircuitState(str, Enum):
    CLOSED = "closed"        # Healthy: requests pass through normally
    OPEN = "open"            # Unhealthy: fast-fail, skip to fallback
    HALF_OPEN = "half_open"  # Testing: allow trial request to probe recovery


class CircuitBreaker:
    """In-memory circuit breaker per model/provider."""

    def __init__(self, failure_threshold: int = 3, recovery_time_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_seconds = recovery_time_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0

    def can_execute(self) -> bool:
        """Determines if the provider is healthy enough to receive a request."""
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.recovery_time_seconds:
                # Cooldown expired, transition to HALF_OPEN to test
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        # HALF_OPEN allows a single probe attempt
        return True

    def record_success(self) -> None:
        """Records a successful call, resetting failure counters."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Records a failed call, opening circuit if threshold is reached."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


class CircuitBreakerRegistry:
    """Registry managing circuit breakers across models and providers."""

    def __init__(self, failure_threshold: int = 3, recovery_time_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_seconds = recovery_time_seconds
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get_breaker(self, model_key: str) -> CircuitBreaker:
        if model_key not in self._breakers:
            self._breakers[model_key] = CircuitBreaker(
                failure_threshold=self.failure_threshold,
                recovery_time_seconds=self.recovery_time_seconds,
            )
        return self._breakers[model_key]

    def reset_all(self) -> None:
        self._breakers.clear()

