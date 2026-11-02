"""
Token Bucket Rate Limiter

A Redis-based token bucket rate limiter implementation using Lua scripts
for atomic operations.

The token bucket algorithm allows requests at a controlled rate by maintaining
a bucket of tokens that refills over time. Each request consumes a token, and
requests are denied when the bucket is empty.
"""

import math
from enum import StrEnum

import redis.asyncio as aioredis
from redis.commands.core import AsyncScript

from app.core.errors.translators import translate_cache_errors
from app.core.infra.circuit_breaker import redis_circuit_breaker

# Lua script for atomic token bucket operations
TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local refill_interval = tonumber(ARGV[3])
local now_string = redis.call('TIME')
local now = tonumber(now_string[1]) + tonumber(now_string[2]) / 1000000

-- Get current state or initialize
local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

-- Initialize if this is the first request
if tokens == nil then
    tokens = capacity
    last_refill = now
end

-- Calculate token refill
local time_passed = now - last_refill
local refills = math.floor(time_passed / refill_interval)

if refills > 0 then
    tokens = math.min(capacity, tokens + (refills * refill_rate))
    last_refill = last_refill + (refills * refill_interval)
end

-- Try to consume a token
local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

local reset_at = last_refill + refill_interval

-- Seconds until the next refill adds tokens. Computed on every request:
-- when allowed it tells the client when more capacity arrives, and when
-- denied it is exactly how long the client must wait (Retry-After).
local reset_in = math.max(0, reset_at - now)

-- Update state
redis.call('HSET', key, 'tokens', tokens, 'last_refill', last_refill)
redis.call('PEXPIRE', key, math.ceil(capacity / refill_rate * refill_interval * 1000))

-- Return: allowed (1 or 0), remaining tokens, reset_in in milliseconds
return {allowed, tokens, math.ceil(reset_in * 1000)}
"""


class RateLimitStatus(StrEnum):
    ALLOWED = "allowed"
    EXCEEDED = "exceeded"
    DOWN = "down"


class TokenBucket:
    """
    Token bucket rate limiter using Redis for distributed rate limiting.

    The token bucket maintains a fixed capacity of tokens that refill at a
    constant rate. Each request consumes one token. When the bucket is empty,
    requests are denied until tokens refill.

    Holds only the bucket parameters, so one instance can be built per limiter
    at import time. The script and Redis client are passed on each call: the
    script is registered in lifespan_redis, after the pool exists.

    Args:
        capacity: Maximum number of tokens in the bucket (default: 10)
        refill_rate: Number of tokens added per refill interval (default: 1)
        refill_interval: Time in seconds between refills (default: 1.0)
    """

    def __init__(
        self,
        capacity: int = 10,
        refill_rate: int = 1,
        refill_interval: float = 1.0,
    ):
        """Initialize the token bucket rate limiter."""
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.refill_interval = refill_interval

    @redis_circuit_breaker.decorator(fallback=(RateLimitStatus.DOWN, 0, 0))
    @translate_cache_errors
    async def allow(
        self, script: AsyncScript, redis: aioredis.Redis, key: str
    ) -> tuple[RateLimitStatus, int, int]:
        """
        Check if a request should be allowed for the given key.

        Args:
            script: The token bucket script registered at startup.
            redis: Redis client of the current request.
            key: The rate limit key (e.g., 'user:123', 'api:endpoint:xyz')

        Returns:
            A tuple of (status, remaining_tokens, reset_in):
                - status: ALLOWED, EXCEEDED, or DOWN (Redis unavailable)
                - remaining_tokens: Number of tokens remaining in the bucket
                - reset_in: Whole seconds (rounded up) until the next refill
                  adds tokens. This is "time until the NEXT token", not
                  "time until the bucket is full again". When status is
                  EXCEEDED it is also the Retry-After value.

        Example:
            >>> status, remaining, reset_in = await bucket.allow(
            ...     script, redis, 'ratelimit:login:1.2.3.4'
            ... )
        """
        result = await script(
            keys=[key],
            args=[self.capacity, self.refill_rate, self.refill_interval],
            client=redis,
        )
        allowed = (
            RateLimitStatus.ALLOWED if bool(result[0]) else RateLimitStatus.EXCEEDED
        )
        remaining = int(result[1])
        reset_in = math.ceil(result[2] / 1000)

        return (
            allowed,
            remaining,
            reset_in,
        )

    @redis_circuit_breaker.decorator()
    @translate_cache_errors
    async def reset(self, redis: aioredis.Redis, key: str):
        await redis.delete(key)
