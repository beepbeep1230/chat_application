# Realtime rewrite: decision log

- **Status:** In progress (design review, not approved). Auth and socket login designed; Redis redundancy, unread counting, seq numbering, resync and blocking decided; what is left is in section 0.1.
- **Started:** 2026-11-03 · **Last updated:** 2026-11-07
- **Will replace:** `docs/design/realtime.md` once approved

How to read this file:

- **Decided** = the owner said it.
- **Proposed** = recommended, not yet confirmed by the owner.
- **Open** = waiting for the owner's answer.

---

## 0. How to resume in a new session

Paste this into a new Claude Code session opened in this repo:

```
Read docs/design/realtime_rewrite.md (sections 2, 3 and 9 first). We are reviewing this
realtime rewrite plan in rounds: one topic at a time, one recommended answer per question,
search online for common practice, and update this file after every round I answer.
Load these skills first: anthropic-skills:architecture-designer, anthropic-skills:fastapi-expert,
anthropic-skills:python-pro, anthropic-skills:api-designer, anthropic-skills:postgres,
redis-development:redis-connections, redis-development:redis-core,
redis-development:redis-clustering. Follow the mentor rules in CLAUDE.md (no app code changes).
Continue with the "Next steps" list in section 0.1, starting with step 1.
```

### 0.1 Next steps (as of 2026-11-07)

Done in the 2026-11-07 session: seq numbering, event rows (IDs only, written by app code),
resync (conversation list + active chat), resync triggers, live sidebar badges, block (groups:
nothing; DMs: silent, with `hidden_from_user_id` and `upTo`), scale numbers (100 / 500 / 30 days).

Suggested order for what is left:

| Step | Item | Question in short |
|---|---|---|
| 1 | 9.6 One channel per conversation | With 100 members, 500 sockets, 2 workers: worth the subscribe bookkeeping and subscribe race, or one channel per user? |
| 2 | 3 "Theft detection", then 9.7 and 9.8 | Confirm the ~30 s `REFRESH_RACE` rule; partial unique index on `sid` (revoke before insert, map the unique violation); where 30 s comes from |
| 3 | 9.9 `Origin` check | Rule for the v2 mobile app (no `Origin` header) |
| 4 | 9.11 File uploads | Size and type limits with a MinIO signed URL; who deletes orphan uploads |
| 5 | Unconfirmed rows in section 3 | Old access tokens after refresh; skip backup round when Redis is unreachable; count unread on demand (99+); backup check itself (owner unsure) |
| 6 | 9.1 detail | `lock_timeout` value for the `seq` counter lock |
| 7 | Laptop sizing | Workers, Postgres/Redis pools; `uvicorn --workers` shares one port (nginx cannot balance); heartbeat reason cites AWS |
| 8 | Doc cleanup | Stale text listed at the end of section 9 |

## 1. Why a rewrite

The first realtime design was written before the stack was familiar. Its code files
(`app/modules/realtime/*.py`) are all empty, so nothing has to be migrated. Section 7 lists the
problems in the old design that this rewrite must fix.

## 2. Decided

| Topic | Decision | Date |
|---|---|---|
| Product level | Built as a real product, not a demo. | 2026-11-03 |
| Deployment | ~~AWS~~ (replaced 2026-11-04). Self-hosted on the owner's laptop (16 GB RAM). The owner sets up the firewall, web server and load balancer by hand to practise infrastructure. Details in a later round. | 2026-11-04 |
| Scale | One chat server machine today, running several worker processes. The design must allow more machines later. | 2026-11-03 |
| Cross-process delivery | Redis pub/sub. | 2026-11-03 |
| Who writes where | Every client write (send, delete, react, mark read) goes through REST. The socket only pushes from server to client. | 2026-11-03 |
| Live delivery | A new message is pushed to every online member of the conversation. | 2026-11-03 |
| Edit / delete | Delete: yes. Edit: not in v1. | 2026-11-03 |
| Message content | Text (emoji included), files alone, or text plus files. Size is limited. | 2026-11-03 |
| System messages | Created automatically when specific events happen in a conversation (which events: later round). | 2026-11-03 |
| Other live events | Deleted, reaction, read receipt, membership change, notification events. Details in a later round. | 2026-11-03 |
| Typing, online status | Later than the first version. | 2026-11-03 |
| After being offline | The client must show everything that changed (new messages, deletes, kicks) without a reload. | 2026-11-03 |
| Clients | Web frontend in v1 (owner builds it). Mobile app in v2 or later, so several devices per user must work. | 2026-11-03 |
| Redis channel shape | One channel per **conversation** (not per user). Reason: one publish per message instead of one per member. | 2026-11-04 |
| File size | Larger than the 10 MB first proposed: must fit everyday office documents. Exact number in section 5. | 2026-11-04 |
| Cost | $0. Solved by self-hosting on the laptop; section 4 is kept only as background. | 2026-11-04 |
| Catch-up after offline | Option B: numbered change log per conversation, `GET /conversations/{id}/events?after=N`; reload (option A) only when the client is older than the kept log. | 2026-11-04 |
| History | Server is the source of truth and keeps messages until a user deletes them; only old change-log rows are cleaned up. | 2026-11-05 |
| Inbox | No per-user inbox table. Change log per conversation + `last_read_seq` on the membership row. | 2026-11-05 |
| Idempotency key field | Body field `clientMessageId` (client-made UUID); also matches the "sending..." bubble. | 2026-11-05 |
| Tab closed | v1: socket only while the tab is open, catch-up on reconnect. Web Push later. | 2026-11-05 |
| Socket login | One-time ticket + `Origin` check (design in section 5). | 2026-11-05 |
| Socket lifetime | Option B: one socket for the whole login; closed when the login ends, not when the access token expires. Needs a stable session id (section 5.1). | 2026-11-05 |
| Multi-tab refresh race | Must be fixed (how: section 5.2). | 2026-11-05 |
| Access token life | 15 min. | 2026-11-05 |
| Session id | One `sid` per login, kept from login to logout (owner's original intent); only `jti` changes on refresh. Reuse the `sid` column. | 2026-11-05 |
| Backup session check | In the plan (every ~60 s, pipelined), owner not fully sure yet; revisit when building part B. | 2026-11-05 |
| Backup check source | Redis only, no DB fallback. Applies **only** to the socket backup check; REST auth keeps the DB fallback (ADR-009). | 2026-11-05 |
| Redis redundancy | v1: AOF persistence (`appendonly yes`, `appendfsync everysec`), so a Redis restart loses at most ~1 s of writes. Replica + Sentinel later (5.5). | 2026-11-05 |
| Unread count | Counted by `seq`, not by message `id` (why: 5.5). `messages` gets a `seq` column copied from its `message.created` event. | 2026-11-05 |
| Notifications | Keep the split from ADR-005: unread badge is derived per chat; the bell is a `notifications` row per social event only. Catch-up now uses the change log. | 2026-11-05 |
| `seq` numbering | Counter column on `conversations` + row lock: `UPDATE conversations SET last_seq = last_seq + 1 WHERE id = ? RETURNING last_seq` inside the write transaction. Under Read Committed (the default; the app sets no other level) a second writer **waits**, then gets the next number; no error, no retry loop. Keep the transaction short; take the counter lock first. | 2026-11-05 |
| Writing change-log rows | App code, not DB triggers: one helper bumps the counter, inserts the event row and returns `seq`, inside the service's transaction. Reason: the logic stays visible in Python, testable, and easy to change. | 2026-11-05 |
| Event row content | IDs only (`seq`, `type`, `message_id` / target id); catch-up joins `messages` by primary key. Reason: content lives in one place, so a delete is correct in catch-up without scrubbing a copy. History reads `messages`, not the event table. | 2026-11-07 |
| Active chat (term) | The one conversation the user has entered: history on screen, can send. Every other conversation is only a sidebar row (name, preview, badge). | 2026-11-07 |
| Resync | One routine: refetch `GET /conversations` (each row: `last_seq`, unread count capped 99+, last message preview, `last_activity_at` for sort), then `events?after=` for the **active chat** only. Sidebar rows get no message fetch; a chat loads history when entered. The list also shows chats joined or left while offline. | 2026-11-07 |
| When to resync | (1) socket reconnects; (2) server sends `resync` to its sockets after its own Redis subscription reconnects; (3) tab becomes visible. A timer only if testing shows it is needed. | 2026-11-07 |
| Live sidebar badges | While connected, a `message.created` push for a non-active chat updates its preview and adds 1 to its badge locally (not for own messages). Ignore a push whose `seq` is not above the row's known `last_seq` (avoids double counting after a resync). `read.updated` sets the badge from the server. | 2026-11-07 |
| Block in groups | Blocking does nothing inside groups: the blocker still sees the blocked user's group messages, and they count in the unread badge. Block only affects DMs and friend requests. Reason: simplest; no seq gaps, no filter in push / catch-up / history / workers. | 2026-11-07 |
| Block in DMs | Silent: the blocked user can still send; the message is saved and shown to the sender as sent, but never shown to the blocker. Hides the block from the blocked user. How: section 3, "Hidden DM messages". | 2026-11-07 |
| Scale numbers | Max group size 100 members; target 500 open sockets; change log kept 30 days (older client = full reload). Small scale on purpose; the owner plans test clients later to load-test these numbers. | 2026-11-07 |
| Lost publish | Accepted in v1 (client heals via seq gap / reconnect); transactional outbox later if needed. | 2026-11-05 |
| Files | MinIO on the laptop (S3 API, signed-URL upload), 25 MB per file. | 2026-11-05 |
| Duplicate sends | Server ID stays the real ID. Add a client-made **idempotency key** (`clientMessageId`), unique per sender; a retry with the same key returns the saved message. | 2026-11-04 |

## 3. Proposed (not confirmed)

| Topic | Proposal | Why |
|---|---|---|
| Machine layout | "One chat server" read as: one machine running several uvicorn workers behind the load balancer. | Matches "multiple workers" and "server will be one". |
| Old access tokens after refresh | Stay valid until their own expiry (max 15 min). | Normal JWT behaviour; follows from a stable sid. Not answered yet. |
| Theft detection | Build together with the stable sid: reuse of a token rotated < ~30 s ago with a newer active row in the same sid -> 401 `REFRESH_RACE`; older reuse -> revoke that sid. | Without the race window, theft detection logs multi-tab users out everywhere. Not answered yet. |
| Sticky sessions | Not needed. | A plain WebSocket stays on the worker that accepted it for its whole life. Socket.IO needs sticky sessions only because of its long-polling fallback, and this app does not use Socket.IO. |
| Heartbeat | Server pings every ~25 s. | Proxies close silent connections (nginx `proxy_read_timeout` and AWS ALB both default to 60 s). |
| Personal channel | Besides one channel per conversation, one channel per **user** for events that belong to a person, not a chat: notifications, "you were added to / removed from a group", "your session ended". | Example: Bob kicks Alice. Bob's request lands on worker A, Alice's socket is on worker B. B must hear "Alice was removed, stop listening to that chat", and only a personal channel can carry it. |
| ~~Block filter in groups~~ | ~~Worker drops group messages from blocked senders.~~ Replaced 2026-11-07: no filter in groups (section 2). | Dropping caused seq gaps that catch-up refilled. |
| Subscription bookkeeping | Each worker subscribes to a conversation channel when one of its connected users is a member, and unsubscribes when the last such user leaves, is kicked or disconnects. | Cost of choosing one channel per conversation. |
| Sockets and the DB | The WebSocket handler never holds a database session for the life of the socket; it opens one only for short lookups. | 500 open sockets would otherwise need 500 Postgres connections and the database would refuse them. |
| Workers | 2 workers (revisit: was sized for a 2 vCPU AWS machine, now a laptop). | One per CPU core; more workers only add memory use. |
| Postgres pool | 5 + overflow 5 per worker (today: 10 + 10). | Async code reuses one connection for many requests; on 2 cores extra connections only wait in line and cost memory. |
| Redis pool | ~20 per worker (today: 50), plus 1 dedicated pub/sub connection per worker. | A listening connection cannot run normal commands, so it cannot come from the pool. |
| Text and file count limits | Text up to 4,000 characters; up to 10 files per message. | Not objected to. |
| File types | Common image, video, audio, PDF and office types; executables blocked. | Not objected to. |
| File upload path | Browser uploads straight to S3 with a short-lived signed URL; the API only signs the permission and saves the file details. | Streaming large uploads through a small machine ties up workers and memory. |
| Redis unreachable during backup check | Skip that round; close a socket only when Redis answered and the `auth:session:{sid}` key is gone. | "Cannot ask" is not "logged out". Closing on error would drop every socket at once and cause a reconnect storm. Not answered yet. |
| Redis memory policy | `maxmemory-policy noeviction`. | Session keys have a TTL; `volatile-*` policies evict them first when memory is full, and the backup check would then close live sockets. |
| Ticket when Redis is down | Fails closed: no new sockets; REST keeps working. | A ticket cannot fail open (anyone could connect). Pub/sub is down at the same time anyway. |
| Unread count method | Count on demand, capped at "99+"; index on `messages (conversation_id, seq)`. | No extra write per message. A stored counter per member (Discord, WeChat style) is the later option if the chat list gets slow. Not answered yet. |
| Mark as read | `POST /conversations/{id}/read {upToSeq}` sets `last_read_seq = GREATEST(last_read_seq, :seq)`, then publishes `read.updated` on the user's personal channel. | `GREATEST` stops a slower device moving the pointer backward; the push clears the badge on the user's other devices. |
| Own messages | Sending a message also moves the sender's own `last_read_seq` to that `seq`. | The sender's own messages never count as unread. |
| Hidden DM messages | Column `messages.hidden_from_user_id` (NULL normally; the blocker's id when sent while blocked). The message still takes a `seq`. It is published on the sender's personal channel, not the conversation channel, so the blocker's worker never receives it. History, catch-up, preview and unread count add `hidden_from_user_id IS DISTINCT FROM :me`. | Keeps the conversation channel and workers filter-free; only DMs pay the cost. **Accepted 2026-11-07.** |
| Catch-up returns `upTo` | `events?after=N` returns the events **and** `upTo` (the conversation's current `last_seq`). The client moves its position to `upTo`, not to the last event it got. | A hidden message makes a seq hole for the blocker; without `upTo` the client would re-fetch that hole forever. Also covers any future skipped seq. **Accepted 2026-11-07.** |
| After unblock | Messages sent while blocked stay hidden forever. | They were never "delivered"; showing them later would reveal the block afterwards. **Accepted 2026-11-07.** |
| Blocker sending | The blocker cannot send in that DM (403, unblock first). | Otherwise the blocked user would get messages from someone who hides theirs. **Accepted 2026-11-07.** |
| Read receipts on hidden messages | Never shown as read. | Reading seq 43 moves the blocker's `last_read_seq` past hidden 42; a "seen" tick there would be false. **Accepted 2026-11-07.** |
| History pagination | Page by `seq` instead of `id`. | One sort order for history, catch-up and unread (fixes section 7). |

Pool sizes above were chosen for a small AWS machine; revisit for the laptop.

## 4. AWS cost finding (background only, superseded 2026-11-04 by self-hosting)

- Accounts opened **since 2025-07-15** get $100 in credits, plus up to $100 more for completing
  tasks. On the Free plan the account closes after 6 months or when credits run out, whichever
  comes first.
- Accounts opened **before 2025-07-15**: the 12-month free offers have ended by now; only
  "always free" allowances remain, and those do not include a server.
- An Application Load Balancer alone costs around $16 a month before traffic (price not
  verified).
- So "load balancer + server + managed database + managed Redis" cannot stay at $0 for long on
  either kind of account.
- **Candidate (not settled):** one machine runs everything: nginx as web server and load balancer
  in front of 2 workers, Postgres, Redis. AWS security groups act as the firewall; S3 holds files.
  No separate AWS load balancer, managed database or managed Redis, because they use credits
  fastest. The code stays ready to move onto them later.
- Not verified: per-service free limits (ALB, S3, ElastiCache) under the 2026 plans. Check the
  official AWS Free Tier page.

Sources: [AWS Builder Center](https://builder.aws.com/content/3Kkt4kNiDSUnO3n6db2weSNubzE/the-dollar0-aws-account-in-2026-free-plan-credits-guardrails),
[Rackspace](https://spot.rackspace.com/blog/aws-free-tier),
[Neowin](https://www.neowin.net/amp/aws-free-tier-overhauled-new-users-get-200-in-credits-but-theres-a-catch/),
[AWS: Aurora PostgreSQL free tier](https://aws.amazon.com/about-aws/whats-new/2026/03/amazon-aurora-postgresql-aws-free-tier),
[InfraTally](https://infratally.com/articles/aws-free-tier-2026/).

## 5. Socket login design and open questions (round 5, asked 2026-11-05)

### Background: why this is not WhatsApp's model

WhatsApp treats the **phone** as the place where history lives. The server is a post office: it
holds a message only until every device of the receiver has it, then deletes it. That works
because messages are end-to-end encrypted (the server cannot read them anyway) and the phone keeps
its own database.

A browser app cannot rely on that: browser storage can be wiped, and a user can log in from any
new browser and expects to see history. So here the **server is the source of truth** and keeps
messages (like Slack, Discord, Messenger, Instagram, Telegram cloud chats).

**Doorbell vs mailbox.** Postgres is the mailbox: every change is saved there first. Redis
pub/sub (and later Web Push) is only the doorbell: it says "something changed in chat X, here it
is". A doorbell can be missed (socket dead, Redis restarted); the client then reads the mailbox
using the change number from 5.1 option B. So pushes never need to be reliable.

Send flow:

```
POST /conversations/{id}/messages  (with clientMessageId)
  -> one transaction: insert message + change-log row (seq = 42)
  -> COMMIT
  -> PUBLISH conv:{id}  {seq: 42, type: "message.created", ...}
  -> every worker subscribed to conv:{id} forwards it to its sockets of that chat's members
  -> client: seq 42 follows 41 -> show it; seq 43 after 41 -> fetch events?after=41
```

Publish happens **after** commit, otherwise a client could get the push and fetch before the row
is visible.

### 5.0 Ticket flow (proposed)

```
1. POST /realtime/ticket            Authorization: Bearer <access>   (normal CurrentUser check)
   server: ticket = secrets.token_urlsafe(32)
           SET realtime:ticket:{ticket} {user_id, sid} EX 30
   reply:  {ticket, expiresIn: 30}
2. new WebSocket("wss://host/api/v1/ws?ticket=...")
3. server, before accept: Origin not in allow-list  -> reject handshake (HTTP 403)
4. server: GETDEL realtime:ticket:{ticket}   (read + delete in one step; Redis >= 6.2)
           missing -> accept, then close 4401 (so the client knows "get a new ticket")
           session no longer active (check_session_is_active) -> close 4401
5. accept; remember {user_id, sid} on the connection; subscribe channels
```

- The socket lives as long as the login (5.1), not the access token.
- Rejecting before accept gives the browser only code 1006 with no reason. That is fine for a bad
  `Origin` (an attacker learns nothing), but the real client needs a reason, so ticket problems
  are reported as close codes after accept.
- Rate-limit `POST /realtime/ticket` like the auth routes.

Proposed close codes (4000-4999 are free for apps):

| Code | Meaning | Client does |
|---|---|---|
| 4401 | Ticket missing / used / expired, or session not active | new ticket; if that fails with 401 -> refresh; if refresh fails -> login page |
| 4000 | Session ended (logout, logout-all, account banned) | do not reconnect; login page |
| 1001 / 1006 / 1011 | Server restart, network loss, server error | reconnect with backoff + jitter, catch-up |

**Finding from the auth code:** every refresh makes a new `sid` (`app/core/security.py:120`) and
revokes the old one (`app/modules/auth/service.py:104-115`). So a `sid` means "one refresh
token", not "one login". Consequences: a socket opened before a refresh holds an old `sid`; a
server-side "close by sid" after logout can miss it. In v1 this is covered because (a) the client
closes its own socket when it logs out, and (b) logout-all closes by `user_id` on the personal
channel.

### 5.1 Socket lifetime = login lifetime (decided: option B) — what changes

Today a `sid` changes on every refresh, so it cannot name "this login". Proposed: **keep the same
`sid` for the whole login**; only `jti` changes on refresh.

| File | Today | Change |
|---|---|---|
| `app/core/security.py:118-120` | refresh token always gets a new `uuid7()` sid | take an optional `session_id`; make a new one only at login |
| `app/modules/auth/service.py:104-115` `refresh` | revokes old sid in cache, `_issue_session` makes a new sid | pass the old sid on; overwrite the cache entry instead of deleting it (deleting leaves a short gap where valid access tokens fall back to the DB) |
| `app/modules/auth/service.py:182` `_issue_session` | no sid argument | accept the sid to reuse |
| `app/modules/auth/models.py:25` `sid` | `unique=True` | rows are kept after revoke, so the same sid now appears in several rows. Replace with a **partial unique index** on `sid` WHERE `revoked_at IS NULL` (one active row per login) + Alembic migration |
| `app/modules/auth/service.py` `logout`, `logout_all` (+ ban later) | only revoke | also publish `session.ended` on the user's personal channel (by sid for logout, all for logout-all) |
| ticket (5.0) | carries `access_exp` | carries only `user_id`, `sid`; no scheduled close |

Side effects:

- An access token made before a refresh stays valid until its own expiry (at most 15 min),
  because its sid is still active. Today it dies at once on refresh. This is the normal JWT
  behaviour.
- Backup check: every ~60 s each worker checks, in one Redis pipeline, that the sids of its open
  sockets still exist (`auth:session:{sid}`, `app/modules/auth/crud_cache.py:62`). This closes
  sockets whose `session.ended` push was lost, and sockets whose login simply expired (the key's
  TTL is the refresh token's expiry). Redis is trusted here with no DB fallback, so it depends on
  AOF persistence, `noeviction` and the "skip when unreachable" rule (5.5).

### 5.2 Multi-tab refresh race (must fix)

- **Client:** one refresh at a time across tabs (Web Locks API); other tabs get the new access
  token over a `BroadcastChannel`. The refresh cookie is shared by all tabs, so a tab that still
  loses the race only needs to retry once.
- **Server:** the model comment (`app/modules/auth/models.py:38-39`) plans "a revoked token used
  again = theft -> revoke all". Not built yet. Once built, a losing tab would log the user out
  everywhere. With a stable sid the server can tell the cases apart: the token was rotated less
  than ~30 s ago and the same sid has an active newer row -> answer 401 `REFRESH_RACE` (client
  retries), no revoke. Older reuse -> theft -> revoke that sid (that login only).

### 5.3 Access token lifetime (decided): 15 min. Set `JWT_ACCESS_TOKEN_LIFE_MIN=15` in `.env`.

### 5.4 Round 6 (answered 2026-11-05: 1 = reuse sid, 3 = in the plan; 2 and 4 moved to section 3)

1. Stable session id: reuse the `sid` column (recommended, fewest changes) or add a new
   `family_id` column?
2. Accept that old access tokens live up to 15 min after a refresh? (recommended: yes)
3. Backup session check every 60 s? (recommended: yes)
4. Build theft detection + the 30 s race window together with this change? (recommended: yes)

### 5.5 Round 7: Redis redundancy, backup check, unread (answered 2026-11-05)

**Backup check without the DB.** The `auth:session:{sid}` key was only a cache (ADR-009): a
missing key meant "not cached", not "logged out". The owner chose to trust Redis for the socket
backup check instead of falling back to the DB, and to make Redis safer instead:

| Failure | Fix | On one laptop |
|---|---|---|
| Redis restarts (crash, update, reboot): RAM wiped, all keys gone | AOF, `appendfsync everysec`: keys reload on start, at most ~1 s lost. Redis docs advise AOF + RDB snapshots for backups. | **v1 choice.** |
| Redis stays down | Replica + Sentinel (automatic failover) | Later. Redis docs need at least 3 Sentinels on separate machines; on one laptop they fail together. Failover can also lose acknowledged writes (asynchronous replication). |

Rules that follow (section 3): skip the check when Redis cannot be reached, `noeviction`, ticket
fails closed. REST auth is unchanged: a failed session `SET` after login is still re-cached from
the DB on the next REST request. Edge case: if no REST call re-caches it within ~60 s, the backup
check closes the socket; the client reconnects and ticket redemption checks the session again.

After a Redis restart or failover the pub/sub connection drops. The worker must re-subscribe its
channels itself (no guarantee found that the client library does it). Pushes in that gap are lost
and healed by the change log.

**Unread: why `seq`, not `id`.** Message `id` is a `uuid7` made in Python *before* commit
(`app/modules/messages/models.py:48`). `seq` is handed out by a row lock on the conversation's
counter and the lock is held *until* commit, so `seq` order is commit order.

```
t1  Worker A: Bob's message gets id AAA (earlier time)
t2  Worker B: Carol's message gets id BBB (later, larger)
t3  Worker B: COMMIT
t4  Alice reads, sets last_read_message_id = BBB
t5  Worker A: COMMIT  (A was slow)
    unread = COUNT(id > BBB) = 0  -> Bob's message counted as read, never seen
```

With `seq`: A takes 42 and holds the lock; B waits and gets 43 only after A commits. Once 43 is
visible, 42 is already visible, so nothing can appear behind the pointer later. (Traced from the
code, not run.)

| Topic | `id` | `seq` |
|---|---|---|
| Late commit | Can slip under the pointer | Cannot |
| Spot a missed push | No | Yes (41 -> 43) |
| One pointer for unread, catch-up, read receipts | No | Yes |
| `last_seq - last_read_seq` as the count | No | Also no (deletes and reactions take numbers too); use `COUNT` |
| Cost on send | Free | One row lock per conversation; sends to one chat run one at a time |

`id` stays the primary key (replies, reactions, URLs point at it); `seq` is the position in the chat.

**Unread badge vs bell.**

| | Unread badge | Bell |
|---|---|---|
| What | New messages per chat | Friend request, accepted, group invite, reaction, mention |
| Stored as | Nothing new: `COUNT(messages WHERE seq > last_read_seq AND sender_id <> me AND not deleted)` | One `notifications` row per event |
| Live | `message.created` on `conv:{id}` | `notification.created` on `user:{id}` |
| After offline | Change log + recount | `GET /notifications?cursor=...` |

### Later rounds

Behaviour when Redis is down, which events create system messages, read receipts in groups, what
a kicked member can still see, monitoring, laptop infrastructure (firewall, nginx, TLS, exposing
it to the internet).

### Round 3 notes (kept for reference)


#### 5.1 Catching up after being offline

**The problem.** Alice's laptop sleeps for 10 minutes. Meanwhile Bob sends 3 messages, Carol
deletes an old message Alice already has on screen, and Bob reacts. Alice's socket was dead, so
Redis delivered those 5 pushes to nobody: Redis pub/sub keeps no copy for absent listeners.

**Option A: reload on reconnect.** Fetch the chat list and the newest 50 messages again. Simple,
but misses Carol's delete if that message is older than the newest 50, misses reactions on old
messages, and re-downloads everything on every reconnect.

**Option B: numbered change log per conversation.** Every change in a conversation gets the next
number (1, 2, 3...) and is saved as a row ("42: message X deleted"). Pushes carry the number. The
client remembers "I have up to 41 in this chat" and on reconnect calls
`GET /conversations/{id}/events?after=41`. A gap while connected (41 then 43) also triggers a
fetch. The number becomes the one true order of the chat, which fixes the "two sort orders"
problem (section 7). Cost: one extra row per change, and the number must be handed out safely in
the same transaction so two messages sent at once never both get 42. Old log rows are cleaned
up after some time; a client older than that falls back to option A.

**Recommended:** B, with A as fallback. It is the only option that meets the "see everything
after being offline" rule.

#### 5.2 Duplicate sends

**Owner's position:** server-made ID only; a client key looks like overhead.

**Counter-case:** Alice sends on a train. The server saves the message, but the reply is lost in
a tunnel. The client cannot know it worked and retries; the server cannot tell it is the same
message and saves a second copy. The client cannot send "the server's ID" on retry because it
never received it. Only an ID created before sending survives a lost reply.

**Recommended:** keep the server ID as the real ID, and add `clientMessageId` used only to catch
retries: one column, a unique rule on (sender, clientMessageId), and "if it exists, return the
existing one" (about 5 lines). Slack, Discord and Telegram all do this in some form. The
alternative is to accept rare duplicates and let users delete them.

#### 5.3 How the socket logs in

**The problem.** In a browser, `new WebSocket(url)` can only set the URL, not the
`Authorization: Bearer` header the REST API uses.

| Way | Risk |
|---|---|
| Token in URL (`/ws?token=`) | URLs are written to load balancer and web server logs; anyone reading them can act as the user until the token expires. |
| Cookie | The browser attaches it automatically, so a page on another site can open a socket as the user unless the server checks the `Origin` header. The access token is not in a cookie today. |
| One-time ticket | Client calls `POST /realtime/ticket` with the Bearer header; server stores a random string in Redis for 30 s; client opens `/ws?ticket=...`; server reads and deletes it in one step. A logged ticket is already used. |

**Token expiry on an open socket.** The socket cannot resend headers. Proposal: the server closes
the socket when the access token expires; the client refreshes, gets a new ticket and reconnects
(cheap with option B in 5.1). On logout or logout-all, the server sends "session ended" on the
personal channel and closes at once.

**Recommended:** one-time ticket plus `Origin` check, close at token expiry, close immediately on
logout. Access-token lifetime is `jwt_access_token_life_min` in `.env` (value not checked).

#### 5.4 File size

**Recommended:** 25 MB per file, the same as Gmail's attachment limit; enough for normal Word,
Excel and PDF files. Larger files are shared as links, as with email.

#### 5.5 AWS account

Was the account created before or after 2025-07-15, and is it on the Free or Paid plan? The
answer decides whether the single-machine candidate in section 4 is needed.

#### Later rounds

Behaviour when Redis is down, which events create system messages, read receipts in groups, what
a kicked member can still see, monitoring.

## 5b. Plan by part

Each part is designed in its own rounds. Status: designed / decided at high level / not started.

| Part | Covers | Status |
|---|---|---|
| A. Auth changes | stable sid, partial unique index + migration, theft detection, `REFRESH_RACE`, `session.ended` publish | designed (5.1, 5.2) |
| B. Socket connection | ticket, `Origin` check, close codes, heartbeat, backup session check, reconnect backoff | designed (5.0); backup check to revisit |
| C. Change log and catch-up | `seq` per conversation, events table, safe numbering in the transaction, retention, `GET .../events?after=`, `messages.seq`, one sort order (fixes section 7) | decided at high level; unread by `seq` decided (5.5) |
| D. Messages | send / delete / react REST, `clientMessageId`, text and file limits, MinIO signed upload | decided at high level |
| E. Fan-out | Redis channels (conversation + personal), subscription bookkeeping, behaviour when Redis is down | decided at high level |
| F. Membership and read state | system messages, kicked member visibility, read receipts in groups, `last_read_seq`, unread counts | not started |
| G. Laptop infrastructure | firewall, nginx, TLS, exposing to the internet, process manager, backups | not started |
| H. Monitoring | logs, metrics, alerts | not started |

## 6. Interview history

| Round | Date | Topics |
|---|---|---|
| 1 | 2026-11-03 | Purpose and scale, first-version events, REST vs socket for writes, offline behaviour, multiple devices. |
| 2 | 2026-11-03 | Catch-up mechanism, duplicate sends, socket login, file limits, Redis channel shape, target size. Owner asked for explanations of catch-up and socket login, rejected the client key, raised the file size, chose one channel per conversation, set the $0 cost goal. |
| 3 | 2026-11-04 | Explanations of catch-up and socket login, counter-case for the client key, 25 MB, AWS account type. Owner chose option B and the idempotency key, asked about "waking" a closed socket, moved hosting to the laptop, asked how WhatsApp-style deletion compares. |
| 4 | 2026-11-04 | Server as source of truth, inbox table, key field, socket open/closed + Web Push, socket login, lost publish, files on the laptop. Owner accepted all recommendations (2026-11-05) and asked how the ticket works and how to keep token refresh seamless. |
| 5 | 2026-11-05 | Ticket flow, close codes, socket lifetime, refresh in the browser and the multi-tab race, access token lifetime. Owner chose one socket per login, wants the race fixed, 15 min tokens. |
| 6 | 2026-11-05 | Stable sid changes, old access tokens after refresh, backup session check, theft detection. Owner confirmed one sid per login, put the backup check in the plan, asked to plan by parts (section 5b). |
| 7 | 2026-11-05 | Design review: backup check vs ADR-009, ticket when Redis is down, ADRs replaced by this plan. Owner chose Redis-only backup check (socket only), AOF for v1, kept the change log + `last_read_seq`, asked `seq` vs `id` for unread. Open gaps parked in section 9. |

## 7. Problems in the old design

| Where | Problem | Why it matters |
|---|---|---|
| `realtime.md` §3 vs §5 and §6; `conversations.md` §7 | Socket called "push-only", but the client sends `read` and `typing` over it, and REST also has `POST /conversations/{id}/read`. | The same action has two paths. |
| `realtime.md` §3 | Access token in the URL (`/ws?token=`). | URLs are written to load balancer and web server logs, so the token leaks there. |
| `realtime.md` §7, reconnect requirement (FR-38 in `prd.md`) | Reconnect fetches messages after the *last-read* pointer. | "Read" is not "received", and deletes, reactions and kicks are not new messages, so they are missed. |
| `app/modules/messages/models.py:48` | Message ID made by the server; the pagination decision record (ADR-004) says the client makes it. No dedupe column. | Re-sends after a lost reply can save the message twice. |
| `app/modules/messages/models.py:66` | `func.now()` is the transaction start time; the same decision record says `clock_timestamp()`. History sorts by `id`, the docs say `created_at`. | Two sort orders that can disagree. |
| `realtime.md` §4 vs the stub files | Doc plans one in-memory manager in `app/ws/`; stubs (`publisher.py`, `subscriber.py`) imply Redis pub/sub across processes. | In-memory "who is online" works only with one process. |

## 8. ADRs this plan replaces

| ADR | Old | New |
|---|---|---|
| ADR-004 `cursor-pagination` point 3 (and point 1's order) | Client makes the message ID; history pages by `id` | Server ID + `clientMessageId`; history pages by `seq` |
| ADR-003 `derived-unread-badges` | `last_read_message_id`, count by `id` | `last_read_seq`, count messages by `seq` (5.5) |
| ADR-005 `event-only-notifications` | Offline catch-up through the last-read pointer | Catch-up through the change log; the rest stays |
| ADR-009 `session-cache-fail-open` | DB fallback everywhere | Unchanged for REST; the socket backup check uses Redis only (5.5) |

## 9. Needs justification (parked, from the 2026-11-05 review)

Each item is a decision with a missing *why*, a missing number, or a contradiction.

| # | Topic | Question |
|---|---|---|
| 1 | Safe `seq` numbering | **Decided 2026-11-05** (section 2). Open detail: a `lock_timeout` value (`55P03` already maps to 503 in `app/core/errors/translators.py:42`). |
| 2 | Event row content | **Decided 2026-11-07** (section 2): IDs only. |
| 3 | Block filter | **Decided 2026-11-07** (section 2): no filter in groups; DMs silent (mechanics proposed in section 3). |
| 4 | Reconnect with many chats | **Decided 2026-11-07** (section 2): resync via the conversation list + active chat catch-up. |
| 5 | Lost publish in a quiet chat | **Decided 2026-11-07** (section 2): resync on Redis re-subscribe and tab visible. |
| 6 | One channel per conversation | Worth the bookkeeping and subscribe race on 2 workers? (Receive-side filter no longer needed; max group size now 100.) |
| 7 | Partial unique index on `sid` | Refresh must revoke before insert in one transaction; map the concurrent-refresh unique violation to `REFRESH_RACE`? |
| 8 | 30 s race window | Where does 30 s come from? Attacker-first case loops until the window passes: acceptable? |
| 9 | `Origin` check | Rule for the v2 mobile app, which sends no `Origin`. |
| 10 | Missing numbers | **Decided 2026-11-07** (section 2): 100 / 500 / 30 days. |
| 11 | File uploads | How are size and type enforced with a signed URL (signed PUT may not cap size; not verified for MinIO)? Who deletes orphan uploads? |

Stale text to clean up: round 3 "close at token expiry" and "ticket carries `access_exp`" (replaced by
option B); "every refresh makes a new sid" (fixed by 5.1); heartbeat reason cites AWS ALB; workers
and pools sized for AWS; upload path says S3 (now MinIO); `uvicorn --workers` shares one socket, so
nginx cannot balance between them (separate processes on separate ports would be needed); section
numbers 5.1-5.4 appear twice.
