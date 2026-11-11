---
name: debug-schedule
description: Explain why the solver could not fill a week (or filled it badly): run the scheduler in trace mode on the development database and report, in plain language, which hard constraint blocks which shift and what the manager could relax or ask. Read-only; never changes data. Use when a manager asks why Generate left slots unfilled.
argument-hint: "<week_start YYYY-MM-DD> [--min-rest H] [--max-shifts N]"
---

# debug-schedule

Answer one question for one week: **why is this shift not fully staffed, and what could the manager do about
it?** The solver already knows. This skill runs it again in trace mode through
`schedule_service.propose_schedule` (no writes) and turns the output into advice. It never edits assignments,
availability, templates or the database.

## 1. Check the week

`week_start` is a **Sunday** (`YYYY-MM-DD`). If the user gave a date that is not a Sunday, use the Sunday on or
before it and say so. The week must already have shifts (generate them first with `POST /api/shifts/generate`);
the script reports `no_shifts_for_week` otherwise. The database must be up: `docker compose up -d db` at the
repository root.

## 2. Run the report

```bash
cd server && uv run python scripts/debug_schedule.py --week <week_start>
# what if the rules were different (does not change configuration):
cd server && uv run python scripts/debug_schedule.py --week <week_start> --min-rest 6 --max-shifts 6
```

`--as <email>` runs as a specific manager (default: the first active one). Rules default to the configured
`SCHEDULER_*` values.

## 3. Read the output

| Section | Meaning |
|---|---|
| `Positions filled: X of Y` | coverage of the week; `search budget used up` means the best result found, not a proof |
| `Unfilled slots` | one sentence per short shift, e.g. "Tuesday 07:00 needs 3, only 2 available; Dana excluded by minimum rest" |
| indented lines under a slot | per employee, the hard constraint and the shift it clashes with (overlap, minimum rest, max shifts per week) |
| `Did not answer available` | people who are not candidates at all: no answer counts as unavailable |
| `What if` | each rule relaxed on its own with the new coverage: options, not fixes |
| `Trace:` | how much the search did; a very large elimination count by one constraint points at the bottleneck |

## 4. Report in prose

Lead with the verdict (how many positions are open and on which shifts), then for each unfilled shift:

1. **Why**, in the solver's words: who could work it and what stops each of them. Name the people and the shifts.
2. **What the manager could do**, most reasonable first:
   - ask the people under "Did not answer available" to answer (availability is the cheapest lever);
   - move a clashing assignment away, or accept a manual edit: overlap and minimum rest are rejected by the
     API, other rules only warn;
   - lower `required_staff` on the template (new shifts only) or split the shift;
   - relax minimum rest or the weekly cap only as a **manager's decision**, quoting the `What if` numbers.
3. **What not to suggest**: never tell the manager to ignore availability silently, to drop a hard constraint by
   editing code, or to publish a schedule they have not reviewed.

If everything is filled, say so and stop. If the search budget ran out (`complete` false), say the result is the
best found, not proven optimal.

## 5. Checklist

- [ ] the week is a Sunday and has shifts
- [ ] the script ran without writing anything (it never does)
- [ ] every unfilled shift got a cause naming people and shifts, not just a constraint name
- [ ] suggestions are options for the manager; no data was changed
