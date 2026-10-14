# ADR-005: Event-Only Notification Rows

- **Status:** Accepted
- **Date:** 2026-09-21
- **Owner:** [you]

## Context

The obvious-but-wrong design writes a notification row for every message (content, sender, time). With derived unread badges (ADR-003), a per-message notification row is pure duplicate work: the badge already encodes "new messages exist", and the message row itself is the source of truth.

## Decision

The `notifications` table holds rows **only for discrete social events**: friend request, friend-request accepted, group invite, reaction, mention. A new **message** never creates a row; it is pushed live over WebSocket (online) or caught up via the last-read pointer (offline). Muting is a membership flag that suppresses alerts but never suppresses the derived badge.

## Consequences

- **Positive:** notification feed stays small and meaningful; no write per message; mute is trivial; push (later) piggybacks on the same event types.
- **Negative:** the feed does not list every message (that's what the conversation panel is for).
- **Neutral:** "bell" = events; "unread" = conversations; the mental split must survive into the UI later.

## References

- `docs/design/notifications.md`, `docs/design/realtime.md` §6