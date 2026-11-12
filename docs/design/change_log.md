# Design — Change Log, Order and Catch-up (scope C)

- **Status:** Target design, not built. Open items in §9.
- **Last updated:** 2026-11-11
- **Uses:** `messages.md` (what a message is), `fanout.md` (how pushes travel), `relations.md` §5.1
  (hidden DM messages add one filter here)

---

## 1. Purpose

Give every conversation one true order, and let a client that missed pushes (sleep, Wi-Fi drop,
Redis restart) find out exactly what changed, without reloading everything.

## 2. Mailbox and doorbell

Postgres is the **mailbox**: every change is saved there first. A push (`fanout.md`) is only the
**doorbell**: "something changed in chat X". A doorbell can be missed; the client then reads the
mailbox using the change number. So pushes never need to be reliable.

The server is the source of truth and keeps history (like Slack, Discord, Telegram cloud chats),
unlike WhatsApp, where the phone keeps history and the server deletes delivered messages. A
browser can lose its storage and a user can log in from a new browser, so the server must keep it.

There is no per-user inbox table: the change log per conversation plus `last_read_seq` on the
membership row (`conversations.md` §5) are enough.

## 3. `seq`: one number per change

Every change in a conversation (message sent, deleted, reaction, member added...) gets the next
number in that conversation: 1, 2, 3...

```sql
-- first statement of the write transaction
UPDATE conversations SET last_seq = last_seq + 1 WHERE id = :id RETURNING last_seq;
```

- The `UPDATE` locks the conversation row until COMMIT. Under Read Committed (the default; the app
  sets no other level) a second writer to the same chat **waits**, then gets the next number. No
  error, no retry loop.
- Take the counter lock **first** and keep the transaction short.
- Inserting a message (foreign key to `conversations`) only takes a `KEY SHARE` lock, which does
  not conflict with this `UPDATE` (it does not change a key column). Only other `UPDATE`s of the
  same row (e.g. a rename) wait.
- `messages.seq` is copied from its event row. `id` stays the primary key (replies, reactions and
  URLs point at it); `seq` is the position in the chat.

**Why `seq` and not the message `id`.** `id` is a `uuid7` made in Python **before** commit, so `id`
order is not commit order:

```
t1  Worker A: Bob's message gets id AAA (earlier time)
t2  Worker B: Carol's message gets id BBB (later, larger)
t3  Worker B: COMMIT
t4  Alice reads, sets last_read = BBB
t5  Worker A: COMMIT  (A was slow)
    unread = COUNT(id > BBB) = 0  -> Bob's message counted as read, never seen
```

With `seq`: A takes 42 and holds the lock; B waits and gets 43 only after A commits. Once 43 is
visible, 42 is already visible, so nothing can appear behind a pointer later. (Traced from the
code, not run.)

| | `id` | `seq` |
|---|---|---|
| Late commit | Can slip under the pointer | Cannot |
| Spot a missed push | No | Yes (41 -> 43) |
| One pointer for unread, catch-up, read receipts | No | Yes |
| Cost on send | Free | One row lock per conversation; sends to one chat run one at a time |

## 4. Lock waits and stuck transactions

Postgres waits for a lock **forever** by default. With 10 pool connections per worker:

```
t0   Alice's send takes the lock, then gets stuck (slow disk, a bug that awaits inside the transaction)
t1   Bob sends to the same group      -> pool connection 1, waits on the lock
t2   ... 9 more sends to that group   -> connections 2-10, all waiting
t3   Carol opens a different chat     -> no free connection -> waits for the pool
     -> one stuck chat froze the whole worker for every user
```

| Setting | Value (a setting) | What it stops |
|---|---|---|
| `lock_timeout` | 2 s | A **waiter** gives up -> `55P03` -> 503 (`app/core/errors/translators.py:42`) -> the connection returns to the pool. The client retries with the same `clientMessageId`; nothing was committed, so nothing is saved twice. |
| `statement_timeout` | ~5 s | A query that runs too long, including the lock **holder** |
| `idle_in_transaction_session_timeout` | ~10 s | A holder that sits idle inside an open transaction |

Why 2 s: the lock is held for insert message + insert event + read up to 100 members + commit, a
few milliseconds (estimate, not measured). At 5 ms each, 2 s lets ~400 sends queue ahead, far more
than a 100-member group sends at once, so it only fires when something is broken. Load tests will
tune it. `lock_timeout` only covers waiters; the other two end the holder.

**Where they live (decided 2026-11-11):** once on the app engine (asyncpg `server_settings`), with
the values in `Settings`. No per-module values: plain reads never wait on row locks, and under
load requests wait for the pool and CPU, not for locks, so a longer limit would only hold
connections longer. A background job that needs more time uses `SET LOCAL` inside its own
transaction. Alembic builds its own engine (`alembic/env.py:81`), so app settings do not reach
migrations.

## 5. Event rows

- App code writes them, not DB triggers: one helper bumps the counter, inserts the event row and
  returns `seq`, inside the service's transaction. The logic stays visible, testable and easy to
  change.
- An event row holds **IDs only**: `seq`, `type`, `message_id` / target id. Catch-up joins
  `messages` by primary key, so content lives in one place and a delete is correct in catch-up
  without scrubbing a copy. History reads `messages`, not the event table.

## 6. Catch-up: `GET /conversations/{id}/events?after=N`

- Returns the events after `N` **and** `upTo` (the conversation's current `last_seq`). The client
  moves its position to `upTo`, not to the last event it got. Reason: a hidden DM message
  (`relations.md` §5.1) leaves a hole in the blocker's sequence; without `upTo` the client would
  re-fetch that hole forever. It also covers any future skipped number.
- A client older than the kept log (30 days) does a full reload instead.
- **Retention (decided 2026-11-11):** a small script run nightly by cron or a systemd timer, outside
  the web workers, deletes event rows older than 30 days in batches of ~5,000, each batch with its
  own longer `SET LOCAL statement_timeout`. Event rows get a `created_at` column for this.
- **Proposed (paused with §9.2):** "too old" vs "nothing new": if `after < last_seq` and event
  `after + 1` is already deleted, answer 410 `EVENTS_EXPIRED` and the client reloads the chat; an
  up-to-date client (`after == last_seq`) gets an empty 200.
- A gap while connected (41, then 43) also triggers a fetch.

## 7. Resync

One routine, run when (1) the socket reconnects, (2) the server sends `resync` after its own Redis
subscription reconnects (`fanout.md`), (3) the tab becomes visible. A timer only if testing shows
it is needed.

1. `GET /conversations`: each row has `last_seq`, unread count (capped 99+), last message
   preview, `last_activity_at` for sorting. This also shows chats joined or left while offline.
2. `events?after=` for the **active chat** only (the one conversation the user has open). Sidebar
   rows get no message fetch; a chat loads its history when entered.

**Live sidebar badges.** While connected, a `message.created` push for a non-active chat updates
its preview and adds 1 to its badge locally (not for your own messages). A push whose `seq` is not
above the row's known `last_seq` is ignored (no double count after a resync). `read.updated` sets
the badge from the server.

**Lost publish.** A publish that never happens (crash between commit and publish) is accepted in
v1: the client heals through a `seq` gap or the next resync. A transactional outbox is the later
fix if needed.

## 8. History

- **Proposed:** history is paged by `seq` instead of `id`, index `messages (conversation_id, seq)`.
  One sort order for history, catch-up and unread.
- Never `OFFSET`; cursor paging as in ADR-004 point 1.

## 9. Open questions

Paused on 2026-11-11: the owner is studying event logs and catch-up first. Resume here.

| # | Question | Recommendation on the table |
|---|---|---|
| 9.2 | Catch-up paging (`upTo` skips later pages) | option 1: `limit` + `upTo` = last seq of the page (or `last_seq` on the last page) + `hasMore`; option 2: no paging, "too many changes" → reload (Matrix `limited`) |
| 9.2a | 410 `EVENTS_EXPIRED` for "too old" (§6) | Proposed |
| 9.4 | Event catalogue | Takes a `seq`: `message.created/deleted`, `reaction.added/removed`, `member.added/removed/role_changed`, `conversation.updated/deleted`. Per user only: `read.updated`, `message.hidden`, `notification.created`, `session.ended`, `resync`. Envelope `{type, conversationId?, seq?, data}`. |
| 9.5 | History paged by `seq` (§8) | `?before=<seq>&limit=50`; unique index `(conversation_id, seq)` replacing `(conversation_id, id)` |
