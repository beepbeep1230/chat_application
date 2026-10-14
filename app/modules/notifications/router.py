"""HTTP endpoints for the notifications feature."""

from fastapi import APIRouter

router = APIRouter(prefix="/notifications", tags=["notifications"])
