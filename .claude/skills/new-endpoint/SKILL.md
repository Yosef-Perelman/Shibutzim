---
name: new-endpoint
description: Add a REST endpoint (or a small group) to the server following the project's layers - schema, repository, service with authorization, router - with tests first (401/403 matrix, error codes, happy path), then docs. Use for any new or changed endpoint under server/app/api. Does not cover pure modules (pay, scheduler) or assistant tools.
argument-hint: "<METHOD /api/path> – what it does and who may call it"
---

# new-endpoint

Build one endpoint group the way plan 001 built auth and time entries. Work only on the step the approved plan
names; if the endpoint is not in the plan, stop and ask for an amendment.

**Reference implementation to copy** (read these before writing anything):

| Layer | File |
|---|---|
| Router | `server/app/api/time_entries.py` |
| Schemas | `server/app/schemas/time_entry.py` |
| Service | `server/app/services/time_entry_service.py` |
| Repository | `server/app/repositories/time_entry_repository.py` |
| Service tests | `server/tests/services/test_time_entry_service.py` |
| API tests | `server/tests/api/test_time_entries.py` |
| Fixtures | `server/tests/conftest.py`, `server/tests/factories.py` |

## 1. Define the contract first (write it down before coding)

Read [error-handling-rules](../../../docs/rules/error-handling-rules.md), [coding-rules](../../../docs/rules/coding-rules.md),
[naming-rules](../../../docs/rules/naming-rules.md) and use the exact words of [glossary.md](../../../docs/glossary.md).
State, in the commit message or the reply:

- method and path (`/api/` + plural kebab-case resource), success status (`200`, `201` create, `204` delete);
- **who may call it**: any authenticated user / the owner or a manager / managers only;
- request fields and response fields (snake_case, same names as the glossary and the DB columns);
- every failure with its HTTP status and **error code**, from the table in error-handling-rules. A code that is not
  in the table is new: it goes into `ErrorCode` in `server/app/core/errors.py` **and** the table, in the same change.

## 2. Tests first - a `test:` commit that is red

Two files per endpoint group. Names: `test_<unit>_<case>`; literal expected values; no test reads the clock.

**Service tests** (`tests/services/`, use `session`, `manager`, `employee`, `other_employee`, factories, `NOW`):
- happy path per operation;
- **authorization**: `Forbidden` for every disallowed role/owner combination - and an employee calling a
  manager-only service gets `Forbidden` even for a missing id (authorization comes before existence);
- every business rule and error code, including boundaries (exactly at the limit vs. one past it);
- `NotFound` codes for missing ids when the caller *is* allowed to know.

**API tests** (`tests/api/`, use `client`, `employee_client`, `manager_client`, `other_employee_client`):
- **401 matrix**: one parametrized test sending each endpoint with no token; expect `401` and `invalid_token`;
- **403 matrix**: every manager-only endpoint with `employee_client`; every owner-only read with
  `other_employee_client`; expect `403` and `forbidden`;
- happy path: status code and the response body shape;
- one test per error code at its HTTP status, asserting `response.json()["error"]["code"]`;
- request validation: missing or malformed input returns `422` with code `validation_error`.

Run `uv run pytest -q`: the new tests must fail for the right reason (missing module), the old ones still pass.
Commit: `test: <what the endpoint must do>`.

## 3. Implement bottom-up - a `feat:` commit

1. **Schemas** (`schemas/<entity>.py`): `<Entity>Out` with `from_attributes=True`; `<Entity>Create` / `Update` for
   input. Datetimes in requests are `AwareDatetime`. Money is `Decimal` (serialized as a string). A partial update
   uses `exclude_unset=True` and rejects an empty body. Never expose `password_hash` or other internals.
2. **Repository** (`repositories/<entity>_repository.py`): SQLAlchemy queries only. No roles, no HTTP errors, no
   business rules. Index anything new that you filter on (new index = new migration).
3. **Service** (`services/<entity>_service.py`): every public function takes `current_user` first and calls
   `ensure_manager` / `ensure_self_or_manager` **before loading or changing anything**. It owns the transaction:
   `session.commit()` after a write. Raise `DomainError` subclasses with an `ErrorCode`; never return `None` for an
   error. Time comes in as `now` - never call `datetime.now()`. To turn a database constraint violation into a
   domain error, wrap the insert in `with session.begin_nested():` and catch `IntegrityError` outside it.
4. **Router** (`api/<entity>.py`): `APIRouter(prefix="/api/<resource>", tags=[...])`; import only from
   `app.deps` (`CurrentUser`, `SessionDep`, `NowDep`), schemas and services - never models, repositories or
   SQLAlchemy. Call **one** service function, return `Out.model_validate(...)`. A query parameter named like a
   Python keyword (`from`) uses `Query(alias="from")`. Declare fixed paths (`/clock-in`) before `/{id}`.
5. **Register** the router in `create_app()` in `server/app/main.py`.

## 4. Check, document, commit

- `cd server && uv run ruff format . && uv run ruff check . && uv run pytest -q` - all green.
- Layering: `grep -nE "app\.models|app\.repositories|sqlalchemy" server/app/api/*.py` prints nothing.
- Pure-module rule still holds: `grep -rE "sqlalchemy|fastapi|app\.(db|repositories|services)" server/app/pay`.
- Update [error-handling-rules](../../../docs/rules/error-handling-rules.md) (new codes) and
  [glossary.md](../../../docs/glossary.md) (new terms, endpoints) in the same commit.
- Stage explicit paths, never `git add -A`. Commit types and order: [git-rules](../../../docs/rules/git-rules.md).

## Checklist (all must be true before you report done)

- [ ] contract stated: path, status, roles, fields, error codes
- [ ] `test:` commit came first and was red for the right reason
- [ ] 401 test for every endpoint; 403 test for every role or ownership rule
- [ ] one test per error code; one `422 validation_error` test
- [ ] service checks authorization first; router has no logic; repository has no roles
- [ ] new error codes in `ErrorCode` **and** error-handling-rules; new terms in the glossary
- [ ] ruff and the whole suite pass; layering greps are clean
