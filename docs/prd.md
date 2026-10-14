# PRD — Chat App

- **Status:** Draft (pending human approval)
- **Last updated:** 2026-09-21
- **Owner:** [you]
- **Authored by:** human designer + agent suggestions

---

## 1. Overview

A real-time chat application. Users register, verify their email, find other users, become friends, and chat 1-on-1 or in groups. Messages can be text, emoji, or files, and support replies, reactions, and deletion (editing comes later). Users control their social graph through friend requests, blocks, and group invites. Notifications surface *events* (friend request, invite, reaction, mention); unread counts are **derived** from read receipts rather than stored per message.

This prototype is **API-only**: no frontend, no mobile push. The API must be designed so a web or mobile client can be added later without reshaping the backend.

## 2. Goals

- A simple, correct, learnable design (this is a learning project).
- Real-time chat over WebSockets; everything else is REST.
- Clean separation between:
  - account credentials (username, password hash),
  - personal data (phone, email, display name),
  - the social graph (friendships, blocks, invitations).

## 3. Non-goals (explicitly out of scope for the prototype)

- Frontend / mobile client
- Message editing (the design leaves room for it)
- Two-factor authentication
- Mobile push notifications (APNs / FCM)
- Full-text search across messages
- Database schema details, Alembic migrations, deployment (later phase)

## 4. Key terms

| Term | Meaning |
|---|---|
| Account | Login identity: username + password hash + status. |
| Profile | Personal data: phone, email, display name, avatar, bio, presence. 1-to-1 with an account. |
| Conversation | A chat. A single concept covers both direct and group chats. |
| Direct conversation | A conversation with exactly 2 members (friends). |
| Group conversation | A conversation with 2+ members and roles (owner / admin / member). |
| Member role | `owner`, `admin`, or `member` inside a group conversation. |
| Friendship | A row for a pair of users with status `pending` or `accepted`. |
| Block | A row from blocker → blocked. Freezes the friendship; drops delivery. |
| Read receipt | Per-member pointer to the last message they have read. |

## 5. Functional requirements

### 5.1 Authentication

- **FR-1** Register with username, email, password.
- **FR-2** Email verification required before first login.
- **FR-3** Login with username **or** email + password → access + refresh tokens.
- **FR-4** Refresh endpoint with token rotation; logout revokes tokens.
- **FR-5** `me` endpoint to fetch and update your own account and profile.

### 5.2 Users

- **FR-6** Search users by username (partial match), paged.
- **FR-7** View a user's profile, limited to public fields.

### 5.3 Friends

- **FR-8** Send a friend request; at most one outstanding request per direction.
- **FR-9** Accept, decline, or withdraw a request.
- **FR-10** List friends and pending requests (incoming and outgoing).
- **FR-11** Unfriend deletes the friendship row entirely.

### 5.4 Blocks

- **FR-12** Block a user (full-ignore semantics, see below).
- **FR-13** While blocked, the blocked user may still "send", but every message is **silently dropped** and never reaches the blocker.
- **FR-14** A friendship with a blocked user is **frozen in place** (row kept) so that unblocking restores it.
- **FR-15** Friend requests and group invites from a blocked user are automatically rejected.
- **FR-16** Users can list who they blocked, and unblock.

### 5.5 Conversations

- **FR-17** Create a direct conversation with a friend (exactly 2 members).
- **FR-18** Create a group conversation; the creator becomes `owner`.
- **FR-19** Invite others to a group; the invite must be accepted to join.
- **FR-20** List my conversations with last-message preview and unread count.
- **FR-21** View conversation detail (members, title, description, mute state).
- **FR-22** Group `admin`/`owner` can edit title and description.
- **FR-23** Group permissions:
  - `member`: nothing (may leave the group).
  - `admin`: invite, kick members, edit title/description.
  - `owner`: everything an admin can do + delete the group + promote/demote admins.
- **FR-24** Mute/unmute a conversation per member. Muted chats still count toward the unread badge but suppress notifications.

### 5.6 Messages

- **FR-25** Message types: `text`, `emoji`, `file`, `system`; replies via a parent-message reference.
- **FR-26** Paginate message history with cursors (never offsets).
- **FR-27** Soft-delete a message → it becomes a "message deleted" placeholder.
- **FR-28** Reactions: one emoji per user per message; add and remove.
- **FR-29** Reply: reference a parent message (threads can come later).
- **FR-30** Read receipts: each member tracks the last message they read; drives delivered/read state and unread badges.
- **FR-31** Message ordering by server timestamp; client-generated message IDs dedupe re-sends after drops.

### 5.7 Files

- **FR-32** Upload a file → returns file metadata; attach it to a message.
- **FR-33** Download requires authentication and membership in the owning conversation.

### 5.8 Notifications

- **FR-34** A notifications feed containing only *events*: friend request, group invite, reaction, mention.
- **FR-35** Per-conversation mute suppresses notifications; the unread badge is always derived from read receipts.
- **FR-36** Mark one notification read; mark all read.

### 5.9 Realtime

- **FR-37** One authenticated WebSocket endpoint pushes events: new message, message deleted, reaction, read, typing, presence.
- **FR-38** Reconnect sync: on connect, the client fetches everything after its last-read pointer.

## 6. Cross-cutting concerns

- **C-1** Personal data (profile) is separated from credentials (account).
- **C-2** All timestamps are UTC; ordering uses server time, never client time.
- **C-3** Rate limiting on message send and social-request endpoints.
- **C-4** Account deletion must eventually be possible; define what happens to messages (deferred, but keep in mind soft-delete structure).
- **C-5** Prototype uses permissive CORS (already configured) since there is no frontend yet.

## 7. Decision log / open questions

| # | Question | Decision |
|---|---|---|
| D-1 | What happens to a direct conversation when users unfriend? | **Proposed:** history stays visible and readable; sending disabled until re-friended. Awaiting user approval. |
| D-2 | Presence scope in the prototype | Only online/offline + `last_seen_at`. Custom statuses later. |

---

*Schema details, index choices, and migrations are deliberately deferred to a later phase (see `docs/design/app_layout.md` §5).*