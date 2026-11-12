# Plan 005 – Deploy, MCP server and PWA

| | |
|---|---|
| **Status** | in progress |
| **Date** | 2026-11-12 |
| **Related docs** | [architecture.md](../docs/architecture.md) §3, §4, §8, §10, §11 · [product-definition.md](../docs/product-definition.md) §5.5, §7 · [coding-rules](../docs/rules/coding-rules.md) · [testing-rules](../docs/rules/testing-rules.md) · [git-rules](../docs/rules/git-rules.md) · [ui-rules](../docs/rules/ui-rules.md) · [design-system](../docs/design-system.md) |
| **Roadmap** | plan 005 of 005 |
| **Branch** | plan/005-deploy-mcp-pwa |

## Goal

Shibutzim runs on a public URL: one container on GCP Cloud Run serves the API and the built client against a
managed PostgreSQL with pgvector, every pull request is linted and tested by GitHub Actions, and a push to `main`
deploys. A manager can add employees and deactivate people who left, so the deployed team is not frozen to the
seed. The same services gain a second machine interface, an MCP server a developer can plug into Claude Code or
Claude Desktop with a user's token and get exactly the tools, authorization and logging the in-app assistant has.
The client installs on a phone home screen as a PWA. The repository ends the roadmap with the README of the final
deliverable: problem, demo, architecture, and how the project was built with AI.

## Scope

### In

- **Team management** (added on Yosef's request, 2026-11-12): `POST /api/users` creates a user (email, name,
  role, hourly rate, initial password) and `PATCH /api/users/{id}` sets `is_active`; both manager-only in
  `user_service`, built with `/new-endpoint` (401 / 403 matrix, `409 conflict` on a duplicate email, 422 on bad
  input, a manager cannot deactivate themself). A **Team** screen at `/manager/team` (a fifth manager navigation
  item) lists everyone with role, rate and status, adds a person through a form in a dialog, and deactivates or
  reactivates from the row. A deactivated user cannot sign in, is not scheduled and keeps their history (this is
  what `is_active` already means in the code).
- **Serving the client from the API**: a `STATIC_DIR` setting; when the directory exists, hashed assets are served
  and every non-`/api` path returns `index.html` (SPA fallback). `/api/*` keeps its JSON 404. Nothing changes in
  development, where the directory does not exist.
- **Dockerfile** (multi-stage: Node 24 builds the client, `python:3.12-slim` + `uv sync --no-dev --frozen` runs the
  server, a non-root user, `PORT` from the environment, migrations at container start), a `.dockerignore`, and an
  `app` service in `docker-compose.yml` behind a profile for the local smoke test.
- **GitHub Actions** `ci.yml`: on pull requests and pushes to `main`, a server job (ruff check and format,
  `alembic upgrade head` + `alembic check`, pytest against a `pgvector/pgvector:pg16` service), a client job
  (`npm ci`, lint, typecheck, test, build) and an image build. A `deploy` job runs only on pushes to `main`, after
  the others: keyless auth to GCP (Workload Identity Federation), push to Artifact Registry, deploy to Cloud Run
  with secrets from Secret Manager.
- **Managed database**: Supabase (pgvector enabled, IPv4 session pooler URL), seeded and with the handbook ingested
  once from Yosef's machine. A `docs/deployment.md` runbook holds every one-time command (GCP project, APIs,
  Artifact Registry, service account, WIF pool, secrets, Supabase project, GitHub secrets and variables, seed,
  ingest, rollback).
- **MCP server** `server/app/mcp/` on the **official Python SDK** (`mcp`, FastMCP class), stdio transport, started
  with `uv run python -m app.mcp`. It builds its tool list from the assistant's `registry.ALL_TOOLS`, acts as the
  user behind `SHIBUTZIM_MCP_TOKEN` (resolved through `auth_service.authenticate_token` on every call, fresh
  session), runs every call through `dispatch.call_tool` so role filtering, argument validation, domain errors
  and the `tool_call_logs` row are identical to the chat, and returns a write tool's proposal as content without
  writing. Tests: tools listed per role, a refused call for the wrong role, a logged call, an identical result to
  the REST endpoint, a missing or invalid token. An example Claude Code / Claude Desktop configuration in the README.
- **PWA**: `vite-plugin-pwa` (`generateSW`, auto update, registration injected into `index.html`), a web manifest
  (name, short name, `#fbfaf9` background, `#ffffff` theme, standalone display), icons generated from one SVG with
  `@vite-pwa/assets-generator` (192, 512, maskable, apple-touch-icon, favicon), iOS meta tags. The service worker
  precaches the app shell only; `/api/*` is excluded from the navigation fallback and from runtime caching, so no
  authenticated data is ever served from a cache.
- **Demo access on the public site**: the demo-account switch on the login screen is currently shown only in
  development builds (`import.meta.env.DEV`). The gate becomes "`VITE_DEMO_USERS` is set", and the Docker build
  sets it for the demo deployment (open question 7).
- **Docs**: product-definition §3 and §5 (a manager adds and deactivates people); architecture §3 (an MCP row in
  the layer table), §4 (new folders), §9 (the Team route), §10 rewritten from "planned" to what runs, §11
  decisions; design-system (five manager navigation items); `.env.example` (`STATIC_DIR`, `SHIBUTZIM_MCP_TOKEN`,
  `PORT`); AGENTS.md commands; glossary (MCP, PWA, deactivated user); `docs/deployment.md`.
- **Final README** (roadmap "Final deliverable"): problem, demo URL and demo accounts, screenshots / GIF (captured
  by Yosef on the deployed site; the plan leaves named placeholders), the architecture diagram (the Mermaid from
  architecture §2), the MCP setup, and a **"How this was built with AI"** section: docs → rules → plans →
  guardrails / hooks → subagents → skills → evals, with links to the real files.

### Out

- An HTTP (streamable) MCP transport mounted in the FastAPI app or deployed to Cloud Run. The stdio server runs on
  a developer's machine against whichever `DATABASE_URL` it is given (open question 4).
- New MCP tools beyond the seven assistant tools, MCP resources or prompts.
- Offline use of the app: the PWA installs and loads its shell offline, but every screen needs the API. No
  background sync, no push notifications, no "update available" toast.
- Custom domain, CDN, Cloud Armor, rate limiting, multiple Cloud Run regions or min-instances above zero.
- Database backups beyond what Supabase does by default; a staging environment; preview deployments per PR.
- Running the assistant evals in CI (architecture §11: they need a key and the provider's quota).
- Self-service sign-up, invitation emails, password reset, a "change my password" screen, editing a user's
  hourly rate or role after creation (a rate change would recompute past pay; it needs its own rule first),
  deleting users, groups or departments, more than one organization (product-definition §8).
- Dependabot / Renovate, code coverage upload, release tags, container vulnerability scanning.
- Changes to pay, scheduler or the assistant's behavior. No schema change and no migration: `users` already has
  every column the Team screen needs.

## Assumptions

Verified in the repository and on this machine on 2026-11-12:

- There is no `Dockerfile`, no `.github/`, no `client/public/`; `GET /api/health` exists; `alembic/env.py` reads
  `DATABASE_URL` from settings; the test fixtures run `alembic downgrade base` + `upgrade head` on a database whose
  name ends in `_test`, and that database is created only by `docker/initdb/01-test-db.sql` (Compose), so CI must
  create it itself.
- The repository `github.com/Yosef-Perelman/Shibutzim` is **public**. A Gemini key committed in `.env.example` by
  the plan-004 closing commit made GitHub's push protection reject the push. On 2026-11-12, before approval, the
  72 unpushed commits were rewritten with `git filter-repo --replace-text --refs a677dc7..main` (backup bundle in
  the session scratchpad); no commit contains the key any more, the 67 pushed commits are byte-identical, and
  `main` is a fast-forward of `origin/main`. Yosef revokes the key in AI Studio.
- The client reads `VITE_API_URL` (empty means same origin) and shows the demo switch only when `import.meta.env.DEV`.
- `users` has `email` (unique), `password_hash`, `name`, `role`, `hourly_rate`, `is_active`; `UserOut` exposes all
  but the hash; `user_service` has `list_users` and `find_active_employee`; the manager navigation has four items
  (Schedule, Team pay, My pay, Assistant). Nothing creates or deactivates a user except the seed.
- Docker 29.9.3 is installed and the daemon runs; Node 24.16, npm 11.13, uv 0.13.7, Python 3.12. `gh` 2.103 and
  Google Cloud SDK 593 were installed on 2026-11-12 and are logged in as Yosef; no `gcloud` project is set yet
  (five projects exist, none for Shibutzim). No image tool (rsvg, ImageMagick, Pillow) is installed, so icons need
  the assets generator.
- PyPI: `mcp` 2.3.0 (2026-10-02) is the newest stable; 1.30.0 (2026-09-07) is the last 1.x. npm: `vite-plugin-pwa`
  2.0.0 (2026-10-03) declares `vite ^8` as a peer. All are older than two weeks (plan 003's rule).
- The chat tools already go through `dispatch.call_tool`, which checks the role, validates arguments and writes
  the log row; `ToolContext` carries the user, session, clock and LLM. The MCP server adds no business logic.

Not verified, to confirm at implementation:

- The exact FastMCP API of `mcp` 2.x (tool registration from a Pydantic model, stdio entry point). If 2.x changed
  it beyond what the docs show, pin `mcp>=1.30,<2` instead (open question 3).
- Cloud Run reaches Supabase over IPv4 only; Supabase's direct host is IPv6, so the **session-mode pooler** URL is
  used. Transaction mode is avoided because psycopg's prepared statements break there.
- Yosef's GCP billing account can be linked to a new project, and he has a Supabase account. With `gcloud` and `gh`
  logged in, the agent runs the runbook commands and shows each one; Yosef supplies the project ID and the Supabase
  connection string (the agent never reads `.env`).
- Cloud Run's free tier and Supabase's free tier cover a demo; Supabase pauses a free project after a week of
  inactivity, which shows as a slow first request or an error until it is resumed.
- The GitHub repository is already public. CI and deploy only run once the branch is
  pushed, which Yosef does (or asks for) at step 1 and again at step 8.

## Steps

Each step is one commit unless noted; tests precede the code they test.

1. **`plan:`** commit the approved plan on `plan/005-deploy-mcp-pwa`. Yosef pushes `main` and the branch (the
   history is clean now), so CI can run from step 8 on.
2. **`test: create and deactivate users`** – service tests (manager creates, employee gets `Forbidden`, duplicate
   email is a `Conflict`, a manager cannot deactivate themself, a deactivated user fails `authenticate_token` and
   `find_active_employee` skips them) and API tests (401 / 403 for both endpoints, 409, 422, happy paths).
3. **`feat: user creation and deactivation endpoints`** – `UserCreate` / `UserStatusUpdate` schemas,
   `user_repository.create` and `set_active`, `user_service.create_user` and `set_user_active` with
   `ensure_manager`, `POST /api/users` and `PATCH /api/users/{id}`; the password is hashed with the existing
   `hash_password`.
4. **`feat: Team screen for managers`** – `client/src/api/users.ts` gains create and update, `TeamStore`,
   `/manager/team` with a table (name, email, role, rate, status badge), an "Add person" dialog with the form
   and validation messages from the server's error shape, a deactivate / reactivate action with an in-page
   confirmation, a fifth manager navigation item (`IconUserPlus` or `IconUsers`), and component tests (list,
   add, deactivate, a 409 shown on the email field).
5. **`test: serve the built client`** – API tests with a temporary static directory: `/` and `/me/shifts` return
   `index.html` (200, `text/html`), `/assets/x.js` is served, `/api/health` stays JSON, `/api/nope` stays the JSON
   404 body, and without the directory the app behaves as today.
6. **`feat: serve the built client from the API`** – `STATIC_DIR` setting (default `server/static`, git-ignored),
   mounted only when present; the fallback route is registered last. `.env.example` documents it.
7. **`chore: Dockerfile and local container run`** – multi-stage build, `.dockerignore`, `start.sh` (`alembic
   upgrade head`, then `uvicorn app.main:app --host 0.0.0.0 --port $PORT`), Compose `app` service under
   `--profile app` using the Compose database. Smoke test locally (validation 4).
8. **`chore: GitHub Actions CI`** – `.github/workflows/ci.yml` with the server, client and image jobs. The server
   job creates `shibutzim_test` with `psql`, sets `DATABASE_URL` / `TEST_DATABASE_URL` to the service and runs
   `alembic upgrade head`, `alembic check`, `pytest -q`. The branch is pushed; CI must be green before step 9.
9. **`docs: deployment runbook`** – `docs/deployment.md`: new GCP project linked to billing with a one-dollar
   budget alert, enable Run / Artifact Registry / Secret Manager / IAM Credentials APIs, Artifact Registry
   repository with a cleanup policy (keep the last three images), deployer service account and roles, WIF pool
   and provider bound to the GitHub repository, secrets (`DATABASE_URL`, `JWT_SECRET`, `GEMINI_API_KEY`),
   Supabase project (region, pgvector extension, session-pooler URL), GitHub secrets / variables, seed and ingest
   from a laptop with `DATABASE_URL` pointed at Supabase, rollback. The agent runs the `gcloud` and `gh` commands
   with Yosef watching; Yosef creates the Supabase project and pastes nothing secret into the chat (secrets go
   straight into `gcloud secrets` / `gh secret set` from his shell).
10. **`chore: deploy to Cloud Run on main`** – the `deploy` job: `google-github-actions/auth` (WIF),
    build and push the image, `deploy-cloudrun` with `--set-secrets`, `--allow-unauthenticated`, region and
    service from variables. First deployment happens when the plan is merged and pushed (validation 6).
11. **`test: MCP server`** – unit tests with the fake LLM and the test database: tool list per role, a manager
    tool called as an employee is refused, a call writes one `tool_call_logs` row, `get_my_hours` equals the pay
    endpoint's totals, `generate_schedule_draft` creates no schedule row, missing / expired token fails clearly.
12. **`feat: MCP server over the assistant tools`** – `server/app/mcp/` (`server.py`, `__main__.py`), dependency
    `mcp==2.3.0`, `SHIBUTZIM_MCP_TOKEN` setting, tool descriptions from the existing prompt files, argument
    schemas from the tools' Pydantic models. No import of repositories or models (validation 8).
13. **`chore: PWA manifest, icons and service worker`** – `vite-plugin-pwa@2.0.0`, `@vite-pwa/assets-generator`
    (dev dependency, `npm run icons`), `client/public/icon.svg` (a placeholder mark in `ink` `#1f1c42`), manifest,
    iOS meta tags, `navigateFallbackDenylist` for `/api`, no runtime caching of `/api`. The test setup leaves the
    plugin out, so component tests are untouched.
14. **`feat: demo accounts switch when VITE_DEMO_USERS is set`** – the gate changes from `DEV` to a non-empty
    variable; the Dockerfile passes it as a build argument; the RootStore test covers both cases.
15. **`docs: product, architecture, design system, glossary, env and commands for plan 005`** – the docs items
    in scope.
16. **`docs: final README`** – the final-deliverable README with screenshot / GIF placeholders Yosef fills.
17. **`plan: close plan 005`** – validation results, "What changed vs. plan", roadmap `done`, merge into `main`.

## Validation

1. `git log --oneline plan/005-deploy-mcp-pwa` reads: plan, test → feat → feat (team), test → feat (static),
   chore (Docker), chore (CI), docs, chore (deploy), test → feat (MCP), chore (PWA), feat (demo switch), docs,
   docs, plan.
2. `git log --all -S'<first characters of the old key>'` prints nothing (already true), `git push` of `main` is accepted by GitHub, and
   Yosef confirms the old key is revoked.
3. `cd server && uv run pytest -q`: all pass, including the new user, static-serving and MCP tests; `uv run ruff
   check .`, `uv run ruff format --check .` and `uv run alembic check` are clean. `cd client && npm run lint &&
   npm run typecheck && npm test && npm run build` pass.
3a. Team, by API: `POST /api/users` unauthenticated → 401; as an employee → 403; as a manager with a new email →
    201 and the person can log in; the same email again → 409 `conflict`; `PATCH /api/users/{id}` with
    `is_active: false` → the person's next request answers 401 and `who_is_available` no longer names them;
    the manager's own id → 4xx with a clear message. In the browser: the Team screen lists the seeded six, adds
    a person, shows the 409 on the email field, and deactivation flips the status badge.
4. `docker build -t shibutzim .` succeeds from the repository root. `docker compose --profile app up -d` then:
   `curl -s localhost:8080/api/health` → `{"status":"ok"}`; `curl -sI localhost:8080/me/shifts` → `200` with
   `content-type: text/html`; `curl -s localhost:8080/api/nope` → the JSON error body with status 404; the login
   screen loads in a browser at `http://localhost:8080` and a demo login works.
5. On GitHub, the pushed branch shows the `ci` workflow green: server, client and image jobs, no deploy job.
6. After the merge is pushed, the `deploy` job is green and the Cloud Run URL answers `/api/health`; Yosef signs
   in with a demo account over HTTPS, opens My shifts, Pay and the Assistant, and the assistant answers.
7. MCP: with `SHIBUTZIM_MCP_TOKEN` of the seeded manager, `npx @modelcontextprotocol/inspector uv run python -m
   app.mcp` (or `claude mcp add shibutzim -- uv run python -m app.mcp`) lists seven tools; with an employee's
   token, four. Calling `get_my_hours` for last week returns the same hours as `GET /api/pay` for the same range, a
   new `tool_call_logs` row appears, and `generate_schedule_draft` returns a proposal and leaves `schedules`
   unchanged.
8. `grep -rn "app.repositories\|app.models" server/app/mcp` prints nothing.
9. `npm run build` writes `dist/manifest.webmanifest`, `dist/sw.js` and the icon files. In Chrome DevTools on the
   deployed site, Application → Manifest reports no errors and the install prompt is offered; a request to
   `/api/pay` in the Network panel is never served by the service worker; on a phone, "Add to Home Screen"
   opens the app standalone (Yosef).
10. The deployed login screen offers the demo accounts; a local `npm run build` without `VITE_DEMO_USERS` does not.
11. `docs/deployment.md` was followed end to end by Yosef without a command that had to be corrected; corrections
    are recorded in "What changed vs. plan".
12. The README renders on GitHub with every section of the final deliverable; every relative link resolves.

## Rollback

- **Code**: revert the plan's commits, or do not merge the branch. There is no migration and no schema change.
- **Team**: reverting the two endpoints and the screen leaves users created through them in place; they are
  ordinary rows and keep working. Deactivation is reversible from the same screen or with one SQL update.
- **Static serving**: unset `STATIC_DIR` or remove the directory; the API behaves as before.
- **CI / deploy**: delete `.github/workflows/ci.yml`; nothing else depends on it. GitHub keeps past runs.
- **Cloud Run**: `gcloud run services update-traffic shibutzim --to-revisions=<previous>=100` returns to the
  previous revision; `gcloud run services delete shibutzim` removes the service. The runbook lists both.
- **Database**: Supabase keeps its data; pausing or deleting the project is Yosef's manual action. Local
  development never touched it.
- **MCP**: remove `server/app/mcp/`, the `mcp` dependency (`uv sync`) and the two settings; nothing else imports it.
- **PWA**: a service worker stays registered in visitors' browsers after the code is reverted. Ship one build with
  `selfDestroying: true` in the plugin options; it unregisters itself and clears its caches on the next visit.
- **Demo switch**: build without `VITE_DEMO_USERS`; the login screen shows no accounts.
- **Secret**: the leaked key is revoked regardless of what else is rolled back. The pre-rewrite bundle in the
  session scratchpad restores the old history if something about the rewrite turns out wrong.

## Open questions (each with a suggested answer)

Decided by Yosef on 2026-11-12 while reviewing the draft: the key is scrubbed from history (done); the database is
**Supabase**; the product stays one organization with no groups; a manager screen to add employees is in scope.

1. **Which GCP project?**
   → *Suggested:* a new project named `shibutzim` linked to your billing account, because the five existing
   projects belong to other things and a budget alert and a later cleanup are simplest per project.

2. **Who may the Team screen create: employees only, or managers too?**
   → *Suggested:* both roles, with "Employee" preselected, because the seed is otherwise the only way to ever get
   a second manager and the service check is the same either way.

3. **MCP SDK and version: official `mcp` 2.3.0, `mcp` 1.30, or the third-party `fastmcp` 4.x?**
   → *Suggested:* the official `mcp==2.3.0`, because the roadmap says "official Python SDK", it ships a `FastMCP`
   class, and it is six weeks old. If its 2.x API turns out to differ from the documented decorator style, fall back
   to `mcp>=1.30,<2` and record it. The third-party `fastmcp` 4.x adds nothing the plan needs.

4. **MCP transport: stdio only, or also streamable HTTP mounted at `/mcp` and deployed?**
   → *Suggested:* stdio only. It is the transport Claude Code and Claude Desktop use locally, it needs no new
   authentication surface on the public site, and it keeps the deployed container unchanged. HTTP can be a
   follow-up plan.

5. **How does the MCP user authenticate?**
   → *Suggested:* a JWT in `SHIBUTZIM_MCP_TOKEN`, obtained from `POST /api/auth/login` (one `curl` in the README),
   validated on every call with the same `authenticate_token` the API uses. No email / password in the MCP
   environment, no new token type, and deactivating the user cuts the MCP off immediately.

6. **GCP credentials in GitHub: Workload Identity Federation or a service-account JSON key?**
   → *Suggested:* WIF, because no long-lived key is stored anywhere and it is what Google recommends; the runbook
   gives the commands once. A JSON key is simpler to set up but is exactly the kind of secret this plan starts by
   removing.

7. **Demo accounts on the public login screen?**
   → *Suggested:* yes, gated on `VITE_DEMO_USERS` being set at build time, with the shared demo password in the
   README. Visitors cannot otherwise try the product. A build for a real customer leaves the variable empty and
   gets today's behavior.

8. **Migrations at container start, or a separate Cloud Run job?**
   → *Suggested:* at container start (`alembic upgrade head && uvicorn …`). One revision at a time serves a demo;
   Alembic takes a lock, so even two cold starts are safe. A job is the right answer for a real multi-instance
   deployment and is noted in the runbook.

9. **Regions?**
   → *Suggested:* Cloud Run `europe-west3` (Frankfurt) and Supabase `eu-central-1` (Frankfurt), so the API and its
   database sit in the same city. `me-west1` (Tel Aviv) is closer to users but Supabase has no Israeli region, and
   the API-to-database round trip matters more than the browser-to-API one.

10. **CI triggers?**
    → *Suggested:* `pull_request` and `push` to `main` for checks; deploy only on `push` to `main` after the checks
    pass, in the same workflow. You never push without deciding to, so a push to `main` is an explicit release.

11. **PWA icon?**
    → *Suggested:* a generated placeholder (rounded `ink` square, white glyph) from one SVG checked into
    `client/public/`, replaced by a designed mark whenever you have one. Only the SVG changes; `npm run icons`
    regenerates the rest.

12. **Is the final README part of this plan?**
    → *Suggested:* yes, as step 14, with named placeholders for the screenshots and GIF you capture on the deployed
    site. It is the roadmap's final deliverable and plan 005 is the last plan.

13. **Is the `client/dist` build output copied into `server/static` during the Docker build only?**
    → *Suggested:* yes. Local development keeps Vite's dev server and proxy; `server/static/` is git-ignored and
    only ever exists inside the image or after an explicit local `npm run build && cp -r`.

14. **How does a new person get their password?**
    → *Suggested:* the manager types an initial password in the form (at least eight characters) and tells the
    person; no email is sent and there is no reset flow. It is the smallest thing that works without an email
    provider; a "change my password" screen is a natural follow-up and is listed as out of scope.

15. **Deactivate from the Team screen: confirmation dialog or an undo?**
    → *Suggested:* an in-page confirmation ("Deactivate Dana? She will not be able to sign in or be scheduled."),
    because the action is reversible from the same row and the design system already has the dialog pattern.

## What changed vs. plan

**Outcome so far (2026-11-12).** Every step of the plan is built and committed on the branch, and everything that can be checked on this machine passes. The plan is **not closed**: the CI run, the first deployment and the phone checks need the branch pushed and the one-time cloud setup, which are Yosef's to start (see Still open). Server: 1,076 tests; client: 220 tests; ruff, `alembic check`, lint, Prettier, typecheck and the build are clean.

### Deviations

| What | Why | Effect |
|---|---|---|
| The leaked key was removed by rewriting history **twice**. | The first rewrite (before approval) cleared the key from the 72 unpushed commits and `main` was then pushed by Yosef. The approval commit of this plan then quoted the first characters of the key as a search pattern, which also made that check match itself. A second rewrite, limited to the branch, replaced it. | `main` and `origin/main` are the same commit. Backup bundles of both states are in the session scratchpad. Validation 2 is reworded below. |
| **mcp 2.3.0 renamed `FastMCP` to `MCPServer`**; the server uses the SDK's low-level `Server`. | The tool names, descriptions and schemas already exist in the registry, so there was nothing to re-declare with decorators. | `app/mcp/server.py` is about 130 lines. Open question 3 resolved as suggested for the version, with this class instead. |
| A manager is offered **four** tools and an employee **four**, not "seven and four". | The role filter gives each role its own set (`search_policy` is shared); seven is the total. | Validation 7 corrected below. |
| The `mcp` dependency got its own `chore:` commit before the tests. | The tests need the MCP client to import. Only additions to the lock file. | One extra commit. |
| `fix:` commits for **HEAD requests** on client files and for `.dockerignore`. | Found by the local container run: `curl -I` got 405, and the ignore patterns only matched at the repository root, so `client/.env.local` would have entered the image. Each has its test or check. | Two extra commits. |
| `ScheduleStore` now asks only for `users.list`. | The new `TeamStore` widened the users API and the schedule store's tests supplied only `list`. | A narrower type, no behavior change. |
| `STATIC_DIR` is a commented example in `.env.example`. | An empty value would parse as the current directory. | None. |
| `workbox-build` and `workbox-window` 7.4.1 and `@vite-pwa/assets-generator` 2.0.0 were added beside `vite-plugin-pwa` 2.0.0. | They are its required and optional peers. | `npm audit` reports findings in Workbox's build-time dependencies and in the existing lint toolchain; with dev dependencies excluded it reports none. |
| The manager navigation has **five** items and the unit tests build without the PWA plugin. | As planned; recorded because the design system line changed. | `docs/design-system.md` updated. |
| Two small files (`schemas/user.py`, `core/errors.py`) were first written through the shell, so the edit hooks did not see them. | A slip against the guardrail note in AGENTS.md. | `ruff` and the whole suite were run by hand right after; nothing was missed. |
| The free-tier amounts in the runbook were checked against Google's page on 2026-11-12. | Yosef does not want to pay. | The amounts matched what was told to Yosef. |

### Validation results

| # | Result |
|---|---|
| 1 | The branch reads: plan, test, feat (users), feat (Team screen), test, feat (static), fix (HEAD), chore (Docker), chore (CI), docs (runbook), chore (deploy), chore (mcp dependency), test, feat (MCP), chore (PWA), fix (dockerignore), feat (demo switch), docs, docs (README). Close to the planned order; the extras are in Deviations. |
| 2 | Searching all history for the first characters of the old key finds nothing, `.env.example` at `HEAD` ends `GEMINI_API_KEY=`, and `main` was pushed and accepted by GitHub. **Revocation of the old key is Yosef's to confirm.** |
| 3 | `uv run pytest -q`: 1,076 passed; `ruff check`, `ruff format --check` and `alembic check` clean. Client lint, Prettier, typecheck, 220 tests and `npm run build` pass. |
| 3a | Through the rebuilt container: no token 401, employee 403, manager 201, the new person logs in 200, the same email again `email_already_used`, deactivation 200, then the person's token and login both 401, the manager deactivating themself `cannot_deactivate_self`, reactivation 200. The temporary user was deleted afterwards. **The Team screen was not opened in a browser** (no browser tool was available); component tests cover the list, add, field errors, confirmation, cancel and reactivation. |
| 4 | `docker build` succeeds. `docker compose --profile app up`: `/api/health` is `{"status":"ok"}`; `HEAD /me/shifts` is 200 `text/html` with `no-cache`; hashed assets are `immutable`; `/api/nope` is a JSON 404; a missing asset is 404; the manifest is `application/manifest+json`; the container runs as a non-root user; a demo login works. The login screen in a browser at port 8080 was **not** opened. |
| 5 | **Open.** The branch is not pushed, so no `ci` run exists. The workflow file parses and its server steps (migrations, `alembic check`, ruff, format) were run locally. |
| 6 | **Open.** Needs the cloud setup and the push to `main`. |
| 7 | Over real stdio against the development database: a manager's token lists 4 tools, an employee's lists 4; `get_team_hours` as the manager and `get_my_hours` as the employee return results; the employee calling a manager tool gets `isError` with `forbidden`; the four log rows are `ok`, `ok`, `ok`, `refused`. `get_my_hours` equals `GET /api/pay` in a test, and the draft proposal leaves `schedules` unchanged in a test. A missing or wrong token exits with code 2 and a message. |
| 8 | `grep -rn "app.repositories\|app.models" server/app/mcp` prints nothing; the router, schema and pure-module greps are silent. |
| 9 | **Partly.** `npm run build` writes the manifest, the service worker, `registerSW.js` and the icons; the worker has one route (the precached shell) with `/api` in the navigation denylist and no runtime caching; the icons were looked at. Chrome DevTools on the deployed site and "Add to Home Screen" on a phone are **open**. |
| 10 | Two image builds: with `VITE_DEMO_USERS` the built client contains the demo email once, without it zero times. The deployed login screen is **open**. |
| 11 | **Open.** `docs/deployment.md` has not been followed by Yosef yet. Its commands were written from the tools' documentation; the `gcloud`, `gh` and Supabase steps are unrun. |
| 12 | Every relative link in the README and the changed docs resolves. It has not been rendered on GitHub; the live address, screenshots and GIF are marked for the author. |

### Still open

1. **Push the branch** (`git push -u origin plan/005-deploy-mcp-pwa`) and watch the `ci` workflow turn green; fix what the first real run finds.
2. **One-time cloud setup**, from `docs/deployment.md`: the GCP project and billing, the budget alert, the service accounts and Workload Identity Federation, the Supabase project, the three secrets, the GitHub variables, then the seed and the handbook ingest against the new database.
3. **Close the plan**: merge into `main`, push, watch the deploy job, then do validations 6, 9 (device) and 10 on the live address, add the address, screenshots and GIF to the README, and set this plan to `done`.
4. Revoke the old Gemini key if that is not done yet.
5. Open the Team screen and the login screen in a browser at desktop width and at 375 px.
