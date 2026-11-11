# Error-handling rules

## One error shape

Every non-2xx API response has this body:

```json
{ "error": { "code": "shift_overlap", "message": "Dana already works an overlapping shift on Tue 07:00." } }
```

- `code` is a stable, lowercase `snake_case` string clients and evals may depend on.
- `message` is human-readable and safe to show; it never contains stack traces, SQL or secrets.
- Optional `details` (object) for field-level validation errors.

## Domain errors

- Services raise typed exceptions from `app/core/errors.py`. Each carries a `code` and a `message`.
- One exception handler in `main.py` maps them to HTTP. Routers do not catch and translate errors themselves.

| Exception | HTTP | Example codes |
|---|---|---|
| `ValidationFailed` | 422 | `validation_error`, `clock_out_before_clock_in`, `entry_too_long`, `invalid_week_start`, `shift_not_in_week`, `user_not_assignable` |
| `Unauthorized` | 401 | `invalid_credentials`, `invalid_token`, `token_expired` |
| `Forbidden` | 403 | `forbidden` |
| `NotFound` | 404 | `user_not_found`, `time_entry_not_found`, `shift_template_not_found`, `shift_not_found` |
| `Conflict` | 409 | `already_clocked_in`, `not_clocked_in`, `time_entry_overlap`, `availability_locked`, `shift_overlap`, `min_rest_violation`, `schedule_published` |
| any other exception | 500 | `internal_error` (logged with traceback, generic message) |

- Pydantic request-validation errors are converted to the same shape with code `validation_error` and `details`.
- A new error code is added to this table in the same change that introduces it.

## Principles

- Validate at the boundary (schemas) and enforce invariants in services; don't re-validate in repositories.
- Fail loudly: never swallow an exception or return `None` to mean "error".
- Authorization failures are `Forbidden`, except when revealing existence would leak data – then `NotFound`.
- Pure modules raise `ValueError` for impossible input; the calling service converts it to a domain error.
- Assistant tools catch domain errors and return them to the model as structured tool results, so the model can
  explain the problem instead of crashing the loop.
- On the client, every request has an error state shown to the user using `error.message`.
