# ADR-009: Redis Session Cache with the Database as Source of Truth

- **Status:** Accepted
- **Date:** 2026-10-30 (recorded; decided during the October refactor)
- **Owner:** [you]

## Context

Every authenticated request must know whether its session (`sid`) was revoked by logout or
refresh. Checking Postgres on every request is a DB round-trip per call. Redis is faster but
is a second system that can be down.

## Decision

- Cache active sessions in Redis: key `auth:session:{sid}`, TTL = remaining refresh lifetime.
- On a cache miss — or when Redis is down — check `user_session` in Postgres and re-cache.
- Wrap every Redis call in a circuit breaker (3 consecutive failures → open for 15 s) that
  returns a fallback instead of raising, so Redis problems never fail a request.
- Write order: **commit the DB row first, then write Redis**, so the cache never points at a
  rolled-back row.

## Alternatives considered

- **DB only** — simplest and always correct, but one extra query per request.
- **Redis only (no DB check)** — fastest, but a Redis outage would log everyone out or let
  revoked sessions through.
- **Stateless JWT, no revocation** — no lookup at all, but logout cannot take effect before expiry.

## Consequences

- **Positive:** fast path in Redis; Redis outages only cost latency; revocation is immediate.
- **Negative:** if a cache `DEL` fails while the DB revoke succeeds, the stale key keeps the
  session alive until its TTL; needs an external reconciliation job (not built).
- The same fail-open pattern is used for the friend-request cooldown (ADR-011).

## References

- `docs/design/accounts_auth.md` §6, `app/core/infra/circuit_breaker.py`
