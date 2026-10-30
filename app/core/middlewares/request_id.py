# LOGGING: Request ID middleware for correlation across requests
import uuid
from collections.abc import Callable
from contextvars import ContextVar

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = str(uuid.uuid4())
        token = request_id_ctx.set(rid)

        with logger.contextualize(request_id=rid):
            client_ip = request.client.host if request.client else "unknown"
            method = request.method
            url = request.url.path

            logger.info(
                "request_start",
                method=method,
                path=url,
                client_ip=client_ip,
            )
            response = await call_next(request)
            response.headers["ChatApp-Request-ID"] = rid
            logger.info(
                "request_end",
                status_code=response.status_code,
                method=method,
                path=url,
            )
            request_id_ctx.reset(token)
            return response
