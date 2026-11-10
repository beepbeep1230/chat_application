# Handoff — prompt for the next session

## Current work (updated 2026-11-11): realtime rewrite design review

**Main file:** `docs/design/realtime_rewrite.md`. It is the only source of truth for the review.
Read it in this order: section 0 (resume prompt), 0.2 (scope map), 0.1 (next steps), then 2, 3,
5.6 and 9.

**State of the repo**

- Branch `docs/realtime-rewrite-review`. The rounds from 2026-11-09 to 2026-11-11 are **not
  committed** (`docs/design/realtime_rewrite.md` and this file). Commit only when the owner asks.
- Design review only: **no app code has been changed**. The mentor rules below still apply. The
  owner writes all code.

**How the review works**

- One topic per round, one recommended answer per question, and a quick search for common
  practice (Okta, Auth0, Redis docs, RFCs). Cite what you find.
- After every round the owner answers, update the plan: the row in section 2 (decided) or 3
  (proposed), the line in the 0.2 scope map, the step in 0.1, and any text the decision makes
  stale (strike it through and give the date, don't delete it).
- The owner likes diagrams for hard choices: ASCII in chat, or an Artifact page with mermaid
  flowcharts. Earlier diagrams for refresh-reuse options A/B/C:
  https://claude.ai/artifact/HoP334nWFQqEhJTt2VMJnJ
- Use a timeline trace ("t0 user sends A → server sets cur=B …") to show any race or failure.
  The owner understands traces best.
- Owner preferences (also in auto-memory): just fix typos, don't explain them; design docs and
  ADRs can change; the small scale (100 / 500 / 30 days) is on purpose, and the owner will write
  load-test clients to find the real limits.

**Decided in the last rounds (details in the plan)**

| Date | Decision | Where |
|---|---|---|
| 2026-11-09 | Fan-out: one Redis channel per user (`user:{id}`), "option U". The owner wants a deeper U vs C explanation from an agent later. | 2, 0.2 E |
| 2026-11-10 | One active tab per browser ("Use here"), client-side only | 2 |
| 2026-11-10 | Refresh reuse: grace window (option C), 30 s setting; theft revokes that login only | 2 |
| 2026-11-10/11 | **Login session model** (three layers): login row in Postgres (30 days absolute, `sid` PK); refresh token in a Redis hash only (7 days = idle timeout); access token JWT 15 min, child of one refresh token (M2: `cur == rti` on every request). The client sends only the refresh token. | 5.6 |
| 2026-11-11 | Redis is required for auth. Redis down → 503 (fail closed). ADR-009 is replaced. | 5.6, 8 |
| 2026-11-11 | False theft after a Redis crash (lost rotation) accepted; `appendfsync always` kept as the fallback | 5.6 |
| 2026-11-11 | After a theft, the login page says "session ended for security reasons"; DPoP (RFC 9449) recorded for later | 5.6 |
| 2026-11-11 | Rename `UserRefreshToken` → `UserSession`, `UserAccount.refresh_tokens` → `sessions` (owner approved) | 5.6 |

**Waiting on the owner (ask these first)**

1. Confirm the refresh **Lua script** (5.6, proposed). If the token is `cur`, rotate. If it is
   `prev` and less than 30 s have passed since the rotation, grace: issue a new token and leave
   `prev` unchanged. Anything else is theft: DEL the key, revoke the login row, publish
   `session.ended`.
2. **ADR-009** still has its old status. Ask whether the owner edits it or allows the agent to
   add one status line ("Superseded by realtime_rewrite.md 5.6").
3. Small doc fixes from the first round. The owner never answered whether to apply them:
   section 5.5 unread COUNT filter text; move the accepted section 3 rows (blocking mechanics,
   `upTo`) to section 2; the "stale text" list at the end of section 9.

**Next topics, in order (section 0.1)**

| Step | Topic |
|---|---|
| 3 | 9.9 `Origin` check rule for the v2 mobile app (no `Origin` header) |
| 4 | 9.11 File uploads: size and type limits with a MinIO signed URL; orphan uploads |
| 5 | Unconfirmed section 3 rows: skip the backup round when Redis is unreachable; unread on demand (99+); the backup check itself (owner unsure) |
| 6 | `lock_timeout` value for the `seq` counter lock |
| 7 | Laptop sizing: workers, pools; `uvicorn --workers` shares one port |
| 8 | Remaining 🟡 rows in 0.2: Lua script, `session.ended` on logout, ticket flow, close codes, heartbeat, mark-as-read, push payload (full message vs IDs + preview), ... |
| 9 | F. Membership: which events create system messages; group read receipts; what a kicked member sees |
| 10 | C. Who deletes change-log rows older than 30 days |
| 11 | E. Redis down: what else breaks beyond auth, the ticket and the backup check |
| 12 | G. Laptop infrastructure: firewall, nginx, TLS, internet exposure, process manager, backups |
| 13 | H. Monitoring: logs, metrics, alerts |
| 14 | Doc cleanup (stale-text list at the end of section 9; section numbers 5.1–5.4 appear twice, and 5.6 sits before 5.5) |

**Code facts the login model will touch (read only, not verified beyond reading)**

- `app/modules/auth/models.py`: `UserRefreshToken`, table `user_session`. `sid` is
  `unique=True` (line 25). The comment at lines 39-40 says "revoke all sessions" on theft, which
  no longer matches.
- `app/core/security.py`: `create_jwt_token` makes a new `uuid7()` sid on every refresh, with exp
  = now + `jwt_refresh_token_life_day` (sliding). `JWTPayload` has no `rti` claim yet.
- `app/modules/auth/service.py`: `refresh` (104-115) revokes, then calls `_issue_session` (new
  sid). `get_current_user` (135-154) falls back to the DB when the cache misses; this fallback
  goes away under 5.6.
- `app/modules/auth/crud_cache.py`: `auth:session:{sid}` hash today holds {user_id, jti}. Under
  5.6 it becomes {user_id, cur, prev, rotated_at, abs_exp}.

**Paste into the next session**

```
Read docs/HANDOFF.md ("Current work") and docs/design/realtime_rewrite.md (section 0.2 first,
then 0.1, 2, 3, 5.6 and 9). We are reviewing the realtime rewrite plan in rounds: one topic at
a time, one recommended answer per question, search online for common practice, and update the
plan after every round I answer. Load the skills listed in CLAUDE.md for each topic. Follow the
mentor rules in CLAUDE.md (no app code changes). Start with the "Waiting on the owner" questions
in HANDOFF.md, then step 3 in section 0.1.
```

---

## Older session plan (design quiz, rate limiter, logging), kept for reference

> The mentor rules in "Who I am and how to work with me" still apply to all work.

---

Load these skills at the start: `fastapi-expert`, `api-designer`, `python-pro`,
`architecture-designer`.

## Who I am and how to work with me

I'm learning backend development by building this chat app myself. Act as a **mentor**:

- Use **simple English**. Explain *why*, not only *what*.
- **Do not write or change code unless I give permission** for that specific change. Give
  hints, point to file:line, and let me write the logic.
- Report findings in **tables** (file / function / problem / fix), ordered
  **crashes → logic bugs → cleanup**.
- **Keep my names.** Ask before renaming anything.
- **Trace real scenarios through the actual code**, run checks when possible, and never
  invent facts — say "I haven't verified this" when that's true.
- When something is my decision, ask me; don't decide for me.

## Project in one paragraph

FastAPI + SQLAlchemy 2.0 async (asyncpg) + PostgreSQL + Redis + Pydantic v2 + Alembic, on
Python 3.14. Feature modules under `app/modules/` (`auth`, `users`, `friends`; `invites`,
`messages`, `notifications` are stubs), each with router → service class → crud /
crud_cache. Errors are RFC 9457 problem+json with a stable `code`. Read these first:
`docs/design/app_layout.md` (map of everything), `accounts_auth.md`, `relations.md`,
`errors.md`, and `docs/adr/` (ADR-007 … ADR-011 are the recent decisions).

## Environment facts

- Run Python as `.venv/bin/python -I` (`python` is not on PATH).
- PostgreSQL on `127.0.0.1:5555`, Redis on `127.0.0.1:6379` (Redis was often down; the app
  still works without it — ADR-009).
- Checks: `ruff` (0.17) and `pyright` (1.1.414) are installed in `~/.local/bin`.
  `pyright --pythonpath .venv/bin/python app` must stay at 0 errors. `uvx`/`npx` downloads
  are blocked by the permission system.
- `alembic check` must say "No new upgrade operations detected."
- `.env.example` is missing `request_cool_down` (required by `Settings`).

## Plan for this session

### Part 1 — Presenting the design (main focus)

I want to be able to explain my own design. Quiz me, one topic at a time:

1. Ask me an open question (e.g. "Walk me through what happens when a request hits
   `GET /friends` with an expired access token").
2. Let me answer **in my own words** before you say anything.
3. Tell me what was right, what was missing or wrong, and point to the doc/code that shows it.
4. Ask a follow-up "why" or "what if" question. Move on only when I can explain it clearly.
5. Keep a short score table of topics: ✅ solid / ⚠️ shaky / ❌ revisit.

Topics to cover:

| Topic | Things I should be able to explain |
|---|---|
| Layout | why router → service → crud; what goes in `core/`; why `app/models.py` exists |
| Request lifecycle | middleware order; dependencies; `scope="function"`; when the commit happens and why it matters |
| Auth | register → verify → login → refresh → logout; access vs refresh token; cookie attributes; why one `INVALID_CREDENTIALS` |
| Session cache | Redis + DB fallback; circuit breaker states; commit-before-Redis; the stale-key limitation |
| Friends | the state machine; auto-accept; one-request-per-pair index; cooldown; what a block does |
| Pagination | keyset vs offset; what is inside a cursor; why `limit + 1` |
| Errors | problem+json members; `type` vs `code`; the 4 handlers; headers; sqlstate translation order |
| Trade-offs | each ADR's alternatives and why they were rejected |

### Part 2 — Rate limiter (I write it)

Facts about the current code (not instructions):

- `ErrorCode.RATE_LIMITED` (429) already exists in `app/core/errors/schemas.py`.
- `AppError` accepts `retry_after`, and `app_error_handler` turns it into a `Retry-After` header.
- So a limiter only needs to raise an `AppError` subclass with status 429, that code, and `retry_after`.
- Redis is available through `RedisClient`; all Redis calls in this project go through the
  circuit breaker and fail **open** — decide whether the limiter should too.
- PRD C-3 asks for limits on message send and social-request endpoints; login/register also matter.

Review my design before I code, then review my code.

### Part 3 — Replace loguru with the standard `logging` module

Verified facts:

- 13 files import loguru (`grep -rln "loguru\|app.core.logging import logger" app`).
- ~32 log calls, ~27 of them use loguru's `logger.info("event", key=value)` style. The
  stdlib raises `TypeError` on unknown keyword arguments, so each becomes
  `logger.info("event", extra={...})` (or a structured-logging helper).
- The current format string ends in `{{extra}}`, which prints a literal `{extra}` — every
  structured field is being **dropped today**.
- loguru-only features to replace: `@logger.catch` (`auth/service.py`, `auth/email.py`),
  `logger.opt(exception=...)` (`core/errors/handlers.py`), `logger.contextualize`
  (`middlewares/request_id.py`, not mounted).
- `core/logging.py` has an `InterceptHandler` that sends stdlib logs **into** loguru — this
  direction goes away.
- `diagnose=True` prints local variables (passwords, tokens) in tracebacks — must not survive.
- Goal: one `logging.getLogger(__name__)` per module, one config (`dictConfig`), request-id
  correlation (fills `traceId` in problem+json), no secrets in logs.

## Open items (not urgent, know they exist)

- Login timing leak (unknown user answers faster) — I will fix before finishing.
- Response models inherit the username **input** pattern.
- `select_user_by_email` docstring is stale; `security.py` raises `AppError` where
  `ValueError` fits.
- 18 files have ruff `I001` import-order warnings.
- 500 responses have no CORS headers; `/docs` shows 422 instead of 400.
- Verification email sending disabled; `dev_mode` auto-activates accounts; the template
  hard-codes "15 minutes".
- Logout does not clear the refresh cookie.
- Replace the placeholder `https://api.chat-app.example` problem-type domain before release.
