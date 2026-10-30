# Design — Notifications

- **Status:** Not implemented (planned) — design only
- **Last updated:** 2026-09-21
- **Related:** ADR-003 (derived unread), ADR-005 (event-only notification rows)

---

## 1. Purpose

Decide what "notification" means, and make it cheap. This is the module people usually over-build.

## 2. Requirements mapping

FR-34..FR-36, FR-24 (mute), C-3.

## 3. The core idea: three different things

"Notifications" are three separate concerns. Do not merge them:

| Concern | What it is | Storage |
|---|---|---|
| **Unread badge** | "4 unread" counters | **Derived** from `last_read_message_id` — no rows |
| **Event feed** | the bell list / inbox | `notifications` rows (events only) |
| **Push alert** | mobile lock-screen buzz | out of scope (API-only) — designed for later |

The rule that keeps this fast:

> A new **message** creates **no** notification row. Only discrete **events** do.

## 4. Events that become notification rows

| `type` | Example scenario | Payload (JSONB) |
|---|---|---|
| `friend_request` | Alice requests Bob | `{request_id, from_user}` |
| `friend_request_accepted` | Bob accepts | `{user_id}` |
| `group_invite` | Alice invites Bob to a group | `{invite_id, conversation_id, from_user}` |
| `reaction` | Alice reacts to Bob's message | `{message_id, conversation_id, emoji, from_user}` |
| `mention` | someone @mentions you | `{message_id, conversation_id, sender}` |

Deferred (nice later): system/proximity events, "new message in a chat you muted" as an inbox tile.

## 5. Lifecycle

```
Event happens
  → 1 notifications row (recipient_id, type, actor_id, payload, read_at=NULL, created_at)
  → if recipient ONLINE: push the event over WebSocket
      (alert sound/emphasis unless the conversation is muted)
  → feed paginates newest-first: GET /notifications?cursor=&limit=

Message arrives (NOT an event)
  → no row
  → online recipient: pushed live; offline: caught up on reconnect via last-read pointer
  → badge count derived on demand
```

## 6. Muting (FR-24, FR-35)

- Stored **per conversation, per member** on the membership row (`muted: bool` / `muted_until`).
- Muted conversation:
  - still increments the unread badge (mute ≠ ignore),
  - suppresses push alerts and mention notifications,
  - appears lower in the chat list (optional ordering tweak).
- The user can mute each conversation independently from `/conversations/{id}/mute`.

## 7. Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/notifications?cursor=` | event feed, newest first, cursor-paginated |
| POST | `/notifications/{id}/read` | mark one read |
| POST | `/notifications/read-all` | mark all read |
| POST | `/conversations/{id}/mute` | mute conversation (mute lives here) |
| DELETE | `/conversations/{id}/mute` | unmute |

## 8. Rules & edge cases

- A notification is per-recipient; `read_at` marks it read.
- Events from **blocked** users never create rows (auto-rejected upstream, relations.md §5).
- Feed is paginated like messages — same cursor pattern (ADR-004).
- When a conversation is deleted, related notifications are soft-purged (or left as dead links — decide at implementation; lean: keep rows, render without deep link).

## 9. Future (not today)

- Global notification *settings table* (e.g. mute-everything, quiet hours).
- Mobile push requires a `device_tokens` table + FCM/APNs integration (PRD: out of scope).