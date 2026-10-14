from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as aioredis

from app.core.exception_handlers import best_effort_cache, translate_cache_errors
from app.modules.users.models import UserRefreshToken

SESSION_KEY = "auth:session:{sid}"


def _session_key(session_id) -> str:
    return SESSION_KEY.format(sid=session_id)


@best_effort_cache()
@translate_cache_errors
async def set_session(r: aioredis.Redis, session: UserRefreshToken) -> None:
    ttl = int((session.expires_at - datetime.now(UTC)).total_seconds())
    if ttl <= 0:
        return
    key = _session_key(session.sid)
    async with r.pipeline(transaction=True) as pipe:
        pipe.hset(
            key, mapping={"user_id": str(session.user_id), "jti": str(session.jti)}
        )
        pipe.expire(key, ttl)
        await pipe.execute()


@best_effort_cache()
@translate_cache_errors
async def revoke_session(r: aioredis.Redis, session_id: str) -> None:
    await r.delete(_session_key(session_id))


@best_effort_cache()
@translate_cache_errors
async def revoke_session_all(r: aioredis.Redis, session_id_list: list[UUID]) -> None:
    keys = [_session_key(str(session_id)) for session_id in session_id_list]
    if not keys:
        return
    await r.delete(*keys)


@best_effort_cache(False)
@translate_cache_errors
async def check_session_is_active(r: aioredis.Redis, session_id: str) -> bool:
    active = bool(await r.exists(_session_key(session_id)))
    return active
