import redis.asyncio as aioredis
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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


async def issue_session(
    db: AsyncSession, r: aioredis.Redis, user_id: str
) -> tuple[str, str]:
    refresh_token, jwt_payload_refresh = create_jwt_token(
        user_id=user_id, option="refresh"
    )
    access_token, _ = create_jwt_token(
        user_id=user_id,
        option="access",
        session_id=jwt_payload_refresh.sid,
    )
    refresh_token_record = await insert_refresh_token(
        db=db, jwt_payload=jwt_payload_refresh
    )
    await db.commit()
    await set_session(r=r, session=refresh_token_record)
    return refresh_token, access_token
