import base64
import json
from datetime import datetime
from uuid import UUID

from app.core.errors.exceptions import InvalidCursor


def encode_cursor_time_id(timestamp: datetime, user_id: UUID) -> str:
    raw = json.dumps({"t": timestamp.isoformat(), "id": str(user_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor_time_id(cursor: str) -> tuple[datetime, UUID]:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(data["t"]), UUID(data["id"])
    except Exception:
        raise InvalidCursor() from None


def encode_cursor_uuid(user_id: UUID) -> str:
    return base64.urlsafe_b64encode(str(user_id).encode()).decode()


def decode_cursor_uuid(cursor: str) -> UUID:
    try:
        return UUID(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        raise InvalidCursor() from None
