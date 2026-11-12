# Design — Accounts & Authentication (scope A)

- **Status:** Registration, login and profile are implemented. The login session model (§6-§9)
  is the target design and is **not built yet**: see §14 for what today's code does differently.
- **Last updated:** 2026-11-12
- **Code:** `app/modules/auth/`, `app/modules/users/`, `app/core/security.py`
- **Uses:** `errors.md` (error shape), `fanout.md` (carries `session.ended`), `realtime.md`
  (sockets close when a login ends)

---

## 1. Purpose

Registration, email verification, login, the login session and its tokens, the check on every
request, and the current user's own profile.

## 2. Requirements mapping

| PRD | Status |
|---|---|
| FR-1 register | ✅ |
| FR-2 email verification before first login | ⚠️ endpoint works; sending the email is disabled and `dev_mode` auto-activates (§15) |
| FR-3 login with username **or** email | ✅ |
| FR-4 refresh with rotation, logout | Target: §9 (rotation inside one login); logout and logout-all built |
| FR-5 read/update own profile | ✅ profile fields only; email change deferred |
| C-1 personal data separate from credentials | ✅ with one deliberate exception: `email` is on the account (§3) |

## 3. Data model

```
user_account   uuid PK (uuid7) · username CITEXT UNIQUE · email CITEXT UNIQUE
               password_hash · status (unverified | active | suspended)
               created_at · updated_at

user_profile   username PK → user_account.username (ON DELETE CASCADE)
               display_name ≤30 · bio ≤200 · avatar_url ≤500 · last_seen_at
               created_at · updated_at

user_session   sid PK · user_id → user_account.uuid (ON DELETE CASCADE)       ← one row per LOGIN
(UserSession)  created_at · expires_at (login + 30 days) · revoked_at (NULL = active)

Redis          auth:session:{sid}  hash {user_id, cur, prev, rotated_at, abs_exp}
                                   ← the refresh token's state; the only copy
```

- `username` and `email` are **case-insensitive** (`CITEXT`): `Alice_01` and `alice_01` collide.
- `email` lives on the **account** because it is a login identifier, a deliberate exception to C-1.
- Class names: `UserSession` (table `user_session`); `UserAccount.sessions`.
- All relationships use `lazy="raise"`: related rows must be loaded explicitly (`joinedload`).

## 4. Input rules

| Field | Rule |
|---|---|
| `username` | 5–30 chars, `^[A-Za-z0-9_.-]{5,30}$`. No `@`, so a username can never equal someone's email (login looks up both) |
| `email` | valid email (`EmailStr`), ≤ 320 chars |
| `password` | 8–30 chars, at least one lowercase, uppercase, digit and punctuation character |
| `passwordRepeated` | must equal `password` (reported without a field name) |

## 5. Tokens

| Token | Where it travels | Lifetime | Claims |
|---|---|---|---|
| access (JWT, HS256) | JSON body → client sends `Authorization: Bearer …` | 15 min | `sub` user id · `sid` · `jti` · `rti` (the parent refresh token's `jti`) · `iat` · `exp` · `type="access"` |
| refresh (JWT) | `refreshToken` cookie only, never in JSON | 7 days, rotated on every use | `sub` · `sid` · `jti` · `iat` · `exp` · `type="refresh"` |
| email verification | link `…/auth/verify-email?token=` | `mail_token_life_min` | the email address, signed with `itsdangerous` (salted); stateless |

Refresh cookie attributes: `HttpOnly`, `Secure`, `SameSite=strict`, `Path=/api/v1/auth`,
`Max-Age` = refresh lifetime. Because of the path, the browser sends it only to `/auth/*`.
Logout, logout-all and the theft response clear it (`Max-Age=0`). `Secure` needs HTTPS: the owner
adds it once the laptop server is set up (scope G, `infrastructure.md` §4.3). Browsers treat
`localhost` as secure, so dev on localhost still works (not checked for the owner's browser).

The client sends only the refresh token, with no second secret: `sid` is readable in every JWT, so
it proves nothing.

## 6. The login session: three layers

```
LOGIN SESSION  (Postgres row, sid PK)          30 days absolute; not a token
  -> REFRESH TOKEN  (Redis hash only)          7 days = idle timeout; rotated on every refresh
       -> ACCESS TOKEN  (JWT, 15 min)          child of ONE refresh token (rti)
```

- One `sid` for the whole login, from login to logout; only `jti` changes on refresh. The socket
  and the backup check (`realtime.md` §5) rely on this.
- **Idle timeout:** a refresh token unused for 7 days expires, and the user logs in again (new
  login row). The login row cannot make a refresh token by itself; accepting expired refresh tokens
  would make the short life meaningless.
- **Access token is a child (M2):** every request checks `HGET auth:session:{sid} cur == rti`. An
  access token dies at its next request after a rotation, not at its own expiry.
- **Login ends** (logout, logout-all, theft, ban): publish `session.ended` with the `sid` on
  `user:{id}` (`fanout.md`); the worker holding that socket closes it with 4000.

## 7. Check on every request; Redis is required

```
Bearer token ──▶ verify signature, expiry, type == "access"             (else 401)
             ──▶ Redis  HGET auth:session:{sid} cur
                   == rti      → active
                   missing                                             → 401 INVALID_TOKEN (login revoked or expired)
                   != rti                                              → 401 TOKEN_EXPIRED (token replaced by a refresh)
                   Redis down / breaker open                           → 503 CACHE_UNAVAILABLE
             ──▶ load account (status must be active) + profile        (else 401 UNAUTHENTICATED)
```

- **Fail closed:** when Redis is down, auth answers 503 and the client shows "reconnecting". There
  is no DB fallback: the hash is the only copy of the refresh token, and when Postgres is down the
  app is down anyway. Availability later comes from a replica + Sentinel on separate machines.
- **How (decided 2026-11-12):** the circuit breaker gets a fail-closed mode. Auth calls **raise**
  `CacheError` (→ 503 `CACHE_UNAVAILABLE`) instead of returning a fallback; the friend cooldown
  keeps its fallback. While the breaker is open, auth answers 503 at once instead of every request
  waiting ~1 s for a Redis timeout, so workers do not pile up. Why: the refresh token lives only in
  Redis, so there is nothing to fall back to.
- **Lost rotation (accepted):** AOF `everysec` can lose ~1 s of writes on a Redis crash (and a
  replica failover can lose writes too). Then Redis holds an older `cur` than the client's token,
  so the next refresh looks like theft: one forced re-login. Estimate, not measured: 500 users /
  900 s ≈ 0.6 rotations/s, so about 1 user per crash.

### 7.1 Write order (Postgres row and Redis key)

Rule: **Redis decides whether a login is alive; the Postgres row is the record.** Decided
2026-11-12; the owner may revisit it during implementation.

| Action | Order | If step 2 fails |
|---|---|---|
| Login | 1. insert row + commit → 2. Redis `HSET` + `EXPIREAT` | 503; the row has no key, so the login is dead; best effort: mark it revoked |
| Logout | 1. Redis `DEL` → 2. mark row revoked + commit → 3. publish `session.ended` | Login already dead; only `revoked_at` is stale |
| Logout-all | 1. read live sids from Postgres → 2. `DEL` all keys in one call → 3. mark rows revoked + commit → 4. publish `session.ended` for each sid | As logout |

Why the row goes first on login:

```
t0  HSET auth:session:S1 (Redis first)
t1  INSERT row S1 -> COMMIT fails
t2  S1 works (Redis says alive) but has no Postgres row
t3  logout-all reads sids from Postgres -> S1 is not there -> S1 survives
```

## 8. Client rules

| Rule | Detail |
|---|---|
| One active tab per browser | A new tab takes over; the old one shows "open in another tab, *Use here*", closes its socket and stops refreshing. Client-only; the server cannot tell tabs apart (same cookie). Election (decided 2026-11-12, details when the client is built): the active tab holds a Web Lock; a new tab sends "take over" on a `BroadcastChannel`; the old tab releases the lock and shows "Use here". |
| Single-flight refresh | One refresh request in flight per browser: a Web Lock (`navigator.locks.request("refresh", ...)`) across tabs, plus one shared promise inside a tab. Requests that get a 401 wait for its result, then retry. Why: §9 trace. |
| After theft | The login page says "Your session was ended for security reasons". |

## 9. Refresh: one Lua script

Inputs: `sid`, the presented token's `jti` (`t`), a new `jti` made by the app (`n`). Checks in order:

| # | Check | Result | Writes |
|---|---|---|---|
| 0 | `now` = Redis `TIME` | | |
| 1 | key `auth:session:{sid}` missing | EXPIRED → 401 `INVALID_TOKEN` "log in again" | none |
| 2 | `now >= abs_exp` | EXPIRED → 401 `INVALID_TOKEN` | `DEL` |
| 3 | `t == cur` | ROTATE | `prev=cur`, `cur=n`, `rotated_at=now`, `EXPIREAT min(now+7d, abs_exp)` |
| 4 | `t == prev` and `now - rotated_at < 30` | GRACE | `cur=n` only; `prev` and `rotated_at` unchanged |
| 5 | anything else | THEFT → 401 `REFRESH_TOKEN_REUSED`, cookie cleared | `DEL`; then the app revokes the login row and publishes `session.ended` (`reason: "theft"`) |

| Detail | Rule | Why |
|---|---|---|
| Grace window | 30 s, a setting | Okta's default (range 0-60). Auth0 also accepts only the token just before the current one (its leeway is off by default). Both issue a **new** token on reuse inside the window. |
| `rotated_at` on grace | Unchanged | Otherwise a thief holding A could call every 29 s and keep the window open forever. Fixed at t0, A dies at t30. |
| `prev` on grace | Unchanged | Stops ping-pong between two holders inside the window |
| Clock | Redis `TIME` | One clock for every worker and later machine (Redis 7 allows `TIME` in scripts; not checked on the installed version) |
| Missing key | 401 "log in again", not theft | Usually a plain expiry or an earlier revoke; the security message is only for case 5 |
| New `jti` | Made by the app, passed in | The app signs the JWT; Lua has no good random source |
| Crash after `DEL`, before the Postgres revoke | Accepted | Redis is the authority, so the login is already dead; only `revoked_at` is stale |
| Concurrency | None needed | Redis runs one script at a time, so two refreshes never interleave |

Sources: Okta https://developer.okta.com/docs/guides/refresh-tokens/refresh-token-rotation/ ·
Auth0 https://auth0.com/docs/secure/tokens/refresh-tokens/configure-refresh-token-rotation

**Why grace exists (one tab is enough to need it):** the tab sends A; the server rotates A → B, but
the response is lost (Wi-Fi drop, reload mid-request). The cookie still holds A. Without grace the
retry is theft. Auth0 calls this the "reuse interval".

**Why single-flight refresh is needed (M2 + grace):**

```
t0  request R1 sends A   -> ROTATE: cur=B, prev=A
t1  request R2 sends A   -> GRACE:  cur=C, prev=A     (R2 started before R1's cookie arrived)
t2  browser applies C's Set-Cookie first, then B's     -> cookie = B
t3  next refresh sends B -> not cur (C), not prev (A) -> THEFT -> false logout
```

One active tab does not prevent this: one tab can get two 401s at the same moment.

**Theft trace (why the real user is logged out too):** user uses A → gets B (cur=B, prev=A). Thief
uses A within 30 s → grace → gets C (cur=C, prev stays A). User later sends B → not cur, not prev →
theft → DEL, revoke the login, `session.ended`. Both are out; only the real user knows the
password. The server cannot tell two holders of the same bytes apart, so prevention means making
the token hard to steal (`HttpOnly` + `Secure` + `SameSite` cookie) or useless once stolen (§13).

## 10. Auth endpoints (`/api/v1/auth`, tag `authentication`)

Common to all: `503 DATABASE_UNAVAILABLE` when Postgres is unreachable or busy (`errors.md` §5);
503 when Redis is down (§7). Every 401 carries `WWW-Authenticate: Bearer`.

### 10.1 `POST /auth/register` → `201`

**Input** (JSON, camelCase only):
```json
{"username": "alice_01", "email": "alice@example.com", "password": "Passw0rd!", "passwordRepeated": "Passw0rd!"}
```
**Output:**
```json
{"message": "Registered successfully, please check you mailbox for the verification mail.",
 "data": {"username": "alice_01", "email": "alice@example.com"}}
```
**Effects:** creates `user_account` (status `unverified`, or `active` when `dev_mode=true`)
and an empty `user_profile`.

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | any rule in §4 fails (`violations` lists each field) |
| 409 | `USER_EXISTS` | username **or** email already taken (also on a simultaneous duplicate, via the unique constraint) |

### 10.2 `GET /auth/verify-email?token=<token>` → `200`

**Input:** query `token` (the link from the email).
**Output:** `{"message": "Verified.", "data": {"username": "…", "email": "…"}}`
**Effects:** status `unverified` → `active`.

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `token` missing (`field: "query.token"`) |
| 401 | `TOKEN_EXPIRED` | token older than `mail_token_life_min` |
| 401 | `INVALID_TOKEN` | bad signature / tampered |
| 404 | `USER_NOT_FOUND` | no account for that email, or the account is suspended |
| 409 | `ALREADY_VERIFIED` | account already active (e.g. link clicked twice) |

### 10.3 `POST /auth/login` → `200`

**Input** (`application/x-www-form-urlencoded`, OAuth2 password form):
`username=<username or email>&password=<password>`
**Output:**
```json
{"message": "Login successfully.", "data": {"accessToken": "<jwt>", "tokenType": "bearer"}}
```
plus `Set-Cookie: refreshToken=<jwt>; HttpOnly; Secure; Path=/api/v1/auth; SameSite=strict; Max-Age=<refresh lifetime>`.
**Effects:** a new login row (new `sid`) and its Redis hash, row first (§7.1).

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `username` or `password` missing |
| 401 | `INVALID_CREDENTIALS` | unknown identifier, wrong password, **or** account not active: one code on purpose, so the response does not reveal which |

### 10.4 `POST /auth/refresh` → `200`

**Input:** `refreshToken` cookie. **Output:** same shape as login, with a new cookie.
**Effects:** the Lua script in §9. Same `sid`; new refresh `jti`; new access token with the new `rti`.

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | cookie missing (`field: "cookie.refreshToken"`) |
| 401 | `TOKEN_EXPIRED` | refresh JWT expired |
| 401 | `INVALID_TOKEN` | Redis key gone (§9 cases 1-2), bad signature, or an access token sent instead: log in again |
| 401 | `REFRESH_TOKEN_REUSED` (**new**) | theft (§9 case 5): login page + "Your session was ended for security reasons"; the response clears the cookie |

### 10.5 `POST /auth/logout` → `200`

**Input:** `refreshToken` cookie. **Output:** `{"message": "Logged out.", "data": null}`
**Effects:** revokes this login (`DEL` the hash, then row `revoked_at`, §7.1); publishes
`session.ended` with `reason: "logout"`; clears the cookie (`Max-Age=0`). Errors: as §10.4.

### 10.6 `POST /auth/logout-all` → `200`

**Input:** `refreshToken` cookie. **Output:** `{"message": "Logged out from all devices.", "data": null}`
**Effects:** revokes **every** active login of the token's user (order in §7.1); publishes
`session.ended` for each `sid` with `reason: "logout_all"`; clears the cookie (`Max-Age=0`). The
token only needs a valid signature: it may already be revoked, so a user can still cut off a thief.

**`session.ended` reasons** (decided 2026-11-12, details when the client is built): `logout`,
`logout_all`, `theft`. The client uses the reason to choose the message on the login page.

## 11. Profile endpoints (`/api/v1/users`, tag `users`)

Both need `Authorization: Bearer <accessToken>`. Auth errors for every protected endpoint
(also used by `relations.md`):

| Status | `code` | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | header missing, or the account is no longer active |
| 401 | `TOKEN_EXPIRED` | access token expired → call `/auth/refresh` |
| 401 | `INVALID_TOKEN` | bad signature, a refresh token sent, or the login was revoked → login page |
| 401 | `TOKEN_EXPIRED` | also when the token's `rti` is no longer `cur` (a refresh happened): single-flight refresh, then retry; if the client already holds a newer access token, just retry |
| 503 | `CACHE_UNAVAILABLE` | Redis down or breaker open (§7): "reconnecting", retry with backoff |

One new code only (`REFRESH_TOKEN_REUSED`, §10.4). A replaced `rti` shares `TOKEN_EXPIRED`
because the client does the same thing; if a thief did the rotation, the next refresh catches it as
theft anyway.

### 11.1 `GET /users/me` → `200`

**Output** (profile only, no email or status):
```json
{"message": null,
 "data": {"username": "alice_01", "displayName": "Alice", "bio": null, "avatarUrl": null,
          "createdAt": "2026-10-30T12:00:00Z", "updatedAt": "2026-10-30T12:00:00Z"}}
```

### 11.2 `PATCH /users/me` → `200`

**Input:** any subset of `displayName` (≤30), `bio` (≤200), `avatarUrl` (≤500).
camelCase or snake_case accepted. Sending `null` clears a field; omitting a field leaves it.
**Output:** `{"message": "Profile updated.", "data": <same shape as 11.1>}`

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | a field too long / wrong type |
| 400 | `EMPTY_UPDATE` | body has no fields (`{}`) |
| 404 | `USER_NOT_FOUND` | profile row missing |

## 12. Security notes

- Passwords: **argon2** via `pwdlib`, hashed in a thread pool so the event loop is not blocked.
- Secrets (`jwt_secret`, `secret_key_email`, `mail_token_salt`) come from `.env` as `SecretStr`.
- `hide_parameters=True` on the engine: emails and password hashes never appear in DB error logs.
- Error responses never contain SQL, table names or stack traces (`errors.md`).
- Login failure reasons are collapsed into one `INVALID_CREDENTIALS` (no account enumeration);
  `EmailNotVerified` exists but is intentionally not raised at login.
- The cookie-authenticated endpoints still need a CSRF review before the browser frontend ships.

## 13. Later (not v1)

- **Sender-constrained tokens (DPoP, RFC 9449).** The browser makes a key pair it cannot export
  (WebCrypto, non-extractable) and signs a small proof for each refresh; the server binds the
  refresh token to that public key, so a stolen refresh token alone is useless. Cost: proof checks
  on the server, key handling in the client. Revisit if theft becomes a real risk.
- **`appendfsync always`.** Redis writes every change to disk before replying, so a restart loses
  nothing and the lost rotation in §7 goes away for restarts (not for failover). Cost: every Redis
  write, rate-limiter counters included, waits for the disk. Measure with load tests first.

## 14. Today's code differs (part A not built)

| Where | Today | Target | Checked |
|---|---|---|---|
| `app/core/security.py:118-120` | every refresh makes a new `uuid7()` sid; exp slides | same `sid` for the whole login; `rti` claim | from the handoff, not re-read |
| `app/modules/auth/service.py:104-115` `refresh` | revokes the row, issues a new session | Lua script (§9) | from the handoff |
| `app/modules/auth/service.py:135-154` `get_current_user` | falls back to the DB on a cache miss | `cur == rti` in Redis only; 503 when down | from the handoff |
| `app/modules/auth/crud_cache.py:18-62` | hash {user_id, jti}; every call wrapped in the circuit breaker with a fallback | hash {user_id, cur, prev, rotated_at, abs_exp}; auth calls use the fail-closed mode and raise `CacheError` → 503 (§7) | read 2026-11-11 |
| `app/core/infra/circuit_breaker.py:69-83` | swallows every Redis error and returns the fallback | add a fail-closed mode that raises `CacheError` (§7) | read 2026-11-11 |
| `app/modules/auth/service.py:197-198` login | commits the row, then writes Redis | same order (§7.1) | read 2026-11-11 |
| logout | revokes the row, deletes the key, commit at the end of the request | `DEL` first, then revoke + commit, then `session.ended` (§7.1) | from the 2026-11-11 review |
| `app/core/errors/schemas.py` | no `REFRESH_TOKEN_REUSED` | new 401 code (§10.4) | not checked |
| `app/modules/auth/models.py:25` | `jti` PK, `sid` unique; class `UserRefreshToken` | `sid` PK, one row per login; class `UserSession` | from the handoff |
| `app/modules/auth/models.py:39-40` | comment: theft revokes all sessions | theft revokes that login only | from the handoff |
| refresh cookie | `HttpOnly`, `SameSite=strict`, path-scoped, no `Secure` (per the old doc); not cleared on logout | add `Secure` after HTTPS is set up; clear on logout, logout-all, theft (§5) | from the old doc, not re-read |

## 15. Known gaps (code)

- **Login timing leak:** an unknown identifier returns before any hashing, so it is faster than a
  wrong password. To fix before release (verify against a dummy hash).
- **Email sending disabled** (`bg_tasks.add_task(...)` commented out in `auth/router.py`); the
  template hard-codes "15 minutes" while the real lifetime is `mail_token_life_min`.
- Verification tokens are stateless: reusable until expiry (a second use returns 409).
- Logout does not clear the cookie (target: §5).
- `UserCreatedResponse` / `UserVerifiedResponse` inherit the username **input** pattern; an old
  username that breaks today's rule would make those responses fail with 500.
- Password reset, 2FA, email change, `phone` field.

## 16. Open questions

None. The five last questions (fail closed, write order, error codes, active-tab election +
`session.ended`, cookie) were answered on 2026-11-12; the decisions are in §5, §7, §8, §10, §11.
