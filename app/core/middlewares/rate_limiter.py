import math
import time

from app.core.errors.exceptions import RateLimitExceeded
from app.core.errors.handlers import app_error_handler
from app.core.infra.rate_limit import RateLimiterStore
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

rate_limiter = RateLimiterStore(max_tokens=10, refill_rate=1, interval=1.0)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = getattr(request.client, "host", "127.0.0.1")
        bucket = await rate_limiter.get_bucket(key=client_ip)

        if not await bucket.allow_request():
            retry_after = await bucket.get_reset_time() - time.monotonic()
            return await app_error_handler(
                request, RateLimitExceeded(math.ceil(retry_after))
            )

        response = await call_next(request)
        response.headers["ChatApp-RateLimit-Limit"] = str(bucket.max_tokens)
        response.headers["ChatApp-RateLimit-Remaining"] = str(
            await bucket.get_remaining()
        )
        response.headers["ChatApp-RateLimit-Reset"] = str(
            int(await bucket.get_reset_time())
        )
        return response
