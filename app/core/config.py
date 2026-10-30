from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    dev_mode: bool

    postgres_username: SecretStr
    postgres_password: SecretStr
    postgres_host: str
    postgres_port: int
    db_name: str

    secret_key_email: SecretStr
    mail_token_salt: SecretStr
    mail_token_life_min: int
    mail_username: SecretStr
    mail_password: SecretStr
    mail_from: str
    mail_port: int
    mail_server: str
    mail_from_name: str

    domain: str
    jwt_secret: SecretStr
    algorithm: str = "HS256"
    jwt_access_token_life_min: int
    jwt_refresh_token_life_day: int

    redis_host: str
    redis_port: int
    redis_password: SecretStr

    request_cool_down: int


# Values are read from .env at runtime; type checkers cannot see that.
settings = Settings()  # pyright: ignore[reportCallIssue]
