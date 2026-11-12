# Design — Fan-out over Redis (scope E)

- **Status:** Target design, not built. Open items in §7.
- **Last updated:** 2026-11-11
- **Uses:** `change_log.md` (pushes carry `seq`; a missed push is healed there), `realtime.md`
  (the sockets that receive pushes)

---

## 1. Purpose

Get a change saved by one worker process to the sockets held by **every** worker process, today on
one machine and later on several.

## 2. Redis pub/sub, one channel per user ("option U")

- Each worker subscribes to `user:{id}` for every user with a socket on that worker: subscribe on
  the user's first local socket, unsubscribe on the last.
- There are **no conversation channels** and no subscription bookkeeping.

Send flow:

```
POST /conversations/{id}/messages  (with clientMessageId)
  -> one transaction: seq UPDATE, insert message + event row (seq = 42)
  -> still inside the transaction, after the seq UPDATE: read the member list
  -> COMMIT
  -> pipeline: PUBLISH user:{member} {seq: 42, type: "message.created", ...}  for each member
  -> every worker subscribed to user:{member} forwards it to that user's sockets
  -> client: 42 follows 41 -> show it; 43 after 41 -> fetch events?after=41
```

- The sender is a member too, so their own sockets (other devices) get the push as confirmation.
- Publish only **after** commit; otherwise a client could get the push, fetch, and not see the row.
- The member list is read **after** the `seq` lock, so it is always current: a member added or
  kicked just before is already in (or out of) the list.

**Why one channel per user (decided 2026-11-09):** no subscription bookkeeping; no leak after a
kick and no missed push after an add (publish order is not commit order, but the list read after
the lock is always right); hidden DM messages need no special path (the blocker is simply left out
of the list, `relations.md` §5.1). Cost: up to 100 publishes per message (one pipelined round trip)
and one copy of the payload per online member. Revisit per-conversation channels only if groups
grow to thousands. A deeper "user channels vs conversation channels" explanation is still owed to
the owner.

## 3. Push payload (proposed)

The push carries the **full message**, not IDs + preview. No second request per push; ~400 KB
through Redis per 4,000-character message in a 100-member group is fine at this size. Switch to
IDs + preview if load tests show Redis bandwidth matters.

## 4. Redis restarts and reconnects

- **Persistence (decided):** AOF on, `appendfsync everysec`: a restart loses at most ~1 s of
  writes. Redis docs advise AOF + RDB snapshots for backups. Replica + Sentinel later (Redis docs
  need at least 3 Sentinels on separate machines; on one laptop they fail together, and failover
  can lose acknowledged writes).
- **Re-subscribe (proposed):** after a Redis restart the pub/sub connection drops. The worker
  re-subscribes its channels itself (no guarantee found that the client library does it), then
  sends `resync` to its sockets (`change_log.md` §7). Pushes in the gap are lost and healed by the
  change log.
- **Memory policy (proposed):** `maxmemory-policy noeviction`. Session keys have a TTL; `volatile-*`
  policies would evict them first when memory is full, and live users would be logged out.

## 5. Connections

One dedicated pub/sub connection per worker: a listening connection cannot run normal commands,
so it cannot come from the pool. Pool sizes: `infrastructure.md`.

## 6. When Redis is down

| Effect | Owner |
|---|---|
| Auth answers 503 (fail closed) | `accounts_auth.md` §7 |
| No new sockets (ticket fails closed) | `realtime.md` §3 |
| Backup session check skips its round | `realtime.md` §5 |
| Pushes stop; clients heal by resync when Redis is back | §4 above |
| Everything else (rate limiter, friend cooldown, ...) | Open, §7 |

## 7. Open questions

| # | Question | Notes |
|---|---|---|
| 7.1 | Behaviour when Redis is down beyond the rows in §6 | |
| 7.2 | Full message in the push (§3) | Proposed |
| 7.3 | Re-subscribe + `resync` (§4) | Proposed |
| 7.4 | `noeviction` (§4) | Proposed |
