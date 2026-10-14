# Design — Application Layout

- **Status:** Draft
- **Last updated:** 2026-09-21

This is the canonical reference for how the whole app is organized: code layers, feature modules, the API surface, and the key data flows.

---

## 1. Code layers

The existing repo skeleton already hints at this structure; the layout below completes it.

```
app/
├─ main.py             FastAPI app, CORS, mounts all routers
├─ config.py           settings from .env (DB URL, JWT secret, SMTP, storage path)
├─ routers/            HTTP endpoints + WebSocket, one file per feature
├─ schemas/            Pydantic request/response shapes
├─ models/             SQLAlchemy models (FILLED IN Phase 2 — schema deferred)
├─ crud/               database operations per feature
├─ auth/               JWT issue/verify, password hashing, current-user dependency
├─ ws/                 WebSocket connection manager
└─ utils/              helpers, exception handlers, rate limiting
```

**Rule of thumb:** routers parse the request and call a crud function; crud talks to the database; anything shared (auth, errors, limits) lives in `auth/` or `utils/`. Keep routers thin.

## 2. Feature modules (what users can do)

```
Auth         register → verify email → login (username|email) → refresh → logout → me
Users        search users, view public profile
Friends      send / accept / decline / withdraw request; list friends; unfriend
Blocks       block; unblock; list blocked users
Conversations  create direct chat; create group; list my chats (preview + unread);
             invite / accept; edit title+description; kick; promote/demote admin;
             leave; mute/unmute; delete group (owner)
Messages     send (text | emoji | file | reply); paginate; soft delete;
             react / unreact; mark read
Files        upload; download (auth + membership checked)
Notifications  event feed; mark read; mark all read
Realtime     /ws — push message_new, message_deleted, reaction_new, read, typing,
             presence; reconnect sync
```

## 3. API surface (endpoint groups)

Conventions: all JSON; auth via `Authorization: Bearer <access>`; cursors via `?cursor=<id>&limit=50`.

### Auth
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | create account (unverified) |
| POST | `/auth/verify-email` | complete registration with token/OTP |
| POST | `/auth/login` | username or email + password → tokens |
| POST | `/auth/refresh` | rotate refresh token |
| POST | `/auth/logout` | revoke refresh token |
| GET | `/auth/me` | own account + profile |
| PATCH | `/auth/me` | update own profile |

### Users
| Method | Path | Purpose |
|---|---|---|
| GET | `/users/search?q=&cursor=` | search by username |
| GET | `/users/{user_id}` | public profile |

### Friends
| Method | Path | Purpose |
|---|---|---|
| POST | `/friends/requests` | send request |
| POST | `/friends/requests/{id}/accept` | accept |
| POST | `/friends/requests/{id}/decline` | decline |
| DELETE | `/friends/requests/{id}` | withdraw own request |
| GET | `/friends/requests` | incoming pending |
| GET | `/friends/requests/sent` | outgoing pending |
| GET | `/friends` | accepted friends |
| DELETE | `/friends/{user_id}` | unfriend (delete row) |

### Blocks
| Method | Path | Purpose |
|---|---|---|
| POST | `/users/{user_id}/block` | block |
| DELETE | `/users/{user_id}/block` | unblock |
| GET | `/users/blocked` | list blocked users |

### Conversations
| Method | Path | Purpose |
|---|---|---|
| GET | `/conversations` | my chats + preview + unread |
| POST | `/conversations` | create direct or group |
| GET | `/conversations/{id}` | detail: members, title, description, mute |
| PATCH | `/conversations/{id}` | edit title/description (admin/owner) |
| DELETE | `/conversations/{id}` | delete group (owner) |
| POST | `/conversations/{id}/invites` | invite user (admin/owner) |
| POST | `/invites/{id}/accept` | accept group invite |
| POST | `/invites/{id}/decline` | decline group invite |
| POST | `/conversations/{id}/members/{user_id}/admin` | promote to admin (owner) |
| DELETE | `/conversations/{id}/members/{user_id}/admin` | demote admin (owner) |
| DELETE | `/conversations/{id}/members/{user_id}` | kick (admin/owner) |
| POST | `/conversations/{id}/leave` | leave (member) |
| POST | `/conversations/{id}/mute` | mute (member) |
| DELETE | `/conversations/{id}/mute` | unmute (member) |

### Messages
| Method | Path | Purpose |
|---|---|---|
| GET | `/conversations/{id}/messages?cursor=` | paginated history (newest first) |
| POST | `/conversations/{id}/messages` | send (text/emoji/file/reply) |
| DELETE | `/messages/{id}` | soft delete |
| POST | `/messages/{id}/reactions` | `{emoji}` |
| DELETE | `/messages/{id}/reactions` | remove my reaction |
| POST | `/conversations/{id}/read` | `{up_to_message_id}` — mark read ack |

### Files
| Method | Path | Purpose |
|---|---|---|
| POST | `/files` | multipart upload → metadata |
| GET | `/files/{id}` | download (auth + membership) |

### Notifications
| Method | Path | Purpose |
|---|---|---|
| GET | `/notifications?cursor=` | event feed (newest first) |
| POST | `/notifications/{id}/read` | mark one read |
| POST | `/notifications/read-all` | mark all read |

### Realtime
| Method | Path | Purpose |
|---|---|---|
| WS | `/ws?token=` | authenticated socket; server pushes events |

## 4. Data flows (the stories that matter)

### 4.1 Sending a message

```
sender ──POST /conversations/{id}/messages──▶ API
  1. API validates membership + block rules, saves the message,
     assigns server timestamp.
  2. API pushes {type:"message_new", payload:msg} to each ONLINE
     recipient's socket (respecting mute for alerts only).
  3. OFFLINE recipients: nothing pushed; their unread count is just
     "messages newer than last_read_message_id" — recomputed on fetch.
  4. Sender's own other sockets also receive the event (multi-device).
```

Client gives each message a UUID so a dropped send can be retried safely (see ADR-004).

### 4.2 Blocking a user

```
A blocks B:
  1. Write a block row (A → B).
  2. Friendship row (if any) is FROZEN, not deleted — unblock restores it.
  3. Conversation is hidden from A's list; A can no longer send to B.
  4. B keeps "sending": messages pass validation but are DROPPED
     (B's client still shows them as sent — no retaliation loop).
  5. Incoming friend requests / group invites from B are auto-rejected.
  6. A's block list shows B; A may unblock anytime.
```

### 4.3 Notification lifecycle

```
Event happens (friend request / invite / reaction / mention):
  → create ONE notifications row (recipient, type, actor, payload, created_at)
  → push the event over WebSocket if recipient is online.

Message arrives (NOT an event):
  → no notification row. Online → pushed live.
  → Offline → caught up on reconnect via last-read pointer.
  → Unread badge = COUNT(messages > last_read_message_id), computed on demand.

Mute (per conversation):
  → suppresses push alerts / mention notifications for that conversation.
  → unread badge still increments (mute ≠ ignore, just quieter).
```

## 5. Deferred to Phase 2

- Database schema, column types, indexes, constraints
- Alembic migrations
- Exact Pydantic schemas / response shapes
- Deployment, environment provisioning

The design docs in this folder define *behavior*; the schema phase turns them into tables.