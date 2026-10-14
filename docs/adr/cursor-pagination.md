# ADR-004: Cursor Pagination, Server Ordering, Client-Generated IDs

- **Status:** Accepted
- **Date:** 2026-09-21
- **Owner:** [you]

## Context

Message history is fetched repeatedly (scroll-up, reconnect sync). Three naive choices bite later: `OFFSET` pagination (skips/duplicates rows under writes), client timestamps for ordering (untrustworthy clocks), and client "sent" identity (no way to dedupe a re-send after a dropped socket).

## Decision

1. **Cursor pagination everywhere:** `?cursor=<last_id>&limit=50`, query shaped as `WHERE conversation_id=? AND id < cursor ORDER BY id DESC LIMIT 50`. Never offsets.
2. **Server-side ordering:** `created_at` from the server clock (`clock_timestamp()`), ID as tiebreaker. Client time is never used for order.
3. **Client-generated message IDs:** the client creates the message UUID before sending; the server dedupes on the unique ID so re-sends after socket drops are safe.

## Consequences

- **Positive:** stable pagination under live traffic; identical query shape for history scroll and reconnect sync; no duplicate messages ever.
- **Negative:** cursors are opaque to clients (by design); message UUIDs must not collide (UUID4/UUIDv7).
- **Neutral:** slightly more discipline in the API contract (cursor, not page number).

## References

- `docs/design/conversations.md` §5, `docs/design/realtime.md` §7