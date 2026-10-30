from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends

from app.api.deps import DbSession, RedisClient
from app.core.security import oauth2_scheme
from app.modules.auth.service import AuthService
from app.modules.users.models import UserAccount


async def get_auth_service(
    redis_client: RedisClient,
    db: DbSession,
) -> AuthService:
    return AuthService(redis=redis_client, db=db)


AuthServiceHandler = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    jwt_token: Annotated[str, Depends(oauth2_scheme)],
    service: AuthServiceHandler,
) -> UserAccount:
    return await service.get_current_user(jwt_token)


CurrentUser = Annotated[UserAccount, Depends(get_current_user)]


RefreshTokenCookie = Annotated[str, Cookie(alias="refreshToken")]
