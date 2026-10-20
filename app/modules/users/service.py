from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError  # LOGGING: for catch exclude
from app.core.logging import logger  # LOGGING: Import logger
from app.core.security import create_jwt_token
from app.modules.users.crud import insert_refresh_token
from app.modules.users.crud_cache import set_session


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refreshToken",
        value=refresh_token,
        httponly=True,
        samesite="strict",
        path="/api/v1/auth",
        max_age=(60 * 60 * 24 * settings.jwt_refresh_token_life_day),
    )


# LOGGING: Session issuance with structured logging.
# exclude=(AppError,) -> expected app errors (DatabaseError/CacheError/...) are
# already logged by translate_*_errors and the 503 handlers, so only truly
# unexpected bugs get the catch traceback here (avoids triple-logging).
@logger.catch(
    reraise=True,
    exclude=(AppError,),
    message="Unexpected failure while issuing session",
)
async def issue_session(
    db: AsyncSession, r: aioredis.Redis, user_id: UUID
) -> tuple[str, str]:
    logger.debug("issuing_session", user_id=str(user_id))
    refresh_token, jwt_payload_refresh = create_jwt_token(
        user_id=str(user_id), option="refresh"
    )
    access_token, _ = create_jwt_token(
        user_id=str(user_id),
        option="access",
        session_id=jwt_payload_refresh.sid,
    )
    refresh_token_record = await insert_refresh_token(
        db=db, jwt_payload=jwt_payload_refresh
    )
    await db.commit()
    await set_session(r=r, session=refresh_token_record)
    logger.info(
        "session_issued",
        user_id=str(user_id),
        sid=str(jwt_payload_refresh.sid),
        jti=str(jwt_payload_refresh.jti),
    )
    return refresh_token, access_token
