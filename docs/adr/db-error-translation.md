# ADR-010: Translate Database Errors by SQLSTATE

- **Status:** Accepted
- **Date:** 2026-10-30
- **Owner:** [you]

## Context

Raw SQLAlchemy errors reaching the handlers became 500s and could leak SQL. Mapping by
SQLAlchemy exception class alone proved unreliable when tested against Postgres:

- a statement timeout (`57014`) arrives as a plain `DBAPIError`, not `OperationalError`;
- an unreachable server arrives as Python's own `TimeoutError` / `OSError`, not a SQLAlchemy error;
- a deferred constraint fails at `COMMIT`, outside any crud function.

## Decision

- `@translate_db_errors` on every crud function catches `SQLAlchemyError` **and** `OSError`.
- `translate_db_error` decides by the Postgres **sqlstate** (`e.orig.sqlstate`) and the
  constraint name (`e.orig.__cause__.constraint_name`): known constraints → precise errors
  (`USER_EXISTS`); `23505`/`23503` → 409; `23514` → 400; transient states (serialization,
  deadlock, timeouts, shutdown, too many connections, class `08`) → 503, with `Retry-After: 1`
  for the retryable ones; anything else → 500 (a bug in our code).
- `get_db` translates errors from the **commit only**, and commits before the response is
  sent (`Depends(..., scope="function")`), so a client never receives 2xx for unsaved data.
- The engine uses `hide_parameters=True` so error text never contains user data.

## Alternatives considered

- **Map by exception class only** — misses the cases above (verified by tests).
- **Let everything become 500** — no difference between "you sent a duplicate" and "we are down".

## Consequences

- **Positive:** correct 4xx/503 split; no SQL or user data in responses or logs.
- **Negative:** constraint names in `_CONSTRAINT_ERRORS` must be kept in sync with migrations.

## References

- `docs/design/errors.md` §5, `app/core/errors/translators.py`, `app/api/deps.py`
