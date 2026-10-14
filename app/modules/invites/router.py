"""HTTP endpoints for the invites feature."""

from fastapi import APIRouter

router = APIRouter(prefix="/invites", tags=["invites"])
