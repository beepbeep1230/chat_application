from abc import ABC, abstractmethod
from typing import Any, assert_never, override

import redis.asyncio as aioredis
from fastapi import Request, Response
from redis.commands.core import AsyncScript

from app.api.deps import RateLimitScript, RedisClient
from app.core.errors.exceptions import RateLimitExceeded
from app.core.infra.token_bucket import RateLimitStatus, TokenBucket
from app.modules.auth.deps import CurrentUser


class RateLimiter(ABC):
    """
    FastAPI dependency that rate limits a route per client IP.

    Usage:
        login_limit = RateLimiter("login", capacity=5, refill_rate=1, refill_interval=12)

        @router.post("/login", dependencies=[Depends(login_limit)])

    Response headers:
        RateLimit-Limit:     Bucket capacity (max burst size).
        RateLimit-Remaining: Tokens left after this request.
        RateLimit-Reset:     Whole seconds (rounded up) until the next refill
                             adds tokens, i.e. time until the NEXT token, not
                             until the bucket is full. Delta seconds, not a
                             Unix timestamp (IETF RateLimit-Reset semantics).
        Retry-After:         Only on 429; same value as RateLimit-Reset, min 1.

    When Redis is unavailable (circuit breaker open) the request is allowed
    and no rate-limit headers are sent (fail open).
    """

    def __init__(
        self,
        scope: str,
        capacity: int,
        refill_rate: int,
        refill_interval: float,
    ):
        self.scope = scope
        self.capacity = capacity
        self.bucket = TokenBucket(
            capacity=capacity,
            refill_rate=refill_rate,
            refill_interval=refill_interval,
        )

    # Headers are lost if a route returns a Response itself.
    # The headers you set on the injected response are only added when the route returns plain data.
    #  If a route returns a JSONResponse (or similar),
    #  the RateLimit-* headers disappear on success. 429s aren't affected.

    @abstractmethod
    async def __call__(self, *args: Any, **kwargs: Any) -> None: ...

    async def _check(
        self, script: AsyncScript, redis: aioredis.Redis, key: str
    ) -> dict[str, str]:
        allowed, remaining, reset_in = await self.bucket.allow(
            script, redis, f"ratelimit:{key}"
        )

        headers_dict = {
            "RateLimit-Limit": str(self.capacity),
            "RateLimit-Remaining": str(remaining),
            "RateLimit-Reset": str(reset_in),
        }
        match allowed:
            case RateLimitStatus.EXCEEDED:
                raise RateLimitExceeded(max(1, reset_in), headers_dict)

            case RateLimitStatus.ALLOWED:
                return headers_dict

            case RateLimitStatus.DOWN:
                return {}

            case _:
                assert_never(allowed)


class IPRateLimiter(RateLimiter):
    @override
    async def __call__(
        self,
        request: Request,
        response: Response,
        redis: RedisClient,
        script: RateLimitScript,
    ) -> None:
        if request.client is None:
            return
        key = f"{self.scope}:ip:{request.client.host}"
        header_dict = await self._check(script, redis, key)
        response.headers.update(header_dict)


class UserRateLimiter(RateLimiter):
    @override
    async def __call__(
        self,
        request: Request,
        response: Response,
        redis: RedisClient,
        script: RateLimitScript,
        user: CurrentUser,
    ) -> None:
        key = f"{self.scope}:user_id:{user.uuid}"
        header_dict = await self._check(script, redis, key)
        response.headers.update(header_dict)
