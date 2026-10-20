import time
from enum import Enum
from functools import wraps

from app.core.exceptions import CacheConnectionError

TIME_BEFORE_RETRY = 15


class CircuitStatus(Enum):
    CLOSED = "closed"
    HALF_OPEN = "half_open"
    OPEN = "open"


class CircuitBreaker:
    def __init__(
        self,
        exception,
        reset_timeout=TIME_BEFORE_RETRY,
        threshold=3,
    ):
        self.threshold = threshold
        self.state = CircuitStatus.CLOSED
        self.failures = 0
        self.opened_at = 0.0
        self.exception = exception
        self.reset_timeout = reset_timeout

    def _record_success(self):
        self.state = CircuitStatus.CLOSED
        self.failures = 0

    def _record_failure(self, exec):
        self.failures += 1
        if self.state in (CircuitStatus.HALF_OPEN, CircuitStatus.CLOSED) and (
            self.failures >= self.threshold
        ):
            self.state = CircuitStatus.OPEN
            self.opened_at = time.monotonic()

    def _allow(self):
        time_passed = time.monotonic() - self.opened_at
        if self.state == CircuitStatus.CLOSED:
            return True
        if self.state == CircuitStatus.OPEN and time_passed >= self.reset_timeout:
            self.state = CircuitStatus.HALF_OPEN
            return True
        return False

    def decorator(self, *, fallback=None):
        def decorate(func):
            @wraps(func)
            async def execute(*args, **kwargs):
                if not self._allow():
                    return fallback
                try:
                    result = await func(*args, **kwargs)
                except self.exception as e:
                    self._record_failure(e)
                    return fallback
                except Exception:
                    raise
                self._record_success()
                return result

            return execute

        return decorate


redis_circuit_breaker = CircuitBreaker(exception=CacheConnectionError)
