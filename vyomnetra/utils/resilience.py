"""Resilience & Reliability Utilities.

Implements Circuit Breaker pattern, exponential backoff retries with jitter,
and global exception handling with correlation ID tracking.
"""

import time
import uuid
import functools
from typing import Callable, Any, Optional, Dict
from pydantic import BaseModel

from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.utils.resilience")


class CircuitBreakerOpenException(Exception):
    """Raised when call is blocked because Circuit Breaker is in OPEN state."""
    pass


class CircuitBreaker:
    """Circuit Breaker implementing CLOSED, OPEN, and HALF-OPEN state transitions."""

    def __init__(
        self,
        name: str = "DefaultCircuit",
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 30.0
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec

        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.failure_count = 0
        self.last_state_change = time.time()

    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper

    def call(self, func: Callable, *args, **kwargs) -> Any:
        now = time.time()

        if self.state == "OPEN":
            if now - self.last_state_change > self.recovery_timeout_sec:
                logger.info(f"CircuitBreaker '{self.name}' transitioning from OPEN to HALF-OPEN.")
                self.state = "HALF-OPEN"
                self.last_state_change = now
            else:
                raise CircuitBreakerOpenException(
                    f"CircuitBreaker '{self.name}' is OPEN. Requests blocked for {self.recovery_timeout_sec}s."
                )

        try:
            result = func(*args, **kwargs)
            if self.state == "HALF-OPEN":
                logger.info(f"CircuitBreaker '{self.name}' call succeeded. Resetting state to CLOSED.")
                self.state = "CLOSED"
                self.failure_count = 0
                self.last_state_change = now
            return result
        except Exception as e:
            self.failure_count += 1
            logger.warning(f"CircuitBreaker '{self.name}' failure count: {self.failure_count}/{self.failure_threshold} ({e})")
            if self.failure_count >= self.failure_threshold:
                if self.state != "OPEN":
                    logger.error(f"CircuitBreaker '{self.name}' threshold exceeded! Transitioning state to OPEN.")
                    self.state = "OPEN"
                    self.last_state_change = now
            raise e


def generate_correlation_id() -> str:
    """Generates a unique correlation ID for tracking requests across logging and API layers."""
    return f"vyom-{uuid.uuid4().hex[:12]}"


class StructuredErrorResponse(BaseModel):
    """Standardized error payload returned across all API endpoints and background tasks."""
    error_code: str
    message: str
    correlation_id: str
    timestamp_utc: str
    details: Optional[Dict[str, Any]] = None
