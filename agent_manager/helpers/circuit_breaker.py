"""
Circuit breaker pattern for resilient HTTP requests.

Prevents hammering endpoints that are repeatedly failing.
States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing) → CLOSED

Configuration-driven thresholds.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker state."""
    CLOSED = "closed"      # Normal: requests go through
    OPEN = "open"          # Too many failures: fast-fail
    HALF_OPEN = "half_open"  # Testing recovery: single request allowed


@dataclass
class CircuitBreaker:
    """Circuit breaker for a single endpoint."""

    url: str
    failure_threshold: int = 5          # Failures before OPEN
    recovery_timeout: float = 300.0     # Seconds before HALF_OPEN (5 min default)
    success_threshold: int = 2          # Successes in HALF_OPEN to close

    # Internal state
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    opened_at: float = 0.0

    def record_success(self) -> None:
        """Record a successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info("Circuit closed for %s (recovered)", self.url)
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0  # Reset on success

    def record_failure(self) -> None:
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.warning(
                    "Circuit opened for %s (%d failures)",
                    self.url, self.failure_count
                )
                self.state = CircuitState.OPEN
                self.opened_at = time.time()
        elif self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit reopened for %s (recovery failed)", self.url)
            self.state = CircuitState.OPEN
            self.opened_at = time.time()
            self.success_count = 0

    def allow_request(self) -> bool:
        """Check if a request is allowed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.opened_at
            if elapsed >= self.recovery_timeout:
                logger.info("Circuit half-open for %s (testing recovery)", self.url)
                self.state = CircuitState.HALF_OPEN
                self.failure_count = 0
                self.success_count = 0
                return True
            return False

        # HALF_OPEN: allow one request at a time
        return True

    def get_status(self) -> dict[str, Any]:
        """Return circuit status."""
        return {
            "url": self.url,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time,
        }


class CircuitBreakerManager:
    """Manages circuit breakers for multiple endpoints."""

    def __init__(self, default_config: dict[str, Any] | None = None) -> None:
        self.breakers: dict[str, CircuitBreaker] = {}
        self.default_config = default_config or {}

    def get_breaker(self, url: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a URL."""
        if url not in self.breakers:
            cfg = self.default_config.copy()
            self.breakers[url] = CircuitBreaker(url=url, **cfg)
        return self.breakers[url]

    def allow_request(self, url: str) -> bool:
        """Check if a request to this URL is allowed."""
        breaker = self.get_breaker(url)
        return breaker.allow_request()

    def record_success(self, url: str) -> None:
        """Record a successful request."""
        breaker = self.get_breaker(url)
        breaker.record_success()

    def record_failure(self, url: str) -> None:
        """Record a failed request."""
        breaker = self.get_breaker(url)
        breaker.record_failure()

    def get_all_status(self) -> dict[str, Any]:
        """Get status of all breakers."""
        return {url: cb.get_status() for url, cb in self.breakers.items()}
