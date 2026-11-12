# Design — Conversations, Membership and Read State (scope F)

- **Status:** Target design, not built. Open items in §8.
- **Last updated:** 2026-11-11
- **Uses:** `messages.md` (what is sent), `change_log.md` (`seq`, resync), `notifications.md`
  (the bell), `relations.md` (friends, blocks, invites)
- **Related ADRs:** ADR-001 (unified conversations), ADR-003 (derived unread)

---

## 1. Purpose

One model for every chat, direct and group: who is in it, what each member may do, and how far
each member has read.

## 2. Requirements mapping

FR-17..FR-24 (conversations, roles, mute), FR-30 (read state). Messages and files: `messages.md`.

## 3. Unified conversations

**There is one `conversations` concept; direct and group are two *types* of it.**

```
conversations         id · type (direct | group) · title · description · last_seq · created_at
conversation_members  conversation_id · user_id · role (owner | admin | member)
                      joined_at · last_read_seq · muted (bool / until)
```

- A **direct** conversation is one whose membership is capped at **2** (both role `member`).
- A group has at most **100 members**.
- Everything (messages, reactions, read state, paging, mute) is written **once** for both types.
  Do not fork the code.
- `last_seq` is the `seq` counter (`change_log.md` §3).

## 4. Membership and roles (group)

| Role | Can do |
|---|---|
| `member` | read, send, react, leave |
| `admin` | invite, kick members, edit title/description |
| `owner` | admin rights + delete group + promote/demote admins |

- Group creator → `owner`. Promotions/demotions only by `owner`. Kicking an admin: `owner` only.
- Direct conversations have no owner; both members are `member`.
- Membership changes write an event (`change_log.md` §5) and a system message (`messages.md` §2;
  which events: open there).

## 5. Read state and unread

- Each member stores `last_read_seq` on the membership row.
- **Unread count** (computed, never stored):
  `COUNT(messages WHERE seq > last_read_seq AND sender_id <> me AND not deleted AND not hidden for me)`.
  "Hidden for me" covers delete-for-me (`messages.md` §6) and blocked DMs (`relations.md` §5.1).
- Not `last_seq - last_read_seq`: deletes and reactions take numbers too.
- The badge is capped at **99+**.

**Proposed:**

- Count on demand with the index `messages (conversation_id, seq)`. A stored counter per member
  (Discord, WeChat style) is the later option if the chat list gets slow. No extra write per message.
- Mark as read: `POST /conversations/{id}/read {upToSeq}` sets
  `last_read_seq = GREATEST(last_read_seq, :seq)`, then publishes `read.updated` on the user's own
  channel. `GREATEST` stops a slower device moving the pointer backward; the push clears the badge
  on the user's other devices.
- Sending a message also moves the sender's own `last_read_seq` to that `seq`, so your own
  messages never count as unread.

## 6. Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/conversations` | list: `last_seq`, unread (99+), preview, `last_activity_at` |
| POST | `/conversations` | create direct (friend) or group |
| GET | `/conversations/{id}` | detail |
| PATCH | `/conversations/{id}` | title/description (admin/owner) |
| DELETE | `/conversations/{id}` | delete group (owner) |
| POST | `/conversations/{id}/invites` | invite (admin/owner; `relations.md` §6) |
| DELETE | `/conversations/{id}/members/{user_id}` | kick (admin/owner) |
| POST / DELETE | `/conversations/{id}/members/{user_id}/admin` | promote / demote (owner) |
| POST | `/conversations/{id}/leave` | leave |
| POST / DELETE | `/conversations/{id}/mute` | mute / unmute |
| POST | `/conversations/{id}/read` | mark read (§5) |
| GET | `/conversations/{id}/events?after=N` | catch-up (`change_log.md` §6) |

## 7. Today's code differs

The conversation and membership models are stubs; `last_read_message_id` from the first design
becomes `last_read_seq`. Not re-checked against the stub code in this round.

## 8. Open questions

| # | Question | Notes |
|---|---|---|
| 8.1 | Read receipts in groups | What "seen" shows with up to 100 readers |
| 8.2 | What a kicked member can still see | History up to the kick? Files? |
| 8.3 | DM after unfriend (PRD D-1) | Proposed in the PRD: history stays readable; sending disabled until friends again |
| 8.4 | Group lifecycle | Owner leaves (first proposal: oldest admin, else oldest member, else delete the group); owner deletes the group (first proposal: conversation and its messages soft-marked deleted, members removed; still open: what members, sockets and the change log see) |
| 8.5 | Mute vs live socket pushes | Decided already: a muted chat still counts in the badge and gets no alerts or mention notifications (`notifications.md` §6) |
| 8.6 | Proposed rows in §5 | Count on demand, mark-as-read, own messages |
