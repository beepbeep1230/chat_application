"""HTTP endpoints for the messages feature."""

from fastapi import APIRouter

router = APIRouter(prefix="/messages", tags=["messages"])
