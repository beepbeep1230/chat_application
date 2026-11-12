# Handoff — prompt for the next session

## Current work (updated 2026-11-12): realtime rewrite design review

**Index:** `docs/design/realtime_rewrite.md`: work order (§1), scope map (§2), round history (§4).
Since 2026-11-11 every scope has its own design doc, and each doc is the source of truth for its
scope:

| Scope | Doc |
|---|---|
| 0 Product | `docs/prd.md` |
| A Auth and sessions | `docs/design/accounts_auth.md` |
| B Socket connection | `docs/design/realtime.md` |
| C Change log, catch-up | `docs/design/change_log.md` |
| D Messages and files | `docs/design/messages.md` |
| E Fan-out (Redis) | `docs/design/fanout.md` |
| F Membership, read state, notifications | `docs/design/conversations.md`, `docs/design/notifications.md` |
| Blocking | `docs/design/relations.md` §5.1 |
| G Laptop infrastructure | `docs/design/infrastructure.md` |
| H Monitoring | `docs/design/monitoring.md` |

**State of the repo**

- Branch `docs/realtime-rewrite-review`. Rounds up to the login session model are committed
  (`eadc4f6`). Rounds 12-15 (Lua script, single-flight refresh, review findings, message model,
  `lock_timeout`, the split into scope docs, ADR status lines, PRD sync) are **not committed**.
  Commit only when the owner asks.
- Design review only: **no app code has been changed**. The owner writes all code.

**How the review works (owner's rules)**

- **One scope at a time**, in the order of the index §1. Stay on a scope until nothing in it is
  open; do not jump between scopes. Something found in another scope is written down as ❓ in that
  scope's doc and asked when that scope comes up.
- One recommended answer per question, plus a quick search for common practice; cite it.
- After each answer: update the scope doc (decision + reason; delete replaced text, git keeps the
  history), the scope's line in index §2, and a row in index §4 at the end of the round.
- Design docs describe the **target design**; a "Today's code differs" section lists what is not
  built yet, with `file:line` and whether it was checked. ADRs are history: only their status line
  changes.
- Labels: scope areas own 0 and A–H. Name review tables "Table 1/2/3" and options "option 1/2/3".
- The owner likes timeline traces ("t0 ... t1 ...") for races and failures, and diagrams (ASCII,
  or an Artifact page with mermaid) for hard choices.
- Other owner preferences (also in auto-memory): just fix typos; the small scale (100 / 500 /
  30 days) is on purpose; load-test clients will find the real limits.

**Scope page for the owner's phone:** https://claude.ai/artifact/Bt6Xds3EroVcEe6umncSaR (rebuild
from index §2 and republish after each round).

**Scope A is done** (2026-11-12, round 15): fail-closed breaker mode, write order (§7.1, the
owner may revisit when building), `REFRESH_TOKEN_REUSED`, active-tab election + `session.ended`
reasons, cookie clearing + `Secure` after HTTPS. Next: ask whether the owner is ready to resume
scope C; if not, ask whether to start scope D instead.

**Scope C is paused** (2026-11-11). Decided: timeouts set once on the engine; nightly cron
cleanup. The owner is studying event logs and catch-up with a self-contained study prompt (given
in chat, made for the mobile Claude app) before answering `change_log.md` §9 (paging + 410 rule,
event catalogue, history by `seq`). Resume C when the owner says they are ready.

**Paste into the next session**

```
Read docs/HANDOFF.md ("Current work") and docs/design/realtime_rewrite.md (§1 and §2). We review
the design one scope at a time, in the order of §1, and stay on a scope until nothing in it is
open. One recommended answer per question; search online for common practice. After each answer,
update the scope's design doc and its line in §2. Load the skills listed in CLAUDE.md. Follow the
mentor rules in CLAUDE.md (no app code changes). Continue with the scope marked "now".
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
- PostgreSQL on `127.0.0.1:5555`, Redis on `127.0.0.1:6379`. Today's code still works without
  Redis (old ADR-009); the target design makes Redis required for auth (`accounts_auth.md` §7).
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
