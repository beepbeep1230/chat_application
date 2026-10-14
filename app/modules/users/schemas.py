from datetime import datetime
from string import punctuation
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)
    username: str = Field(max_length=30)
    email: EmailStr = Field(max_length=320)
    password: str
    password_repeated: str

    @field_validator("password")
    @classmethod
    def check_password(cls, value):
        if len(value) < 8 or len(value) > 30:
            raise ValueError("Password must contain 8 to 30 characters.")
        if not (
            any(c.isupper() for c in value)
            and any(c.isdigit() for c in value)
            and any(c in punctuation for c in value)
        ):
            raise ValueError(
                "Password must contain lowercase, uppercase, digit and punctuation."
            )
        return value

    @model_validator(mode="after")
    def check_passwords_match(self):
        pw1 = self.password
        pw2 = self.password_repeated
        if pw1 is not None and pw2 is not None and pw1 != pw2:
            raise ValueError("Passwords do not match")
        return self


class UserLogin(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)
    identifier: str
    password: str = Field(min_length=8, max_length=30)


class UserProfileBase(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)
    display_name: str | None = Field(default=None, max_length=30)
    bio: str | None = Field(default=None, max_length=200)
    avatar_url: str | None = Field(default=None, max_length=500)


class UserProfileResponse(UserProfileBase):
    model_config = ConfigDict(
        validate_by_name=True, from_attributes=True, alias_generator=to_camel
    )
    username: str = Field(max_length=30)
    created_at: datetime
    updated_at: datetime


class UserUpdateProfileRequest(UserProfileBase):
    model_config = ConfigDict(validate_by_name=True)


class TokenResponse(BaseModel):
    model_config = ConfigDict(validate_by_name=True, alias_generator=to_camel)
    access_token: str
    token_type: str = "bearer"
