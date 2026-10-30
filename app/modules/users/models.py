from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid7

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

# from uuid_extension import UUID7, uuid7
from app.core.infra.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import UserRefreshToken


class AccountStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    ACTIVE = "active"
    SUSPENDED = "suspended"


def _enum_values(enum_class: type[enum.Enum]) -> list[str]:
    return [str(member.value) for member in enum_class]


# Stored as lowercase values ("unverified") instead of member names ("UNVERIFIED").
ACCOUNT_STATUS = Enum(
    AccountStatus,
    name="account_status",
    values_callable=_enum_values,
)


class UserAccount(Base):
    """Private side: credentials + auth state. Never shown to other users."""

    __tablename__ = "user_account"

    uuid: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    username: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        ACCOUNT_STATUS, default=AccountStatus.UNVERIFIED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    profile: Mapped[UserProfile] = relationship(
        back_populates="account",
        cascade="save-update, merge, expunge, delete, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
    refresh_tokens: Mapped[list[UserRefreshToken]] = relationship(
        back_populates="account",
        cascade="save-update, merge, expunge, delete, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )


class UserProfile(Base):
    """Public side: what other users may see, via explicit API schemas only."""

    __tablename__ = "user_profile"

    username: Mapped[str] = mapped_column(
        CITEXT,
        ForeignKey("user_account.username", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Presence heartbeat (not login state): set on socket connect/disconnect and
    # throttled to ~1 update/min app-side, so we don't UPDATE on every message.
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    account: Mapped["UserAccount"] = relationship(  # noqa
        back_populates="profile", lazy="raise"
    )
