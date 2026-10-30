from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from app.core.errors.translators import translate_db_errors
from app.core.security import JWTPayload
from app.modules.auth.models import UserRefreshToken
from app.modules.users.models import AccountStatus, UserAccount, UserProfile
from sqlalchemy import CursorResult, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


# Account
@translate_db_errors
async def select_user_by_email(db: AsyncSession, email: str) -> UserAccount | None:
    stmt = select(UserAccount).where(UserAccount.email == email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@translate_db_errors
async def check_user_existence(db: AsyncSession, email: str, username: str) -> bool:
    stmt = select(
        select(UserAccount.uuid)
        .where(or_(UserAccount.username == username, UserAccount.email == email))
        .exists()
    )
    return bool(await db.scalar(stmt))


@translate_db_errors
async def create_user_account(
    db: AsyncSession,
    username: str,
    email: str,
    password_hash: str,
    status: AccountStatus,
) -> UserAccount:
    user_account = UserAccount(
        username=username,
        email=email,
        password_hash=password_hash,
        status=status,
    )
    user_account.profile = UserProfile(username=user_account.username)
    db.add(user_account)
    await db.flush()
    await db.refresh(user_account)
    return user_account


@translate_db_errors
async def select_user_by_identifier(
    db: AsyncSession, identifier: str
) -> UserAccount | None:
    """Look up an account by username OR email (login form accepts both)."""
    stmt = (
        select(UserAccount)
        .where(or_(UserAccount.username == identifier, UserAccount.email == identifier))
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@translate_db_errors
async def select_active_user_with_profile(
    db: AsyncSession, user_id: UUID
) -> UserAccount | None:
    stmt = (
        select(UserAccount)
        .where(UserAccount.uuid == user_id)
        .where(UserAccount.status == AccountStatus.ACTIVE)
        .options(joinedload(UserAccount.profile))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@translate_db_errors
async def update_user_account_status(
    db: AsyncSession, email: str, status: AccountStatus
) -> bool:
    stmt = update(UserAccount).where(UserAccount.email == email).values(status=status)
    # DML returns a CursorResult at runtime; the stub only says Result.
    result = cast(CursorResult[Any], await db.execute(stmt))
    return result.rowcount > 0


# Token
@translate_db_errors
async def insert_refresh_token(
    db: AsyncSession, jwt_payload: JWTPayload
) -> UserRefreshToken:
    refresh_token = UserRefreshToken(
        jti=UUID(jwt_payload.jti),
        sid=UUID(jwt_payload.sid),
        user_id=UUID(jwt_payload.sub),
        expires_at=datetime.fromtimestamp(jwt_payload.exp, tz=UTC),
    )
    db.add(refresh_token)
    await db.flush()
    return refresh_token


@translate_db_errors
async def revoke_refresh_token(db: AsyncSession, jti: UUID) -> UserRefreshToken | None:
    """Revoke one active token. None = unknown or already revoked."""
    stmt = (
        update(UserRefreshToken)
        .where(UserRefreshToken.jti == jti)
        .where(UserRefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
        .returning(UserRefreshToken)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@translate_db_errors
async def get_refresh_token(
    db: AsyncSession, session_id: str
) -> UserRefreshToken | None:
    stmt = (
        select(UserRefreshToken)
        .where(UserRefreshToken.sid == UUID(session_id))
        .where(UserRefreshToken.revoked_at.is_(None))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@translate_db_errors
async def revoke_all_for_user(db: AsyncSession, user_id: UUID) -> list[UUID]:
    """Revoke every active token of the user; return their session ids."""
    stmt = (
        update(UserRefreshToken)
        .where(UserRefreshToken.user_id == user_id)
        .where(UserRefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
        .returning(UserRefreshToken.sid)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
