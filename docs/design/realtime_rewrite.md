# Realtime rewrite: index and review log

- **Status:** Design review in progress, nothing approved for building yet. Since 2026-11-11 the
  details live in one design doc per scope (§2); this file only tracks status and order.
- **Started:** 2026-11-03 · **Last updated:** 2026-11-12

✅ Decided (the owner said it) · 🟡 Proposed (recommended, not confirmed) · ❓ Open

---

## 0. How to resume in a new session

```
Read docs/HANDOFF.md ("Current work") and docs/design/realtime_rewrite.md (§1 and §2). We review
the design one scope at a time, in the order of §1, and stay on a scope until nothing in it is
open. One recommended answer per question; search online for common practice. After each answer,
update the scope's own design doc and the line in §2. Load the skills listed in CLAUDE.md. Follow
the mentor rules in CLAUDE.md (no app code changes).
```

## 1. Work order (one scope at a time)

| Order | Scope | Doc | Left |
|---|---|---|---|
| 1 ✅ | A. Auth and sessions | `accounts_auth.md` §16 | nothing open (done 2026-11-12) |
| 2 (next, paused) | C. Change log, order, catch-up | `change_log.md` §9 | paging, 410 rule, event catalogue, history by `seq`: paused while the owner studies event logs; resume when the owner says so |
| 3 | D. Messages and files | `messages.md` §9 | signed-URL limits; orphan uploads; download; system message events; limits |
| 4 | B. Socket connection | `realtime.md` §8 | mobile `Origin`; slow client; backup check; proposed rows |
| 5 | E. Fan-out (Redis) | `fanout.md` §7 | Redis down; proposed rows; the deeper U vs C explanation the owner asked for |
| 6 | F. Membership, read state, notifications | `conversations.md` §8 | group receipts; kicked member; unfriend DM; group lifecycle; mute; proposed rows |
| 7 | Blocking | `relations.md` §9 | merge `hidden_from_user_id` into `message_hidden_for`? |
| 8 | G. Laptop infrastructure | `infrastructure.md` §4 | sizing; workers and ports; TLS; process manager; backups; hardening |
| 9 | H. Monitoring | `monitoring.md` §3 | logs, metrics, alerts |
| 10 | 0. Product and scope | `docs/prd.md` §3 | "one chat server" wording; account deletion (deferred) |

## 2. Scope map

One line per item; the reasons are in the scope doc.

**0. Product and scope** → `docs/prd.md` §3
- ✅ Real product; web v1, mobile v2 · ✅ 100 members / 500 sockets / 30-day log · ✅ one machine,
  several workers, more machines later · ✅ $0, self-hosted laptop · ✅ delete yes, edit later ·
  ✅ typing and presence later · ✅ socket only while the tab is open, Web Push later · ✅ AI bots
  later · ✅ PRD synced with the scope docs (2026-11-11)
- 🟡 "One chat server" = one machine, several workers behind the load balancer
- ❓ Account deletion (C-4): deferred, listed so it is not lost

**A. Auth and sessions** → `accounts_auth.md`
- ✅ Three layers: login row 30 days, refresh in Redis only 7 days, access 15 min child of one
  refresh token (§6) · ✅ one `sid` per login · ✅ Redis required, fail closed (§7) · ✅ lost
  rotation accepted (§7) · ✅ one active tab, single-flight refresh, theft message (§8) · ✅ Lua
  script, 30 s grace, theft revokes that login only (§9) · ✅ rename to `UserSession` (§3) ·
  ✅ DPoP and `appendfsync always` kept for later (§13)
- ✅ Fail closed: breaker fail-closed mode, auth raises → 503 (§7) · ✅ write order: row first on
  login, Redis first on logout (§7.1; may revisit when building) · ✅ one new code
  `REFRESH_TOKEN_REUSED`, replaced `rti` = `TOKEN_EXPIRED` (§10.4, §11) · ✅ active-tab election +
  `session.ended` reasons `logout` / `logout_all` / `theft` (§8, §10.5-10.6; details when building) ·
  ✅ clear the cookie on logout / logout-all / theft; `Secure` once HTTPS is set up (§5)

**B. Socket connection** → `realtime.md`
- ✅ REST writes, socket pushes (§1) · ✅ one-time ticket + `Origin` check (§2) · ✅ one socket per
  login, closed when the login ends (§5) · ✅ backup check, Redis only (§5, owner not fully sure)
- 🟡 Ticket flow, fails closed (§3) · 🟡 close codes (§4) · 🟡 skip the backup round when Redis
  is unreachable (§5) · 🟡 heartbeat 25 s, no sticky sessions (§6) · 🟡 no DB session per socket (§7)
- ❓ Mobile `Origin` rule · ❓ slow client (§8)

**C. Change log, order, catch-up** → `change_log.md`
- ✅ Server is the source of truth, no inbox table (§2) · ✅ `seq` counter + row lock (§3) ·
  ✅ `lock_timeout` 2 s, `statement_timeout` ~5 s, `idle_in_transaction_session_timeout` ~10 s (§4) ·
  ✅ event rows by app code, IDs only (§5) · ✅ catch-up with `upTo`, reload after 30 days (§6) ·
  ✅ resync routine, triggers, live badges, lost publish accepted (§7) · ✅ timeouts set once on the
  engine (§4) · ✅ nightly cron cleanup of rows older than 30 days (§6)
- 🟡 History paged by `seq` (§8)
- ⏸ Paused for study: catch-up paging + 410 rule · event catalogue · history by `seq` (§9)

**D. Messages and files** → `messages.md`
- ✅ One send = one message; attachments table; `type` = user / system; system messages as event +
  JSON; bots are accounts (§2) · ✅ `clientMessageId` (§3) · ✅ 25 MB, MinIO, signed upload (§4-§5) ·
  ✅ delete for everyone (author) / delete for me, other devices by push only (§6)
- 🟡 4,000 characters, 10 files, file types (§4)
- ❓ Signed-URL limits · ❓ orphan uploads · ❓ download · ❓ which events make system messages (§9)

**E. Fan-out (Redis)** → `fanout.md` (owner: fine for now; wants a deeper explanation)
- ✅ Pub/sub, one channel per user, publish after commit (§2) · ✅ AOF `everysec`, replica later (§4)
- 🟡 Full message in the push (§3) · 🟡 re-subscribe + `resync`, `noeviction` (§4)
- ❓ Redis down beyond auth, ticket and backup check (§6-§7)

**F. Membership, read state, notifications** → `conversations.md`, `notifications.md` (owner: fine
for now; wants a deeper explanation)
- ✅ Unified conversations, roles (§3-§4) · ✅ `last_read_seq`, unread by `seq`, 99+ (§5) ·
  ✅ notifications keep the ADR-005 split (`notifications.md` §3)
- 🟡 Count on demand · 🟡 mark-as-read with `GREATEST` · 🟡 sending moves your own pointer (§5)
- ❓ Group receipts · ❓ kicked member · ❓ unfriend DM · ❓ group lifecycle · ❓ mute (§8)

**Blocking** → `relations.md` §5.1
- ✅ Groups: no effect · ✅ DMs: silent, `hidden_from_user_id`, published to all but the blocker,
  hidden forever, blocker cannot send, never shown as read
- ❓ Merge into `message_hidden_for`? (§9)

**G. Laptop infrastructure** → `infrastructure.md` (owner: fine for now)
- ✅ Self-hosted, set up by hand; MinIO (§2)
- 🟡 2 workers, pool sizes (§3)
- ❓ Sizing · ❓ workers and ports · ❓ TLS and exposure · ❓ process manager · ❓ backups · ❓ hardening (§4)

**H. Monitoring** → `monitoring.md`
- ❓ Logs, metrics, alerts

## 3. ADRs changed by this review

| ADR | Now |
|---|---|
| ADR-002 soft delete | Amended: delete for me decided (`messages.md` §6) |
| ADR-003 derived unread | Amended: `last_read_seq` (`conversations.md` §5) |
| ADR-004 cursor pagination | Points 2-3 replaced by `seq` and `clientMessageId` |
| ADR-005 event-only notifications | Amended: catch-up through the change log |
| ADR-006 frozen-friendship blocking | Amended: DM messages hidden, not dropped (`relations.md` §5.1) |
| ADR-009 session cache fail open | Superseded: Redis required, fail closed (`accounts_auth.md` §7) |

## 4. Round history

| Round | Date | Topics and outcome |
|---|---|---|
| 1 | 2026-11-03 | Purpose and scale, first-version events, REST vs socket for writes, offline behaviour, several devices |
| 2 | 2026-11-03 | Catch-up, duplicate sends, socket login, file limits, channel shape, size, $0 cost |
| 3 | 2026-11-04 | Change log (option B), `clientMessageId`, 25 MB, hosting moved to the laptop |
| 4 | 2026-11-04/05 | Server as source of truth, no inbox table, Web Push later, ticket, lost publish, MinIO |
| 5 | 2026-11-05 | Ticket flow, close codes, socket = login lifetime, multi-tab race, 15-min tokens |
| 6 | 2026-11-05 | One `sid` per login, backup check in the plan, plan by parts |
| 7 | 2026-11-05 | Redis-only backup check, AOF, `seq` vs `id` for unread |
| 8 | 2026-11-07 | `seq` numbering, event rows, resync, live badges, blocking, scale numbers |
| 9 | 2026-11-09 | One channel per user (option U) |
| 10 | 2026-11-10 | One active tab; grace reuse (option C, 30 s). Diagrams: https://claude.ai/artifact/HoP334nWFQqEhJTt2VMJnJ |
| 11 | 2026-11-10/11 | Login session model; Redis required (fail closed); lost rotation accepted; theft message; rename to `UserSession` |
| 12 | 2026-11-11 | Lua script details, single-flight refresh, doc cleanup, whole-design review (findings became ❓ items) |
| 13 | 2026-11-11 | Message model and delete rules (scope D); `lock_timeout` and holder limits (scope C); docs split into one per scope |
| 14 | 2026-11-11 | Scope C: timeouts on the engine, nightly cleanup script. Paging, event catalogue, history by `seq` paused while the owner studies event logs and catch-up (mobile study prompt). Scope A moved first; its five last questions asked |
| 15 | 2026-11-12 | Scope A closed: fail-closed breaker mode, write order, `REFRESH_TOKEN_REUSED`, active-tab election + `session.ended` reasons, cookie clearing + `Secure` after HTTPS |
