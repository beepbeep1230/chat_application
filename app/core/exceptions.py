class AppError(Exception):
    def __init__(
        self, message: str = "Service is unavailable", name: str = "SystemError"
    ):
        self.message = message
        self.name = name
        super().__init__(self.message, self.name)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.name = cls.__name__


class DatabaseError(AppError):
    def __init__(self, message="Database error"):
        super().__init__(message=message)


class AuthError(AppError):
    """Parent of all errors related to Authenication"""

    def __init__(self, message="AuthError"):
        super().__init__(message=message)


class InvalidToken(AuthError):
    def __init__(self, message="Token is invalid."):
        super().__init__(message=message)


class ExpiredToken(AuthError):
    def __init__(self, message="Token is expired."):
        super().__init__(message=message)


class Unauthenticated(AuthError):
    def __init__(self, message="Can not authenticate."):
        super().__init__(message=message)


class UserNotFound(AuthError):
    def __init__(self, message="User Not Found."):
        super().__init__(message=message)


class EmailNotVerified(AuthError):
    def __init__(self, message="Email not verified"):
        super().__init__(message=message)


class UserExists(AuthError):
    def __init__(self, message="User exists."):
        super().__init__(message=message)


class InvalidCredentials(AuthError):
    def __init__(self, message="Username or password is invalid."):
        super().__init__(message=message)


# Redis
class CacheError(AppError):
    def __init__(self, message="Cache server is unavailible."):
        super().__init__(message=message)


class CacheConnectionError(CacheError):
    def __init__(self, message="Cache server is busy."):
        super().__init__(message=message)


class CacheServerError(CacheError):
    def __init__(self, message="Cache server error."):
        super().__init__(message=message)
