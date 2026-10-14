"""API v1 router.

Aggregates every feature module's router under a single ``/api/v1`` prefix.
Each module owns its own ``prefix`` and ``tags``; this file only wires them in.
"""

from fastapi import APIRouter

from app.modules.invites.router import router as invites_router
from app.modules.messages.router import router as messages_router
from app.modules.notifications.router import router as notifications_router
from app.modules.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(users_router)
api_router.include_router(messages_router)
api_router.include_router(notifications_router)
api_router.include_router(invites_router)
