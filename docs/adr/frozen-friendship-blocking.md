# ADR-006: Full-Ignore Blocking with Frozen Friendships

- **Status:** Accepted
- **Date:** 2026-09-21
- **Owner:** [you]

## Context

The design brief: "the user who got blocked can still send messages, but the blocker never receives them." This is an *ignore* semantic (Facebook-style) rather than a hard block (Telegram-style, which prevents sending entirely). We also had to decide whether blocking deletes the friendship.

## Decision

- A block is a row `(blocker → blocked)`.
- The blocked user may keep "sending", but every message is **silently dropped** server-side (their client shows it as sent — avoids retaliation loops).
- The blocker's view is **frozen**: the chat is hidden, sending is disabled while blocked.
- A friendship involving a blocked user is **kept but frozen** — unblocking restores it without re-requesting.
- Friend requests and group invites from a blocked user are auto-rejected; presence is hidden from them.
- A dedicated blocked-list endpoint lets users review and unblock (FR-16).

## Consequences

- **Positive:** safe to block (no detectable retaliation signal); unblock is non-destructive; simple `(blocker, blocked)` pair with uniqueness.
- **Negative:** asymmetric behaviour (B "sends" but A never gets it) must be handled carefully in message-send logic.
- **Neutral:** this is a policy decision, recorded because it shapes message delivery and the friendship state machine.

## References

- `docs/design/relations.md` §5, `docs/prd.md` §5.4