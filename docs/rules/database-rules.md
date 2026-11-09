# Database rules

PostgreSQL with pgvector, SQLAlchemy 2, Alembic. Table and column names come from
[glossary.md](../glossary.md).

## Models

- SQLAlchemy 2 declarative style with `Mapped[...]` and `mapped_column(...)`.
- One model per file in `server/app/models/`, imported in `models/__init__.py` so Alembic sees all of them.
- Tables are plural `snake_case`; columns `snake_case`. Primary key `id` (integer identity).
- Foreign keys are named `<entity>_id` and declare `ondelete` explicitly.
- Every uniqueness rule in the domain is a database constraint (`UniqueConstraint`), not only a check in code.
- Enums are stored as `text` with a `CHECK` constraint (via SQLAlchemy `Enum(..., native_enum=False)`), so adding a
  value is a simple migration.

## Types

| Data | Column type |
|---|---|
| timestamps | `timestamptz`, always UTC |
| calendar dates (`week_start`, work day) | `date` |
| times of day in templates | `time` (local, interpreted in `Asia/Jerusalem`) |
| money | `numeric(10, 2)` |
| embeddings | `vector(N)` (pgvector), N fixed by the embedding model |
| free JSON (tool args) | `jsonb` |

## Migrations

- Alembic only. Every schema change is a new migration generated with `--autogenerate` and then **read and
  corrected by hand**.
- **Never edit a migration after it is created.** A mistake is fixed by a new migration. (Enforced by a hook.)
- Every migration has a working `downgrade()`.
- Migration file names: `NNNN_short_description.py` (set with `--rev-id`).
- Extensions (`vector`) are created in a migration, not by hand.

## Queries

- Queries live in repositories only. No raw SQL outside repositories; inside them prefer the SQLAlchemy expression
  API and use `text()` only with bound parameters.
- Avoid N+1: load related rows explicitly (`selectinload`) when a service needs them.
- Index every foreign key and every column used in a frequent filter (e.g. `time_entries (user_id, clock_in)`).

## Data

- Seed data comes only from `server/scripts/seed.py`; it is idempotent (safe to re-run).
- Tests use a separate database and never touch the development database.
