# Testing rules

## Order

- **Tests first for pure logic.** For `pay/` and `scheduler/`, the test is written and seen failing before the code.
  Commit order within a plan: `test:` commit, then `feat:` commit.
- Every bug fix starts with a test that reproduces it.

## Levels

| Level | Location | Scope | Database |
|---|---|---|---|
| Unit | `server/tests/unit/` | pure modules, helpers | none |
| Service | `server/tests/services/` | business rules + authorization | test database |
| API | `server/tests/api/` | routing, status codes, error shape, auth | test database |
| Evals | `server/evals/` | assistant behavior | test database + LLM stub or real model, run on demand |

- Test database: a separate Postgres database (`shibutzim_test`); each test runs in a transaction that is rolled
  back. Never SQLite – the production behavior (timestamptz, pgvector, constraints) must be tested.
- **No test calls a real LLM.** Unit and API tests use a fake `llm` implementation. Real-model runs are evals only.
- No test depends on the current time: pass `now` in, or freeze it.

## Mandatory matrices

These cases must exist and pass before any change to the module is merged.

**Pay (`pay.calculate`)**: exactly 8h; 9h; 12h; split shift 07–11 + 16–22 = 10h; 22:00–06:00 crossing midnight (one
work day); two work days in one period; no entries; rounding to the cent with `Decimal`.

**Pay rules** (every new rule added by the `add-pay-rule` skill): exactly at the boundary; crossing midnight; split
shift; combined with overtime tiers; zero hours.

**Scheduler (`scheduler.solve`)**: no solution (reports unfilled slots with reasons); tight solution (exactly
enough staff); fairness (hours spread across employees); each hard constraint violated in isolation is never
produced (availability, required staff, overlap, minimum rest, max shifts per week); preferred shifts honored when
possible.

**Authorization**: for every endpoint, an employee accessing another employee's data or a manager-only action gets
`403`, and an unauthenticated call gets `401`.

## Style

- One behavior per test; the name says which (`test_calculate_exactly_8h_has_no_overtime`).
- Arrange / act / assert, with literal expected values (`Decimal("412.50")`), not values recomputed with the code
  under test.
- Use `pytest.mark.parametrize` for matrices; keep each case readable.
- Fixtures in `conftest.py`; factory helpers for users, shifts and time entries instead of copy-pasted setup.

## Commands

```bash
cd server && uv run pytest -q          # everything
cd server && uv run pytest -q tests/unit/pay
```
