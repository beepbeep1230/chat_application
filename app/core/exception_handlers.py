# from contextlib import asynccontextmanager
from functools import wraps

from fastapi import Request, status
from fastapi.responses import JSONResponse
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


def translate_db_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except SQLAlchemyError as e:
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


def best_effort_cache(default=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except CacheError:
                return default

        return wrapper

    return decorator


def translate_cache_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except RedisError as e:
            raise translate_cache_error(e) from e
        except Exception:
            raise


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
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": exc.message},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def user_not_found_handler(request: Request, exc: UserNotFound):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.message},
    )


async def user_exists_handler(request: Request, exc: UserExists):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": exc.message},
    )


async def email_not_verified_handler(request: Request, exc: EmailNotVerified):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"message": exc.message},
    )


async def database_error_handler(request: Request, exc: DatabaseError):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"message": exc.message},
    )


async def cache_error_handler(
    request: Request, exc: CacheConnectionError | CacheServerError | CacheError
):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"message": exc.message},
    )
