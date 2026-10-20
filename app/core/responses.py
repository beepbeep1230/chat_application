from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    message: str | None = Field(default=None)
    data: T | None = Field(default=None)
