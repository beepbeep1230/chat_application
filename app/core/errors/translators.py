from collections.abc import Awaitable, Callable
from functools import wraps

from app.core.errors.exceptions import (
    AppError,
    CacheConnectionError,
    CacheError,
    CacheServerError,
    ConflictError,
    ConstraintViolation,
    DatabaseError,
    UserExists,
)
from loguru import logger  # LOGGING: Import logger
from redis import ConnectionError, DataError, RedisError, ResponseError
from redis import TimeoutError as RedisTimeoutError
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

# IntegrityError only: the client's request conflicts with the stored data.
_SQLSTATE_ERRORS: dict[str, type[AppError]] = {
    "23505": ConflictError,  # unique_violation
    "23503": ConflictError,  # foreign_key_violation
    "23514": ConstraintViolation,  # check_violation
}

# IntegrityError only, checked before _SQLSTATE_ERRORS: a precise error for a
# known constraint (names verified with pg_constraint).
_CONSTRAINT_ERRORS: dict[str, type[AppError]] = {
    "user_account_email_key": UserExists,
    "user_account_username_key": UserExists,
}

# Any error class: the database is busy or unreachable -> 503.
# Matched by sqlstate because the SQLAlchemy class is not reliable here
# (e.g. a statement timeout arrives as a plain DBAPIError, not OperationalError).
_TRANSIENT_SQLSTATES = frozenset(
    {
        "40001",  # serialization_failure
        "40P01",  # deadlock_detected
        "55P03",  # lock_not_available
        "57014",  # query_canceled (statement_timeout)
        "57P01",  # admin_shutdown
        "57P02",  # crash_shutdown
        "57P03",  # cannot_connect_now
        "53300",  # too_many_connections
    }
)
_TRANSIENT_SQLSTATE_CLASSES = ("08",)  # connection_exception class
# Transient errors that are safe to retry right away -> send Retry-After.
_RETRYABLE_SQLSTATES = frozenset({"40001", "40P01"})
_RETRY_AFTER_SECONDS = 1


# LOGGING: DB error translation - log the raw SQLAlchemy error before translating
def translate_db_errors[**P, R](
    func: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        # OSError: a connection failure (refused / timeout) is raised by the
        # driver as a plain OSError and is never wrapped by SQLAlchemy.
        except (SQLAlchemyError, OSError) as e:
            # LOGGING: warning (not error) - translated to an AppError below
            logger.warning(
                "sqlalchemy_error_translated",
                func=func.__qualname__,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise translate_db_error(e) from e

    return wrapper


def translate_db_error(e: Exception) -> AppError:
    if isinstance(e, OSError):
        return DatabaseError()
    orig = getattr(e, "orig", None)
    sqlstate: str | None = getattr(orig, "sqlstate", None)
    cause = getattr(orig, "__cause__", None)
    constraint: str | None = getattr(cause, "constraint_name", None)
    if isinstance(e, IntegrityError):
        if constraint is not None and constraint in _CONSTRAINT_ERRORS:
            return _CONSTRAINT_ERRORS[constraint]()
        if sqlstate is not None and sqlstate in _SQLSTATE_ERRORS:
            return _SQLSTATE_ERRORS[sqlstate]()
    if sqlstate is not None and (
        sqlstate in _TRANSIENT_SQLSTATES
        or sqlstate.startswith(_TRANSIENT_SQLSTATE_CLASSES)
    ):
        retry_after = (
            _RETRY_AFTER_SECONDS if sqlstate in _RETRYABLE_SQLSTATES else None
        )
        return DatabaseError(retry_after=retry_after)
    if isinstance(e, (OperationalError, PoolTimeoutError)):
        return DatabaseError()
    return AppError()


# LOGGING: Redis error translation - log the raw Redis error before translating
def translate_cache_errors[**P, R](
    func: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except RedisError as e:
            # LOGGING: warning (not error) - translated to a 503 response below
            logger.warning(
                "redis_error_translated",
                func=func.__qualname__,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise translate_cache_error(e) from e

    return wrapper


def translate_cache_error(e: Exception) -> AppError:
    if isinstance(e, (ConnectionError, RedisTimeoutError)):
        return CacheConnectionError()
    if isinstance(e, (ResponseError, DataError)):
        return CacheServerError()
    return CacheError()
