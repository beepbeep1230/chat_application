# ADR-011: Pending-Only Friend Requests with a Redis Decline Cooldown

- **Status:** Accepted
- **Date:** 2026-10-30 (recorded; decided during the October refactor)
- **Owner:** [you]

## Context

A declined user should not be able to spam new requests right away. Keeping declined rows in
`friend_requests` (with a status column) would grow the table forever and complicate the
"one request per pair" rule.

## Decision

- `friend_requests` holds **pending** requests only, with a unique index on
  `(LEAST(a, b), GREATEST(a, b))` — at most one request per pair in either direction.
- Accepting moves the pair to `friends_lists` (two rows, one per direction); declining,
  withdrawing and blocking delete the row.
- A decline stores `friend:cooldown:{requester}:{addressee}` in Redis with a TTL of
  `request_cool_down` days. A new request inside the window gets `429 REQUEST_COOLDOWN`
  with `Retry-After` = remaining seconds.
- If the other user later sends a request themselves, the cooldown is cleared.
- Sending a request to someone who already requested you auto-accepts it.

## Alternatives considered

- **Status column (`pending/accepted/declined`) in one table** — history kept, but more rows,
  more conditions in every query, and declined rows need cleanup anyway.
- **Cooldown in Postgres** — durable, but needs a cleanup job for expired rows.

## Consequences

- **Positive:** small tables, simple queries, expiry handled by Redis TTL.
- **Negative:** the cooldown **fails open** — if Redis is down it is not enforced, and a
  cooldown written during an outage is lost. Accepted for a social feature.

## References

- `docs/design/relations.md` §3–§4, §7.1, §8
