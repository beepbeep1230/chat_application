import time
from collections.abc import Awaitable, Callable
from enum import Enum
from functools import wraps
from typing import Any, overload

from app.core.errors.exceptions import CacheError
from app.core.logging import logger

TIME_BEFORE_RETRY = 15

type AsyncFunc[**P, R] = Callable[P, Awaitable[R]]


class CircuitStatus(Enum):
    CLOSED = "closed"
    HALF_OPEN = "half_open"
    OPEN = "open"


class CircuitBreaker:
    def __init__(
        self,
        exception: type[Exception],
        reset_timeout: float = TIME_BEFORE_RETRY,
        threshold: int = 3,
    ) -> None:
        self.threshold = threshold
        self.state = CircuitStatus.CLOSED
        self.failures = 0
        self.opened_at = 0.0
        self.exception = exception
        self.reset_timeout = reset_timeout

    def _record_success(self) -> None:
        self.state = CircuitStatus.CLOSED
        self.failures = 0

    def _record_failure(self, exec: Exception) -> None:
        self.failures += 1
        if self.state in (CircuitStatus.HALF_OPEN, CircuitStatus.CLOSED) and (
            self.failures >= self.threshold
        ):
            self.state = CircuitStatus.OPEN
            self.opened_at = time.monotonic()

    def _allow(self) -> bool:
        time_passed = time.monotonic() - self.opened_at
        if self.state != CircuitStatus.OPEN:
            return True
        if time_passed >= self.reset_timeout:
            self.state = CircuitStatus.HALF_OPEN
            return True
        return False

    # The overloads keep the decorated function's exact signature for type
    # checkers: it returns R, or the fallback's type when the breaker trips.
    @overload
    def decorator[**P, R](
        self,
    ) -> Callable[[AsyncFunc[P, R]], AsyncFunc[P, R | None]]: ...
    @overload
    def decorator[**P, R, F](
        self, *, fallback: F
    ) -> Callable[[AsyncFunc[P, R]], AsyncFunc[P, R | F]]: ...
    def decorator(
        self, *, fallback: Any = None  # Any: the overloads above are the public types
    ) -> Callable[[AsyncFunc[..., Any]], AsyncFunc[..., Any]]:
        def decorate(func: AsyncFunc[..., Any]) -> AsyncFunc[..., Any]:
            @wraps(func)
            async def execute(*args: Any, **kwargs: Any) -> Any:
                if not self._allow():
                    return fallback
                try:
                    result = await func(*args, **kwargs)
                except self.exception as e:
                    self._record_failure(e)
                    return fallback
                except Exception:
                    logger.exception(
                        "circuit_breaker_unexpected_error", func=func.__qualname__
                    )
                    return fallback
                self._record_success()
                return result

            return execute

        return decorate


redis_circuit_breaker = CircuitBreaker(exception=CacheError)
