# Handoff — prompt for the next session

> Paste everything below the line into a new Claude Code session opened in this repo.
> **Before that, commit the working tree** — nothing after `1a77720` is committed yet, and
> the refactor, friends module, error handling and these docs only exist on disk.

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
