from typing import Literal
from uuid import UUID

from app.core.config import settings
from app.core.errors.exceptions import (
    AlreadyVerified,
    AppError,  # LOGGING: for catch exclude
    InvalidCredentials,
    InvalidToken,
    Unauthenticated,
    UserExists,
    UserNotFound,
)
from app.core.logging import logger  # LOGGING: Import logger
from app.core.security import (
    JWTPayload,
    create_jwt_token,
    hash_password,
    verify_jwt_token,
    verify_password,
)
from app.modules.auth import crud, crud_cache
from app.modules.auth.models import UserRefreshToken
from app.modules.auth.email import verify_verification
from app.modules.users.models import AccountStatus, UserAccount
from fastapi.concurrency import run_in_threadpool
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


class AuthService:
    def __init__(self, redis: Redis, db: AsyncSession) -> None:
        self.db = db
        self.redis = redis

    # Registration
    async def register(self, username: str, email: str, password: str) -> UserAccount:
        if await crud.check_user_existence(self.db, email=email, username=username):
            raise UserExists()
        hashed_password = await run_in_threadpool(hash_password, password)
        created_user = await crud.create_user_account(
            self.db,
            username=username,
            email=email,
            password_hash=hashed_password,
            status=AccountStatus.ACTIVE
            if settings.dev_mode
            else AccountStatus.UNVERIFIED,
        )
        # LOGGING: Registration success (no password/PII beyond username+email, which
        # the existing response body already returns).
        logger.info(
            "user_registered",
            username=created_user.username,
            email=created_user.email,
        )
        return created_user

    async def verify_email(self, url_token: str) -> UserAccount:
        email_from_url_token = verify_verification(url_token=url_token)
        user_by_email = await crud.select_user_by_email(
            self.db, email=email_from_url_token
        )
        if user_by_email is None or user_by_email.status == AccountStatus.SUSPENDED:
            raise UserNotFound()
        if user_by_email.status == AccountStatus.ACTIVE:
            raise AlreadyVerified()
        updated = await crud.update_user_account_status(
            self.db, email=user_by_email.email, status=AccountStatus.ACTIVE
        )
        if not updated:
            raise UserNotFound()
        # LOGGING: Email verified (account activated)
        logger.info(
            "email_verified",
            username=user_by_email.username,
            email=user_by_email.email,
        )
        return user_by_email

    # Session
    async def login(self, identifier: str, password: str) -> tuple[str, str]:
        """Return (refresh_token, access_token)."""
        # LOGGING: Attempt before auth (failure path is logged by unauthorized_handler)
        logger.info("login_attempt", identifier=identifier)
        user_account = await crud.select_user_by_identifier(self.db, identifier)
        if not user_account:
            raise InvalidCredentials()
        password_verified = await run_in_threadpool(
            verify_password,
            plain_password=password,
            hash_password=user_account.password_hash,
        )
        if not password_verified or user_account.status != AccountStatus.ACTIVE:
            raise InvalidCredentials()

        user_id = user_account.uuid
        tokens = await self._issue_session(user_id)
        # LOGGING: Success with stable identifiers (never log the tokens themselves)
        logger.info("login_success", user_id=str(user_id), identifier=identifier)
        return tokens

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        """Rotate: revoke the presented refresh token, issue a new pair."""
        old_record = await self._revoke_refresh_token(refresh_token)
        user_id, old_sid = old_record.user_id, old_record.sid
        # LOGGING: Token rotation - old sid revoked, new one issued by _issue_session
        logger.info(
            "refresh_token_rotated",
            user_id=str(user_id),
            old_sid=str(old_sid),
        )
        await crud_cache.revoke_session_cache(self.redis, session_id=str(old_sid))
        return await self._issue_session(user_id)

    async def logout(self, refresh_token: str) -> None:
        record = await self._revoke_refresh_token(refresh_token)
        user_id, sid = record.user_id, record.sid
        await crud_cache.revoke_session_cache(self.redis, session_id=str(sid))
        # LOGGING: Single-device logout
        logger.info("logout_success", user_id=str(user_id), sid=str(sid))

    async def logout_all(self, refresh_token: str) -> int:
        payload = self._verify_token(refresh_token, expected_type="refresh")
        session_id_list = await crud.revoke_all_for_user(self.db, UUID(payload.sub))
        await crud_cache.revoke_session_all_cache(
            self.redis, session_id_list=session_id_list
        )
        # LOGGING: warning level - "log out everywhere" is security-adjacent
        logger.warning("logout_all_devices", sessions_revoked=len(session_id_list))
        return len(session_id_list)

    # Current user (used by the CurrentUser dependency)
    async def get_current_user(self, access_token: str) -> UserAccount:
        payload = self._verify_token(access_token, expected_type="access")

        active = await crud_cache.check_session_is_active(
            self.redis, session_id=payload.sid
        )
        if not active:
            refresh_token_record = await crud.get_refresh_token(
                self.db, session_id=payload.sid
            )
            if refresh_token_record is None:
                raise InvalidToken()
            await crud_cache.set_session(self.redis, session=refresh_token_record)

        current_user = await crud.select_active_user_with_profile(
            self.db, UUID(payload.sub)
        )
        if current_user is None:
            raise Unauthenticated()
        return current_user

    # Helpers
    @staticmethod
    def _verify_token(
        token: str, expected_type: Literal["access", "refresh"]
    ) -> JWTPayload:
        payload = verify_jwt_token(jwt_token=token)
        if payload.type != expected_type:
            raise InvalidToken()
        return payload

    async def _revoke_refresh_token(self, refresh_token: str) -> UserRefreshToken:
        payload = self._verify_token(refresh_token, expected_type="refresh")
        record = await crud.revoke_refresh_token(self.db, jti=UUID(payload.jti))
        if record is None:
            raise InvalidToken()
        return record

    # LOGGING: Session issuance with structured logging.
    # exclude=(AppError,) -> expected app errors (DatabaseError/CacheError/...) are
    # already logged by translate_*_errors and the 503 handlers, so only truly
    # unexpected bugs get the catch traceback here (avoids triple-logging).
    @logger.catch(
        reraise=True,
        exclude=(AppError,),
        message="Unexpected failure while issuing session",
    )
    async def _issue_session(self, user_id: UUID) -> tuple[str, str]:
        logger.debug("issuing_session", user_id=str(user_id))
        refresh_token, jwt_payload_refresh = create_jwt_token(
            user_id=str(user_id), option="refresh"
        )
        access_token, _ = create_jwt_token(
            user_id=str(user_id),
            option="access",
            session_id=jwt_payload_refresh.sid,
        )
        refresh_token_record = await crud.insert_refresh_token(
            self.db, jwt_payload=jwt_payload_refresh
        )
        # Commit before the Redis write so the cache never points at a row that
        # was rolled back.
        await self.db.commit()
        await crud_cache.set_session(self.redis, session=refresh_token_record)
        logger.info(
            "session_issued",
            user_id=str(user_id),
            sid=str(jwt_payload_refresh.sid),
            jti=str(jwt_payload_refresh.jti),
        )
        return refresh_token, access_token
