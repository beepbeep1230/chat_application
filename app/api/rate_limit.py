import hashlib
from collections.abc import AsyncGenerator
from typing import Annotated, assert_never

import redis.asyncio as aioredis
from fastapi import Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from redis.commands.core import AsyncScript

from app.api.deps import RateLimitScript, RedisClient
from app.core.errors.exceptions import RateLimitExceeded
from app.core.infra.token_bucket import RateLimitStatus, TokenBucket
from app.modules.auth.deps import CurrentUser


class RateLimiter:
    """
    Base class for token bucket rate limiters used as FastAPI dependencies.

    Not used directly. Subclasses decide WHAT is counted (the key) and
    implement __call__; this class holds the bucket and the Redis logic.

    One instance = one bucket per key. Attaching the same instance to several
    routes makes them share one budget; give each action its own instance
    (and scope) when they should be counted separately.

    Args:
        scope: Name of the action being limited (e.g. "login",
            "friend_request_send"). Part of every Redis key.
        capacity: Max requests in a row (burst size).
        refill_rate: Tokens added back every refill_interval.
        refill_interval: Seconds between refills. Long-run speed is
            refill_rate / refill_interval requests per second.

    Redis key:
        ratelimit:{scope}:{subclass part}, e.g. ratelimit:login:ip:1.2.3.4.
        Expires on its own once the bucket would be full again.

    Response headers (set on success by IPRateLimiter and UserRateLimiter):
        RateLimit-Limit:     Bucket capacity (max burst size).
        RateLimit-Remaining: Tokens left after this request.
        RateLimit-Reset:     Whole seconds (rounded up) until the next refill
                             adds tokens, i.e. time until the NEXT token, not
                             until the bucket is full. Delta seconds, not a
                             Unix timestamp (IETF RateLimit-Reset semantics).
        Retry-After:         Only on 429; same value as RateLimit-Reset, min 1.

    Success headers are only sent when the route returns plain data. If a
    route returns a Response object itself (e.g. JSONResponse), the headers
    set on the injected response are dropped. 429s are not affected.

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

    # async def __call__(self, *args: Any, **kwargs: Any) -> None | AsyncGenerator: ...

    def _redis_key(self, key: str) -> str:
        return f"ratelimit:{key}"

    async def _reset(self, redis: aioredis.Redis, key: str) -> None:
        await self.bucket.reset(redis, self._redis_key(key))

    async def _check(
        self, script: AsyncScript, redis: aioredis.Redis, key: str
    ) -> dict[str, str]:
        allowed, remaining, reset_in = await self.bucket.allow(
            script, redis, self._redis_key(key)
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
    """
    Counts every request per client IP. For routes without a logged-in user.

    Key: ratelimit:{scope}:ip:{ip}

    Many users can share one public IP (home Wi-Fi, office, mobile carrier),
    so keep limits loose for cheap routes. Behind a reverse proxy, uvicorn
    must run with --proxy-headers, or every client shares the proxy's IP.
    Requests without a client address are not limited.

    Usage:
        register_ip_limit = IPRateLimiter(
            "register", capacity=5, refill_rate=1, refill_interval=600
        )

        @router.post("/register", dependencies=[Depends(register_ip_limit)])
    """

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
    """
    Counts every request per logged-in user. For authenticated routes.

    Key: ratelimit:{scope}:user_id:{uuid}

    Depends on CurrentUser, so the access token is checked before the limit:
    an invalid token gets 401 and uses no token. CurrentUser is cached per
    request, so the route's own CurrentUser does not authenticate again.

    Usage:
        friend_request_send_limit = UserRateLimiter(
            "friend_request_send", capacity=20, refill_rate=1, refill_interval=180
        )

        @router.post("/friends/requests", dependencies=[Depends(friend_request_send_limit)])
    """

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


class LoginPairRateLimiter(RateLimiter):
    """
    Counts FAILED logins per (identifier, client IP) pair.

    Key: ratelimit:{scope}:fail:{sha256(identifier)[:16]}:{ip}
    The identifier is stripped and lowercased first (CITEXT makes Alice ==
    alice) and hashed so no emails are stored in Redis.

    Flow (yield dependency):
        1. Before the route: take a token. Empty bucket -> 429, the route
           (user lookup + argon2) never runs.
        2. yield: the login route runs.
        3. Route raised (e.g. InvalidCredentials): the error leaves at the
           yield, the reset below is skipped, the token stays used = 1 failure.
        4. Route succeeded: the pair bucket is deleted.

    Being per pair, an attacker at IP X cannot lock out the real user at IP Y.
    No headers on success, so an attacker can't read how many guesses are
    left; on 429 the headers come with RateLimitExceeded.

    Must be attached with scope="function" (RedisClient is function-scoped,
    FastAPI refuses to start otherwise), and after the IP limiter so a blocked
    IP does not use pair tokens.

    Usage:
        @router.post(
            "/login",
            dependencies=[
                Depends(login_ip_limit),
                Depends(login_pair_limit, scope="function"),
            ],
        )
    """

    async def __call__(
        self,
        request: Request,
        redis: RedisClient,
        script: RateLimitScript,
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    ) -> AsyncGenerator[None]:
        if request.client is None:
            yield
            return

        identifier = form_data.username.strip().lower()
        hashed_identifier = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:16]
        key = f"{self.scope}:fail:{hashed_identifier}:{request.client.host}"
        await self._check(script, redis, key)
        yield
        await self._reset(redis, key)
