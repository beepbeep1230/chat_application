# LOGGING: Initialize logging at startup
from app.core.logging import setup_logging

setup_logging(level="INFO")

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.errors.handlers import register_exception_handlers
from app.core.infra.cache import lifespan_redis
from app.core.infra.database import lifespan_database
from app.core.infra.lifespan import combine_lifespans

app = FastAPI(lifespan=combine_lifespans(lifespan_database, lifespan_redis))


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000"],
    allow_credentials=True,  # COOKIE
    allow_methods=["GET", "POST", "PATCH", "DELETE"],  # CRUD METHODS
    allow_headers=["Content-type", "Authorization"],
    expose_headers=[
        "RateLimit-Limit",
        "RateLimit-Remaining",
        "RateLimit-Reset",
        "Retry-After",
    ],
)

app.include_router(api_router)
register_exception_handlers(app)

if __name__ == "__main__":
    uvicorn.run(
        app="app.main:app",
        host="127.0.0.1",
        port=8000,
        log_config=None,
        reload=True,
        reload_dirs="app",
    )
