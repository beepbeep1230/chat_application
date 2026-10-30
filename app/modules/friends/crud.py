from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from app.core.errors.translators import translate_db_errors
from app.modules.friends.models import FriendLists, FriendRequest, UserBlockLists
from app.modules.users.models import UserAccount, UserProfile
from sqlalchemy import CursorResult, Row, and_, delete, exists, literal, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute


@translate_db_errors
async def check_existence_by_id(db: AsyncSession, user_id: UUID) -> bool:
    stmt = select(exists().where(UserAccount.uuid == user_id))
    return bool(await db.scalar(stmt))


# FriendRequest
@translate_db_errors
async def select_friend_existing_request(
        db: AsyncSession, user_a: UUID, user_b: UUID
) -> FriendRequest | None:
    stmt = select(FriendRequest).where(
        or_(
            and_(
                FriendRequest.requester_id == user_a,
                FriendRequest.addressee_id == user_b,
            ),
            and_(
                FriendRequest.requester_id == user_b,
                FriendRequest.addressee_id == user_a,
            ),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@translate_db_errors
async def create_friend_request(
        db: AsyncSession, requester_id: UUID, addressee_id: UUID
) -> FriendRequest | None:
    stmt = (
        insert(FriendRequest)
        .values(requester_id=requester_id, addressee_id=addressee_id)
        .on_conflict_do_nothing()
        .returning(FriendRequest)
    )
    new_friend_request = (await db.execute(stmt)).scalar_one_or_none()

    return new_friend_request


@translate_db_errors
async def delete_claim_friend_request(
        db: AsyncSession, user_id: UUID, friend_request_id: UUID
) -> FriendRequest | None:
    stmt = (
        delete(FriendRequest)
        .where(
            FriendRequest.addressee_id == user_id,
            FriendRequest.id == friend_request_id,
        )
        .returning(FriendRequest)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# Withdraw the request made by ME
@translate_db_errors
async def delete_withdraw_friend_request(
        db: AsyncSession, user_id: UUID, friend_request_id: UUID
) -> bool:
    stmt = delete(FriendRequest).where(
        FriendRequest.requester_id == user_id,
        FriendRequest.id == friend_request_id,
        # FriendRequest.status == FriendRequestStatus.pending,
    )
    # DML returns a CursorResult at runtime; the stub only says Result.
    result = cast(CursorResult[Any], await db.execute(stmt))
    return result.rowcount == 1


@translate_db_errors
async def select_friend_requests(
        db: AsyncSession,
        *,
        me_col: InstrumentedAttribute[UUID],
        other_col: InstrumentedAttribute[UUID],
        me: UUID,
        limit: int,
        cursor: UUID | None,
) -> Sequence[Row[Any]]:
    stmt = (
        select(
            FriendRequest.id.label("request_id"),
            UserAccount.uuid.label("user_id"),
            UserAccount.username,
            UserProfile.display_name,
            UserProfile.avatar_url,
            FriendRequest.created_at,
        )
        .select_from(FriendRequest)
        .join(UserAccount, UserAccount.uuid == other_col)
        .outerjoin(UserProfile, UserProfile.username == UserAccount.username)
        .where(me_col == me)
        .order_by(FriendRequest.id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        stmt = stmt.where(FriendRequest.id < cursor)
    result = await db.execute(stmt)
    friend_requests_sent = result.all()
    return friend_requests_sent


# FriendList
@translate_db_errors
async def select_check_are_friends(
        db: AsyncSession, user_id: UUID, friend_id: UUID
) -> bool:
    stmt = select(
        exists().where(
            FriendLists.user_id == user_id, FriendLists.friend_id == friend_id
        )
    )
    result = await db.execute(stmt)
    return bool(result.scalar())


@translate_db_errors
async def insert_to_friend_list(
        db: AsyncSession, user_id: UUID, friend_id: UUID
) -> None:
    record_list = [
        {"user_id": user_id, "friend_id": friend_id},
        {"user_id": friend_id, "friend_id": user_id},
    ]
    stmt = insert(FriendLists).values(record_list).on_conflict_do_nothing()
    await db.execute(stmt)


@translate_db_errors
async def delete_from_friend_list(
        db: AsyncSession, user_id: UUID, friend_id: UUID
) -> bool:
    stmt = delete(FriendLists).where(
        or_(
            and_(FriendLists.user_id == user_id, FriendLists.friend_id == friend_id),
            and_(FriendLists.user_id == friend_id, FriendLists.friend_id == user_id),
        )
    )
    # DML returns a CursorResult at runtime; the stub only says Result.
    result = cast(CursorResult[Any], await db.execute(stmt))
    return result.rowcount > 0


@translate_db_errors
async def select_friend_list(
        db: AsyncSession,
        user_id: UUID,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
) -> Sequence[Row[Any]]:
    subq = exists().where(
        UserBlockLists.user_id == user_id,
        UserBlockLists.blocked_user_id == FriendLists.friend_id,
    )
    stmt = (
        select(
            UserAccount.uuid.label("user_id"),
            UserAccount.username,
            UserProfile.display_name,
            UserProfile.avatar_url,
            FriendLists.created_at,
        )
        .select_from(FriendLists)
        .join(UserAccount, UserAccount.uuid == FriendLists.friend_id)
        .outerjoin(UserProfile, UserProfile.username == UserAccount.username)
        .where(FriendLists.user_id == user_id, ~subq)
        .order_by(FriendLists.created_at.desc(), FriendLists.friend_id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        stmt = stmt.where(
            tuple_(FriendLists.created_at, FriendLists.friend_id)
            < tuple_(literal(cursor[0]), literal(cursor[1]))
        )
    result = await db.execute(stmt)
    friends = result.all()
    return friends


# Block
@translate_db_errors
async def select_is_blocked_between(
        db: AsyncSession, user_a: UUID, user_b: UUID
) -> bool:
    stmt = select(
        exists().where(
            or_(
                and_(
                    UserBlockLists.user_id == user_a,
                    UserBlockLists.blocked_user_id == user_b,
                ),
                and_(
                    UserBlockLists.user_id == user_b,
                    UserBlockLists.blocked_user_id == user_a,
                ),
            )
        )
    )
    return bool(await db.scalar(stmt))


@translate_db_errors
async def insert_block_record(
        db: AsyncSession, user_id: UUID, other: UUID
) -> UserBlockLists | None:
    stmt = (
        insert(UserBlockLists)
        .values(user_id=user_id, blocked_user_id=other)
        .on_conflict_do_nothing()
        .returning(UserBlockLists)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@translate_db_errors
async def delete_requests_between(
        db: AsyncSession, user_id: UUID, other: UUID
) -> None:
    stmt = delete(FriendRequest).where(
        or_(
            and_(
                FriendRequest.requester_id == user_id,
                FriendRequest.addressee_id == other,
            ),
            and_(
                FriendRequest.requester_id == other,
                FriendRequest.addressee_id == user_id,
            ),
        )
    )
    await db.execute(stmt)


@translate_db_errors
async def delete_unblock(db: AsyncSession, user_id: UUID, other: UUID) -> bool:
    stmt = delete(UserBlockLists).where(
        UserBlockLists.user_id == user_id, UserBlockLists.blocked_user_id == other
    )
    # DML returns a CursorResult at runtime; the stub only says Result.
    result = cast(CursorResult[Any], await db.execute(stmt))
    return result.rowcount == 1


@translate_db_errors
async def select_blocked_list(
        db: AsyncSession,
        user_id: UUID,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
) -> Sequence[Row[Any]]:
    stmt = (
        select(
            UserAccount.uuid.label("user_id"),
            UserAccount.username,
            UserProfile.display_name,
            UserProfile.avatar_url,
            UserBlockLists.blocked_at,
        )
        .select_from(UserBlockLists)
        .join(UserAccount, UserAccount.uuid == UserBlockLists.blocked_user_id)
        .outerjoin(UserProfile, UserProfile.username == UserAccount.username)
        .where(UserBlockLists.user_id == user_id)
        .order_by(
            UserBlockLists.blocked_at.desc(), UserBlockLists.blocked_user_id.desc()
        )
        .limit(limit + 1)
    )
    if cursor is not None:
        stmt = stmt.where(
            tuple_(UserBlockLists.blocked_at, UserBlockLists.blocked_user_id)
            < tuple_(literal(cursor[0]), literal(cursor[1]))
        )
    result = await db.execute(stmt)
    blocked_users = result.all()
    return blocked_users
