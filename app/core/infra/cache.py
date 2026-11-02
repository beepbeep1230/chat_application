from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from redis.backoff import ExponentialWithJitterBackoff
from redis.retry import Retry

from app.core.config import settings
from app.core.infra.token_bucket import TOKEN_BUCKET_SCRIPT
from redis import ConnectionError, TimeoutError

retry = Retry(ExponentialWithJitterBackoff(), 2)


@asynccontextmanager
async def lifespan_redis(app: FastAPI) -> AsyncGenerator[None]:

    app.state.redis_pool = aioredis.ConnectionPool(
        password=settings.redis_password.get_secret_value(),
        host=settings.redis_host,
        port=settings.redis_port,
        db=0,
        socket_timeout=1,
        socket_connect_timeout=1,
        max_connections=50,
        decode_responses=True,
        retry=retry,
        retry_on_error=[ConnectionError, TimeoutError],
    )
    # register_script() only hashes the script locally (no Redis call), so this
    # is safe while Redis is down. The first EVALSHA loads it on NoScriptError.
    client = aioredis.Redis(connection_pool=app.state.redis_pool)
    app.state.token_bucket_script = client.register_script(TOKEN_BUCKET_SCRIPT)
    yield

    await app.state.redis_pool.aclose()
