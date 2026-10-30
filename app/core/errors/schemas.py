from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class Violation(BaseModel):
    field: str | None = None
    message: str


class ProblemDetail(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True, alias_generator=to_camel, validate_by_name=True
    )

    type: str
    status: int
    title: str
    detail: str
    instance: str | None = None
    trace_id: str | None = None
    code: str
    violations: list[Violation] | None = None


# Base of every problem ``type`` URI (RFC 9457 section 3.1.1).
# ".example" is a reserved TLD (RFC 2606): swap in your real domain before
# going public, and never change a published URI after that.
PROBLEM_TYPE_BASE = "https://api.chat-app.example/problems"


class ErrorCode(StrEnum):
    """Stable, machine-readable error codes (the ``code`` member of ProblemDetail).

    Grouped by the HTTP status each one is sent with. Clients branch on these,
    never on ``detail``, so once published a value must not be renamed.
    """

    # 400 Bad Request
    SELF_REQUEST = "SELF_REQUEST"  # SelfRequestError
    INVALID_CURSOR = "INVALID_CURSOR"  # InvalidCursor
    EMPTY_UPDATE = "EMPTY_UPDATE"  # PATCH /users/me with an empty body
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"  # IntegrityError, sqlstate 23514
    BAD_REQUEST = "BAD_REQUEST"  # Starlette HTTPException(400) fallback
    VALIDATION_ERROR = "VALIDATION_ERROR"  # RequestValidationError

    # 401 Unauthorized  (send header WWW-Authenticate: Bearer)
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    INVALID_TOKEN = "INVALID_TOKEN"  # InvalidToken
    TOKEN_EXPIRED = "TOKEN_EXPIRED"  # ExpiredToken -> client should call /auth/refresh
    UNAUTHENTICATED = "UNAUTHENTICATED"  # Unauthenticated, missing bearer token
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"  # InvalidCredentials (login)

    # 403 Forbidden
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"  # EmailNotVerified
    REQUEST_NOT_ALLOWED = "REQUEST_NOT_ALLOWED"  # FriendRequestNotAllowedError (block)

    # 404 Not Found
    USER_NOT_FOUND = "USER_NOT_FOUND"  # UserNotFound, UserRequestedNotFound
    REQUEST_NOT_FOUND = "REQUEST_NOT_FOUND"  # RequestNotFound
    NOT_FRIENDS = "NOT_FRIENDS"  # NotFriendsError
    NOT_BLOCKED = "NOT_BLOCKED"  # BlockRecordNotFound
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"  # Starlette 404 (unknown URL)

    # 405 Method Not Allowed
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"  # Starlette 405

    # 409 Conflict
    USER_EXISTS = "USER_EXISTS"  # UserExists
    ALREADY_VERIFIED = "ALREADY_VERIFIED"  # verify-email on an active account
    ALREADY_FRIENDS = "ALREADY_FRIENDS"  # FriendsAlreadyError
    REQUEST_ALREADY_EXISTS = "REQUEST_ALREADY_EXISTS"  # RequestedAlreadyError
    ALREADY_BLOCKED = "ALREADY_BLOCKED"  # BlockedAlready
    CONFLICT = "CONFLICT"  # IntegrityError, sqlstate 23505 / 23503

    # 429 Too Many Requests  (send header Retry-After)
    REQUEST_COOLDOWN = "REQUEST_COOLDOWN"  # CoolDownError
    RATE_LIMITED = "RATE_LIMITED"  # future rate limiter

    # 500 Internal Server Error
    INTERNAL_ERROR = (
        "INTERNAL_ERROR"  # AppError base, unhandled Exception, other SQLAlchemyError
    )

    # 503 Service Unavailable
    DATABASE_UNAVAILABLE = (
        "DATABASE_UNAVAILABLE"  # DatabaseError (OperationalError, pool timeout)
    )
    CACHE_UNAVAILABLE = "CACHE_UNAVAILABLE"  # CacheError and subclasses

    # Any other Starlette HTTPException status
    HTTP_ERROR = "HTTP_ERROR"
