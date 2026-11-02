from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        url = request.url.path

        logger.info(f"Request: {method} {url} from {client_ip}")

        # Process the request
        response = await call_next(request)

        # Log response details
        status_code = response.status_code
        logger.info(f"Response: {method} {url} returned {status_code} to {client_ip}")

        return response
