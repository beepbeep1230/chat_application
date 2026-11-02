from fastapi import APIRouter, Depends, status

from app.api.rate_limit import UserRateLimiter
from app.core.responses import SuccessResponse
from app.modules.auth.deps import CurrentUser
from app.modules.users.deps import UserProfileDependency, UserServiceHandler
from app.modules.users.schemas import UserProfileResponse, UserUpdateProfileRequest

# Read on every app load / tab open: loose.
profile_read_limit = UserRateLimiter(
    "profile_read", capacity=30, refill_rate=1, refill_interval=2
)
# Profile edits are rare.
profile_update_limit = UserRateLimiter(
    "profile_update", capacity=10, refill_rate=1, refill_interval=60
)

router = APIRouter(prefix="/users", tags=["users"])


# | GET | `/users/me` | access | own account + profile |
@router.get(
    "/me",
    response_model=SuccessResponse[UserProfileResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(profile_read_limit)],
)
async def get_profile(
    user_profile: UserProfileDependency,
) -> SuccessResponse[UserProfileResponse]:
    return SuccessResponse(data=user_profile)


# | PATCH | `/users/me` | access | update display_name/avatar/bio/phone (email change deferred) |
@router.patch(
    "/me",
    response_model=SuccessResponse[UserProfileResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(profile_update_limit)],
)
async def update_profile(
    user_profile_data: UserUpdateProfileRequest,
    current_user: CurrentUser,
    service: UserServiceHandler,
) -> SuccessResponse[UserProfileResponse]:
    user_profile_dict = user_profile_data.model_dump(exclude_unset=True)

    updated_user_profile = await service.update_profile(
        username=current_user.username, user_profile_data=user_profile_dict
    )
    return SuccessResponse(message="Profile updated.", data=updated_user_profile)
