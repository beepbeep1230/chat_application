# Design — Relations (Friendship, Invites, Blocks)

- **Status:** Draft
- **Last updated:** 2026-09-21
- **Related:** `docs/prd.md` §5.3, §5.4; ADR-006

This doc covers the *social graph*: friendships, group invites, and blocks.

---

## 1. Purpose

Define how users connect (friend requests), group together (conversation invites), and cut ties (blocks, unfriends).

## 2. Requirements mapping

FR-8..FR-11 (friends), FR-12..FR-16 (blocks), FR-19 (group invites), D-1 (unfriend → DM rule).

## 3. Friendship model

One row per pair of users, in a fixed direction `(requester → addressee)`:

| State | Meaning |
|---|---|
| `pending` | request sent, not yet answered |
| `accepted` | friends; DMs allowed |
| (no row) | strangers; must request to chat |

Rules:

- At most one outstanding request per direction (`requester, addressee` unique).
- Two users could theoretically both have pending requests to each other — **simplify:** when a request exists in either direction, sending the reverse request auto-accepts instead of creating a second pending row.
- **Unfriend** = delete the friendship row entirely. To be friends again you must re-request.
- **Block + friendship:** while a block exists, an `accepted` friendship is *frozen*, not deleted. Unblocking restores it (see ADR-006).

### What happens to the DM on unfriend? (D-1)

**Proposed rule:** the direct conversation's *history stays visible and readable*, but sending is disabled until the pair is friends again. Restrictive enough to make friendship meaningful; forgiving enough not to nuke chat history. *Awaiting user approval.*

## 4. Group invites

Invitation to join a group conversation, one row per invite:

```
inviter, invitee, conversation_id, status: pending | accepted | declined
```

Rules:

- Sent by group `admin`/`owner` (see `conversations.md`).
- Received invites appear in the invitee's feed; accepting adds them as a `member`.
- **Blocked users**: invites from a blocked user auto-reject (FR-15).
- The invitee must accept; you cannot join a group silently.

## 5. Blocks — full-ignore semantics

A block is one row `(blocker → blocked)`. It means **out-of-sight, not retaliation-free**:

| What | Behavior |
|---|---|
| Blocked → blocker DMs | still "sent" by B, **silently dropped** by server (A never sees them) |
| Blocker → blocked DMs | **frozen** — A's chat is hidden, A can't send while blocked |
| Friendship row | kept but frozen; unblock restores it |
| Friend request from blocked | auto-rejected |
| Group invite from blocked | auto-rejected |
| Presence | blocked user does not see the blocker's online status |
| Blocked list | blocker can list / unblock anytime |

Why drop instead of error? If B's app shows "delivered" while A never sees it, B has no signal to retaliate — a standard safety pattern in messaging products.

## 6. Endpoints

### Friends
| Method | Path | Purpose |
|---|---|---|
| POST | `/friends/requests` | `{to_user_id}` — send request |
| POST | `/friends/requests/{id}/accept` | accept |
| POST | `/friends/requests/{id}/decline` | decline |
| DELETE | `/friends/requests/{id}` | withdraw own request |
| GET | `/friends/requests` | incoming pending |
| GET | `/friends/requests/sent` | outgoing pending |
| GET | `/friends` | accepted friendships |
| DELETE | `/friends/{user_id}` | unfriend |

### Blocks
| Method | Path | Purpose |
|---|---|---|
| POST | `/users/{user_id}/block` | block |
| DELETE | `/users/{user_id}/block` | unblock |
| GET | `/users/blocked` | list blocked |

### Invites (also cross-referenced in conversations.md)
| Method | Path | Purpose |
|---|---|---|
| POST | `/conversations/{id}/invites` | invite (admin/owner) |
| POST | `/invites/{id}/accept` | accept |
| POST | `/invites/{id}/decline` | decline |

## 7. Rules & edge cases

- Can't friend, invite, or DM yourself.
- Can't block yourself.
- Blocking a user also removes them from your presence visibility (they see you as offline).
- If a friendship is pending and the requester blocks the addressee, the pending request is auto-cancelled.
- Unblock ≠ re-friend: it only unfreezes whatever friendship existed.

## 8. Open questions / decisions

- **D-1** pending approval: unfriend keeps DM history visible but read-only.
- Should unfriending also *remove* your messages from the DM? (Lean: no — soft-delete plus read-only keeps things reversible and learnable.)