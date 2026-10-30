from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession
from app.modules.auth.deps import CurrentUser
from app.modules.users.schemas import UserProfileResponse
from app.modules.users.service import UserService


async def get_user_service(db: DbSession) -> UserService:
    return UserService(db=db)


UserServiceHandler = Annotated[UserService, Depends(get_user_service)]


async def get_profile_dependency(
    current_user: CurrentUser,
) -> UserProfileResponse:
    return UserProfileResponse.model_validate(current_user.profile)


UserProfileDependency = Annotated[UserProfileResponse, Depends(get_profile_dependency)]
