from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)
from pydantic.alias_generators import to_camel


class UserBrief(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, alias_generator=to_camel, validate_by_name=True
    )
    user_id: UUID
    username: str
    display_name: str | None = None
    avatar_url: str | None = None


class FriendRequestItem(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, alias_generator=to_camel, validate_by_name=True
    )
    request_id: UUID
    user: UserBrief
    created_at: datetime


class FriendRequestResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, alias_generator=to_camel, validate_by_name=True
    )
    status: Literal["accepted", "pending"]
    sent_from: UUID
    sent_to: UUID
    request_id: UUID
    created_at: datetime


class BlockResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, alias_generator=to_camel, validate_by_name=True
    )
    blocked_user: UUID
    blocked_at: datetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    model_config = ConfigDict(
        from_attributes=True, alias_generator=to_camel, validate_by_name=True
    )
    items: list[T] = Field(default_factory=lambda: [])
    next_cursor: str | None = None


class FriendRequestList(Page[FriendRequestItem]):
    pass


class UserList(Page[UserBrief]):
    pass


class UserFriendList(UserList):
    pass


class UserBlockedList(UserList):
    pass
