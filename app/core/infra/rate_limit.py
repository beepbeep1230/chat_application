import asyncio
import time


class TokenBucket:
    def __init__(self, max_tokens: int, refill_rate: int, interval: float):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.interval = interval

        self.tokens = max_tokens
        self.refilled_at = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.refilled_at

        if elapsed >= self.interval:
            num_refills = int(elapsed // self.interval)
            self.tokens = min(
                self.max_tokens, self.tokens + num_refills * self.refill_rate
            )
            # Advance the timestamp by the number of full intervals consumed,
            # not to `now`, so partial intervals aren't lost.
            self.refilled_at += num_refills * self.interval

    async def allow_request(self, token: int = 1) -> bool:
        async with self._lock:
            self._refill()
            if self.tokens >= token:
                self.tokens -= token
                return True
            return False

    async def get_remaining(self):
        async with self._lock:
            self._refill()
            return self.tokens

    async def get_reset_time(self) -> float:
        async with self._lock:
            self._refill()
            return self.refilled_at + self.interval


class RateLimiterStore:
    def __init__(self, max_tokens: int, refill_rate: int, interval: float):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.interval = interval
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def get_bucket(self, key: str) -> TokenBucket:
        async with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(
                    max_tokens=self.max_tokens,
                    refill_rate=self.refill_rate,
                    interval=self.interval,
                )
            return self._buckets[key]
