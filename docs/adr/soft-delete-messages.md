# ADR-002: Soft-Delete Messages

- **Status:** Accepted. Amended (2026-11-11) by `docs/design/messages.md` §6: "delete for me" is decided (table `message_hidden_for`), and delete for everyone also removes the message's file links. The soft-delete idea stays.
- **Date:** 2026-09-21
- **Owner:** [you]

## Context

Messages can be deleted. Hard-deleting rows breaks the parts of the app that reference messages by ID: read receipts, reactions, replies, and in-chat ordering all rely on rows existing. It also makes "delete for me only" and account-retention rules impossible later.

## Decision

Messages are **soft-deleted**: a `deleted_for_everyone` flag; on delete the `content` is set to NULL and the UI renders a placeholder ("This message was deleted"). The row and its metadata survive. Per-user deletion (`deleted_for`) is a later extension, not part of the prototype.

## Consequences

- **Positive:** replies/reactions/receipts keep working after a delete; reversible and auditable; clean path to delete-for-me later.
- **Negative:** rows accumulate (mitigated later by purging jobs); every read of a message must apply the deleted filter.
- **Neutral:** "deleted" is a rendering rule, not a storage rule.

## References

- `docs/design/messages.md` §6