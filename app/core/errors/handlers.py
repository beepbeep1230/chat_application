from http import HTTPStatus

from app.core.errors.exceptions import AppError
from app.core.errors.schemas import (
    PROBLEM_TYPE_BASE,
    ErrorCode,
    ProblemDetail,
    Violation,
)
from app.core.logging import logger
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException


def _map_loc(loc: tuple[int | str, ...]) -> str:
    parts: list[str] = []
    for p in loc:
        if p == "body":
            continue
        parts.append(str(p))
    return ".".join(parts)


def _title(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Error"


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> Response:

    violations = [
        Violation(
            field=_map_loc(e["loc"]), message=e["msg"].removeprefix("Value error, ")
        )
        for e in exc.errors()
    ]

    body = ProblemDetail(
        type=f"{PROBLEM_TYPE_BASE}/validation-error",
        status=400,
        title="Bad Request",
        detail="Input Data Validation Error.",
        instance=request.url.path,
        code=ErrorCode.VALIDATION_ERROR,
        trace_id=getattr(request.state, "trace_id", None),
        violations=violations,
    )

    return Response(
        content=body.model_dump_json(indent=2, exclude_none=True),
        status_code=400,
        media_type="application/problem+json",
    )


async def app_error_handler(request: Request, exc: AppError) -> Response:
    headers: dict[str, str] = {}
    body = ProblemDetail(
        type=exc.type,
        status=exc.status,
        title=_title(exc.status),
        detail=exc.detail,
        instance=request.url.path,
        code=exc.code,
        trace_id=getattr(request.state, "trace_id", None),
    )
    if exc.status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)

    return Response(
        content=body.model_dump_json(indent=2, exclude_none=True),
        status_code=exc.status,
        media_type="application/problem+json",
        headers=headers,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> Response:
    type = None
    match exc.status_code:
        case 400:
            code = ErrorCode.BAD_REQUEST
        case 401:
            code = ErrorCode.UNAUTHENTICATED
        case 404:
            code = ErrorCode.ROUTE_NOT_FOUND
        case 405:
            code = ErrorCode.METHOD_NOT_ALLOWED
        case _:
            code = ErrorCode.HTTP_ERROR
            type = "about:blank"
    body = ProblemDetail(
        type=f"{PROBLEM_TYPE_BASE}/{code.lower().replace('_', '-')}"
        if type is None
        else type,
        status=exc.status_code,
        title=_title(exc.status_code),
        detail=str(exc.detail) or "HTTP Error",
        instance=request.url.path,
        code=code,
        trace_id=getattr(request.state, "trace_id", None),
    )
    return Response(
        content=body.model_dump_json(indent=2, exclude_none=True),
        status_code=exc.status_code,
        media_type="application/problem+json",
        headers=exc.headers,
    )


async def generic_error_handler(request: Request, exc: Exception) -> Response:
    body = ProblemDetail(
        type=f"{PROBLEM_TYPE_BASE}/internal-error",
        status=500,
        title="Internal Server Error",
        detail="Internal server error",
        instance=request.url.path,
        code=ErrorCode.INTERNAL_ERROR,
        trace_id=getattr(request.state, "trace_id", None),
    )
    logger.opt(exception=exc).error(
        "unhandled_error", method=request.method, path=request.url.path
    )
    return Response(
        content=body.model_dump_json(indent=2, exclude_none=True),
        status_code=500,
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    # Starlette types every handler as (Request, Exception); a handler for a
    # subclass is correct at runtime, so the narrower signatures are ignored.
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,  # pyright: ignore[reportArgumentType]
    )
    app.add_exception_handler(AppError, app_error_handler)  # pyright: ignore[reportArgumentType]
    app.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,  # pyright: ignore[reportArgumentType]
    )
    app.add_exception_handler(Exception, generic_error_handler)
