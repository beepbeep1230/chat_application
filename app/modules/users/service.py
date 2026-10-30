from app.core.errors.exceptions import EmptyUpdate, UserNotFound
from app.modules.users import crud, schemas
from sqlalchemy.ext.asyncio import AsyncSession


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # Profile
    async def update_profile(
        self, username: str, user_profile_data: dict[str, str | None] | None
    ) -> schemas.UserProfileResponse:
        if not user_profile_data:
            raise EmptyUpdate()
        user_profile = await crud.update_user_profile(
            self.db, username=username, user_profile_data=user_profile_data
        )
        if user_profile is None:
            raise UserNotFound()
        return schemas.UserProfileResponse.model_validate(user_profile)
