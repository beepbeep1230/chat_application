from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

username = settings.postgres_username.get_secret_value()
password = settings.postgres_password.get_secret_value()
host = settings.postgres_host
port = settings.postgres_port
db_name = settings.db_name
echo = False

DB_URL = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{db_name}"

async_engine = create_async_engine(
    DB_URL,
    echo=echo,
    pool_size=10,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
)

async_session_local = async_sessionmaker(
    bind=async_engine, expire_on_commit=False, class_=AsyncSession
)


@asynccontextmanager
async def lifespan_database(app: FastAPI):
    yield
    await async_engine.dispose()


class Base(DeclarativeBase):
    """Declarative base shared by every SQLAlchemy model.

    Alembic autogenerate reads ``Base.metadata`` (see ``alembic/env.py``), so
    each feature module's models must be imported before migrations run.
    """
