from time import time
from typing import Literal
from uuid import UUID, uuid7

import jwt
from fastapi.security import OAuth2PasswordBearer
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import BadSignature, SignatureExpired
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
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
    return password_hash.verify(plain_password, hash_password)


# Email verification
serializer = URLSafeTimedSerializer(settings.secret_key_email.get_secret_value())


def create_url_safe_token(email: str, salt: str) -> str:
    token = serializer.dumps(email, salt=salt)
    return token


def verify_url_safe_token(token: str, salt: str, max_age_seconds: int) -> str:
    try:
        email = serializer.loads(token, salt=salt, max_age=max_age_seconds)
    except SignatureExpired as e:
        raise ExpiredToken from e
    except BadSignature as e:
        raise InvalidToken from e

    return email


# JWT

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_jwt_token(
    jwt_token: str,
    secret: str = settings.jwt_secret.get_secret_value(),
    algorithm: str = settings.algorithm,
) -> JWTPayload:
    try:
        decoded_payload = jwt.decode(jwt_token, key=secret, algorithms=[algorithm])
        return JWTPayload(**decoded_payload)
    except ExpiredSignatureError as e:
        raise ExpiredToken from e
    except InvalidTokenError as e:
        raise InvalidToken from e
    except ValidationError as e:
        raise InvalidToken from e


def create_jwt_token(
    user_id: UUID, option: Literal["access", "refresh"], session_id: str | None = None
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
