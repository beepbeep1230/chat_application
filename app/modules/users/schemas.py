from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


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
