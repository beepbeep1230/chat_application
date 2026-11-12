# Design — Laptop Infrastructure (scope G)

- **Status:** Mostly open. The owner said "fine for now" on 2026-11-11.
- **Last updated:** 2026-11-11
- **Uses:** `fanout.md` §4 (Redis persistence and memory policy), `change_log.md` §4 (database
  timeouts), `realtime.md` §6 (heartbeat vs proxy timeout)

---

## 1. Purpose

Where the app runs and how its processes, pools and network are set up.

## 2. Decided

- **Self-hosted** on the owner's laptop (16 GB RAM), $0 cost. The owner sets up the firewall, web
  server and load balancer by hand, to practise infrastructure.
- **One machine, several worker processes.** The design must allow more machines later.
- **Object storage:** MinIO on the laptop (S3 API) (`messages.md` §5).

## 3. Proposed (sized for a 2 vCPU AWS machine; revisit for the laptop)

| Item | Value | Why |
|---|---|---|
| "One chat server" | One machine running several uvicorn workers behind the load balancer | Matches "multiple workers" and "server will be one" |
| Workers | 2 | One per CPU core; more workers only add memory use |
| Postgres pool | 5 + overflow 5 per worker (today: 10 + 10) | Async code reuses one connection for many requests; on 2 cores extra connections only wait in line and cost memory |
| Redis pool | ~20 per worker (today: 50), plus 1 dedicated pub/sub connection per worker | A listening connection cannot run normal commands, so it cannot come from the pool |

## 4. Open questions

| # | Question | Notes |
|---|---|---|
| 4.1 | Sizing for the laptop (workers, pools) | Load-test clients will measure the real limits |
| 4.2 | `uvicorn --workers N` shares one listening socket, so nginx cannot balance between those workers | Separate processes on separate ports would be needed for nginx to balance |
| 4.3 | TLS and how the laptop is exposed to the internet | |
| 4.4 | Process manager (restart on crash, start on boot) | |
| 4.5 | Backups (Postgres, Redis AOF/RDB, MinIO) | |
| 4.6 | Network hardening: Postgres, Redis and MinIO reachable only from the app; Redis auth (ACL user, `protected-mode`) | |
