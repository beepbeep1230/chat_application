from functools import wraps

from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger  # LOGGING: Import logger
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app.core.exceptions import (
    AppError,
    AuthError,
    CacheConnectionError,
    CacheError,
    CacheServerError,
    DatabaseError,
    EmailNotVerified,
    ExpiredToken,
    InvalidCredentials,
    InvalidToken,
    Unauthenticated,
    UserExists,
    UserNotFound,
)
from redis import ConnectionError, DataError, RedisError, ResponseError
from redis import TimeoutError as RedisTimeoutError


# LOGGING: DB error translation - log the raw SQLAlchemy error before translating
def translate_db_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except SQLAlchemyError as e:
            # LOGGING: warning (not error) - translated to a 503 response below
            logger.warning(
                "sqlalchemy_error_translated",
                func=func.__qualname__,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise translate_db_error(e) from e
        except Exception:
            raise

    return wrapper


def translate_db_error(e: Exception) -> AppError:
    if isinstance(e, IntegrityError):
        return UserExists()
    if isinstance(e, (OperationalError, PoolTimeoutError)):
        return DatabaseError()
    return DatabaseError()


# LOGGING: Redis error translation - log the raw Redis error before translating
def translate_cache_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
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
        except Exception:
            raise

    # BUGFIX: this was missing - without it, the decorator returns None and
    # every decorated function (set_session, revoke_*, ...) becomes None.
    return wrapper


def translate_cache_error(e: Exception) -> AppError:
    if isinstance(e, (ConnectionError, RedisTimeoutError)):
        return CacheConnectionError()
    if isinstance(e, (ResponseError, DataError)):
        return CacheServerError()
    return CacheError()


async def unauthorized_handler(
    request: Request,
    exc: InvalidToken | ExpiredToken | Unauthenticated | InvalidCredentials | AuthError,
):
    # LOGGING: Auth failure seen by the client (raw cause already logged at source)
    logger.warning(
        "auth_failure_response",
        path=request.url.path,
        status_code=status.HTTP_401_UNAUTHORIZED,
        reason=type(exc).__name__,
        client_ip=request.client.host if request.client else "unknown",
    )
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": exc.message},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def user_not_found_handler(request: Request, exc: UserNotFound):
    logger.info("user_not_found_response", path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.message},
    )


async def user_exists_handler(request: Request, exc: UserExists):
    # LOGGING: Duplicate registration attempt (also covers IntegrityError path)
    logger.warning(
        "user_exists_response", path=request.url.path, client_ip=request.client.host if request.client else "unknown"
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": exc.message},
    )


async def email_not_verified_handler(request: Request, exc: EmailNotVerified):
    logger.warning("email_not_verified_response", path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"message": exc.message},
    )


async def database_error_handler(request: Request, exc: DatabaseError):
    # LOGGING: 503 - raw SQLAlchemy cause already logged in translate_db_errors
    logger.error(
        "database_error_response", path=request.url.path, reason=type(exc).__name__
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"message": exc.message},
    )


async def cache_error_handler(
    request: Request, exc: CacheConnectionError | CacheServerError | CacheError
):
    # LOGGING: 503 - raw Redis cause already logged in translate_cache_errors
    logger.error(
        "cache_error_response", path=request.url.path, reason=type(exc).__name__
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"message": exc.message},
    )
