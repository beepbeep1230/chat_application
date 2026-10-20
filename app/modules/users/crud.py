from datetime import UTC, datetime
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

# from sqlalchemy.orm import joinedload
from app.core.config import settings
from app.core.exception_handlers import translate_db_errors
from app.core.exceptions import (
    InvalidCredentials,
    InvalidToken,
    UserExists,
    UserNotFound,
)
from app.core.logging import logger
from app.core.security import (
    JWTPayload,
    hash_password,
    verify_jwt_token,
    verify_password,
)
from app.modules.users.models import (
    AccountStatus,
    UserAccount,
    UserProfile,
    UserRefreshToken,
)


@translate_db_errors
async def check_user_email_verified(db: AsyncSession, email: str):
    stmt = (
        select(UserAccount)
        .where(UserAccount.email == email)
        .where(UserAccount.status == AccountStatus.UNVERIFIED)
    )
    result = await db.execute(stmt)
    user_by_email = result.scalar_one_or_none()
    if user_by_email is None:
        raise UserNotFound()
    return user_by_email


@translate_db_errors
async def check_user_existence(db: AsyncSession, email: str, username: str):
    stmt = (
        select(UserAccount)
        .where(or_(UserAccount.username == username, UserAccount.email == email))
        .limit(1)
    )
    result = await db.execute(stmt)

    existing = result.scalar_one_or_none()
    if existing is not None:
        raise UserExists()


@translate_db_errors
async def create_user_account(
    db: AsyncSession, username: str, email: str, password: str
) -> UserAccount:
    hashed_password = await run_in_threadpool(hash_password, password)
    user_account = UserAccount(
        username=username,
        email=email,
        password_hash=hashed_password,
        status=AccountStatus.ACTIVE if settings.dev_mode else AccountStatus.UNVERIFIED,
    )
    user_account.profile = UserProfile(username=user_account.username)
    db.add(user_account)
    await db.flush()
    await db.refresh(user_account)
    return user_account


@translate_db_errors
async def authenticate_user_account(
    db: AsyncSession, identifier: str, password: str
) -> UserAccount:
    stmt = (
        select(UserAccount)
        .where(or_(UserAccount.username == identifier, UserAccount.email == identifier))
        .limit(1)
    )
    result = await db.execute(stmt)
    user_account = result.scalar_one_or_none()
    if not user_account:
        raise InvalidCredentials()
    password_verified = await run_in_threadpool(
        verify_password,
        plain_password=password,
        hash_password=user_account.password_hash,
    )
    if not password_verified or user_account.status != AccountStatus.ACTIVE:
        raise InvalidCredentials()
    return user_account


@translate_db_errors
async def update_user_account_status(
    db: AsyncSession, user: UserAccount
) -> UserAccount:
    stmt = (
        update(UserAccount)
        .where(UserAccount.email == user.email)
        .values(status=AccountStatus.ACTIVE)
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise UserNotFound()
    await db.refresh(user)
    return user


# Profile


@translate_db_errors
async def update_user_profile(
    db: AsyncSession, user: UserAccount, user_profile_data: dict
) -> UserProfile:
    stmt = (
        update(UserProfile)
        .where(UserProfile.username == user.username)
        .values(**user_profile_data)
        .returning(UserProfile)
    )
    result = await db.execute(stmt)
    # await db.refresh(result)
    user_profile = result.scalar_one_or_none()
    if user_profile is None:
        raise UserNotFound()
    return user_profile


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
async def revoke_refresh_token(db: AsyncSession, token: str):
    payload = verify_jwt_token(jwt_token=token)
    if payload.type != "refresh":
        raise InvalidToken()
    stmt = (
        update(UserRefreshToken)
        .where(UserRefreshToken.jti == UUID(payload.jti))
        .where(UserRefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
        .returning(UserRefreshToken)
    )
    result = await db.execute(stmt)
    user_refresh_token = result.scalar_one_or_none()
    if user_refresh_token is None:
        raise InvalidToken()
    return user_refresh_token


@translate_db_errors
async def get_refresh_token(db: AsyncSession, session_id: str) -> UserRefreshToken:
    stmt = (
        select(UserRefreshToken)
        .where(UserRefreshToken.sid == UUID(session_id))
        .where(UserRefreshToken.revoked_at.is_(None))
    )
    result = await db.execute(stmt)
    user_refresh_token = result.scalar_one_or_none()
    if user_refresh_token is None:
        raise InvalidToken()
    return user_refresh_token


@translate_db_errors
async def revoke_all_for_user(db: AsyncSession, token: str):
    payload = verify_jwt_token(jwt_token=token)
    if payload.type != "refresh":
        raise InvalidToken()
    stmt = (
        update(UserRefreshToken)
        .where(UserRefreshToken.user_id == UUID(payload.sub))
        .where(UserRefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
        .returning(UserRefreshToken.sid)
    )
    result = await db.execute(stmt)
    sids = list(result.scalars().all())
    return sids
