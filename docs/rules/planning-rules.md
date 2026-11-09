# Planning rules

No implementation starts without a written plan that the human approved. The plan, not the code, is the center of
gravity: it is where scope, assumptions and risks are decided.

## One plan at a time

- Plans run in the order of [plans/ROADMAP.md](../../plans/ROADMAP.md). A plan starts only after the previous one is
  `done`.
- Work outside the current plan's scope needs either a plan amendment approved by the human or a new plan.

## File

- Path: `plans/NNN-YYYY-MM-DD-short-name.md` – three-digit number from the roadmap, the date the draft was written,
  a kebab-case name of two to four words. Example: `plans/001-2026-11-12-skeleton-auth-pay.md`.
- Use the template below. Every section is required; write "None" rather than deleting a section.

## Status lifecycle

| Status | Meaning | Who sets it |
|---|---|---|
| `draft` | written, waiting for the human | agent |
| `approved` | the human approved it; no code yet | agent, only after explicit human approval |
| `in progress` | the first implementation commit exists | agent |
| `done` | validation passed; "What changed vs. plan" is filled | agent |

- A draft is **not committed**. On approval it is committed alone, with status `approved`
  (`plan: add plan NNN – <name> (approved)`).
- Changes the human requests at approval time go into an **Amendment on approval** section, not silently into the
  text.
- `plans/ROADMAP.md` uses `todo` / `in progress` / `done`. A roadmap row becomes `in progress` when its plan is
  drafted and `done` when the plan is closed.

## Writing a good plan

- **Goal**: one paragraph – the outcome, not the activity.
- **Scope**: explicit *In* and *Out* lists. Out-of-scope items that a reader might expect are listed on purpose.
- **Assumptions**: everything taken as true without verification. A wrong assumption is the most common cause of a
  wrong implementation.
- **Steps**: numbered, each small enough to verify on its own and ideally one commit. Tests come before the code
  they test.
- **Validation**: commands and observable results that prove the goal is met. "It works" is not validation.
- **Rollback**: how to undo, including data and migrations.
- **Open questions**: every question carries a **suggested answer** and the reason for it, so the human can approve
  with one word.
- Reference docs and rules by link; don't copy them into the plan.

## Closing a plan

1. Run every validation item and record failures honestly.
2. Fill **What changed vs. plan**: deviations, why, and anything deferred.
3. Set status `done`, update `plans/ROADMAP.md`, commit (`plan: close plan NNN`).
4. Draft the next plan with `/new-plan` and **stop for approval**.

## Template

```markdown
# Plan NNN – Title

| | |
|---|---|
| **Status** | draft |
| **Date** | YYYY-MM-DD |
| **Related docs** | links |
| **Roadmap** | plan NNN of 005 |
| **Branch** | plan/NNN-short-name |

## Goal

## Scope

### In

### Out

## Assumptions

## Steps

## Validation

## Rollback

## Open questions (each with a suggested answer)

1. **Question?**
   → *Suggested:* answer, because reason.

## What changed vs. plan

*(filled in when the plan is closed)*
```
