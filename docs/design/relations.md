# Design — Relations (Friend Requests, Friendships, Blocks)

- **Status:** Friends & blocks implemented; group invites planned
- **Last updated:** 2026-10-30
- **Code:** `app/modules/friends/`
- **Related:** `docs/prd.md` §5.3–5.4, `errors.md`, ADR-004, ADR-006 (amended), ADR-011

---

## 1. Purpose

The social graph: how two users become friends, stop being friends, and block each other.

## 2. Requirements mapping

| PRD | Status |
|---|---|
| FR-8 send request, one outstanding per pair | ✅ (one per **pair**, either direction) |
| FR-9 accept / decline / withdraw | ✅ + cooldown after decline (ADR-011) |
| FR-10 list friends, incoming and outgoing requests | ✅ cursor-paginated |
| FR-11 unfriend deletes the friendship | ✅ |
| FR-12 block | ✅ |
| FR-13 messages from a blocked user dropped | planned (needs messages) |
| FR-14 friendship kept while blocked | ✅ kept — see §5 and ADR-006 amendment |
| FR-15 requests from a blocked user rejected | ✅ (`403`, both directions); invites planned |
| FR-16 list / unblock | ✅ |

## 3. Data model

```
friend_requests   id PK (uuid7) · requester_id · addressee_id · created_at
                  CHECK requester_id <> addressee_id
                  UNIQUE (LEAST(requester_id, addressee_id), GREATEST(...))   ← one request per pair
                  holds PENDING requests only

friends_lists     (user_id, friend_id) PK · created_at
                  CHECK user_id <> friend_id
                  TWO rows per friendship (A→B and B→A) so "my friends" is one indexed lookup

user_block_lists  (user_id, blocked_user_id) PK · blocked_at
                  CHECK user_id <> blocked_user_id      one row per direction
```

All foreign keys point to `user_account.uuid` with `ON DELETE CASCADE`.
A request row is **deleted** when it is accepted (moved to `friends_lists`), declined
(cooldown goes to Redis), withdrawn, or cleared by a block.

## 4. Friend-request state machine

```
              send (A→B)                        accept (by B)
 (nothing) ─────────────▶ pending A→B ───────────────────────▶ friends (2 rows)
     ▲                       │  │  │
     │      withdraw (by A)  │  │  │ decline (by B) ──▶ (nothing) + cooldown A→B in Redis
     └───────────────────────┘  │  │
     B sends B→A while pending ─┘  └─ A or B blocks the other ──▶ (nothing)
     = auto-accept → friends
```

## 5. Blocks — what is implemented

A block is one row `(blocker → blocked)`.

| Effect | Behaviour today |
|---|---|
| Pending requests between the pair | deleted (both directions) |
| New friend requests | rejected with `403 REQUEST_NOT_ALLOWED`, **either** direction |
| Existing friendship | **kept** (rows untouched) |
| Blocker's `GET /friends` | hides the blocked user |
| Blocked user's `GET /friends` | still shows the blocker (accepted trade-off — ADR-006 amendment) |
| Unfriend while blocked | allowed |
| Unblock | the blocked user reappears in the blocker's friend list |
| Messages, invites, presence | planned with those features |

## 6. Group invites (planned)

One row per invite `(inviter, invitee, conversation_id, status)`. Sent by group admin/owner,
must be accepted to join, auto-rejected when a block exists. Details: `conversations.md`.

## 7. Endpoints (`/api/v1`, tag `relations`)

All endpoints need `Authorization: Bearer <accessToken>` and can return the auth errors of
`accounts_auth.md` §8 and `503 DATABASE_UNAVAILABLE`.

`UserBrief` (used in lists): `{"userId", "username", "displayName", "avatarUrl"}`.

### 7.1 `POST /friends/requests` → `201`

**Input:** `{"userId": "<uuid>"}`
**Output:**
```json
{"message": "Friend request sent.",
 "data": {"status": "pending", "sentFrom": "<me>", "sentTo": "<them>",
          "requestId": "<uuid>", "createdAt": "2026-10-30T12:00:00Z"}}
```
If **they had already sent me** a request, it is accepted instead: same `201`, but
`data.status` is `"accepted"`. Clients must read `data.status`, not the status code.

Checks, in this order:

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | body missing / `userId` not a UUID |
| 400 | `SELF_REQUEST` | `userId` is me |
| 404 | `USER_NOT_FOUND` | no such user |
| 403 | `REQUEST_NOT_ALLOWED` | a block exists in either direction |
| 409 | `ALREADY_FRIENDS` | already friends |
| 409 | `REQUEST_ALREADY_EXISTS` | I already have a pending request to them (also on a simultaneous duplicate) |
| 429 | `REQUEST_COOLDOWN` | they declined me recently; header `Retry-After: <seconds>` |

Side effect: if I had declined **them** earlier, their cooldown toward me is cleared.

### 7.2 `GET /friends/requests` (incoming) and `GET /friends/requests/sent` (outgoing) → `200`

**Input:** `?limit=1..100` (default 50), `?cursor=<nextCursor>`
**Output:** newest first; `user` is the **other** person.
```json
{"message": null,
 "data": {"items": [{"requestId": "<uuid>", "user": {"userId": "…", "username": "bob_02",
                     "displayName": "Bob", "avatarUrl": null}, "createdAt": "…"}],
          "nextCursor": "<opaque or null>"}}
```

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `limit` out of range |
| 400 | `INVALID_CURSOR` | cursor not produced by this endpoint |

### 7.3 `POST /friends/requests/{request_id}/accept` → `200`

Only the **addressee** can accept.
**Output:** `{"message": "Request accepted.", "data": {<as 7.1, status "accepted">}}`

| Status | `code` | When |
|---|---|---|
| 404 | `REQUEST_NOT_FOUND` | no such pending request addressed to me |

### 7.4 `POST /friends/requests/{request_id}/decline` → `204`

Only the addressee. Deletes the request and stores a cooldown for the requester
(`request_cool_down` days, ADR-011). Errors: `404 REQUEST_NOT_FOUND`.

### 7.5 `DELETE /friends/requests/{request_id}` (withdraw) → `204`

Only the **requester**. Errors: `404 REQUEST_NOT_FOUND`.

### 7.6 `GET /friends` → `200`

**Input:** `?limit`, `?cursor`. **Output:** `{"items": [UserBrief], "nextCursor"}` — newest
friendship first; users **I** blocked are hidden. Errors: `400 VALIDATION_ERROR`, `400 INVALID_CURSOR`.

### 7.7 `DELETE /friends/{user_id}` (unfriend) → `204`

Deletes both rows. Re-friending needs a new request.

| Status | `code` | When |
|---|---|---|
| 400 | `SELF_REQUEST` | `user_id` is me |
| 404 | `NOT_FRIENDS` | not friends |

### 7.8 `POST /blocks/{user_id}` → `201`

**Output:** `{"message": null, "data": {"blockedUser": "<uuid>", "blockedAt": "…"}}`
Effects: §5.

| Status | `code` | When |
|---|---|---|
| 400 | `SELF_REQUEST` | blocking myself |
| 404 | `USER_NOT_FOUND` | no such user |
| 409 | `ALREADY_BLOCKED` | already blocked |

### 7.9 `DELETE /blocks/{user_id}` (unblock) → `204`

| Status | `code` | When |
|---|---|---|
| 400 | `SELF_REQUEST` | myself |
| 404 | `NOT_BLOCKED` | no such block |

### 7.10 `GET /blocks` → `200`

**Input:** `?limit`, `?cursor`. **Output:** `{"items": [UserBrief], "nextCursor"}` — most
recently blocked first. Errors: `400 VALIDATION_ERROR`, `400 INVALID_CURSOR`.

## 8. Concurrency and failure behaviour

- Two users sending each other a request at the same moment: the unique pair index lets
  only one insert win; the other gets `409 REQUEST_ALREADY_EXISTS` (`ON CONFLICT DO NOTHING`).
- Accepting inserts both friendship rows with `ON CONFLICT DO NOTHING`, so a double accept is harmless.
- **Redis down:** the cooldown fails **open** — `cooldown_remaining_second` returns 0 (no
  cooldown enforced) and a failed `set_cooldown` is only logged. Friend features keep working.

## 9. Open questions

- D-1 (PRD): what the direct conversation shows after an unfriend — decide with messages.
- Rename `SELF_REQUEST` for unfriend/block self-actions? (Stable codes must not be renamed
  after clients depend on them — decide before release.)
