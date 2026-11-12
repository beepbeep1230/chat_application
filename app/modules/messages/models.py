"""SQLAlchemy models for the messages feature.

Import every model defined in this module (directly or indirectly) so Alembic
autogenerate can discover it through ``app.core.infra.database.Base.metadata``.
"""

import enum

from sqlalchemy import (
    Enum,
)


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
