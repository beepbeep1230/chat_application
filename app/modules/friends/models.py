from datetime import datetime
from uuid import UUID, uuid7

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.infra.database import Base


class FriendRequest(Base):
    """Pending friend requests only. Declined/cooldown state lives in Redis."""

    __tablename__ = "friend_requests"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    requester_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("user_account.uuid", ondelete="CASCADE"), nullable=False
    )
    addressee_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("user_account.uuid", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "requester_id <> addressee_id", name="ck_friend_request_not_self"
        ),
        Index(
            "uq_friend_request_pair",
            text("LEAST(requester_id, addressee_id)"),
            text("GREATEST(requester_id, addressee_id)"),
            unique=True,
        ),
        Index("ix_friend_request_addressee", "addressee_id", "id"),
        Index("ix_friend_request_requester", "requester_id", "id"),
    )


class FriendLists(Base):
    __tablename__ = "friends_lists"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_account.uuid", ondelete="CASCADE"), primary_key=True
    )
    friend_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_account.uuid", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("user_id <> friend_id", name="ck_friend_not_self"),
        Index("ix_friends_friend_id", "friend_id"),
    )


class UserBlockLists(Base):
    __tablename__ = "user_block_lists"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_account.uuid", ondelete="CASCADE"), primary_key=True
    )
    blocked_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_account.uuid", ondelete="CASCADE"), primary_key=True
    )
    blocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        CheckConstraint("user_id <> blocked_user_id", name="ck_blocked_user_not_self"),
        Index("ix_user_block_lists_blocked_user_id", "blocked_user_id"),
    )
