# ADR-003: Derived Unread Badges (No Per-Message Read Rows)

- **Status:** Accepted
- **Date:** 2026-09-21
- **Owner:** [you]

## Context

"Unread count" and "read receipts" can be implemented per-message (a `message_reads(user, message, read_at)` row for every read) or as a per-member pointer. Writing a row per message per reader is a write-amplification nightmare and gives chat apps more data than they use.

## Decision

Each membership row tracks **one pointer**: `last_read_message_id`. Unread count is **derived** — `COUNT(messages WHERE conversation_id = ? AND id > last_read_message_id)` — computed on demand, never stored as rows. An ack endpoint (`POST /conversations/{id}/read {up_to_message_id}`) moves the pointer forward.

## Consequences

- **Positive:** O(1) writes per read instead of O(messages); unread badges and "delivered/read" state free; easy multi-device sync.
- **Negative:** no per-message read timestamps (nobody needs them in the prototype); unread counts are approximate while a user is mid-conversation (acceptable).
- **Neutral:** read state is per-conversation, not per-message.

## References

- `docs/design/conversations.md` §5, `docs/design/notifications.md` §3