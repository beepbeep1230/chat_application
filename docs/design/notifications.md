# Design — Notifications (scope F)

- **Status:** Target design, not built.
- **Last updated:** 2026-11-11
- **Uses:** `conversations.md` §5 (unread badge), `fanout.md` (live delivery), `relations.md`
  (blocked users)
- **Related ADRs:** ADR-003 (derived unread), ADR-005 (event-only notification rows)

---

## 1. Purpose

Decide what "notification" means, and keep it cheap. This is the module people usually over-build.

## 2. Requirements mapping

FR-34..FR-36, FR-24 (mute).

## 3. Three different things

| Concern | What it is | Storage |
|---|---|---|
| **Unread badge** | "4 unread" per chat | **Derived** from `last_read_seq` (`conversations.md` §5), no rows |
| **Bell** (event feed) | the notification list | `notifications` rows, events only |
| **Push alert** | lock-screen buzz | Web Push later; mobile push with the v2 app |

> A new **message** creates **no** notification row. Only discrete **events** do.

## 4. Events that become rows

| `type` | Example | Payload (JSONB) |
|---|---|---|
| `friend_request` | Alice requests Bob | `{request_id, from_user}` |
| `friend_request_accepted` | Bob accepts | `{user_id}` |
| `group_invite` | Alice invites Bob | `{invite_id, conversation_id, from_user}` |
| `reaction` | Alice reacts to Bob's message | `{message_id, conversation_id, emoji, from_user}` |
| `mention` | someone @mentions you | `{message_id, conversation_id, sender}` |

## 5. Lifecycle

```
Event happens
  -> 1 notifications row (recipient_id, type, actor_id, payload, read_at = NULL, created_at)
  -> live: notification.created on user:{recipient} (fanout.md)
  -> after being offline: GET /notifications?cursor=...  (newest first)

Message arrives (not an event)
  -> no row; badge derived on demand; catch-up through the change log (change_log.md §6)
```

## 6. Muting

- Stored per conversation, per member, on the membership row (`muted` / `muted_until`).
- A muted chat still counts in the unread badge (mute is not ignore).
- A muted chat suppresses alerts and mention notifications (PRD FR-24, FR-35).
- Whether a muted chat still gets live socket pushes: open (`conversations.md` §8.5).

## 7. Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/notifications?cursor=` | bell feed, newest first, cursor-paged |
| POST | `/notifications/{id}/read` | mark one read |
| POST | `/notifications/read-all` | mark all read |

Mute lives on the conversation: `conversations.md` §6.

## 8. Rules

- A notification is per recipient; `read_at` marks it read.
- Events from **blocked** users never create rows (rejected upstream, `relations.md` §5).
- When a conversation is deleted, related rows stay and render without a deep link (lean; decide
  with `conversations.md` §8.4).

## 9. Later

- A notification settings table (mute everything, quiet hours).
- Mobile push needs a `device_tokens` table + FCM/APNs (v2).
