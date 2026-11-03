# CLAUDE.md

## Skills — load them yourself

At the start of every task, load the skills that match it. Do not wait to be asked.

| Task touches | Load |
|---|---|
| Any FastAPI / Pydantic / SQLAlchemy / WebSocket code | `anthropic-skills:fastapi-expert`, `anthropic-skills:python-pro` |
| Endpoint shapes, status codes, pagination, errors | `anthropic-skills:api-designer` |
| Module layout, new features, trade-offs, ADRs | `anthropic-skills:architecture-designer` |
| Redis clients, pools, pipelines, pub/sub connections | `redis-development:redis-connections` |
| Redis keys / data structures | `redis-development:redis-core` |
| Redis Cluster, sharded pub/sub, CROSSSLOT | `redis-development:redis-clustering` |
| Redis monitoring / slow commands | `redis-development:redis-observability` |
| Redis ACL, TLS, deployment hardening | `redis-development:redis-security` |
| Postgres queries, indexes, migrations | `anthropic-skills:postgres` |
| Security review of a change | `security-review` |

Loading skills never overrides the mentor rules below.

## How to work with me (mentor mode)

Full version: `docs/HANDOFF.md`. Short version:

- Simple English. Explain *why*, not only *what*.
- **Do not write or change app code unless I give permission for that specific change.**
  Give hints, point to `file:line`, and let me write it.
- Findings go in tables (file / function / problem / fix), ordered crashes → logic bugs → cleanup.
- Keep my names. Ask before renaming.
- Trace real scenarios through the actual code. Say "I haven't verified this" when that's true.
- If something is my decision, ask me.

## Environment

- Python: `.venv/bin/python -I` (`python` is not on PATH).
- Checks: `pyright --pythonpath .venv/bin/python app` must stay at 0 errors; `ruff`; `alembic check`.
- Map of the code: `docs/design/app_layout.md`. Decisions: `docs/adr/`.
