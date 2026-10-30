# Design — Conversations & Messages

- **Status:** Not implemented (planned) — design only
- **Last updated:** 2026-09-21
- **Related:** ADR-001 (unified conversations), ADR-002 (soft delete), ADR-003 (derived unread), ADR-004 (cursor pagination)

This is the heart of the app. It covers conversations (direct + group), membership and roles, messages, reactions, read receipts, and file attachments.

---

## 1. Purpose

One consistent model for every chat — direct and group — plus the full message feature set.

## 2. Requirements mapping

FR-17..FR-24 (conversations/roles), FR-25..FR-31 (messages), FR-32..FR-33 (files).

## 3. Unified conversations (the big decision)

**There is one `conversations` concept; direct and group are just two *types* of it.**

```
conversations  id, type: direct|group, title, description, created_at
conversation_members  conversation_id, user_id, role: owner|admin|member,
                      joined_at, last_read_message_id, muted (bool / until)
messages       conversation_id, sender_id, type, content, parent_message_id,
               deleted_for_everyone, created_at
message_reactions  message_id, user_id, emoji
files          id, uploader_id, path, size, mime, created_at   (link from a message)
```

- A **direct** conversation is just one whose membership is capped at **2** (both default to role `member`).
- Everything — messages, reactions, read receipts, pagination, mute — is written **once**, for both types. Do not fork the code.
- `system` messages (member joined/left, renamed, invite accepted) are regular messages with `type = 'system'` and no `sender_id` semantics needed beyond the actor.

## 4. Membership & roles (group)

| Role | Can do |
|---|---|
| `member` | read, send, react, leave |
| `admin` | invite, kick members, edit title/description |
| `owner` | admin rights + delete group + promote/demote admins |

Creation rules:

- Group creator → `owner`.
- Promotions/demotions only by `owner`.
- Direct conversations have no owner; both members are `member`.

### Ownership edge cases (decide at implementation)

| Situation | Proposed rule |
|---|---|
| Owner leaves | transfer ownership to the oldest admin, else oldest member, else delete group. |
| Owner deletes group | conversation + its messages soft-marked deleted; members removed. |
| Kick an admin | allowed only by `owner`. |

## 5. Messages

### Types & reply

| Field | Meaning |
|---|---|
| `type` | `text` \| `emoji` \| `file` \| `system` |
| `content` | text or emoji payload; for files, the `file_id` reference |
| `parent_message_id` | reply-to reference (nullable, self-referencing) |

### Ordering & dedupe (ADR-004)

- Server timestamps (`clock_timestamp()`) define order; tie-break by message ID.
- The client **generates the message UUID** before sending. If the socket drops, the client re-sends the same UUID and the server **dedupes** on the unique ID. No double messages.

### Pagination (ADR-004)

```
GET /conversations/{id}/messages?cursor=<last_message_id>&limit=50
  → WHERE conversation_id = ? AND id < cursor ORDER BY id DESC LIMIT 50
```

- Newest first; scroll up by passing the oldest ID you have as the next cursor.
- Never `OFFSET` — it degrades and skips rows when new messages arrive.

### Deletion (ADR-002)

- **Soft delete only**, flag `deleted_for_everyone`.
- On delete, `content` → NULL and a placeholder ("This message was deleted") renders instead.
- The row survives so read receipts, reactions, replies, and ordering stay intact.
- "Delete for me only" is a later extension (`deleted_for` per-user), not the prototype.

### Reactions (FR-28)

- One emoji per user per message: `UNIQUE (message_id, user_id)`.
- Re-reacting with the same emoji is idempotent; an empty reaction removes it.

### Read receipts & unread (FR-30, ADR-003)

- Each member stores `last_read_message_id` on their membership row.
- `POST /conversations/{id}/read {up_to_message_id}` moves that pointer forward.
- **Unread count = messages with `id > last_read_message_id`** — computed, never stored.
- Delivered/read UI: if a message ID is ≤ the recipient's pointer, it's "read".

## 6. Files (FR-32/33)

- `POST /files` multipart upload → metadata row + storage path (local disk; swap to S3/MinIO later via a storage interface).
- Message with `type='file'` references the `file_id`.
- `GET /files/{id}` checks **authentication + membership** in the owning conversation before streaming.

## 7. Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/conversations` | list with preview + unread |
| POST | `/conversations` | create direct (friend) or group |
| GET | `/conversations/{id}` | detail |
| PATCH | `/conversations/{id}` | title/description (admin/owner) |
| DELETE | `/conversations/{id}` | delete group (owner) |
| POST | `/conversations/{id}/invites` | invite (admin/owner) |
| DELETE | `/conversations/{id}/members/{user_id}` | kick (admin/owner) |
| POST | `/conversations/{id}/members/{user_id}/admin` | promote (owner) |
| DELETE | `/conversations/{id}/members/{user_id}/admin` | demote (owner) |
| POST | `/conversations/{id}/leave` | leave |
| POST | `/conversations/{id}/mute` | mute |
| DELETE | `/conversations/{id}/mute` | unmute |
| GET | `/conversations/{id}/messages` | paginated history |
| POST | `/conversations/{id}/messages` | send |
| DELETE | `/messages/{id}` | soft delete |
| POST | `/messages/{id}/reactions` | react |
| DELETE | `/messages/{id}/reactions` | unreact |
| POST | `/conversations/{id}/read` | mark read |

## 8. Rules & edge cases

- A **blocked** user's messages into a conversation they share with the blocker: dropped for the blocker (see relations.md §5).
- Sending into a **frozen** (blocked) direct conversation: rejected for the blocker, dropped for the blocked.
- Sending to a conversation you're not a member of: 403.
- Message send is rate-limited (C-3).
- Deleting a message also removes its reactions but keeps the row.

## 9. Open questions / decisions

- D-1 (unfriend DM rule) is the only open behavioral decision affecting this module.
- Threads (reply trees) are a later feature; replies-as-parent-reference already give us the data.