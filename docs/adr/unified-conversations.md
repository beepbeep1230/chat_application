# ADR-001: Unified Conversations

- **Status:** Accepted
- **Date:** 2026-09-21
- **Owner:** [you]

## Context

The app has two kinds of chat: direct (1-on-1 between friends) and group (2+ members with roles). A tempting design is two separate room models (e.g. `direct_chats` + `group_chats`), but every feature — messages, reactions, read receipts, pagination, mute — then has to be implemented twice, and cross-chat features (forwarding, search, pins) become painful.

## Decision

Use **one `conversations` entity** with `type: direct | group`. A direct conversation is just a conversation whose membership is capped at two. All message/reaction/read/mute logic lives on the unified model. Roles (`owner | admin | member`) apply to groups; direct members default to `member`.

## Consequences

- **Positive:** one implementation of the message stack; free future features (forwarding, unified search, pinning); simpler API.
- **Negative:** rules like "direct chats have ≤ 2 members" and "no roles in direct chats" must be enforced at the application layer rather than by separate tables.
- **Neutral:** conversation membership becomes the single source of truth for "who can see this chat".

## References

- `docs/design/conversations.md` §3