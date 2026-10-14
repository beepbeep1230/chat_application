from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import (
    CurrentUser,
    DbSession,
    RedisClient,
    RefreshTokenCookie,
    UserProfileDependency,
)
from app.core.responses import SuccessResponse
from app.core.security import verify_jwt_token
from app.modules.users.crud import (
    authenticate_user_account,
    # check_refresh_token,
    check_user_email_verified,
    check_user_existence,
    create_user_account,
    # delete_account_username_test,
    revoke_all_for_user,
    revoke_refresh_token,
    update_user_account_status,
    update_user_profile,
)
from app.modules.users.crud_cache import revoke_session, revoke_session_all
from app.modules.users.email import (  # noqa
    send_verification_mail,
    verify_verification,
)
from app.modules.users.schemas import (
    TokenResponse,
    UserCreateRequest,
    UserProfileResponse,
    UserUpdateProfileRequest,
)
from app.modules.users.service import issue_session, set_refresh_cookie

# Endpoints

# | Method | Path | Auth | Purpose |
# |---|---|---|---|


router = APIRouter(prefix="/auth", tags=["authentication"])


# | POST | `/auth/register` | — | create account + profile, email verification |
@router.post(
    "/register",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_account(
    user_data: UserCreateRequest,
    bg_tasks: BackgroundTasks,
    db: DbSession,
) -> SuccessResponse:

    await check_user_existence(
        db=db, username=user_data.username, email=user_data.email
    )
    created_user = await create_user_account(
        db=db,
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
    )
    # bg_tasks.add_task(
    #     send_verification_mail,
    #     username=created_user.username,
    #     email=created_user.email,
    #     subject="Verify your email for the fresh account in Chatapp.",
    # )

    return SuccessResponse(
        message="Registered successfully, please check you mailbox for the verification mail.",
        data={"username": created_user.username, "email": created_user.email},
    )


# | POST | `/auth/login` | — | tokens |
@router.post("/login", response_model=SuccessResponse, status_code=status.HTTP_200_OK)
async def login_account(
    user_form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    redis_client: RedisClient,
    db: DbSession,
    response: Response,
) -> SuccessResponse:
    login_user = await authenticate_user_account(
        db=db, identifier=user_form_data.username, password=user_form_data.password
    )
    refresh_token, access_token = await issue_session(
        db=db, r=redis_client, user_id=login_user.uuid
    )
    set_refresh_cookie(response, refresh_token)

    return SuccessResponse(
        message="Login successfully.",
        data=TokenResponse(access_token=access_token),
    )


# | GET | `/auth/verify-email` | — | activate account |
@router.post(
    "/verify-email",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_user_account(
    url_token: Annotated[str, Body()], db: DbSession
) -> SuccessResponse:

    email_from_url_token = verify_verification(url_token=url_token)
    user_by_email = await check_user_email_verified(db=db, email=email_from_url_token)
    updated_user = await update_user_account_status(db=db, user=user_by_email)
    return SuccessResponse(
        message="Verified.",
        data={
            "username": updated_user.username,
            "email": updated_user.email,
        },
    )


# | POST | `/auth/refresh` | refresh token | rotate tokens |
@router.post("/refresh", response_model=SuccessResponse, status_code=status.HTTP_200_OK)
async def refresh_access_token(
    user_refresh_token: RefreshTokenCookie,
    db: DbSession,
    redis_client: RedisClient,
    response: Response,
) -> SuccessResponse:
    old_refresh_token_record = await revoke_refresh_token(
        db=db, token=user_refresh_token
    )
    await revoke_session(r=redis_client, session_id=old_refresh_token_record.sid)

    refresh_token, access_token = await issue_session(
        db=db, r=redis_client, user_id=old_refresh_token_record.user_id
    )
    set_refresh_cookie(response, refresh_token)
    return SuccessResponse(
        message="Refreshed successfully.",
        data=TokenResponse(access_token=access_token),
    )


# | POST | `/auth/logout` | refresh token | revoke |
@router.post("/logout", response_model=SuccessResponse, status_code=status.HTTP_200_OK)
async def logout_user(
    user_refresh_token: RefreshTokenCookie,
    db: DbSession,
    redis_client: RedisClient,
) -> SuccessResponse:
    refresh_token_record = await revoke_refresh_token(db=db, token=user_refresh_token)
    await revoke_session(r=redis_client, session_id=refresh_token_record.sid)

    return SuccessResponse(message="Logged out.")


@router.post(
    "/logout-all", response_model=SuccessResponse, status_code=status.HTTP_200_OK
)
async def logout_user_all(
    user_refresh_token: RefreshTokenCookie,
    redis_client: RedisClient,
    db: DbSession,
) -> SuccessResponse:
    refresh_token_payload = verify_jwt_token(jwt_token=user_refresh_token)
    session_id_list = await revoke_all_for_user(
        db=db, user_id=refresh_token_payload.sub
    )
    await revoke_session_all(r=redis_client, session_id_list=session_id_list)
    return SuccessResponse(message="Logged out from all devices.")


# | GET | `/auth/me` | access | own account + profile |
@router.get("/me", response_model=SuccessResponse, status_code=status.HTTP_200_OK)
async def get_profile(
    user_profile: UserProfileDependency,
) -> SuccessResponse:
    return SuccessResponse(data=user_profile)


# | PATCH | `/auth/me` | access | update display_name/avatar/bio/phone (email change deferred) |
@router.patch("/me", response_model=SuccessResponse, status_code=status.HTTP_200_OK)
async def update_profile(
    user_profile_data: UserUpdateProfileRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> SuccessResponse:
    user_profile_dict = user_profile_data.model_dump(exclude_unset=True)
    if not user_profile_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    updated_user_profile = await update_user_profile(
        db=db, user=current_user, user_profile_data=user_profile_dict
    )

    data = UserProfileResponse.model_validate(updated_user_profile)
    return SuccessResponse(message="Profile updated.", data=data)
