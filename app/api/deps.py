from typing import Annotated
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Cookie, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import async_session_local
from app.core.exception_handlers import translate_db_errors
from app.core.exceptions import InvalidToken, Unauthenticated
from app.core.security import oauth2_scheme, verify_jwt_token
from app.modules.users.crud import get_refresh_token
from app.modules.users.crud_cache import check_session_is_active, set_session
from app.modules.users.models import AccountStatus, UserAccount
from app.modules.users.schemas import UserProfileResponse


async def get_db():
    async with async_session_local() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis(request: Request):
    async with aioredis.Redis(
        connection_pool=request.app.state.redis_pool
    ) as redis_client:
        yield redis_client


@translate_db_errors
async def get_current_user(
    jwt_token: Annotated[str, Depends(oauth2_scheme)],
    redis_client: RedisClient,
    db: DbSession,
) -> UserAccount:
    payload = verify_jwt_token(jwt_token=jwt_token)
    if payload.type != "access":
        raise InvalidToken()

    active = await check_session_is_active(r=redis_client, session_id=payload.sid)
    if not active:
        refresh_token_record = await get_refresh_token(db=db, session_id=payload.sid)
        await set_session(r=redis_client, session=refresh_token_record)

    stmt = (
        select(UserAccount)
        .where(UserAccount.uuid == UUID(payload.sub))
        .where(UserAccount.status == AccountStatus.ACTIVE)
        .options(joinedload(UserAccount.profile))
    )
    result = await db.execute(stmt)
    current_user = result.scalar_one_or_none()
    if current_user is None:
        raise Unauthenticated()
    return current_user


async def get_profile_dependency(
    current_user: CurrentUser,
) -> UserProfileResponse:
    return UserProfileResponse.model_validate(current_user.profile)


DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserAccount, Depends(get_current_user)]
UserProfileDependency = Annotated[UserProfileResponse, Depends(get_profile_dependency)]
RefreshTokenCookie = Annotated[str, Cookie(alias="refreshToken")]
RedisClient = Annotated[aioredis.Redis, Depends(get_redis)]
