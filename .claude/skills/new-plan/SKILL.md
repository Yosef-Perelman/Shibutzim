---
name: new-plan
description: Draft the next plan from plans/ROADMAP.md using the project's planning template, then stop for the user's approval. Use after a plan is closed, or when the user asks for the next plan. Never writes code.
argument-hint: "[plan number, optional – defaults to the first `todo` row]"
---

# new-plan

Draft exactly one plan file and stop. This skill never writes application code, never commits the draft, and never
starts implementation.

## Procedure

1. **Find the plan to draft.** Read `plans/ROADMAP.md`.
   - If an argument was given, use that plan number. Otherwise take the first row with status `todo`.
   - Stop and tell the user if any earlier plan is not `done`: plans run strictly in order.
   - Stop if a file for that plan number already exists in `plans/`; show it instead of overwriting.
2. **Load context.** Read [planning-rules.md](../../../docs/rules/planning-rules.md) (template and lifecycle), the
   roadmap row's content, the previous plan's "What changed vs. plan" section, and only the docs the roadmap row
   touches (use the task map in `AGENTS.md`). Inspect the current repo state relevant to the plan (existing
   files, installed tools) so assumptions are facts where possible.
3. **Name the file** `plans/NNN-YYYY-MM-DD-short-name.md`: three-digit number, today's date, two to four kebab-case
   words. The branch is `plan/NNN-short-name`.
4. **Write the plan** with every section of the template, status `draft`:
   - **Goal** – the outcome in one paragraph.
   - **Scope** – *In* covers everything in the roadmap row; *Out* names what a reader might expect but won't get.
   - **Assumptions** – state what was verified and what wasn't.
   - **Steps** – numbered, small, each verifiable and ideally one commit; tests before the code they test; follow
     [git-rules.md](../../../docs/rules/git-rules.md) commit types.
   - **Validation** – concrete commands and expected observable results, including the mandatory test matrices
     from [testing-rules.md](../../../docs/rules/testing-rules.md) when the plan touches pay, scheduler or
     endpoints.
   - **Rollback** – including migrations and data.
   - **Open questions** – every question has a *Suggested* answer and the reason. Include every decision a reviewer
     could reasonably want to make (dependencies, trade-offs, defaults). Prefer asking here over assuming silently.
   - **What changed vs. plan** – placeholder.
5. **Update the roadmap**: set the row's status to `in progress` and link the new file.
6. **Check the draft** against the template: all sections present, every open question has a suggested answer, every
   validation item is observable, nothing from the roadmap row is missing from *In* or *Out*.
7. **Stop.** Do not commit and do not implement. Reply to the user with: the file path, a three-to-five line summary
   of the scope, and the open questions with their suggested answers, then ask for approval or changes.

## On approval (next turn, not part of this skill run)

Apply any requested changes in an **Amendment on approval** section, set status `approved`, and commit the plan
alone: `plan: add plan NNN – <name> (approved)`. Implementation starts after that commit.
