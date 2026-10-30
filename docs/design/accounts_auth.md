# Design — Accounts & Authentication

- **Status:** Implemented — describes the code as it is
- **Last updated:** 2026-10-30
- **Code:** `app/modules/auth/`, `app/modules/users/`, `app/core/security.py`
- **Related:** `docs/prd.md` §5.1, `app_layout.md`, `errors.md`, ADR-009

---

## 1. Purpose

Registration, email verification, login, the token lifecycle, per-request session checks,
and the current user's own profile.

## 2. Requirements mapping

| PRD | Status |
|---|---|
| FR-1 register | ✅ |
| FR-2 email verification before first login | ⚠️ endpoint works; sending the email is disabled and `dev_mode` auto-activates (§11) |
| FR-3 login with username **or** email | ✅ |
| FR-4 refresh with rotation, logout | ✅ (+ logout from all devices) |
| FR-5 read/update own profile | ✅ profile fields only; email change deferred |
| C-1 personal data separate from credentials | ✅ with one deliberate exception: `email` is on the account (§3) |
| C-3 rate limiting | ❌ planned |

## 3. Data model

```
user_account   uuid PK (uuid7) · username CITEXT UNIQUE · email CITEXT UNIQUE
               password_hash · status (unverified | active | suspended)
               created_at · updated_at

user_profile   username PK → user_account.username (ON DELETE CASCADE)
               display_name ≤30 · bio ≤200 · avatar_url ≤500 · last_seen_at
               created_at · updated_at

user_session   jti PK · sid UNIQUE · user_id → user_account.uuid (ON DELETE CASCADE)
(UserRefreshToken)  expires_at · revoked_at (NULL = active)
```

- `username` and `email` are **case-insensitive** (`CITEXT`): `Alice_01` and `alice_01` collide.
- `email` lives on the **account** because it is a login identifier — a deliberate exception to C-1.
- Only token **metadata** is stored (`jti`, `sid`); the token itself is never persisted.
- Revoked rows are **kept**, as groundwork for stolen-token detection (§11).
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
| access (JWT, HS256) | JSON body → client sends `Authorization: Bearer …` | `jwt_access_token_life_min` | `sub` user id · `sid` session id · `jti` · `iat` · `exp` · `type="access"` |
| refresh (JWT) | `refreshToken` cookie only, never in JSON | `jwt_refresh_token_life_day` | same claims, `type="refresh"` |
| email verification | link `…/auth/verify-email?token=` | `mail_token_life_min` | the email address, signed with `itsdangerous` (salted); stateless |

Refresh cookie attributes: `HttpOnly`, `SameSite=strict`, `Path=/api/v1/auth`,
`Max-Age` = refresh lifetime. Because of the path, the browser sends it only to `/auth/*`.

## 6. Session check (every authenticated request) — ADR-009

```
Bearer token ──▶ verify signature, expiry, type == "access"     (else 401)
             ──▶ Redis  EXISTS auth:session:{sid}
                   hit  → session active
                   miss / Redis down / breaker open
                        → DB: user_session WHERE sid = ? AND revoked_at IS NULL
                              found → re-cache it          not found → 401 INVALID_TOKEN
             ──▶ load account (status must be active) + profile   (else 401 UNAUTHENTICATED)
```

- **Revocation is immediate:** logout/refresh delete the cache key and set `revoked_at`, so
  every access token of that session stops working on its next request.
- **Redis down never blocks login or requests:** cache calls are wrapped in the circuit
  breaker (3 failures → open for 15 s) and return `None`; the DB is the source of truth.
  `CACHE_UNAVAILABLE` therefore never reaches a client from these paths.
- **Limitation:** if the cache `DEL` fails while the DB revoke succeeds, the stale key can
  keep the session alive until its TTL (the refresh token's remaining lifetime). Fixing this
  needs an external reconciliation job (§11).

## 7. Auth endpoints (`/api/v1/auth`, tag `authentication`)

Common to all: `503 DATABASE_UNAVAILABLE` when Postgres is unreachable or busy (`errors.md` §5).
Every 401 carries `WWW-Authenticate: Bearer`.

### 7.1 `POST /auth/register` → `201`

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

### 7.2 `GET /auth/verify-email?token=<token>` → `200`

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

### 7.3 `POST /auth/login` → `200`

**Input** (`application/x-www-form-urlencoded`, OAuth2 password form):
`username=<username or email>&password=<password>`
**Output:**
```json
{"message": "Login successfully.", "data": {"accessToken": "<jwt>", "tokenType": "bearer"}}
```
plus `Set-Cookie: refreshToken=<jwt>; HttpOnly; Path=/api/v1/auth; SameSite=strict; Max-Age=<refresh lifetime>`.
**Effects:** new `user_session` row (committed **before** the Redis write) and cache key.

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `username` or `password` missing |
| 401 | `INVALID_CREDENTIALS` | unknown identifier, wrong password, **or** account not active — one code on purpose, so the response does not reveal which |

### 7.4 `POST /auth/refresh` → `200`

**Input:** `refreshToken` cookie. **Output:** same shape as login, with a new cookie.
**Effects:** rotation — the presented token's row gets `revoked_at`, its cache key is
deleted, and a new session (new `sid`) is issued.

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | cookie missing (`field: "cookie.refreshToken"`) |
| 401 | `TOKEN_EXPIRED` | refresh token expired |
| 401 | `INVALID_TOKEN` | bad signature, an access token sent instead, or token unknown / already revoked (reuse of a rotated token) |

### 7.5 `POST /auth/logout` → `200`

**Input:** `refreshToken` cookie. **Output:** `{"message": "Logged out.", "data": null}`
**Effects:** revokes this session (DB + cache). Errors: as §7.4.
Note: the server does not clear the cookie; the browser keeps a revoked token (§11).

### 7.6 `POST /auth/logout-all` → `200`

**Input:** `refreshToken` cookie. **Output:** `{"message": "Logged out from all devices.", "data": null}`
**Effects:** revokes **every** active session of the token's user.
Errors: 400 / 401 `TOKEN_EXPIRED` / 401 `INVALID_TOKEN` (signature or type). The token only
needs a valid signature — it may already be revoked, so a user can still cut off a thief.

## 8. Profile endpoints (`/api/v1/users`, tag `users`)

Both need `Authorization: Bearer <accessToken>`. Auth errors for every protected endpoint
(also used by `relations.md`):

| Status | `code` | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | header missing, or the account is no longer active |
| 401 | `TOKEN_EXPIRED` | access token expired → call `/auth/refresh` |
| 401 | `INVALID_TOKEN` | bad signature, a refresh token sent, or the session was revoked |

### 8.1 `GET /users/me` → `200`

**Output** (profile only — no email or status):
```json
{"message": null,
 "data": {"username": "alice_01", "displayName": "Alice", "bio": null, "avatarUrl": null,
          "createdAt": "2026-10-30T12:00:00Z", "updatedAt": "2026-10-30T12:00:00Z"}}
```

### 8.2 `PATCH /users/me` → `200`

**Input:** any subset of `displayName` (≤30), `bio` (≤200), `avatarUrl` (≤500).
camelCase or snake_case accepted. Sending `null` clears a field; omitting a field leaves it.
**Output:** `{"message": "Profile updated.", "data": <same shape as 8.1>}`

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | a field too long / wrong type |
| 400 | `EMPTY_UPDATE` | body has no fields (`{}`) |
| 404 | `USER_NOT_FOUND` | profile row missing |

## 9. Security notes

- Passwords: **argon2** via `pwdlib`, hashed in a thread pool so the event loop is not blocked.
- Secrets (`jwt_secret`, `secret_key_email`, `mail_token_salt`) come from `.env` as `SecretStr`.
- `hide_parameters=True` on the engine: emails and password hashes never appear in DB error logs.
- Error responses never contain SQL, table names or stack traces (`errors.md`).
- The refresh cookie is `SameSite=strict` and path-scoped; the cookie-authenticated
  endpoints still need a CSRF review before a browser frontend exists.

## 10. Decisions

- Metadata-only session storage (no token hash) — revisit if theft detection is added.
- Login failure reasons are collapsed into one `INVALID_CREDENTIALS` (no account enumeration
  through the message); `EmailNotVerified` exists but is intentionally not raised at login.
- Cache TTL = remaining refresh lifetime (shorter TTL would self-heal stale revocations faster).

## 11. Known gaps / deferred

- **Login timing leak:** an unknown identifier returns before any hashing, so it is faster
  than a wrong password. To fix before release (verify against a dummy hash).
- **Email sending disabled** (`bg_tasks.add_task(...)` commented out in `auth/router.py`);
  the template hard-codes "15 minutes" while the real lifetime is `mail_token_life_min`.
- Verification tokens are stateless: reusable until expiry (a second use returns 409).
- Logout does not clear the cookie.
- Stolen-token detection (reuse of a revoked refresh token → revoke all) — groundwork only.
- Session-cache reconciliation job (external).
- `UserCreatedResponse` / `UserVerifiedResponse` inherit the username **input** pattern; an
  old username that breaks today's rule would make those responses fail with 500.
- Password reset, 2FA, email change, `phone` field, rate limiting.
