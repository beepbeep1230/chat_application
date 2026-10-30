from typing import Annotated
from uuid import UUID

from app.core.responses import SuccessResponse
from app.modules.auth.deps import CurrentUser
from app.modules.friends import schemas
from app.modules.friends.deps import FriendServiceHandler
from fastapi import APIRouter, Body, Path, Query, status

router = APIRouter(tags=["relations"])


# | POST | `/friends/requests` | `{to_user_id}` — send request |
@router.post(
    "/friends/requests",
    response_model=SuccessResponse[schemas.FriendRequestResponse],
    status_code=status.HTTP_201_CREATED,
)
async def send_friend_request(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    user_id: Annotated[UUID, Body(embed=True, alias="userId")],
) -> SuccessResponse[schemas.FriendRequestResponse]:
    response = await service.send_request(current_user.uuid, user_id)
    return SuccessResponse(message="Friend request sent.", data=response)


# | GET | `/friends/requests` | incoming pending |
@router.get(
    "/friends/requests",
    response_model=SuccessResponse[schemas.FriendRequestList],
    status_code=status.HTTP_200_OK,
)
async def incoming_friend_requests(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> SuccessResponse[schemas.FriendRequestList]:
    response = await service.list_requests(
        current_user.uuid, option="received", limit=limit, cursor=cursor
    )
    return SuccessResponse(data=response)


# | GET | `/friends/requests/sent` | outgoing pending |
@router.get(
    "/friends/requests/sent",
    response_model=SuccessResponse[schemas.FriendRequestList],
    status_code=status.HTTP_200_OK,
)
async def outgoing_friend_requests(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> SuccessResponse[schemas.FriendRequestList]:
    response = await service.list_requests(
        current_user.uuid, option="sent", limit=limit, cursor=cursor
    )
    return SuccessResponse(data=response)


# | POST | `/friends/requests/{id}/accept` | accept |
@router.post(
    "/friends/requests/{request_id}/accept",
    response_model=SuccessResponse[schemas.FriendRequestResponse],
    status_code=status.HTTP_200_OK,
)
async def accept_friend_requests(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    request_id: Annotated[UUID, Path()],
) -> SuccessResponse[schemas.FriendRequestResponse]:
    response = await service.accept(current_user.uuid, request_id)
    return SuccessResponse(message="Request accepted.", data=response)


# | POST | `/friends/requests/{id}/decline` | decline |
@router.post(
    "/friends/requests/{request_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def decline_friend_requests(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    request_id: Annotated[UUID, Path()],
) -> None:
    await service.decline(current_user.uuid, request_id)


# | DELETE | `/friends/requests/{id}` | withdraw own request |
@router.delete(
    "/friends/requests/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def withdraw_friend_requests(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    request_id: Annotated[UUID, Path()],
) -> None:
    await service.withdraw(current_user.uuid, request_id)


# | GET | `/friends` | accepted friendships |
@router.get(
    "/friends",
    response_model=SuccessResponse[schemas.UserFriendList],
    status_code=status.HTTP_200_OK,
)
async def get_friends_list(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> SuccessResponse[schemas.UserFriendList]:
    response = await service.list_friends(current_user.uuid, limit, cursor)
    return SuccessResponse(data=response)


# | DELETE | `/friends/{user_id}` | unfriend |
@router.delete(
    "/friends/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_friends(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    user_id: Annotated[UUID, Path()],
) -> None:
    await service.unfriend(current_user.uuid, user_id)


# | POST | `/block/{user_id}` | block |
@router.post(
    "/blocks/{user_id}",
    response_model=SuccessResponse[schemas.BlockResponse],
    status_code=status.HTTP_201_CREATED,
)
async def block_user(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    user_id: Annotated[UUID, Path()],
) -> SuccessResponse[schemas.BlockResponse]:
    response = await service.block_user(current_user.uuid, user_id)
    return SuccessResponse(data=response)


# | DELETE | `/block/{user_id}` | unblock |
@router.delete(
    "/blocks/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unblock_user(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    user_id: Annotated[UUID, Path()],
) -> None:
    await service.unblock_user(current_user.uuid, user_id)


# | GET | `/block` | list blocked |
@router.get(
    "/blocks",
    response_model=SuccessResponse[schemas.UserBlockedList],
    status_code=status.HTTP_200_OK,
)
async def get_blocked_list(
    current_user: CurrentUser,
    service: FriendServiceHandler,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> SuccessResponse[schemas.UserBlockedList]:
    response = await service.list_blocked_users(current_user.uuid, limit, cursor)
    return SuccessResponse(data=response)
