from time import time
from typing import Literal
from uuid import uuid7

import jwt
from fastapi.security import OAuth2PasswordBearer
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import BadSignature, SignatureExpired
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from loguru import logger
from pwdlib import PasswordHash
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import AppError, ExpiredToken, InvalidToken


class JWTPayload(BaseModel):
    jti: str
    sid: str
    sub: str
    iat: int
    exp: int
    type: Literal["access", "refresh"]


# Password exception: UnknownHashError
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hash_password: str) -> bool:
    result = password_hash.verify(plain_password, hash_password)
    # LOGGING: Log failure only (never log passwords). Identity is logged at router level.
    if not result:
        logger.warning("password_verification_failed")
    return result


# Email verification
serializer = URLSafeTimedSerializer(settings.secret_key_email.get_secret_value())


def create_url_safe_token(email: str, salt: str) -> str:
    token = serializer.dumps(email, salt=salt)
    return token


def verify_url_safe_token(token: str, salt: str, max_age_seconds: int) -> str:
    try:
        email = serializer.loads(token, salt=salt, max_age=max_age_seconds)
    # LOGGING: Security-relevant events - distinguish expired vs forged/bad token
    except SignatureExpired as e:
        logger.warning("email_token_expired")
        raise ExpiredToken from e
    except BadSignature as e:
        logger.warning("email_token_invalid_signature")
        raise InvalidToken from e

    return email


# JWT

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_jwt_token(
    jwt_token: str,
    secret: str = settings.jwt_secret.get_secret_value(),
    algorithm: str = settings.algorithm,
) -> JWTPayload:
    # LOGGING: Never log the raw token - only the failure reason (+ jti/sid when decodable)
    try:
        decoded_payload = jwt.decode(jwt_token, key=secret, algorithms=[algorithm])
        return JWTPayload(**decoded_payload)
    except ExpiredSignatureError as e:
        logger.warning("jwt_expired", jti=_safe_claim(jwt_token, "jti"))
        raise ExpiredToken from e
    except InvalidTokenError as e:
        logger.warning("jwt_invalid", reason=type(e).__name__)
        raise InvalidToken from e
    except ValidationError as e:
        logger.warning("jwt_payload_invalid", reason=type(e).__name__)
        raise InvalidToken from e


def _safe_claim(jwt_token: str, claim: str) -> str | None:
    """LOGGING helper: read an unverified claim for debugging without validating.

    Used only to enrich logs (e.g. jti of an expired token). Never trust this
    value for authorization decisions.
    """
    try:
        data = jwt.decode(
            jwt_token,
            key="",
            algorithms=[settings.algorithm],
            options={"verify_signature": False},
        )
        value = data.get(claim)
        return str(value) if value is not None else None
    except Exception:
        return None


def create_jwt_token(
    user_id: str, option: Literal["access", "refresh"], session_id: str | None = None
):
    if option == "access":
        if session_id is None:
            raise AppError("Session ID must be provided for access token.")
        exp = int(time() + settings.jwt_access_token_life_min * 60)
        sid = session_id
    elif option == "refresh":
        exp = int(time() + settings.jwt_refresh_token_life_day * 3600 * 24)
        sid = str(uuid7())
    else:
        raise AppError("Invalid token type")
    iat = int(time())
    jti = uuid7()

    to_encode = JWTPayload(
        jti=str(jti),
        sid=sid,
        sub=str(user_id),
        iat=iat,
        exp=exp,
        type=option,
    )

    encoded = jwt.encode(
        payload=to_encode.model_dump(mode="json"),
        key=settings.jwt_secret.get_secret_value(),
        algorithm=settings.algorithm,
    )
    return encoded, to_encode
