from typing import Annotated

from app.core.config import settings
from app.core.responses import SuccessResponse
from app.modules.auth.deps import AuthServiceHandler, RefreshTokenCookie
from app.modules.auth.email import send_verification_mail  # noqa
from app.modules.auth.schemas import (
    TokenResponse,
    UserCreatedResponse,
    UserCreateRequest,
    UserVerifiedResponse,
)
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
    status,
)
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["authentication"])


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refreshToken",
        value=refresh_token,
        httponly=True,
        samesite="strict",
        path="/api/v1/auth",
        max_age=(60 * 60 * 24 * settings.jwt_refresh_token_life_day),
    )


# | POST | `/auth/register` | — | create account + profile, email verification |
@router.post(
    "/register",
    response_model=SuccessResponse[UserCreatedResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register_account(
    user_data: UserCreateRequest,
    bg_tasks: BackgroundTasks,
    service: AuthServiceHandler,
) -> SuccessResponse[UserCreatedResponse]:
    created_user = await service.register(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
    )
    # Email task still commented out.
    # bg_tasks.add_task(
    #     send_verification_mail,
    #     username=created_user.username,
    #     email=created_user.email,
    #     subject="Verify your email for the fresh account in chatapp."
    # )

    return SuccessResponse(
        message="Registered successfully, please check you mailbox for the verification mail.",
        data=UserCreatedResponse(
            username=created_user.username, email=created_user.email
        ),
    )


# | POST | `/auth/login` | — | tokens |
@router.post(
    "/login",
    response_model=SuccessResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
)
async def login_account(
    user_form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: AuthServiceHandler,
    response: Response,
) -> SuccessResponse[TokenResponse]:
    refresh_token, access_token = await service.login(
        identifier=user_form_data.username, password=user_form_data.password
    )
    set_refresh_cookie(response, refresh_token)
    return SuccessResponse(
        message="Login successfully.",
        data=TokenResponse(access_token=access_token),
    )


# | GET | `/auth/verify-email` | — | activate account |
@router.get(
    "/verify-email",
    response_model=SuccessResponse[UserVerifiedResponse],
    status_code=status.HTTP_200_OK,
)
async def verify_user_account(
    url_token: Annotated[str, Query(alias="token")], service: AuthServiceHandler
) -> SuccessResponse[UserVerifiedResponse]:
    verified_user = await service.verify_email(url_token)
    return SuccessResponse(
        message="Verified.",
        data=UserVerifiedResponse(
            username=verified_user.username, email=verified_user.email
        ),
    )


# | POST | `/auth/refresh` | refresh token | rotate tokens |
@router.post(
    "/refresh",
    response_model=SuccessResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
)
async def refresh_access_token(
    user_refresh_token: RefreshTokenCookie,
    service: AuthServiceHandler,
    response: Response,
) -> SuccessResponse[TokenResponse]:
    refresh_token, access_token = await service.refresh(user_refresh_token)
    set_refresh_cookie(response, refresh_token)
    return SuccessResponse(
        message="Refreshed successfully.",
        data=TokenResponse(access_token=access_token),
    )


# | POST | `/auth/logout` | refresh token | revoke |
@router.post("/logout", response_model=SuccessResponse, status_code=status.HTTP_200_OK)
async def logout_user(
    user_refresh_token: RefreshTokenCookie,
    service: AuthServiceHandler,
) -> SuccessResponse[None]:
    await service.logout(user_refresh_token)
    return SuccessResponse(message="Logged out.")


@router.post(
    "/logout-all", response_model=SuccessResponse, status_code=status.HTTP_200_OK
)
async def logout_user_all(
    user_refresh_token: RefreshTokenCookie,
    service: AuthServiceHandler,
) -> SuccessResponse[None]:
    await service.logout_all(user_refresh_token)
    return SuccessResponse(message="Logged out from all devices.")
