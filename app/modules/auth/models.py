from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.infra.database import Base

if TYPE_CHECKING:
    from app.modules.users.models import UserAccount


class UserRefreshToken(Base):
    """
    Store the refresh token, mainly checking the session id,
    reject the access token has the session id which matchs revoked token's session id.
    """

    __tablename__ = "user_session"

    jti: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    sid: Mapped[UUID] = mapped_column(Uuid, unique=True, index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("user_account.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # issued_at: Mapped[datetime] = mapped_column(
    #     DateTime(timezone=True), nullable=False
    # )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # NULL = active; set on logout or rotation. Row is kept (not deleted):
    # presenting a revoked token later is a theft signal -> revoke all sessions.

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    account: Mapped[UserAccount] = relationship(
        back_populates="refresh_tokens", lazy="raise"
    )
