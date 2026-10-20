from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from redis.backoff import ExponentialWithJitterBackoff
from redis.retry import Retry

from app.core.config import settings
from redis import ConnectionError, TimeoutError

retry = Retry(ExponentialWithJitterBackoff(), 2)


@asynccontextmanager
async def lifespan_redis(app: FastAPI):

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
    yield
    await app.state.redis_pool.aclose()
