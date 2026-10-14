from typing import Generic, TypeVar

from pydantic import BaseModel, Field

# class ErrorResponse(BaseModel):
#     status: int  # HTTP status code
#     error: str  # Error short description
#     message: str  # Details
#     path: str  # Path to the endpoint
#     timestamp: str

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    message: str | None = Field(default=None)
    data: T | None = Field(default=None)
