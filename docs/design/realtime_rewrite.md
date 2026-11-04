# Realtime rewrite: decision log

- **Status:** In progress (requirements interview, not approved). Round 3 questions are waiting for answers.
- **Started:** 2026-11-03 · **Last updated:** 2026-11-04
- **Will replace:** `docs/design/realtime.md` once approved

How to read this file:

- **Decided** = the owner said it.
- **Proposed** = recommended, not yet confirmed by the owner.
- **Open** = waiting for the owner's answer.

---

## 0. How to resume in a new session

Paste this into a new Claude Code session opened in this repo:

```
Read docs/design/realtime_rewrite.md. We are in the middle of a requirements interview for the realtime messaging rewrite. Load these skills first: superpowers:brainstorming, mattpocock-skills:grilling, anthropic-skills:architecture-designer, fullstack-dev-skills:websocket-engineer, anthropic-skills:fastapi-expert, anthropic-skills:python-pro, anthropic-skills:api-designer, anthropic-skills:postgres, redis-development:redis-connections, redis-development:redis-clustering. Continue from section 5 (open questions, round 3): I will answer them now. Keep asking in rounds, one recommended answer per question, and update this file after every round.
```

## 1. Why a rewrite

The first realtime design was written before the stack was familiar. Its code files
(`app/modules/realtime/*.py`) are all empty, so nothing has to be migrated. Section 7 lists the
problems in the old design that this rewrite must fix.

## 2. Decided

| Topic | Decision | Date |
|---|---|---|
| Product level | Built as a real product, not a demo. | 2026-11-03 |
| Deployment | AWS. Traffic passes a firewall, a load balancer and a web server before it reaches the app. | 2026-11-03 |
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
| Cost | Must work on AWS (S3 included) and cost nothing. See section 4 for why this conflicts with the planned AWS setup. | 2026-11-04 |

## 3. Proposed (not confirmed)

| Topic | Proposal | Why |
|---|---|---|
| Machine layout | "One chat server" read as: one machine running several uvicorn workers behind the load balancer. | Matches "multiple workers" and "server will be one". |
| Sticky sessions | Not needed. | A plain WebSocket stays on the worker that accepted it for its whole life. Socket.IO needs sticky sessions only because of its long-polling fallback, and this app does not use Socket.IO. |
| Heartbeat | Server pings every ~25 s. | An AWS Application Load Balancer closes a connection after 60 s of silence by default. |
| Personal channel | Besides one channel per conversation, one channel per **user** for events that belong to a person, not a chat: notifications, "you were added to / removed from a group", "your session ended". | Example: Bob kicks Alice. Bob's request lands on worker A, Alice's socket is on worker B. B must hear "Alice was removed, stop listening to that chat", and only a personal channel can carry it. |
| Block filter in groups | The worker that holds a user's socket drops group messages from senders that user blocked, using a block list loaded when the socket opens and updated through the personal channel. | With one channel per conversation, every member's worker receives every message, so the filter has to sit on the receiving side. |
| Subscription bookkeeping | Each worker subscribes to a conversation channel when one of its connected users is a member, and unsubscribes when the last such user leaves, is kicked or disconnects. | Cost of choosing one channel per conversation. |
| Sockets and the DB | The WebSocket handler never holds a database session for the life of the socket; it opens one only for short lookups. | 500 open sockets would otherwise need 500 Postgres connections and the database would refuse them. |
| Workers | 2 workers. | One per CPU core on a 2 vCPU free-tier machine; more workers only add memory use. |
| Postgres pool | 5 + overflow 5 per worker (today: 10 + 10). | Async code reuses one connection for many requests; on 2 cores extra connections only wait in line and cost memory. |
| Redis pool | ~20 per worker (today: 50), plus 1 dedicated pub/sub connection per worker. | A listening connection cannot run normal commands, so it cannot come from the pool. |
| Text and file count limits | Text up to 4,000 characters; up to 10 files per message. | Not objected to. |
| File types | Common image, video, audio, PDF and office types; executables blocked. | Not objected to. |
| File upload path | Browser uploads straight to S3 with a short-lived signed URL; the API only signs the permission and saves the file details. | Streaming large uploads through a small machine ties up workers and memory. |

Not verified yet: real memory use of the whole stack on a 1 GB machine; maximum connections of
the smallest managed AWS Postgres.

## 4. AWS cost finding

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

## 5. Open questions (round 3, asked 2026-11-04)

### 5.1 Catching up after being offline

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

### 5.2 Duplicate sends

**Owner's position:** server-made ID only; a client key looks like overhead.

**Counter-case:** Alice sends on a train. The server saves the message, but the reply is lost in
a tunnel. The client cannot know it worked and retries; the server cannot tell it is the same
message and saves a second copy. The client cannot send "the server's ID" on retry because it
never received it. Only an ID created before sending survives a lost reply.

**Recommended:** keep the server ID as the real ID, and add `clientMessageId` used only to catch
retries: one column, a unique rule on (sender, clientMessageId), and "if it exists, return the
existing one" (about 5 lines). Slack, Discord and Telegram all do this in some form. The
alternative is to accept rare duplicates and let users delete them.

### 5.3 How the socket logs in

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

### 5.4 File size

**Recommended:** 25 MB per file, the same as Gmail's attachment limit; enough for normal Word,
Excel and PDF files. Larger files are shared as links, as with email.

### 5.5 AWS account

Was the account created before or after 2025-07-15, and is it on the Free or Paid plan? The
answer decides whether the single-machine candidate in section 4 is needed.

### Later rounds

Behaviour when Redis is down, which events create system messages, read receipts in groups, what
a kicked member can still see, monitoring.

## 6. Interview history

| Round | Date | Topics |
|---|---|---|
| 1 | 2026-11-03 | Purpose and scale, first-version events, REST vs socket for writes, offline behaviour, multiple devices. |
| 2 | 2026-11-03 | Catch-up mechanism, duplicate sends, socket login, file limits, Redis channel shape, target size. Owner asked for explanations of catch-up and socket login, rejected the client key, raised the file size, chose one channel per conversation, set the $0 cost goal. |
| 3 | 2026-11-04 | Explanations of catch-up and socket login, counter-case for the client key, 25 MB, AWS account type. Waiting for answers. |

## 7. Problems in the old design

| Where | Problem | Why it matters |
|---|---|---|
| `realtime.md` §3 vs §5 and §6; `conversations.md` §7 | Socket called "push-only", but the client sends `read` and `typing` over it, and REST also has `POST /conversations/{id}/read`. | The same action has two paths. |
| `realtime.md` §3 | Access token in the URL (`/ws?token=`). | URLs are written to load balancer and web server logs, so the token leaks there. |
| `realtime.md` §7, reconnect requirement (FR-38 in `prd.md`) | Reconnect fetches messages after the *last-read* pointer. | "Read" is not "received", and deletes, reactions and kicks are not new messages, so they are missed. |
| `app/modules/messages/models.py:48` | Message ID made by the server; the pagination decision record (ADR-004) says the client makes it. No dedupe column. | Re-sends after a lost reply can save the message twice. |
| `app/modules/messages/models.py:66` | `func.now()` is the transaction start time; the same decision record says `clock_timestamp()`. History sorts by `id`, the docs say `created_at`. | Two sort orders that can disagree. |
| `realtime.md` §4 vs the stub files | Doc plans one in-memory manager in `app/ws/`; stubs (`publisher.py`, `subscriber.py`) imply Redis pub/sub across processes. | In-memory "who is online" works only with one process. |
