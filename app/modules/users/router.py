from app.core.responses import SuccessResponse
from app.modules.auth.deps import CurrentUser
from app.modules.users.deps import UserProfileDependency, UserServiceHandler
from app.modules.users.schemas import UserProfileResponse, UserUpdateProfileRequest
from fastapi import APIRouter, status

router = APIRouter(prefix="/users", tags=["users"])


# | GET | `/users/me` | access | own account + profile |
@router.get(
    "/me",
    response_model=SuccessResponse[UserProfileResponse],
    status_code=status.HTTP_200_OK,
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
