from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as aioredis
from app.core.errors.translators import translate_db_error
from app.core.infra.database import async_session_local
from fastapi import Depends, Request
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_local() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        # The commit is outside every @translate_db_errors function, so its
        # errors are translated here. Only the commit: an OSError raised by
        # the route itself (e.g. SMTP) must not turn into "database down".
        try:
            await session.commit()
        except (SQLAlchemyError, OSError) as e:
            await session.rollback()
            # LOGGING: same event as translate_db_errors
            logger.warning(
                "sqlalchemy_error_translated",
                func="get_db.commit",
                error_type=type(e).__name__,
                error=str(e),
            )
            raise translate_db_error(e) from e
        finally:
            await session.close()


async def get_redis(request: Request) -> AsyncGenerator[aioredis.Redis]:
    async with aioredis.Redis(
        connection_pool=request.app.state.redis_pool
    ) as redis_client:
        yield redis_client


DbSession = Annotated[AsyncSession, Depends(get_db, scope="function")]
RedisClient = Annotated[aioredis.Redis, Depends(get_redis, scope="function")]
