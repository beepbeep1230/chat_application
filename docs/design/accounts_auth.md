# Design — Accounts & Authentication

- **Status:** Draft
- **Last updated:** 2026-09-21
- **Related:** `docs/prd.md` §5.1, `docs/design/app_layout.md` §3

---

## 1. Purpose

Handle registration, email verification, login, token lifecycle, and the current user's own account/profile management.

## 2. Requirements mapping

FR-1 (register), FR-2 (email verify), FR-3 (login), FR-4 (refresh/logout), FR-5 (me), C-1 (personal data separated from credentials).

## 3. Core idea: two entities, not one

Credentials and personal data are stored separately (1-to-1):

```
accounts      username (unique), password_hash, status (active|suspended), created_at
user_profiles phone, email (unique), display_name, avatar_url, bio, last_seen_at
              └ tied to exactly one account
```

- Use the **account** for login and security.
- Use the **profile** for anything a human sees or is contacted by.
- Login is by **username or email** → so email needs a unique index even though it lives on the profile.
- Protect the profile from leaking into chat endpoints: message payloads carry `user_id`, `username`, `display_name`, `avatar_url` — never phone or email (see §7).

Deliberately **not** in the prototype: 2FA, password reset flows (deferred).

## 4. Registration flow

```
1. POST /auth/register {username, email, password}
   → validate, hash password (argon2), create account (status=unverified)
   → create profile row
2. Server generates a short-lived verification token → email it.
3. POST /auth/verify-email {token}
   → token valid → account status = active → done.
4. Login is rejected until the account is verified.
```

Notes:

- One outstanding verification token per account; regenerate on re-request.
- Verification token is single-use and expires (e.g. 24h).
- Prototype sends email via SMTP; in dev you can log the token to console instead (`.env` switch).

## 5. Login & token lifecycle

```
POST /auth/login {login: "username or email", password}
  → verify password
  → issue {access_token, refresh_token}

access_token    short-lived (15 min), stateless JWT, identifies user_id
refresh_token   long-lived (e.g. 30 days), stored server-side (hashed)
                so logout/revocation actually works

POST /auth/refresh  → rotate: old refresh invalidated, new pair returned
POST /auth/logout   → revoke the presented refresh token
```

- The `current_user` dependency validates the access token and loads the account.
- Refresh-token **rotation** (one-time use) is cheap and prevents replay if a token leaks.

## 6. Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | — | create account + profile, email verification |
| POST | `/auth/verify-email` | — | activate account |
| POST | `/auth/login` | — | tokens |
| POST | `/auth/refresh` | refresh token | rotate tokens |
| POST | `/auth/logout` | refresh token | revoke |
| GET | `/auth/me` | access | own account + profile |
| PATCH | `/auth/me` | access | update display_name/avatar/bio/phone (email change deferred) |

## 7. Security notes

- Passwords hashed with **argon2** (via `pwdlib`); never store or log plaintext.
- Profile fields (`phone`, `email`, `bio`) never appear in chat, user-search, or notification payloads — the API defines explicit public profile schema.
- Username and email have unique constraints; reject duplicates with a clear error.
- Rate-limit register/login to slow credential stuffing.
- JWT secret comes from `.env`, never hardcoded.

## 8. Open questions / decisions

- **D-1 (from PRD):** email-change flow — deferred until after the prototype.
- Verification token delivery in dev: SMTP vs console logging — decide at implementation time.