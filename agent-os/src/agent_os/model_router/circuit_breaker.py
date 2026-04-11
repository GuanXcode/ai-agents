"""Circuit breaker for LLM provider resilience."""

from __future__ import annotations

import time

import structlog

logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """熔断器：连续失败达到阈值后熔断，超时后自动恢复。"""

    def __init__(self, failure_threshold: int = 3, reset_timeout_sec: int = 30) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout_sec = reset_timeout_sec
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._state = "closed"  # closed | open | half_open

    @property
    def state(self) -> str:
        if self._state == "open" and self._should_try_reset():
            self._state = "half_open"
        return self._state

    def record_success(self) -> None:
        if self._state != "closed":
            logger.info("circuit_breaker_closed")
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = "open"
            logger.warning(
                "circuit_breaker_opened",
                failure_count=self._failure_count,
                threshold=self._failure_threshold,
            )

    def allow_request(self) -> bool:
        return self.state in ("closed", "half_open")

    def _should_try_reset(self) -> bool:
        return (time.monotonic() - self._last_failure_time) >= self._reset_timeout_sec
