# Naming rules

The vocabulary is defined in [glossary.md](../glossary.md). **Use those words and no synonyms**: a time entry is
never a "punch" or "log", an assignment is never a "booking". When a new concept appears, add it to the glossary in
the same change.

## Cases

| Where | Rule | Example |
|---|---|---|
| Python modules, functions, variables | `snake_case` | `time_entry_service.py`, `clock_in()` |
| Python classes, schemas, enums | `PascalCase` | `TimeEntry`, `PayBreakdown`, `Role` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_MIN_REST_HOURS` |
| Tables | plural `snake_case` | `time_entries` |
| Columns, JSON fields, TS DTO fields | `snake_case`, same word everywhere | `week_start` |
| API paths | `/api/` + plural kebab-case resource | `/api/time-entries/{id}` |
| Enum values | lowercase strings | `"preferred"` |
| Error codes | lowercase `snake_case` | `already_clocked_in` |
| TS components and types | `PascalCase` | `ScheduleBoard`, `TimeEntry` |
| TS files | components `PascalCase.tsx`, everything else `camelCase.ts` | `ScheduleBoard.tsx`, `apiClient.ts` |
| MobX stores | `<Domain>Store` | `PayStore` |

## Files and functions

- Server files are named by layer and entity: `api/time_entries.py`, `services/time_entry_service.py`,
  `repositories/time_entry_repository.py`, `models/time_entry.py`, `schemas/time_entry.py`.
- Functions are verbs: `calculate`, `list_time_entries`, `ensure_manager`. Booleans read as questions: `is_open`,
  `has_overlap`.
- Request schemas end in `Create` / `Update`; response schemas use the plain entity name or end in `Out` when both
  exist (`TimeEntryCreate`, `TimeEntryOut`).

## Tests

- Test files: `test_<module>.py`, mirroring the source path (`tests/unit/pay/test_calculate.py`).
- Test functions: `test_<unit>_<case>` describing the behavior: `test_calculate_split_shift_sums_before_tiers`.

## Branches and plans

- Plan files: `plans/NNN-YYYY-MM-DD-short-name.md`. Branches: `plan/NNN-short-name`. See
  [git-rules.md](git-rules.md).
