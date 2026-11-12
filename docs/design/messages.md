# Design — Messages and Files (scope D)

- **Status:** Target design, not built. Open items in §9.
- **Last updated:** 2026-11-11
- **Uses:** `change_log.md` (every write takes a `seq`), `conversations.md` (who may send),
  `relations.md` §5.1 (blocked DMs)

---

## 1. Purpose

What a message is, how it is sent once even when the network drops, how files travel, and what
delete means.

## 2. Message model

**One send = one message**, even with several files of different types (photo + PDF + audio). It is
never split into one message per file. One send is one thing to reply to, react to, delete and
count in the unread badge, and AI agent bots added to groups later fit the same model.

```
messages             id PK (uuid7) · conversation_id · sender_id (NULL for system)
                     seq · type (user | system) · content (text, NULL allowed)
                     parent_message_id (reply) · client_message_id
                     deleted_for_everyone · created_at
message_attachments  message_id · file_id · position          (up to 10, any mix of types)
files                id · uploader_id · object key · size · mime · created_at
message_hidden_for   (message_id, user_id) PK · hidden_at      (delete for me)
message_reactions    message_id · user_id · emoji              UNIQUE (message_id, user_id)
```

| Piece | Rule | Why |
|---|---|---|
| `type` | Who made it: `user` or `system`. Not what is inside. | "Emoji" is just text (the client can show a lone emoji big); a file is an attachment, not a kind of message. Discord's `type` works the same way. |
| Files | Rows in `message_attachments`; each `files` row has its own `mime` | Any mix of types in one message, in order |
| `content` | Text, or NULL when the message is files only, or after delete for everyone | |
| "Text or at least one file" | Checked in the service | It spans two tables; a `CHECK` sees one row only |
| System messages | An event name + small JSON (`member_added`, actor, target), drawn by the client | The client words it ("Bob added Carol") and can translate it; a rename leaves no stale text |
| Bots (later) | A bot is an account (`is_bot`) that joins as a member and sends `user` messages | `sender_id`, membership, the 100-member cap, push and unread need no new paths |
| Replies | `parent_message_id`; threads later | |
| Reactions | One emoji per user per message; same emoji again is a no-op; an empty reaction removes it | |

## 3. Sending once: `clientMessageId`

The server ID stays the real ID. The client also sends `clientMessageId` (a UUID it makes),
unique per sender; a retry with the same key returns the saved message.

Why: Alice sends on a train; the server saves the message but the reply is lost in a tunnel. The
client cannot know it worked and retries. It cannot send "the server's ID" because it never got
it; only an ID made **before** sending survives a lost reply. The same key matches the
"sending..." bubble to the saved message. Slack, Discord and Telegram all do this in some form.

## 4. Limits (proposed)

- Text up to 4,000 characters; up to 10 files per message.
- Common image, video, audio, PDF and office types; executables blocked.
- 25 MB per file (decided): fits everyday office documents; the same as Gmail's attachment limit.

## 5. Files

- Stored in **MinIO** on the laptop (S3 API).
- Upload: the browser uploads straight to MinIO with a short-lived **signed URL**; the API only
  signs the permission and saves the file details. Streaming large uploads through the app would
  tie up workers and memory.

## 6. Delete

| Who deletes | Result |
|---|---|
| The author, "delete for everyone" | Row kept as a placeholder ("message deleted"); `content` set to NULL **and file links removed**; `message.deleted` event with a `seq` |
| Any member, "delete for me" (the author too) | Row in `message_hidden_for`; only that member stops seeing it |

- Delete for everyone also removes the message's reactions (rule from the first design).
- Only the author can delete for everyone in v1 (admin moderation later). No time limit.
- The row is kept so replies, reactions, read receipts and `seq` keep working (ADR-002).
- Delete for me reaches the user's **other** devices by a push `message.hidden` on `user:{id}`
  only. In v1 an offline device keeps showing the message until it reloads the chat.
- History, catch-up, preview and unread add `NOT EXISTS (message_hidden_for ... me)`.

## 7. Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/conversations/{id}/messages` | history (paging: `change_log.md` §8) |
| POST | `/conversations/{id}/messages` | send (`clientMessageId`, text, file ids) |
| DELETE | `/messages/{id}` | delete for everyone (author only) |
| POST | `/messages/{id}/hide` | delete for me (name not final) |
| POST / DELETE | `/messages/{id}/reactions` | react / unreact |
| POST | `/files/uploads` | get a signed upload URL (name not final) |

Sending to a conversation you are not a member of: 403. Send is rate-limited (PRD C-3).

## 8. Today's code differs

Read 2026-11-11, `app/modules/messages/models.py`:

- `MessageType` is `text` / `emoji` / `system` (`:28-31`); target is `user` / `system`.
- `ck_messages_content_unless_deleted` (`:70-73`) forbids NULL content unless deleted; a files-only
  message breaks it, so it must change.
- No `seq`, `client_message_id`, `parent_message_id` columns; index is on `(conversation_id, id)`.
- The comment at `:32` points to `conversations.md` §6, which moved here (§5).

## 9. Open questions

| # | Question | Notes |
|---|---|---|
| 9.1 | Enforcing size and type with a signed URL | A signed PUT may not cap size (not verified for MinIO) |
| 9.2 | Who deletes orphan uploads (uploaded, never attached) | |
| 9.3 | File download (PRD FR-33) | Signed GET URL issued after a membership check; what happens for kicked members and deleted messages |
| 9.4 | Which events create system messages | |
| 9.5 | Limits in §4 | Proposed, not confirmed |
