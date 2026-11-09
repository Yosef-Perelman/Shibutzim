# Coding rules

Applies to all code. Layer details are in [architecture.md §3](../architecture.md#3-layers-and-their-rules); this
file turns them into rules.

## Layers (server)

- **Routers** (`server/app/api/`) handle HTTP only: parse input with Pydantic schemas, get the current user from
  the dependency, call **one** service function, return a schema. No business logic, no models, no repositories,
  no DB session use beyond passing it on.
- **Services** (`server/app/services/`) hold business rules **and authorization**. Every public service function
  takes `current_user` as an explicit parameter (except auth/login) and checks access first, before loading or
  changing anything. Services own the transaction: they commit or roll back.
- **Repositories** (`server/app/repositories/`) contain SQLAlchemy queries only. They never check roles and never
  raise HTTP errors.
- **Pure modules** (`server/app/pay/`, `server/app/scheduler/`) take plain data and return plain data. They must not
  import SQLAlchemy, FastAPI, `app.db`, `app.repositories`, `app.services`, the LLM adapter, or read the clock
  (`datetime.now()` is passed in, never called inside).
- **Assistant tools** call services as the current user. They never import repositories or models. Write tools
  return a proposal and never write.
- Imports flow downward only: routers → services → repositories / pure modules. Never upward, never sideways
  between routers.

## Python

- Python 3.12. Type hints on every function signature and public attribute. `from __future__ import annotations`
  is not needed on 3.12; don't add it.
- Pydantic v2 models for all API input and output. Never return a SQLAlchemy model from a router.
- Money is `decimal.Decimal`. Never `float` for money or for hours that become money.
- Datetimes are timezone-aware. A naive `datetime` is a bug. Use helpers in `app/core/time.py` for work-day and week
  boundaries.
- Small functions with one job. A function that needs a comment to explain its sections should be split.
- No dead code, commented-out code, or `print` debugging in commits.
- Configuration comes from `app/config.py` (pydantic-settings). No `os.environ` elsewhere; no secrets or URLs in
  code.

## TypeScript

- `strict: true`. No `any`; use `unknown` and narrow.
- DTO types mirror server schemas field for field (see [naming-rules.md](naming-rules.md)).
- Server state lives in MobX stores; components never call `fetch` directly (see [ui-rules.md](ui-rules.md)).

## Dependencies

- A new dependency (Python or npm) is added only when an approved plan names it. Otherwise ask first.
- Prefer the standard library and the libraries already in the stack.

## Assistant code

- Prompts live in `server/app/assistant/prompts/` as files. No prompt text inline in Python.
- The model never receives raw database rows it does not need; tools return compact, purpose-built results.
- Every tool call goes through the logging wrapper.
