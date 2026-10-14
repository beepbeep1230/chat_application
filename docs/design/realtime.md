# Design — Realtime (WebSockets)

- **Status:** Draft
- **Last updated:** 2026-09-21
- **Related:** `docs/prd.md` §5.9, ADR-004

---

## 1. Purpose

Push events to connected clients in real time, and define what happens when they disconnect and reconnect.

## 2. Requirements mapping

FR-37 (one socket, push events), FR-38 (reconnect sync), C-2 (server-time ordering).

## 3. Principle: WebSockets push, REST does everything else

- **One** socket endpoint: `WS /ws?token=<access_token>`.
- The socket is **push-only from the server** (plus small acks from the client).
- Sending messages, pagination, reactions, everything is ordinary HTTP — durable and retryable.
- The socket authenticates with the same access token as REST; a 401/expired token closes the socket.

## 4. Connection manager

In-process manager (one instance today; documented upgrade path below):

```
class ConnectionManager:
    connections: dict[user_id, set[WebSocket]]

    connect(ws, user_id)
    disconnect(ws, user_id)
    send_to_user(user_id, event: dict)
    broadcast_to_conversation(conversation_id, event)   # via member lookup
    is_online(user_id) -> bool                          # feeds presence
```

- Multiple sockets per user (multiple devices/tabs) — `set[WebSocket]`.
- On app startup, this lives in `app/ws/`. 

### Scale-up path (when you leave the prototype)

Move the pub/sub bus to **Redis pub/sub** or **Postgres LISTEN/NOTIFY**; every API worker subscribes and forwards events. The *event envelope format does not change* — only where `send_to_user` publishes.

## 5. Event envelope

Every server → client message is one JSON envelope:

```json
{
  "type": "message_new",
  "conversation_id": "uuid",
  "payload": { },
  "server_ts": "2026-09-21T12:00:00Z"
}
```

Client → server acks are minimal:

```json
{ "type": "read", "conversation_id": "uuid", "up_to_message_id": "uuid" }
```

## 6. Event catalog

| Event | Trigger | Payload includes |
|---|---|---|
| `message_new` | message saved | full message body |
| `message_deleted` | soft delete | message_id, placeholder render flag |
| `reaction_new` / `reaction_removed` | reaction change | message_id, emoji, user |
| `read` | recipient acks `up_to_message_id` | conversation_id, user, pointer |
| `typing` | client sends `typing` | conversation_id, user (no persistence) |
| `presence` | connect/disconnect | user_id, online, last_seen_at |
| `membership` | invited/joined/kicked/promoted | conversation_id, user, role-change |

## 7. Reconnect & ordering (FR-38, ADR-004)

1. Client connects → sends `{"type":"read", "up_to_message_id": <last seen>}` or fetches `GET /conversations/{id}/messages`.
2. Server orders everything by its own `created_at` (+ message id tiebreak).
3. Client-side: if an event is older than the oldest frame the client holds, ignore or refetch — never insert out of order.
4. **Dedupe:** client-generated message UUIDs make re-sends idempotent (see ADR-004).

## 8. Presence

- `connect` marks user online + pushes `presence` to relevant others.
- `disconnect` (heartbeat timeout) marks offline + sets `last_seen_at`.
- Heartbeat: client pings every ~30s; server drops dead sockets after ~2 missed.
- Blocked users never see each other's presence (relations.md §5).

## 9. Rules & edge cases

- Every pushed event must be authorised: the server resolves conversation membership before pushing.
- Never echo messages to a sender as an *exception* — echo them as confirmation to all their sockets.
- Socket receives **no** message content for conversations they were kicked from; a `membership` event closes lingering handlers.
- Rate limit socket connects to prevent reconnect storms.

## 10. Future (not today)

- Typing indicators (already designed; trivial to implement).
- Ephemeral "is online" list per conversation.
- Mobile push bridging (FCM/APNs) — build on the same event catalog.