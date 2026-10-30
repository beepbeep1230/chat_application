# ADR-008: Feature Modules with Router → Service → CRUD Layers

- **Status:** Accepted
- **Date:** 2026-10-30 (recorded; decided during the October refactor)
- **Owner:** [you]

## Context

In the first commit, all account code lived in `modules/users/`, routers called crud
functions directly, and some auth logic sat in `api/deps.py`. Business rules, SQL and HTTP
concerns were mixed, and splitting models across modules broke SQLAlchemy relationship
lookups ("failed to locate a name") when a module was imported alone.

## Decision

- One folder per feature under `app/modules/` (`auth`, `users`, `friends`, …), each with
  `router.py`, `deps.py`, `service.py`, `crud.py`, optional `crud_cache.py`, `schemas.py`, `models.py`.
- **Router:** HTTP only. **Service class** (`AuthService`, `UserService`, `FriendService`):
  business rules, raises domain errors, injected via `Annotated[..., Depends(...)]` aliases
  (`*ServiceHandler`). **CRUD:** one database (or Redis) operation per function, returns
  values/`None`/`bool` instead of raising business errors.
- Cross-cutting code lives in `app/core/` (`errors/`, `infra/`, `middlewares/`, security, pagination).
- `app/models.py` imports every module's models; Alembic and scripts import it so relationships
  across modules always resolve.

## Alternatives considered

- **Layer-first folders** (`routers/`, `crud/`, `schemas/` at top level) — the original plan;
  a feature change touches many folders.
- **No service layer** (router → crud) — fewer files, but rules end up in routers and are not
  reusable or testable without HTTP.

## Consequences

- **Positive:** each feature is self-contained; services are testable with fake crud/Redis;
  routers stay thin; errors are raised in one place.
- **Negative:** more files per feature; the model registry must be kept up to date when a
  module adds models.

## References

- `docs/design/app_layout.md` §2–§3
