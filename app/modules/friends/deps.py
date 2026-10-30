from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession, RedisClient
from app.modules.friends.service import FriendService


async def get_friend_service(
    redis_client: RedisClient,
    db: DbSession,
) -> FriendService:
    return FriendService(redis=redis_client, db=db)


FriendServiceHandler = Annotated[FriendService, Depends(get_friend_service)]
