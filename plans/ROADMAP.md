# Roadmap

The single source of **what's next**. Plans run strictly in order: a plan starts only after the previous one is
`done` (validation passed, "What changed vs. plan" filled). Status values: `todo` / `in progress` / `done`.
Workflow details: [AGENTS.md](../AGENTS.md#plan-to-plan-workflow) and
[planning-rules.md](../docs/rules/planning-rules.md).

| Plan | Status | File | Content |
|---|---|---|---|
| **000** | in progress | [000-2026-11-10-ai-sdlc-setup.md](000-2026-11-10-ai-sdlc-setup.md) | AI SDLC setup: docs trio, AGENTS.md / CLAUDE.md, rules, this roadmap, archive the brief locally, `.claude/` settings, hooks, subagents, `new-plan` skill |
| **001** | todo | – | Skeleton (FastAPI, config, Docker Compose Postgres + pgvector), all DB models + first migration, seed, JWT auth + roles, **pay module (TDD)**, time-entry endpoints, `GET /api/pay`; then the `add-pay-rule` skill |
| **002** | todo | – | Availability endpoints, **CSP scheduler** (TDD, with a trace/explain mode), generate / edit / publish schedule; then the `debug-schedule` skill |
| **003** | todo | – | Client: login + role switch, my shifts, availability form, manager schedule board, pay page (React + TS + MobX) |
| **004** | todo | – | Assistant: agent loop, tools, confirmation flow, tool-call logging, handbook RAG, evals |
| **005** | todo | – | Dockerfile + GitHub Actions (lint + tests on PR, deploy) → **GCP Cloud Run** (DB stays managed: Supabase / Neon); **MCP server** (official Python SDK / FastMCP, exposing the same services – "same core, two interfaces: REST and MCP"); PWA |

Plan 005 is part of the roadmap, not optional.

## Skills built along the way

| Skill | Built in | Purpose |
|---|---|---|
| `new-plan` | 000 | draft the next plan from this roadmap using the planning template, then stop for approval |
| `add-pay-rule` | after 001 | add a pay rule (e.g. night or weekend premium) to `PayRules` with a fixed edge-case matrix (exactly at the boundary, crossing midnight, split shift, combined with overtime tiers, zero hours); update glossary and docs; run the pay tests; fail if any matrix case is missing |
| `debug-schedule` | after 002 | run the solver with trace mode on a week it couldn't fill (or filled badly) and report which hard constraint blocks which shift/slot, e.g. "Tuesday 07:00 needs 3, only 2 available; Dana excluded by minimum rest", and suggest what the manager could relax. Requires `scheduler.solve(..., trace=True)` |

## Never compromise on

Pay tests · scheduler tests · authorization in services · the docs and plans trail.

## Final deliverable

Public GitHub repo with a strong README: problem, demo GIF / screenshots, architecture diagram, and a
**"How this was built with AI"** section describing docs → rules → plans → guardrails / hooks → subagents → skills →
evals.
