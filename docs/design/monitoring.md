# Design — Monitoring (scope H)

- **Status:** Not started.
- **Last updated:** 2026-11-11
- **Uses:** `infrastructure.md` (where it runs)

---

## 1. Purpose

See whether the app is healthy, find out why it is slow, and get told when something breaks.

## 2. Already known

- Logging moves from loguru to the standard `logging` module with request-id correlation and no
  secrets in logs (older plan in `docs/HANDOFF.md`).
- The load-test clients the owner plans will produce the first real numbers (500 sockets, 100
  members per group).

## 3. Open questions

| # | Question | Notes |
|---|---|---|
| 3.1 | Logs: format, where they go, how long they are kept | |
| 3.2 | Metrics: which ones (open sockets, publish rate, `lock_timeout` hits, Redis memory, pool waits) and where they are stored | |
| 3.3 | Alerts: what wakes the owner up, and how | |
