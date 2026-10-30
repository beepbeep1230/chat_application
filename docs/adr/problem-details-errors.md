# ADR-007: RFC 9457 Problem Details for All Errors

- **Status:** Accepted
- **Date:** 2026-10-30 (recorded; decided during the October refactor)
- **Owner:** [you]

## Context

The first version answered our errors with `{"message": "..."}` (6 handler functions,
registered one by one for 10 exception classes), while FastAPI's own errors used
`{"detail": "..."}` and validation errors `{"detail": [...]}`. Clients had no stable value to
branch on, and every new exception needed its own `add_exception_handler` line.

## Decision

- Every error response is RFC 9457 Problem Details (`application/problem+json`).
- Each problem kind has a stable `type` URI: `https://<domain>/problems/<slug>`, where the
  slug is derived from the `code`.
- An extension member `code` (the `ErrorCode` enum) is the stable machine-readable value.
- Validation errors add `violations: [{field, message}]` and use **400**.
- Each exception class owns its `code`, `status`, `type` and `detail`; four handlers cover
  everything (`AppError`, validation, Starlette HTTP errors, catch-all).
- Status-based header rules live in the handler (`401` → `WWW-Authenticate`); per-error data
  lives on the exception (`retry_after` → `Retry-After`).

## Alternatives considered

- **Custom `{error: {code, message}}` envelope** — simple, but not a standard; no tooling support.
- **Keep FastAPI defaults** — three different shapes, no stable codes.
- **422 for validation** — FastAPI's default; 400 was chosen as the more widely understood
  "your input is wrong" status. Cost: the generated `/docs` still advertises 422.

## Consequences

- **Positive:** one shape for every error; clients switch on `code`; adding an error = one class.
- **Negative:** the `type` URIs must never change once published (the placeholder domain must
  be replaced before release); `/docs` needs `responses=` declarations to stop showing 422.

## References

- `docs/design/errors.md`; RFC 9457; RFC 9110 §11.6.1 (`WWW-Authenticate` on 401)
