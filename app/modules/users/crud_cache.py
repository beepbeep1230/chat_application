from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as aioredis

from app.core.circuit_breaker import redis_circuit_breaker
from app.core.exception_handlers import translate_cache_errors
from app.core.logging import logger  # LOGGING: Import logger
from app.modules.users.models import UserRefreshToken

SESSION_KEY = "auth:session:{sid}"


def _session_key(session_id) -> str:
    return SESSION_KEY.format(sid=session_id)


@redis_circuit_breaker.decorator()
@translate_cache_errors
async def set_session(r: aioredis.Redis, session: UserRefreshToken) -> None:
    ttl = int((session.expires_at - datetime.now(UTC)).total_seconds())
    if ttl <= 0:
        logger.debug(
            "session_cache_skipped_negative_ttl", sid=str(session.sid), ttl=ttl
        )
        return
    key = _session_key(session.sid)
    async with r.pipeline(transaction=True) as pipe:
        pipe.hset(
            key, mapping={"user_id": str(session.user_id), "jti": str(session.jti)}
        )
        pipe.expire(key, ttl)
        await pipe.execute()
    # LOGGING: Log successful cache set (id/sid only, no sensitive data)
    logger.debug("session_cached", sid=str(session.sid), ttl=ttl)


# LOGGING: Each cache op wraps Redis errors via translate_cache_errors -> CacheError.
# The exception handler in main.py (cache_error_handler) will log these with context,
# so we only need lightweight debug traces here for success paths.
@redis_circuit_breaker.decorator()
@translate_cache_errors
async def revoke_session_cache(r: aioredis.Redis, session_id: str) -> None:
    await r.delete(_session_key(session_id))
    logger.debug("session_cache_revoked", sid=str(session_id))


@redis_circuit_breaker.decorator()
@translate_cache_errors
async def revoke_session_all_cache(
    r: aioredis.Redis, session_id_list: list[UUID]
) -> None:
    keys = [_session_key(str(session_id)) for session_id in session_id_list]
    if not keys:
        return
    await r.delete(*keys)
    logger.debug("sessions_cache_revoked_all", count=len(keys))


@redis_circuit_breaker.decorator()
@translate_cache_errors
async def check_session_is_active(r: aioredis.Redis, session_id: str) -> bool:
    active = bool(await r.exists(_session_key(session_id)))
    if not active:
        logger.warning("session_inactive_or_revoked", sid=str(session_id))
    return active
