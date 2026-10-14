from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.cache import lifespan_redis
from app.core.database import lifespan_database
from app.core.exception_handlers import (
    cache_error_handler,
    database_error_handler,
    email_not_verified_handler,
    unauthorized_handler,
    user_exists_handler,
    user_not_found_handler,
)
from app.core.exceptions import (
    AuthError,
    CacheError,
    DatabaseError,
    EmailNotVerified,
    ExpiredToken,
    InvalidCredentials,
    InvalidToken,
    Unauthenticated,
    UserExists,
    UserNotFound,
)
from app.core.lifespan import combine_lifespans

app = FastAPI(lifespan=combine_lifespans(lifespan_database, lifespan_redis))


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000"],
    allow_credentials=True,  # COOKIE
    allow_methods=["GET", "POST", "PATCH", "DELETE"],  # CRUD METHODS
    allow_headers=["Content-type", "Authorization"],
)


app.include_router(api_router)
app.add_exception_handler(InvalidToken, unauthorized_handler)
app.add_exception_handler(ExpiredToken, unauthorized_handler)
app.add_exception_handler(Unauthenticated, unauthorized_handler)
app.add_exception_handler(InvalidCredentials, unauthorized_handler)
app.add_exception_handler(AuthError, unauthorized_handler)
app.add_exception_handler(UserNotFound, user_not_found_handler)
app.add_exception_handler(UserExists, user_exists_handler)
app.add_exception_handler(EmailNotVerified, email_not_verified_handler)
app.add_exception_handler(DatabaseError, database_error_handler)
app.add_exception_handler(CacheError, cache_error_handler)
