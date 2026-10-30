from uuid import UUID

import redis.asyncio as aioredis
from app.core.errors.translators import translate_cache_errors
from app.core.infra.circuit_breaker import redis_circuit_breaker
from app.core.logging import logger  # LOGGING: Import logger

COOLDOWN_KEY = "friend:cooldown:{requester}:{addressee}"


def _cooldown_key(requester: UUID, addressee: UUID) -> str:
    return COOLDOWN_KEY.format(requester=requester, addressee=addressee)


@redis_circuit_breaker.decorator(fallback=False)
@translate_cache_errors
async def set_cooldown(
        r: aioredis.Redis, requester_id: UUID, addressee_id: UUID, ttl: int
) -> bool:
    await r.set(_cooldown_key(requester_id, addressee_id), "1", ex=ttl)
    logger.debug("cool_down_key_set", requester=requester_id, addressee=addressee_id)
    return True


@redis_circuit_breaker.decorator(fallback=0)
@translate_cache_errors
async def cooldown_remaining_second(
        r: aioredis.Redis, requester_id: UUID, addressee_id: UUID
) -> int:
    ttl = await r.ttl(_cooldown_key(requester_id, addressee_id))
    return max(0, ttl)


@redis_circuit_breaker.decorator(fallback=False)
@translate_cache_errors
async def clear_cooldown(
        r: aioredis.Redis, requester_id: UUID, addressee_id: UUID
) -> bool:
    result = await r.delete(_cooldown_key(requester_id, addressee_id))
    return bool(result)
