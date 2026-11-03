"""SQLAlchemy models for the messages feature.

Import every model defined in this module (directly or indirectly) so Alembic
autogenerate can discover it through ``app.core.infra.database.Base.metadata``.
"""

import enum
from datetime import datetime
from uuid import UUID, uuid7

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.infra.database import Base


class MessageType(str, enum.Enum):
    TEXT = "text"
    EMOJI = "emoji"
    SYSTEM = "system"
    # FILE = "file" — later, together with the files table (conversations.md §6)


# Stored as lowercase values ("text") instead of member names ("TEXT").
MESSAGE_TYPE = Enum(
    MessageType,
    name="message_type",
    values_callable=lambda e: [str(m.value) for m in e],
)


class Messages(Base):
    """One message in a conversation (direct or group — ADR-001)."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    # NULL for system messages, and after the sender's account is deleted
    # (the message stays so the conversation history keeps its shape).
    sender_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("user_account.uuid", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[MessageType] = mapped_column(
        MESSAGE_TYPE, default=MessageType.TEXT, nullable=False
    )
    # NULL only after "delete for everyone" (ADR-002).
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_for_everyone: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "deleted_for_everyone OR content IS NOT NULL",
            name="ck_messages_content_unless_deleted",
        ),
        # History page: WHERE conversation_id = ? AND id < cursor ORDER BY id DESC
        Index("ix_messages_conversation_id_id", "conversation_id", "id"),
    )
