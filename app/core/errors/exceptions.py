from app.core.errors.schemas import PROBLEM_TYPE_BASE, ErrorCode
from fastapi import status as status_code


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        detail: str = "Internal Server Error.",
        status: int = 500,
        type: str = f"{PROBLEM_TYPE_BASE}/internal-error",
        retry_after: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status
        self.type = type
        self.retry_after = retry_after


class DatabaseError(AppError):
    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__(
            code=ErrorCode.DATABASE_UNAVAILABLE,
            detail="Database Not Available.",
            status=status_code.HTTP_503_SERVICE_UNAVAILABLE,
            type=f"{PROBLEM_TYPE_BASE}/database-unavailable",
            retry_after=retry_after,
        )


class DomainError(AppError):
    def __init__(
        self,
        code: ErrorCode,
        detail: str,
        status: int = 400,
        type: str = f"{PROBLEM_TYPE_BASE}/domain-error",
    ) -> None:
        super().__init__(code, detail, status, type)


class ConflictError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.CONFLICT,
            detail="Resource Conflict.",
            status=status_code.HTTP_409_CONFLICT,
            type=f"{PROBLEM_TYPE_BASE}/conflict",
        )


class ConstraintViolation(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.CONSTRAINT_VIOLATION,
            detail="Constraint Violation.",
            status=status_code.HTTP_400_BAD_REQUEST,
            type=f"{PROBLEM_TYPE_BASE}/constraint-violation",
        )


# Authentication Errors
class AuthError(DomainError):
    """Parent of all errors related to Authentication"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.AUTHENTICATION_ERROR,
        detail: str = "Authentication Error.",
        status: int = status_code.HTTP_401_UNAUTHORIZED,
        type: str = f"{PROBLEM_TYPE_BASE}/authentication-error",
    ) -> None:

        super().__init__(code, detail, status, type)


class InvalidToken(AuthError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.INVALID_TOKEN,
            detail="Invalid Token.",
            type=f"{PROBLEM_TYPE_BASE}/invalid-token",
        )


class ExpiredToken(AuthError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.TOKEN_EXPIRED,
            detail="Token Expired.",
            type=f"{PROBLEM_TYPE_BASE}/token-expired",
        )


class Unauthenticated(AuthError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.UNAUTHENTICATED,
            detail="Unauthenticated.",
            type=f"{PROBLEM_TYPE_BASE}/unauthenticated",
        )


class EmailNotVerified(AuthError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.EMAIL_NOT_VERIFIED,
            detail="Email Not Verified.",
            status=status_code.HTTP_403_FORBIDDEN,
            type=f"{PROBLEM_TYPE_BASE}/email-not-verified",
        )


class AlreadyVerified(AuthError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.ALREADY_VERIFIED,
            detail="Already Verified.",
            status=status_code.HTTP_409_CONFLICT,
            type=f"{PROBLEM_TYPE_BASE}/already-verified",
        )


class InvalidCredentials(AuthError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.INVALID_CREDENTIALS,
            detail="Username Or Password Is Invalid.",
            type=f"{PROBLEM_TYPE_BASE}/invalid-credentials",
        )


class UserNotFound(AuthError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.USER_NOT_FOUND,
            detail="User Not Found.",
            status=status_code.HTTP_404_NOT_FOUND,
            type=f"{PROBLEM_TYPE_BASE}/user-not-found",
        )


class UserExists(AuthError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.USER_EXISTS,
            detail="User Exists.",
            status=status_code.HTTP_409_CONFLICT,
            type=f"{PROBLEM_TYPE_BASE}/user-exists",
        )


class EmptyUpdate(DomainError):
    def __init__(
        self,
        code: ErrorCode = ErrorCode.EMPTY_UPDATE,
        detail: str = "Empty Payload Not Allowed.",
        status: int = 400,
        type: str = f"{PROBLEM_TYPE_BASE}/empty-update",
    ) -> None:
        super().__init__(code, detail, status, type)


# Redis Errors
class CacheError(AppError):
    def __init__(
        self,
        code: ErrorCode = ErrorCode.CACHE_UNAVAILABLE,
        detail: str = "Cache Server Unavailable.",
        status: int = status_code.HTTP_503_SERVICE_UNAVAILABLE,
        type: str = f"{PROBLEM_TYPE_BASE}/cache-unavailable",
    ) -> None:
        super().__init__(code, detail, status, type)


class CacheConnectionError(CacheError):
    def __init__(self) -> None:
        super().__init__(detail="Cache Server Busy.")


class CacheServerError(CacheError):
    def __init__(self) -> None:
        super().__init__(detail="Cache Server Error.")


# Friend Request Errors
class FriendRequestError(DomainError):
    def __init__(
        self,
        code: ErrorCode = ErrorCode.BAD_REQUEST,
        detail: str = "Friend Request Error.",
        status: int = status_code.HTTP_400_BAD_REQUEST,
        type: str = f"{PROBLEM_TYPE_BASE}/friend-request-error",
    ) -> None:
        super().__init__(code, detail, status, type)


class FriendsAlreadyError(FriendRequestError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.ALREADY_FRIENDS,
            detail="Already Friends.",
            status=status_code.HTTP_409_CONFLICT,
            type=f"{PROBLEM_TYPE_BASE}/already-friends",
        )


class FriendRequestNotAllowedError(FriendRequestError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.REQUEST_NOT_ALLOWED,
            detail="Friend Request Not Allowed.",
            status=status_code.HTTP_403_FORBIDDEN,
            type=f"{PROBLEM_TYPE_BASE}/request-not-allowed",
        )


class SelfRequestError(FriendRequestError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.SELF_REQUEST,
            detail="Self Request Not Allowed.",
            status=status_code.HTTP_400_BAD_REQUEST,
            type=f"{PROBLEM_TYPE_BASE}/self-request",
        )


class RequestNotFound(FriendRequestError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.REQUEST_NOT_FOUND,
            detail="Request Not Found.",
            status=status_code.HTTP_404_NOT_FOUND,
            type=f"{PROBLEM_TYPE_BASE}/request-not-found",
        )


class RequestedAlreadyError(FriendRequestError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.REQUEST_ALREADY_EXISTS,
            detail="Already Requested.",
            status=status_code.HTTP_409_CONFLICT,
            type=f"{PROBLEM_TYPE_BASE}/request-already-exists",
        )


class CoolDownError(FriendRequestError):
    def __init__(self, cool_down: int) -> None:
        super().__init__(
            code=ErrorCode.REQUEST_COOLDOWN,
            detail=f"Retry After {cool_down}s.",
            status=status_code.HTTP_429_TOO_MANY_REQUESTS,
            type=f"{PROBLEM_TYPE_BASE}/request-cooldown",
        )
        self.retry_after = cool_down


class NotFriendsError(FriendRequestError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.NOT_FRIENDS,
            detail="Users Not Friends.",
            status=status_code.HTTP_404_NOT_FOUND,
            type=f"{PROBLEM_TYPE_BASE}/not-friends",
        )


class UserRequestedNotFound(FriendRequestError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.USER_NOT_FOUND,
            detail="User Requested Not Found.",
            status=status_code.HTTP_404_NOT_FOUND,
            type=f"{PROBLEM_TYPE_BASE}/user-not-found",
        )


class RelationError(DomainError):
    def __init__(
        self,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        detail: str = "Unexpected Failure With Users' Relation.",
        status: int = status_code.HTTP_500_INTERNAL_SERVER_ERROR,
        type: str = f"{PROBLEM_TYPE_BASE}/relation-error",
    ) -> None:
        super().__init__(code, detail, status, type)


class BlockedAlready(RelationError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.ALREADY_BLOCKED,
            detail="Already Blocked",
            status=status_code.HTTP_409_CONFLICT,
            type=f"{PROBLEM_TYPE_BASE}/already-blocked",
        )


class BlockRecordNotFound(RelationError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.NOT_BLOCKED,
            detail="Not Blocked.",
            status=status_code.HTTP_404_NOT_FOUND,
            type=f"{PROBLEM_TYPE_BASE}/not-blocked",
        )


class InvalidCursor(AppError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.INVALID_CURSOR,
            detail="Invalid Cursor.",
            status=status_code.HTTP_400_BAD_REQUEST,
            type=f"{PROBLEM_TYPE_BASE}/invalid-cursor",
        )


# Rate Limit
class RateLimitExceeded(AppError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            code=ErrorCode.RATE_LIMITED,
            detail="Too Many Requests.",
            status=status_code.HTTP_429_TOO_MANY_REQUESTS,
            type=f"{PROBLEM_TYPE_BASE}/rate-limited",
        )
        self.retry_after = retry_after


class IpMissingError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.RATE_LIMITED,
            detail="Too Many Requests.",
            status=status_code.HTTP_429_TOO_MANY_REQUESTS,
            type=f"{PROBLEM_TYPE_BASE}/rate-limited",
        )
