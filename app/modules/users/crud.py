from typing import Any
from uuid import UUID

from app.core.errors.translators import translate_db_errors
from app.modules.users.models import UserAccount, UserProfile
from sqlalchemy import Row, select, update
from sqlalchemy.ext.asyncio import AsyncSession


# Profile
@translate_db_errors
async def update_user_profile(
        db: AsyncSession, username: str, user_profile_data: dict[str, str | None]
) -> UserProfile | None:
    stmt = (
        update(UserProfile)
        .where(UserProfile.username == username)
        .values(**user_profile_data)
        .returning(UserProfile)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@translate_db_errors
async def select_user_brief(db: AsyncSession, user_id: UUID) -> Row[Any] | None:
    stmt = (
        select(
            UserAccount.uuid.label("user_id"),
            UserAccount.username,
            UserProfile.display_name,
            UserProfile.avatar_url,
        )
        .select_from(UserAccount)
        .outerjoin(UserProfile, UserProfile.username == UserAccount.username)
        .where(UserAccount.uuid == user_id)
    )
    return (await db.execute(stmt)).one_or_none()
