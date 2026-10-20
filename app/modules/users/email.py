# Send verification via Email
from pathlib import Path

from fastapi_mail import (
    ConnectionConfig,
    FastMail,
    MessageSchema,
    MessageType,
)
from pydantic import EmailStr

from app.core.config import settings
from app.core.exceptions import ExpiredToken, InvalidToken  # LOGGING: for catch exclude
from app.core.logging import logger  # LOGGING: Import logger
from app.core.security import create_url_safe_token, verify_url_safe_token

BASE_DIR = Path(__file__).resolve().parents[3]


conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username.get_secret_value(),
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_FROM_NAME=settings.mail_from_name,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(BASE_DIR, "templates"),
)


# LOGGING: Catch and log email sending failures
@logger.catch(reraise=True, message="Failed to send verification email")
async def send_verification_mail(username: str, email: EmailStr, subject: str):

    fastapi_mail = FastMail(config=conf)
    token = create_url_safe_token(
        email=email, salt=settings.mail_token_salt.get_secret_value()
    )
    link = f"http://{settings.domain}/api/v1/auth/verify-email?token={token}"
    message = MessageSchema(
        recipients=[email],
        subject=subject,
        template_body={"username": username, "link": link, "expiration_minutes": 15},
        subtype=MessageType.html,
    )
    await fastapi_mail.send_message(message=message, template_name="verify_email.html")
    # LOGGING: Log successful email send (avoid logging token/link)
    logger.info("verification_email_sent", email=str(email), username=username)


# LOGGING: Catch unexpected errors only. Expected auth errors
# (ExpiredToken/InvalidToken) are already logged in security.verify_url_safe_token
# and answered by unauthorized_handler, so excluding them avoids double-logging.
@logger.catch(
    reraise=True,
    exclude=(ExpiredToken, InvalidToken),
    message="Unexpected failure while verifying email token",
)
def verify_verification(url_token: str):
    decode_email = verify_url_safe_token(
        token=url_token,
        salt=settings.mail_token_salt.get_secret_value(),
        max_age_seconds=settings.mail_token_life_min * 60,
    )
    logger.debug("email_token_verified", email=decode_email)
    return decode_email
