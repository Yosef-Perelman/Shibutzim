# Plan 003 – Design system and client

| | |
|---|---|
| **Status** | in progress |
| **Date** | 2026-11-11 |
| **Related docs** | [product-definition.md](../docs/product-definition.md) §3, §5.1–§5.4, §6.3 · [architecture.md](../docs/architecture.md) §4, §9, §10 · [glossary.md](../docs/glossary.md) · rules: [ui](../docs/rules/ui-rules.md), [coding](../docs/rules/coding-rules.md) (TypeScript), [naming](../docs/rules/naming-rules.md), [style](../docs/rules/style-rules.md), [error-handling](../docs/rules/error-handling-rules.md), [testing](../docs/rules/testing-rules.md), [git](../docs/rules/git-rules.md) · subagents: [frontend](../.claude/agents/frontend.md), [backend](../.claude/agents/backend.md) · skill: [new-endpoint](../.claude/skills/new-endpoint/SKILL.md) |
| **Roadmap** | plan 003 of 005 |
| **Branch** | plan/003-design-system-client |

## Goal

At the end of this plan a person can use Shibutzim in a browser instead of through `/docs`. The look is decided
**before** any screen exists: Yosef's reference screenshots become `docs/design-system.md` (colors, typography,
spacing, radius, component do's and don'ts), the document becomes a Mantine theme, and a static style preview page
is approved by Yosef before the first screen is written. Then the React + TypeScript + MobX client covers the
weekly cycle and pay over the existing REST API: login (with a demo-user switch), the employee's shifts,
availability form and pay page at phone width, and the manager's schedule board and team pay on a desktop. Every
screen shows the server's truth: the client never computes pay or validates scheduling rules.

## Scope

### In

1. **Design system document** `docs/design-system.md`, derived from the screenshots in `design/references/`
   (local, git-ignored): palette with semantic roles (primary, surface, text, success / warning / danger, one color
   per availability status and per schedule status), type scale and font stack, spacing and radius scales, shadows,
   component do's and don'ts (buttons, inputs, tables, cards, badges, empty / loading / error states), and the
   mobile-first and desktop-first layout rules for employee and manager screens. Only what is **derived** is
   committed; no screenshot is.
2. **Client scaffold** in `client/`: Vite + React + TypeScript (`strict`), ESLint (typescript-eslint, react-hooks),
   Prettier (100 columns, single quotes, semicolons, trailing commas), Vitest + React Testing Library, the folder
   layout of architecture §4 (`api/`, `stores/`, `features/`, `components/`, `routes/`), npm scripts `dev`,
   `build`, `lint`, `typecheck`, `test`, `format`. `client/.env.example` documents the only variable.
3. **Mantine theme** (`client/src/theme.ts`) implementing the design system, plus a **static style preview** route
   (`/design`, available in development only) that shows every token and component state from the document.
   **The plan pauses here until Yosef approves the preview**; the approval is recorded in this file.
4. **Typed API client** (`client/src/api/`): one module per resource with DTOs mirroring the server schemas field
   for field (`snake_case`), a base `apiClient` that attaches the JWT, parses the one error shape into a typed
   `ApiError { status, code, message, details }`, and signals `401` so the auth store can log the user out.
5. **MobX stores** behind a root store and React context: `AuthStore` (token, current user, login, logout,
   demo-user switch, token kept in `localStorage`), `ScheduleStore` (a week's shifts and schedule, generate, edit,
   publish, unfilled reasons), `AvailabilityStore` (a week's answers, dirty state, save, lock state), `PayStore`
   (own breakdown, team table), `TimeStore` (own open entry, clock in / out – see open question 4).
   `AssistantStore` waits for plan 004.
6. **Routing and shell**: `/login`; `/me/*` for employees, `/manager/*` for managers, guarded by the store's role;
   a manager may also open `/me/*` for their own data. Navigation per role, current user and role badge, logout.
   Unknown routes and the wrong role redirect to that role's home.
7. **Employee screens** (designed at 375 px, then widened):
   - **My shifts** (`/me/shifts`): the published schedule of a week (this week by default, previous / next week
     navigation), own assignments first and highlighted, then the whole team's; "not published yet" empty state when
     the server answers `schedule_not_found`.
   - **Availability** (`/me/availability`): next week by default, one row per shift with a three-state control
     (`available` / `preferred` / `unavailable`, text and icon, never color alone), a single Save that sends the
     whole week with `PUT /api/availabilities`; read-only with an explanation when the week is locked
     (`availability_locked`) or in the past.
   - **Pay** (`/me/pay`): month picker (default: current month), totals, per work day the hours and amount with
     the tier lines, open-entries notice; money as `₪` with two decimals, hours as the server's display hours.
8. **Manager screens** (desktop-first, usable on a tablet):
   - **Schedule board** (`/manager/schedule`): week picker; a Sunday–Saturday grid of shift cards showing name,
     local times, `assigned / required` coverage and the assigned names; status badge (`no schedule`, `draft`,
     `published`); actions **Create this week's shifts** (when `no_shifts_for_week`), **Generate** (shows the
     score, `complete` flag and every unfilled slot's `sentence` and reasons), **add / replace / remove** an
     assignment from a card (employee picker from `GET /api/users`; blocking errors such as `shift_overlap` and
     `min_rest_violation` shown inline; edit warnings shown as notifications), and **Publish** behind a
     confirmation dialog; `schedule_published` and `availability_ignored` messages come from the server.
   - **Team pay** (`/manager/pay`): date range (default: current month), one row per user with hours, amount and
     open entries, totals, and a drill-down to one employee's breakdown (the same component as `/me/pay`).
9. **Server additions** (via `/new-endpoint`, tests first): `GET /api/users` for managers, with optional
   `role` and `is_active` filters, returning a list of `UserOut` (the endpoint is manager-only, so exposing
   `hourly_rate` is fine). Nothing else changes on the server.
10. **Tooling**: a PostToolUse hook for `.ts` / `.tsx` edits running Prettier and ESLint `--fix` (same pattern as
    `post_edit_py.py`); `.claude/settings.json` allows `npm run *`, `npx tsc *`, `npx vitest *`.
11. **Docs**: architecture §9 brought to the real file names and the dev-server / API proxy decision; AGENTS.md
    "Common commands" gets the client commands; glossary gets the new client-facing terms (schedule board, demo user
    switch, style preview); `docs/design-system.md` added to the AGENTS.md task map for client work.

### Out

- The **assistant chat panel** and `AssistantStore` (plan 004); the MCP server, PWA manifest, Dockerfile that serves
  the built client, CI (plan 005).
- **Shift-template management UI** and **manager time-entry corrections UI** (manual entries, corrections,
  deletes): both stay API-only in this plan (see open question 5); the seed provides templates and entries.
- A cross-week **"my assignments"** endpoint (deferred by plan 002): the client reads one published week at a time.
- Hebrew UI text and right-to-left layout (open question 8); dark mode; i18n framework.
- Realtime updates (polling or websockets), offline support, printing a schedule.
- Password change, user management, registration, refresh tokens.
- Visual regression or end-to-end browser tests (Playwright); unit tests cover the API client and stores only.
- Seed changes.

## Assumptions

Verified:

- The server exposes everything the screens need except an employee list: login, `/api/auth/me`, shifts,
  availabilities, schedules with assignment edits and publish, time entries with clock in / out, pay and team pay
  (`server/app/api/`). The schedule response already carries `user_name`, per-shift coverage and the unfilled
  slots' `sentence`, so no new read endpoint is needed for the board.
- CORS already allows `http://localhost:5173`, the Vite default port (`server/app/config.py`).
- The seed creates one manager (`dana@shibutzim.example`) and five employees (`noa@`, `omer@`, `tamar@`,
  `yonatan@`, `lior@`), all with `SEED_PASSWORD`, a published schedule for this week and an unscheduled next week.
- Node 24.16 and npm 11.13 are installed; no `client/` folder exists; no `.github/workflows/` yet.
- `design/references/` **is currently empty.** Step 1 cannot start until Yosef drops the screenshots there (open
  question 1).
- The PostToolUse hook runs only for `.py` files; nothing formats TypeScript yet.

Not verified (taken as true):

- Mantine 8 is the current major and its `@mantine/dates` package works with `dayjs`; exact versions are pinned at
  install time to the latest stable at least two weeks old.
- The employee screens' users have phones at roughly 375 px wide; the manager uses a laptop ≥ 1280 px.
- A manager who wants their own data can use `/me/*`; managers are never assigned shifts, so "My shifts" for a
  manager shows the team's schedule only.
- Eight-hour tokens are acceptable for the demo; the client logs out on `401` and does not refresh tokens.

## Steps

Each step is one commit unless noted. Client steps are done by the `frontend` subagent, step 11 by `backend`,
tests may be delegated to `qa`.

1. `docs: add the design system derived from the reference screenshots` – read every file in
   `design/references/`, write `docs/design-system.md` (section list in *In* 1), link it from architecture §9 and
   the AGENTS.md task map. Commit the document only. **Gate:** screenshots present.
2. `chore: scaffold the client (Vite, React, TypeScript, Mantine, MobX)` – `npm create vite@latest client --
   --template react-ts`, strict `tsconfig`, ESLint + Prettier configs, Vitest + Testing Library + jsdom, the
   PostCSS preset Mantine needs, folder layout, `client/.env.example` (`VITE_API_URL`), `/api` dev proxy to
   `http://localhost:8000`, a one-line `client/README.md`, root `.gitignore` already covers `node_modules` and
   `dist`. `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` all pass on the empty app.
3. `chore: format and lint TypeScript after every edit` – `.claude/hooks/post_edit_ts.py` (Prettier + ESLint
   `--fix` on the edited file, output fed back on failure), registered in `.claude/settings.json` next to the Python
   hook; permission allow-list for `npm run *`, `npx tsc *`, `npx vitest *`.
4. `feat: Mantine theme and the style preview page` – `client/src/theme.ts` (colors, fonts, spacing, radius,
   component defaults from the document), `features/design/StylePreview.tsx` at `/design` in development builds
   only: tokens, buttons in every variant and state, inputs with labels and errors, badges for the three
   availability statuses and the two schedule statuses, a table, a card, the loading / empty / error state
   components from `components/`. **Stop. Yosef reviews the page at 375 px and 1280 px and approves or asks for
   changes; changes loop inside this step. The approval (date and any asked change) is recorded under "Amendment on
   approval" below before step 5 starts.**
5. `test: API client turns the error shape into ApiError and attaches the token` then
   `feat: typed API client and DTOs` – `api/apiClient.ts`, `api/types/` mirroring every response schema used
   (`UserOut`, `TokenOut`, `ShiftOut`, `AvailabilityOut`, `ScheduleOut`, `ScheduleGenerateOut`,
   `AssignmentEditOut`, `TimeEntryOut`, `PayOut`, `TeamPayOut`), one module per resource (`auth.ts`, `users.ts`,
   `shifts.ts`, `availabilities.ts`, `schedules.ts`, `timeEntries.ts`, `pay.ts`). Vitest with a mocked `fetch`:
   bearer header, JSON error → `ApiError` with `code`, non-JSON failure → `internal_error`, `401` triggers the
   unauthorized callback.
6. `test: AuthStore logs in, restores a session and logs out on 401` then `feat: auth store, login screen, role
   routes and app shell` – root store + context, `AuthStore` (login → token + user, `me` on start-up to restore
   a stored token, logout, demo-user switch that logs in as another seeded account – see open question 3), routes
   per role with guards, `AppShell` with navigation per role, loading / empty / error state components shared by
   every screen. Login shows the server's `invalid_credentials` message verbatim.
7. `test: ScheduleStore exposes a week's published schedule with own assignments first` then `feat: My shifts
   screen` – `ScheduleStore.loadWeek(week_start)` (`schedule_not_found` → empty state, not error), week navigation
   helper in `Asia/Jerusalem` (`dayjs` with the timezone plugin; Sunday is day 0), `features/me/MyShifts.tsx`.
8. `test: AvailabilityStore tracks dirty answers and the lock state` then `feat: Availability form` –
   `AvailabilityStore.loadWeek`, `setAnswer`, `save` (`PUT` with every shift that has an answer), lock from
   `availability_locked` or a past week, `features/me/AvailabilityForm.tsx` with a `SegmentedControl` per shift.
9. `test: PayStore formats money and hours as the server sends them` then `feat: Pay page` –
   `PayStore.loadMine(from, to)`, month picker, `features/pay/PayBreakdown.tsx` (shared with the manager
   drill-down), `features/me/MyPay.tsx`. Amounts are rendered from the server's strings, never recomputed.
10. `feat: Clock in / out card` *(only if open question 4 is approved)* – `TimeStore` (open entry from
    `GET /api/time-entries?from=&to=` of today, clock in, clock out, `already_clocked_in` / `not_clocked_in`
    shown inline), card on the employee home.
11. `test: GET /api/users requires a manager` then `feat: GET /api/users for managers` (via `/new-endpoint`):
    401 / 403 matrix, filters `role` and `is_active`, ordered by name; glossary and error table unchanged (no new
    code). Server tests still pass.
12. `test: ScheduleStore generates, edits and publishes a week` then `feat: Manager schedule board` –
    `ScheduleStore` actions `createShifts`, `generate` (keeps the `unfilled`, `score`, `complete` of the last
    run), `addAssignment`, `replaceAssignment`, `removeAssignment` (warnings → notifications), `publish`;
    `features/manager/ScheduleBoard.tsx` with `WeekPicker`, `ShiftCard`, `AssignmentPicker` (employees from
    `GET /api/users?role=employee&is_active=true`), `UnfilledPanel`, publish confirmation. Blocking errors keep
    the dialog open and show `error.message`.
13. `feat: Team pay screen` – `PayStore.loadTeam(from, to)`, `features/manager/TeamPay.tsx`, row click opens the
    shared `PayBreakdown` for that employee via `GET /api/pay?user_id=`.
14. `docs: client architecture, commands and glossary after plan 003` – architecture §9 (real file names, proxy
    decision, the `401` logout rule), AGENTS.md "Common commands" (dev server, lint, typecheck, test, build),
    glossary terms (schedule board, demo user switch, style preview, week picker), ui-rules if a rule was refined.
15. `plan: close plan 003` – validation results and "What changed vs. plan", roadmap row `done`, merge into `main`.

## Validation

| # | Command / action | Expected |
|---|---|---|
| 1 | `docs/design-system.md` exists; `git ls-files design/` | the document is tracked; the listing is empty (no screenshot committed) |
| 2 | Yosef opens `http://localhost:5173/design` at 375 px and 1280 px | approval recorded in this file under "Amendment on approval" before step 5's commit exists (`git log` order) |
| 3 | `cd client && npm run lint && npm run typecheck && npm test && npm run build` | all four exit 0; `dist/` is produced and git-ignored |
| 4 | `cd server && uv run pytest -q` | all tests pass, including `GET /api/users`: 401 without a token, 403 for an employee, 200 for a manager with the filters applied |
| 5 | `grep -rn "fetch(" client/src --include=*.tsx` | no match: components never call `fetch` (only `api/apiClient.ts` does) |
| 6 | `grep -rn "hourly_rate\|multiplier" client/src/features` | used only to display server values; no arithmetic on amounts (reviewed by hand) |
| 7 | Dev DB seeded, server on 8000, `npm run dev`; log in as `noa@shibutzim.example` | lands on `/me/shifts`; this week shows the published schedule with Noa's assignments first; next week shows "not published yet"; `/manager/schedule` redirects to `/me/shifts` |
| 8 | As Noa, `/me/availability` | this week is read-only with the lock explanation; next week shows every shift with a three-state control; changing two answers and saving returns to a clean state and a reload shows the same answers |
| 9 | As Noa, `/me/pay` for the current month | totals and the per-day tier lines equal `GET /api/pay` for the same range (compared by eye on two days); amounts show `₪` and two decimals |
| 10 | Chrome device toolbar at 375 px on `/me/*` | no horizontal scroll, every control reachable with a thumb, every input has a visible label |
| 11 | Log in as `dana@shibutzim.example`, `/manager/schedule`, next week | `no schedule`; **Create this week's shifts** is a no-op (shifts exist) or creates them; **Generate** shows the draft with the coverage, the score and the unfilled sentences from plan 002's smoke test |
| 12 | On the draft: add Noa to a shift that breaks minimum rest; add someone who answered `unavailable`; remove an assignment; **Publish**, then **Publish** again | `min_rest_violation` message inline, nothing changes; `availability_ignored` warning notification and the name appears; the card updates; confirmation dialog, then the badge turns `published`; the second publish shows `schedule_published` |
| 13 | As Dana, `/manager/pay` for the current month; click a row | one row per seeded user, totals at the bottom; the drill-down equals `/me/pay` for that user |
| 14 | Stop the server, reload any data screen | the error state shows a message and a retry button; no blank page, no console exception |
| 15 | Delete the token in `localStorage` or wait for expiry, then act | the client lands on `/login` with a "session expired" notice |
| 16 | Edit a `.tsx` file with a formatting error through Claude Code | the hook reformats it and reports lint errors |
| 17 | `git log --oneline main..plan/003-design-system-client` | reads docs → chore → feat (preview) → test/feat pairs → docs → plan |

## Rollback

- No migration and no data change: the server gains one read-only endpoint; reverting its commit restores plan 002's
  API exactly.
- The client is additive: deleting `client/`, the `.ts` hook and the settings allow-list lines returns the
  repository to plan 002 plus the design-system document, which can stay or be reverted on its own.
- Nothing is deployed; the branch is merged only when validation passes. If the plan is abandoned midway, the
  branch is deleted and the roadmap row goes back to `todo`.

## Open questions (each with a suggested answer)

1. **`design/references/` is empty. Should step 1 wait for the screenshots, or start from Mantine's defaults?**
   → *Suggested:* wait – Yosef drops the screenshots in before approving this plan (any image format, named
   freely, with an optional `notes.md` saying what to take from each), because the roadmap makes the design system
   the first deliverable and a document derived from defaults would be redone later.
2. **Which libraries and versions?**
   → *Suggested:* React 19, Vite 7, TypeScript 5, Mantine 8 (`@mantine/core`, `@mantine/hooks`, `@mantine/dates`,
   `@mantine/notifications`), MobX 6 with `mobx-react-lite`, React Router 7, `dayjs` (Mantine's date dependency,
   with the `timezone` plugin for `Asia/Jerusalem`), `@tabler/icons-react` (Mantine's icon set); dev: ESLint 9 with
   `typescript-eslint` and `eslint-plugin-react-hooks`, Prettier 3, Vitest 3, Testing Library, jsdom, the PostCSS
   preset Mantine requires. Exact versions pinned at install to releases at least two weeks old, because these are
   the stack the docs already name and nothing else is needed.
3. **What is the "role switch" of the roadmap row?**
   → *Suggested:* a **demo-user switch** on the login screen and in the user menu: a list of the six seeded
   accounts that logs in as the chosen one with `SEED_PASSWORD` (the password is typed once and kept in memory
   only; the list is shown only when `VITE_DEMO_USERS` is set in development). It lets a reviewer jump between
   Dana and Noa in one click, because a real role switch does not exist on the server (the role is in the token
   and cross-checked with the row) and should not for a scheduling product.
4. **Should the employee home include clock in / out?**
   → *Suggested:* yes, as one card on `/me/shifts` with the open entry's start time and a single button (step 10),
   because employees clock in and out from the same phone screen in the product definition, the endpoints exist, and
   it costs one store and one component. Decline and step 10 is dropped.
5. **Shift-template management and manager time-entry corrections in the UI?**
   → *Suggested:* out of this plan, because the seed covers both for the demo and each is a form-heavy CRUD screen
   that would double the plan; they become a short follow-up plan (or part of 005) once the assistant exists.
6. **How does the client reach the API in development?**
   → *Suggested:* a Vite `/api` proxy to `http://localhost:8000`, so the browser stays same-origin, cookies and
   CORS never matter, and plan 005's single container (FastAPI serving `dist/`) works without a change;
   `VITE_API_URL` stays available for an explicit host.
7. **Where does the token live?**
   → *Suggested:* `localStorage`, read once at start-up and validated with `GET /api/auth/me`, because the token
   expires in eight hours and the demo has no refresh flow; an `httpOnly` cookie would require server changes.
8. **UI language and direction?**
   → *Suggested:* English, left-to-right, with the product name "Shibutzim" and `₪` for money, because every doc,
   seed and error message is in English and the server's messages are shown verbatim; RTL and Hebrew strings would
   need every message translated on the server too.
9. **What do unit tests on the client cover?**
   → *Suggested:* the API client's error mapping and token handling, and each store's actions against a mocked API
   module (loading / empty / error transitions, dirty tracking, own-first ordering). No component rendering tests
   beyond a smoke render of the shell, because the business rules are tested on the server and screen behavior is
   verified by validation items 7–15 in the browser.
10. **Should the `.ts` hook block on lint errors like the Python hook blocks on failing tests?**
    → *Suggested:* reformat and auto-fix, and report remaining lint errors as feedback to fix before moving on, but
    do not run the whole Vitest suite on every edit, because `tsc` and Vitest on each edit would slow every step and
    `npm run typecheck && npm test` are required before each commit anyway.
11. **Week navigation range for employees?**
    → *Suggested:* any week, previous and next buttons without a limit, because past weeks are read-only and
    unpublished weeks show the empty state; the server already hides drafts from employees.

## Amendment on approval

Approved on 2026-11-11 by Yosef ("implement plan 003"). All eleven open questions are accepted **as suggested**.
Open question 1 is resolved: four screenshots (`image.png` to `image4.png`) are now in `design/references/`, so
step 1 may start. The style-preview gate in step 4 still applies: no screen is written before Yosef approves it.

**Style preview approved by Yosef on 2026-11-11** (`/design`, no changes requested). Steps 5 onward may start.

## What changed vs. plan

*(Running notes while the plan is in progress; the final table is written when it is closed.)*

**Progress.** Steps 1 to 4 are committed. **Gate (step 4): passed on 2026-11-11**, see "Amendment on approval".

**Deviations so far**

| What | Why | Effect |
|---|---|---|
| Versions are newer majors than open question 2 listed: Mantine 9.7.4, MobX 7.1.3, Vite 8.3.5, React Router 8.5.1, Vitest 5.0.5, React 19.3.1, ESLint 10.13.0. All pinned exactly, each at least two weeks old (cutoff 2026-10-28). | The plan said "pinned at install to releases at least two weeks old"; the named majors were suggestions and are no longer current. | `client/package.json` and the lockfile are the source of truth. |
| TypeScript is **6.0.3**, not 7. | `typescript-eslint` 8.72 accepts only TypeScript below 6.1; TypeScript 7 made `npm install` fail. | Move to 7 when `typescript-eslint` supports it. |
| The TypeScript hook (step 3) is committed but **not registered** in `.claude/settings.json`, and the `npm` / `npx` permission rules are not added. | The harness denied the command that edited `settings.json` (it grants permissions). | Until Yosef approves the edit, `npm run lint` and `npm run format` run by hand before each commit. The exact change is in `post_edit_ts.py` plus one PostToolUse entry and five allow rules. |
| Design system differs from the references on purpose: the primary blue is darker (`#2f6fe0`) and muted text is darker (`#6b677a`). | The references fail WCAG AA (white on `#4d96f8` is 2.99:1; their grey text is 3.5:1). | Documented in `docs/design-system.md` §1 and §2. |
| The availability control is three equal tiles with the icon above the word, not three pills. | At 375 px the pill version clipped "Unavailable" (found by rendering in a real 375 px frame). | Updated in the design system §6.2. |
| Button height is 44 px everywhere, not 44 on phones and 40 on desktop. | One value is simpler and meets the touch-target rule on every device. | Design system §6.1. |


