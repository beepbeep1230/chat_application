# Design — Accounts & Authentication

- **Status:** Draft
- **Last updated:** 2026-10-17
- **Related:** `docs/prd.md` §5.1, `docs/design/app_layout.md` §3

---

## 1. Purpose

Handle registration, email verification, login, token lifecycle, per-request session
validation, and the current user's own account/profile management.

## 2. Requirements mapping

FR-1 (register), FR-2 (email verify), FR-3 (login), FR-4 (refresh/logout), FR-5 (me),
C-1 (personal data separated from credentials).

> Email delivery/enforcement and stolen-token detection are **deferred for v1** — see §10.

## 3. Core idea: two entities, not one

Credentials and personal data are stored separately (1-to-1):

```
user_account    uuid (PK, uuid7), username (unique, CITEXT), email (unique, CITEXT),
                password_hash, status (unverified|active|suspended),
                created_at, updated_at

user_profile    username (PK, FK -> user_account.username, ON DELETE CASCADE),
                display_name, bio, avatar_url, last_seen_at,
                created_at, updated_at
```

- Login is by **username or email** → `email` carries a unique index.
- `email` lives on the **account**, not the profile, because it is a login identifier
  (a deliberate deviation from the PRD's "personal data lives on the profile" — see §9).
  `phone` is **not** implemented in v1 (see §10).
- The profile is keyed by `username` (FK to the account) with `ON DELETE CASCADE`.
- Use the **account** for login and security; use the **profile** for anything a human sees.
- Protect the profile from leaking into chat endpoints: message payloads carry `user_id`,
  `username`, `display_name`, `avatar_url` — never phone or email.

Deliberately **not** in the prototype: 2FA, password reset, email change, phone (§10).

## 4. Registration flow

```
1. POST /auth/register {username, email, password, passwordRepeated}
   → validate (password policy, passwords match), hash (argon2),
     create account (status=unverified), create profile row.
2. Server mints a signed, time-limited verification token.
3. POST /auth/verify-email "<token>"   (token sent as a raw string body; field `url_token`)
   → token valid → account status = active.
4. Login is rejected until the account is active.
```

Notes:

- Password policy: 8–30 chars, must contain an uppercase letter, a digit, and punctuation.
- The verification token is an `itsdangerous` `URLSafeTimedSerializer` value (signed,
  expires after `mail_token_life_min`). It is **stateless** — not stored or tracked, so it
  is not single-use.
- `dev_mode` auto-activates new accounts (skips verification). Email sending is currently
  disabled — see §10.

## 5. Login & token lifecycle

```
POST /auth/login  (OAuth2 form: `username`, `password` — `username` = identifier)
  → verify password
  → issue access_token (JSON) + refresh_token (httpOnly cookie)

access_token   short-lived JWT (`jwt_access_token_life_min`); claims: sub (user_id),
               sid (session id), jti, iat, exp, type="access"

refresh_token  long-lived JWT (`jwt_refresh_token_life_day`); claims include sid, jti,
               type="refresh"; delivered as a cookie (see below)

POST /auth/refresh    → rotate: revoke the old session (DB + cache), issue a new pair
POST /auth/logout     → revoke the presented refresh token
POST /auth/logout-all → revoke every active session for the user
```

- **Refresh-token transport:** `httpOnly`, `samesite=strict`, `path=/api/v1/auth`,
  `max_age` = refresh lifetime. It is never returned in the JSON body.
- **Server-side session record** (`user_session`): `jti` (PK), `sid` (unique), `user_id`,
  `expires_at`, `revoked_at`. Only this **metadata** is stored — the token itself is *not*
  persisted (no `token_hash`). Rotation = set `revoked_at` on the old row and issue a new one.
- Revoked rows are **kept**, not deleted (groundwork for future theft detection — §10).
- The `current_user` dependency validates the access token, checks the session cache (§6),
  and loads the account.

## 6. Session cache & resilience

Access-token validation is backed by a Redis session cache to avoid a DB hit per request:

```
key:    auth:session:{sid}      (hash: user_id, jti; TTL = refresh-token lifetime)
write:  on login / refresh                       (set_session)
check:  on every authenticated request           (check_session_is_active -> EXISTS)
delete: on logout / refresh / logout-all         (revoke_*)
```

**Authority / fallback.** The DB is the source of truth. On a cache miss — key absent,
Redis down, or breaker open — the dependency falls back to the DB (`get_refresh_token`,
filtering `revoked_at IS NULL`) and repopulates the cache. A down or stale cache therefore
can never *grant* access the DB denies; it fails **closed** to the authoritative check.

**Circuit breaker** (`app/core/circuit_breaker.py`, shared `redis_circuit_breaker`):

- Counts `CacheConnectionError` (connection/timeout) only. Server/command errors
  (`CacheServerError`) propagate and do **not** trip it.
- `threshold = 3` consecutive failures; `reset_timeout = 15s` before a half-open probe.
- When **open**, cache calls fail fast and return their `fallback` (currently `None`):
  reads → falsy → DB fallback; writes/deletes → silently skipped.
- Limitation: a failed `DEL` is silent, so a revoked session can linger in Redis until its
  key TTL expires. Reconciling this is **external to the app** (not Python) — see §9/§10.

## 7. Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | — | create account + profile |
| POST | `/auth/verify-email` | — | activate account (raw token body) |
| POST | `/auth/login` | — | issue tokens (access JSON + refresh cookie) |
| POST | `/auth/refresh` | refresh cookie | rotate tokens |
| POST | `/auth/logout` | refresh cookie | revoke current session |
| POST | `/auth/logout-all` | refresh cookie | revoke all sessions |
| GET | `/auth/me` | access | own **profile** |
| PATCH | `/auth/me` | access | update profile (display_name / bio / avatar_url) |

Note: `/auth/me` currently returns profile fields only (no email/status); email change is
deferred.

## 8. Security notes

- Passwords hashed with **argon2** (via `pwdlib`); never store or log plaintext.
- Password policy enforced at registration (8–30, uppercase + digit + punctuation).
- `username` and `email` are **case-insensitive** (`CITEXT`) with unique constraints;
  duplicates return a conflict error.
- Profile fields never appear in chat / search / notification payloads.
- The refresh token is a `httpOnly`, `samesite=strict` cookie → `/auth/refresh`,
  `/auth/logout`, and `/auth/logout-all` are cookie-authenticated and need a CSRF story.
- JWT secrets come from `.env`, never hardcoded; access tokens are short-lived.
- Suspended accounts are rejected at login (same generic `InvalidCredentials` as a wrong
  password).
- **Not implemented in v1:** rate limiting (C-3), email verification enforcement,
  stolen-token detection.

## 9. Open questions / decisions

- **D-1 (from PRD):** email-change flow — deferred until after the prototype.
- Verification token delivery in dev: SMTP vs console logging — decide at implementation time.
- **Refresh-token storage:** this doc previously said "hashed"; the implementation stores
  metadata only. Confirm we keep metadata-only (and hash later only if theft detection is added).
- **Cache TTL policy:** session key TTL currently equals the refresh-token lifetime. Decide
  whether to shorten it (e.g. to the access-token lifetime) so stale revocations self-heal faster.
- **Reconciliation:** confirm the external mechanism (job / SQL cron), its scan window, and its
  overlap with the TTL above.
- **`phone`:** implement later, or drop from the PRD/design.
- **C-1 tension:** `email` is PII but lives on the account (it is the login identifier). Record
  this as a deliberate deviation from "personal data separate from credentials."

## 10. Deferred / out of scope for v1

- **Email delivery & verification enforcement** — `send_verification_mail` is wired but the task
  is disabled, and `dev_mode` auto-activates accounts. Also note the emailed link uses `?token=`
  while the endpoint reads the token as a **body** — reconcile with the email work.
- **Verification token single-use / one-outstanding-per-account** — not tracked (tokens are
  stateless).
- **Stolen-token detection** — presenting a revoked token later should be treated as a theft
  signal and revoke all sessions. The revoked-row retention groundwork exists; the detection
  does not.
- **Password reset**, **2FA**, **email change**.
- **Rate limiting** on register/login (C-3).
- **`phone`** field.
- **Session-cache reconciliation** (external, not Python — see §6/§9).
