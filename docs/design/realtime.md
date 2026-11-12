# Design — Socket Connection (scope B)

- **Status:** Target design, not built. Open items in §8.
- **Last updated:** 2026-11-11
- **Uses:** `accounts_auth.md` (the login session a socket belongs to), `fanout.md` (what arrives
  on the socket), `change_log.md` §7 (resync after a reconnect)

---

## 1. Principle

- Every client write (send, delete, react, mark read) goes through **REST**: durable, retryable.
- The socket only **pushes from server to client**. One endpoint: `WS /api/v1/ws?ticket=...`.
- A socket exists only while the tab is open (Web Push later). After a gap, the client resyncs.
- One socket per login (`sid`), and one active tab per browser (`accounts_auth.md` §8).

## 2. Why a ticket

In a browser, `new WebSocket(url)` can set only the URL, not the `Authorization` header.

| Way | Risk |
|---|---|
| Token in the URL (`/ws?token=`) | URLs are written to proxy and web server logs; anyone reading them can act as the user |
| Cookie | Sent automatically, so another site can open a socket as the user unless `Origin` is checked |
| **One-time ticket** (chosen) | A logged ticket is already used |

## 3. Ticket flow (proposed)

```
1. POST /api/v1/realtime/ticket     Authorization: Bearer <access>   (normal auth check)
   server: ticket = secrets.token_urlsafe(32)
           SET realtime:ticket:{ticket} {user_id, sid} EX 30
   reply:  {ticket, expiresIn: 30}
2. new WebSocket("wss://host/api/v1/ws?ticket=...")
3. server, before accept: Origin not in the allow-list -> reject the handshake (HTTP 403)
4. server: GETDEL realtime:ticket:{ticket}   (read + delete in one step; Redis >= 6.2)
           missing -> accept, then close 4401
           login no longer active -> close 4401
5. accept; remember {user_id, sid}; subscribe user:{user_id} (fanout.md)
```

- Rejecting before accept gives the browser only code 1006 with no reason. Fine for a bad
  `Origin` (an attacker learns nothing); the real client needs a reason, so ticket problems are
  close codes after accept.
- The ticket endpoint is rate-limited like the auth routes.
- Redis down: no ticket can be checked, so **no new sockets** (fails closed; it cannot fail open,
  or anyone could connect). Pub/sub is down at the same time anyway.

## 4. Close codes (proposed)

| Code | Meaning | Client does |
|---|---|---|
| 4401 | Ticket missing / used / expired, or login not active | new ticket; if that gets 401 -> refresh; if refresh fails -> login page |
| 4000 | Login ended (logout, logout-all, theft, ban) | do not reconnect; login page |
| 1001 / 1006 / 1011 | Server restart, network loss, server error | reconnect with backoff + jitter, then resync |

## 5. Lifetime and the backup check

- The socket lives as long as the **login** (`sid`), not the 15-minute access token: tokens rotate
  under it. It closes when the login ends: `session.ended` arrives on `user:{id}` with the `sid`
  (`accounts_auth.md` §6), and the worker closes that `sid`'s socket with 4000.
- **Backup check** (in the plan; the owner is not fully sure yet): every ~60 s each worker checks,
  in one Redis pipeline, that `auth:session:{sid}` still exists for each open socket. It closes
  sockets whose `session.ended` push was lost and sockets whose login expired. Redis only, no DB.
- **Proposed:** when Redis cannot be reached, **skip that round**. Close a socket only when Redis
  answered and the key is gone. "Cannot ask" is not "logged out"; closing on error would drop
  every socket at once and cause a reconnect storm.

## 6. Keeping the connection alive (proposed)

- The server pings every ~25 s: nginx closes a silent proxied connection after 60 s
  (`proxy_read_timeout` default).
- No sticky sessions: a plain WebSocket stays on the worker that accepted it. (Socket.IO needs
  sticky sessions only for its long-polling fallback; this app does not use Socket.IO.)

## 7. Database use (proposed)

The socket handler never holds a database session for the socket's life; it opens one only for
short lookups. 500 open sockets would otherwise need 500 Postgres connections.

## 8. Open questions

| # | Question | Notes |
|---|---|---|
| 8.1 | `Origin` rule for the v2 mobile app, which sends no `Origin` header | |
| 8.2 | Slow client: a client that does not read fills the worker's send buffer | Proposal: bounded send queue per socket; when full, close with a 4xxx code; the client resyncs |
| 8.3 | Backup check itself (§5) | Owner not fully sure |
| 8.4 | Proposed rows: ticket flow, close codes, skip rule, heartbeat, no DB session | Confirm or change |
