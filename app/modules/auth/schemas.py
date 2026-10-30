from string import punctuation
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel


class UserIdentifier(BaseModel):
    username: str = Field(
        min_length=5, max_length=30, pattern=r"^[A-Za-z0-9_.-]{5,30}$"
    )
    email: EmailStr = Field(max_length=320)


class UserCreateRequest(UserIdentifier):
    model_config = ConfigDict(alias_generator=to_camel)
    password: str
    password_repeated: str

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        if len(value) < 8 or len(value) > 30:
            raise ValueError("Password must contain 8 to 30 characters.")
        if not (
            any(c.isupper() for c in value)
            and any(c.islower() for c in value)
            and any(c.isdigit() for c in value)
            and any(c in punctuation for c in value)
        ):
            raise ValueError(
                "Password must contain lowercase, uppercase, digit and punctuation."
            )
        return value

    @model_validator(mode="after")
    def check_passwords_match(self) -> Self:
        # Both fields are required str, so neither can be None here.
        if self.password != self.password_repeated:
            raise ValueError("Passwords do not match")
        return self


class UserCreatedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str
    email: EmailStr


class UserVerifiedResponse(UserCreatedResponse):
    pass


class UserLogin(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)
    identifier: str
    password: str = Field(min_length=8, max_length=64)


class TokenResponse(BaseModel):
    model_config = ConfigDict(validate_by_name=True, alias_generator=to_camel)
    access_token: str
    token_type: str = "bearer"
