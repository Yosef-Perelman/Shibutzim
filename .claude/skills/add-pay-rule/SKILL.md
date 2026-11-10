---
name: add-pay-rule
description: Add a pay rule (for example a night or weekend premium) to the pure pay module with its fixed five-case edge-case matrix, tests first, then docs, and fail if any matrix case is missing. Use only for a rule the approved plan names. With "dry run" it lists the files and test cases it would create and stops without writing anything.
argument-hint: "<rule_name> - what it pays, when it applies [dry run]"
---

# add-pay-rule

Add one rule to `server/app/pay/` the way `overtime_tiers` was built: test matrix first, pure code second, docs
last. Pay is money: **never skip the matrix** and never compute an expected value with the code under test.

**Dry run:** if the argument says "dry run" (or "plan only"), do steps 1-3 *in your head and the reply*, run the
checker for the new rule name (it must fail with all five cases missing), list every file you would create or
change and the five cases with their hand-computed values, then **stop**. Write nothing.

## 0. Gate

The rule must be named by the approved plan (AGENTS.md: no features beyond the plan). If it is not, stop and ask
for an amendment. v1 has daily overtime tiers only; premiums are "designed for, not built"
([product-definition §6.1](../../../docs/product-definition.md)).

## 1. Read

[product-definition §5.4 and §6.1](../../../docs/product-definition.md), the pay matrices in
[testing-rules](../../../docs/rules/testing-rules.md), the pay terms in [glossary](../../../docs/glossary.md), and
the current module: `server/app/pay/rules.py`, `breakdown.py`, `calculate.py` and
`server/tests/unit/pay/test_calculate.py` (the reference matrix, rule name `overtime_tiers`).

## 2. Specify the rule - and ask about every choice you would otherwise assume

Write the rule in words, then put each decision to the user **with a suggested answer and why**, as plan
questions do. Never assume silently:

- `rule_name`: `snake_case`, used in the marker `@pytest.mark.pay_rule("<rule_name>")`.
- **Window or trigger** and its boundaries. Use half-open intervals `[from, to)` in `Asia/Jerusalem` local time.
- **Stacking** with the overtime tiers: a separate premium line (independent of tiers) or added to the tier
  multiplier? The two give different amounts; state which and why.
- **Rounding**: one `ROUND_HALF_UP` per line; every total is the sum of its lines (plan 001, question 7).
- **Default**: the rule is off unless configured, so `PayRules.default()` and every existing result stay unchanged.
- DST days, work-day assignment (an entry belongs to the day it started), open entries (excluded).

## 3. Tests first - a red `test:` commit

Add one parametrized test to `server/tests/unit/pay/` (new file `test_<rule_name>.py`), marked
`@pytest.mark.pay_rule("<rule_name>")`, with **exactly these case ids** (the checker reads them):

| Case id | What it proves |
|---|---|
| `at_boundary` | entries ending exactly at, starting exactly at, and one minute across the rule's boundary |
| `crossing_midnight` | 22:00-06:00, one work day, not split at midnight |
| `split_shift` | two entries on one day, the rule applying to only one of them |
| `with_overtime_tiers` | a day long enough to use the 125 % and 150 % tiers, rule and tiers together |
| `zero_hours` | no entries: no days, `Decimal("0.00")`, no rule lines |

Put the **hand calculation in a comment** above each case and a literal `Decimal` as the expected value. Add
extra cases and plain tests freely (validation of the new rule object, rounding of the rule's line).

Run the checker and the suite. The suite must fail for the right reason (missing code); the checker must report
the five ids as present:

```bash
cd server && uv run python ../.claude/skills/add-pay-rule/check_matrix.py <rule_name>
```

Commit: `test: <rule_name> matrix`.

## 4. Implement in the pure module - a `feat:` commit

- Put the rule object in `server/app/pay/rules.py` (frozen dataclass, validated in `__post_init__`) and add it to
  `PayRules` as an optional field with a default that disables it. Extend `breakdown.py` with a line type and
  `calculate.py` to emit rule lines **in addition to** tier lines; do not rewrite the tier logic.
- Durations stay integer seconds, money stays `Decimal`, no `float`, no clock, no settings, no I/O.
- If the response shape changes, update `schemas/pay.py` and `api/pay.py` and extend `tests/api/test_pay.py`
  (follow `/new-endpoint`); enabling the rule for real users is a product decision made in `Settings.pay_rules`.

## 5. Docs, then verify

- [glossary](../../../docs/glossary.md): the rule's term and its names in code and API.
- [product-definition §6.1](../../../docs/product-definition.md): the business rule in one or two sentences.
- [architecture decision log](../../../docs/architecture.md) if you chose between designs.

```bash
cd server
uv run ruff format . && uv run ruff check . && uv run pytest -q
uv run pytest tests/unit/pay -v                       # every case by name
uv run python ../.claude/skills/add-pay-rule/check_matrix.py   # fails if any rule lacks a case
grep -rE "sqlalchemy|fastapi|app\.(db|repositories|services)" app/pay   # must print nothing
```

## Checklist

- [ ] the plan names the rule; every ambiguous choice was put to the user with a suggestion
- [ ] `test:` commit first; matrix marked `pay_rule("<rule_name>")` with all five case ids
- [ ] hand-computed expected values in comments, literal `Decimal`s in assertions
- [ ] default `PayRules` results unchanged (`overtime_tiers` matrix still green)
- [ ] checker exits 0; purity grep prints nothing; ruff and the whole suite pass
- [ ] glossary and product-definition updated

## Worked example - dry run for a hypothetical "night premium"

*Illustrative only: v1 has no night premium, and these choices are suggestions, not product decisions.*

Rule `night_premium`: hours worked in the local window `[22:00, 06:00)` earn an extra 25 % of the base rate,
as a **separate premium line** that ignores the overtime tiers. Rate 50.00/h, so the premium is 12.50 per hour.

**Would create** `server/tests/unit/pay/test_night_premium.py` (the five cases below plus rule-object
validation), then change `server/app/pay/rules.py` (`NightPremium`, optional `PayRules.night_premium`),
`breakdown.py` (`PremiumLine`, `DayBreakdown.premium_lines`), `calculate.py`, `__init__.py`, and - because the
response gains lines - `schemas/pay.py`, `api/pay.py`, `tests/api/test_pay.py`, plus the glossary and
product-definition §6.1. **Would not touch** the tier logic or the seed.

| Case | Entries (local) | Tiers | Premium | Total |
|---|---|---|---|---|
| `at_boundary` | 21:00-22:00 → 0 s in window; 06:00-07:00 → 0 s; 22:00-23:00 → 1 h; 21:59-22:01 → 60 s | 50.00 for 1 h; 50.00; 50.00; 1.67 for 2 min | 0.00; 0.00; 12.50; 0.21 (60 s × 12.50/3600 = 0.2083) | 50.00; 50.00; 62.50; 1.88 |
| `crossing_midnight` | 22:00-06:00 (8 h, all in window) | 8 × 50.00 = 400.00 | 8 × 12.50 = 100.00 | 500.00 |
| `split_shift` | 07:00-11:00 + 18:00-23:00 (9 h) | 400.00 + 1 × 62.50 = 462.50 | only 22:00-23:00 counts: 12.50 | 475.00 |
| `with_overtime_tiers` | 14:00-02:00 (12 h) | 400.00 + 125.00 + 150.00 = 675.00 | 22:00-02:00 = 4 h × 12.50 = 50.00 | 725.00 |
| `zero_hours` | none | no days | no lines, 0.00 | 0.00 |

The checker for the new rule fails before step 3 (`missing at_boundary, crossing_midnight, split_shift,
with_overtime_tiers, zero_hours`) and passes after it.
