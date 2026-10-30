from typing import Literal
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors.exceptions import (
    BlockedAlready,
    BlockRecordNotFound,
    CoolDownError,
    FriendRequestNotAllowedError,
    FriendsAlreadyError,
    NotFriendsError,
    RequestedAlreadyError,
    RequestNotFound,
    SelfRequestError,
    UserRequestedNotFound,
)
from app.core.logging import logger
from app.core.pagination import (
    decode_cursor_time_id,
    decode_cursor_uuid,
    encode_cursor_time_id,
    encode_cursor_uuid,
)
from app.modules.friends import crud, crud_cache, models, schemas


class FriendService:
    def __init__(self, redis: Redis, db: AsyncSession) -> None:
        self.db = db
        self.redis = redis
        self._cool_down_days = settings.request_cool_down

    async def send_request(
        self, me: UUID, to_user_id: UUID
    ) -> schemas.FriendRequestResponse:
        # Raise if sending request to himself/herself
        self._check_is_same_user(me, to_user_id)
        # Raise if the user does not exists
        await self._check_user_existence(to_user_id)
        if await crud.select_is_blocked_between(self.db, me, to_user_id):
            raise FriendRequestNotAllowedError()
        # Check if users are already friends
        if await crud.select_check_are_friends(self.db, me, to_user_id):
            raise FriendsAlreadyError()

        # Check if there is friend request between two users
        existing_request = await crud.select_friend_existing_request(
            self.db, me, to_user_id
        )
        if existing_request is not None:
            resolved_response = await self._resolve_existing_request(
                me, existing_request
            )
            return resolved_response

        # Sender got declined
        cool_down_left = await crud_cache.cooldown_remaining_second(
            self.redis, requester_id=me, addressee_id=to_user_id
        )
        if cool_down_left > 0:
            raise CoolDownError(cool_down=cool_down_left)

        friend_request_record = await crud.create_friend_request(
            self.db, me, to_user_id
        )
        if friend_request_record is None:  # ON CONCLICT DO NOTHING
            raise RequestedAlreadyError()
        await self.db.commit()
        # Sender declined
        await crud_cache.clear_cooldown(
            self.redis, requester_id=to_user_id, addressee_id=me
        )
        return self._request_created_response(friend_request_record)

    async def accept(self, me: UUID, request_id: UUID) -> schemas.FriendRequestResponse:
        friend_request_record = await crud.delete_claim_friend_request(
            self.db, me, request_id
        )
        if friend_request_record is None:
            raise RequestNotFound()

        await crud.insert_to_friend_list(
            self.db,
            friend_request_record.requester_id,
            friend_request_record.addressee_id,
        )

        return self._request_created_response(friend_request_record, status="accepted")

    async def decline(self, me: UUID, request_id: UUID) -> None:
        friend_request_record = await crud.delete_claim_friend_request(
            self.db, me, request_id
        )
        if friend_request_record is None:
            raise RequestNotFound()
        # Ensure the record is deleted then set the cool down
        await self.db.commit()
        success = await crud_cache.set_cooldown(
            self.redis,
            friend_request_record.requester_id,
            friend_request_record.addressee_id,
            ttl=self._cool_down_days * 24 * 3600,
        )
        if not success:
            logger.warning(
                "declined_friend_request_cannot_set",
                requester=friend_request_record.requester_id,
                addressee=friend_request_record.addressee_id,
            )

    async def withdraw(self, me: UUID, request_id: UUID) -> None:
        deleted = await crud.delete_withdraw_friend_request(self.db, me, request_id)
        if not deleted:
            raise RequestNotFound()

    async def unfriend(self, me: UUID, friend_id: UUID) -> None:
        self._check_is_same_user(me, friend_id)
        deleted = await crud.delete_from_friend_list(self.db, me, friend_id)
        if not deleted:
            raise NotFriendsError()

    async def list_requests(
        self,
        me: UUID,
        option: Literal["sent", "received"],
        limit: int,
        cursor: str | None = None,
    ) -> schemas.FriendRequestList:
        if option == "sent":
            me_col = models.FriendRequest.requester_id
            other_col = models.FriendRequest.addressee_id
        elif option == "received":
            me_col = models.FriendRequest.addressee_id
            other_col = models.FriendRequest.requester_id
        else:
            raise ValueError('Only "sent" or "received" is allowed.')
        rows = await crud.select_friend_requests(
            self.db,
            me_col=me_col,
            other_col=other_col,
            me=me,
            limit=limit,
            cursor=decode_cursor_uuid(cursor) if cursor is not None else None,
        )
        if len(rows) == 0:
            return schemas.FriendRequestList(items=[])

        has_more = len(rows) > limit
        friend_requests = rows[:limit]
        next_cursor = (
            encode_cursor_uuid(friend_requests[-1].request_id) if has_more else None
        )

        return schemas.FriendRequestList(
            items=[
                schemas.FriendRequestItem(
                    request_id=request.request_id,
                    user=schemas.UserBrief(
                        user_id=request.user_id,
                        username=request.username,
                        display_name=request.display_name,
                        avatar_url=request.avatar_url,
                    ),
                    created_at=request.created_at,
                )
                for request in friend_requests
            ],
            next_cursor=next_cursor,
        )

    # Friend List
    async def list_friends(
        self,
        me: UUID,
        limit: int,
        cursor: str | None = None,
    ) -> schemas.UserFriendList:
        rows = await crud.select_friend_list(
            self.db,
            user_id=me,
            limit=limit,
            cursor=decode_cursor_time_id(cursor) if cursor is not None else None,
        )
        if len(rows) == 0:
            return schemas.UserFriendList(items=[])
        has_more = len(rows) > limit
        friends = rows[:limit]
        cursor_raw_tuple = (friends[-1].created_at, friends[-1].user_id)
        next_cursor = encode_cursor_time_id(*cursor_raw_tuple) if has_more else None
        return schemas.UserFriendList(
            items=[schemas.UserBrief.model_validate(user) for user in friends],
            next_cursor=next_cursor,
        )

    # Block other Users
    async def block_user(self, me: UUID, other: UUID) -> schemas.BlockResponse:
        self._check_is_same_user(me, other)
        await self._check_user_existence(other)
        block_record = await crud.insert_block_record(self.db, user_id=me, other=other)
        if block_record is None:
            raise BlockedAlready()
        await crud.delete_requests_between(self.db, user_id=me, other=other)

        return schemas.BlockResponse(
            blocked_user=block_record.blocked_user_id,
            blocked_at=block_record.blocked_at,
        )

    async def unblock_user(self, me: UUID, other: UUID) -> None:
        self._check_is_same_user(me, other)
        deleted = await crud.delete_unblock(self.db, me, other)
        if not deleted:
            raise BlockRecordNotFound()

    async def list_blocked_users(
        self,
        me: UUID,
        limit: int,
        cursor: str | None = None,
    ) -> schemas.UserBlockedList:
        rows = await crud.select_blocked_list(
            self.db,
            user_id=me,
            limit=limit,
            cursor=decode_cursor_time_id(cursor) if cursor is not None else None,
        )
        if len(rows) == 0:
            return schemas.UserBlockedList(items=[])
        has_more = len(rows) > limit
        blocked_users = rows[:limit]
        cursor_raw_tuple = (blocked_users[-1].blocked_at, blocked_users[-1].user_id)
        next_cursor = encode_cursor_time_id(*cursor_raw_tuple) if has_more else None
        return schemas.UserBlockedList(
            items=[schemas.UserBrief.model_validate(user) for user in blocked_users],
            next_cursor=next_cursor,
        )

    async def _resolve_existing_request(
        self, me: UUID, existing_request: models.FriendRequest
    ) -> schemas.FriendRequestResponse:
        if existing_request.addressee_id == me:
            return await self.accept(me, existing_request.id)

        # return self._request_created_response(existing_request)
        raise RequestedAlreadyError()

    @staticmethod
    def _check_is_same_user(user_a: UUID, user_b: UUID) -> None:
        if user_a == user_b:
            raise SelfRequestError()

    @staticmethod
    def _request_created_response(
        record: models.FriendRequest,
        status: Literal["accepted", "pending"] = "pending",
    ) -> schemas.FriendRequestResponse:
        return schemas.FriendRequestResponse(
            status=status,
            sent_from=record.requester_id,
            sent_to=record.addressee_id,
            request_id=record.id,
            created_at=record.created_at,
        )

    async def _check_user_existence(self, to_user_id: UUID) -> None:
        user_existence = await crud.check_existence_by_id(self.db, to_user_id)
        if not user_existence:
            raise UserRequestedNotFound()
