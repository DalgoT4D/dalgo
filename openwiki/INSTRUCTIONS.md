---
type: Repository guide
title: Repository Wiki Instructions
description: What the Dalgo code wiki must cover, where the reasoning behind the code lives, and the ground rules a page may never contradict.
tags: [documentation, repository, code-wiki]
---

Dalgo is an open-source data platform for NGOs. It replaces Excel and Google Sheets workflows with
ingestion (Airbyte), transformation (dbt), orchestration (Prefect) and dashboards (native charts, plus Superset).
This is a monorepo with one top-level directory per service:
- **`backend/`**: Django + Django Ninja (`ddpui/`). The multi-tenant API, Celery workers, and the AI features in `ddpui/core/ai/`.
- **`webapp/`**: Next.js 15, React 19. Charts, dashboards, reports, the pipeline UI and settings.
- **`prefect-proxy/`**: FastAPI. The backend's only route to Prefect. It vendors `prefect_airbyte/`.
- **`ai-llm-service/`**: FastAPI. The LLM service the backend calls.
- **`docker/`** and **`.github/workflows/`**: images, compose files, CI and deploy.
- **`docs/`**: Docusaurus. User-facing docs for NGO staff. Link to it; do not restate it.
- **`harness/`**: specs, plans and engineering tooling. No application code.

The wiki is for engineers and coding agents about to change code, not for NGO staff.

## Pages wanted

- `quickstart`: first run for each service, the commands that matter, and which page to read for which task.
- One architecture page per area:
  - Backend layers: API, core, schemas, models. Request flow, permissions, `api_response`, multi-tenancy.
  - Ingestion: `ddpui/ddpairbyte/`, sources, connections, sync, and the Airbyte calls.
  - Transformation: dbt workspaces, `ddpui/core/dbt_automation/`, the UI transform and canvas.
  - Orchestration: `ddpui/ddpprefect/`, prefect-proxy, deployments, flow runs, webhooks, the job runner.
  - Warehouses: `WarehouseFactory`, Postgres and BigQuery clients.
  - Charts, dashboards and reports: backend and frontend together, including filters and sharing.
  - AI features: `ddpui/core/ai/` (Chat with Data, summaries) and `ai-llm-service/`.
  - Auth, orgs, roles and permissions: the seed fixtures, `has_permission`, the `x-dalgo-org` header.
  - Background work: Celery tasks, Redis (`TaskProgress`, `TaskLock`, caches).
  - Webapp: routes, feature folders, `lib/api.ts`, SWR hooks, Zustand stores.
  - Platform: Docker images, compose files, CI, staging and production deploys.
- Workflows:
  - an NGO's pipeline end to end: connect a source, sync, transform, run, and see a chart;
  - adding a backend endpoint (layer by layer) and a webapp feature that calls it;
  - writing and applying a Django migration;
  - deploying to staging and to production.
- Operations: env vars per service (from the `.env.template` files), local services, and external dependencies.
- Testing: backend pytest, webapp Jest and Playwright, prefect-proxy and ai-llm-service tests.

Keep pages practical: file paths, the order things happen in, and what breaks if a rule is ignored.

## Where the reasoning lives

The code says *what*. These say *why*. Read them before describing a design choice:
- `CLAUDE.md` at the root, plus `backend/.claude/CLAUDE.md`, `webapp/CLAUDE.md`, `backend/ddpui/core/ai/CLAUDE.md`
  and `prefect-proxy/prefect_airbyte/CLAUDE.md`. These hold the invariants contributors must keep.
- `webapp/.claude/rules/*.md` and `backend/.claude/skills/`: area-specific conventions.
- `harness/domain-map.md`: the product entity graph.
- `harness/features/<name>/<version>/spec.md` and `plan.md`: why each feature was built and how.
  `tasks.md` shows how much of a plan is done. Report a partly built plan as partly built.
- The git log: PR titles and bodies explain most changes.

Link to a spec or plan rather than restating it.

## Ground rules a page must never contradict

- Backend dependency direction is API → core → models, one way only.
- Every domain object has an `org` foreign key and every query filters by it. The org comes from `request.orguser.org`, never from the client.
- Every endpoint has `@has_permission([...])` and returns through `api_response(...)`.
- Schemas with `extra="forbid"` validate payloads before calls to dbt, Airbyte or Prefect.
- The backend reaches Prefect only through prefect-proxy. Prefect reports back to `POST /webhooks/v1/notification/`, which queues a Celery task.
- Warehouses are reached through `WarehouseFactory.get_warehouse_client(...)`.
- The webapp calls the API only through `lib/api.ts`. Cookies are HTTP-only, and the frontend never handles tokens.
- Roles and permissions come from `backend/seed/001_roles.json`, `002_permissions.json` and `003_role_permissions.json`.

## Facts that earlier pages got wrong

Check these against the code before restating them:
- **`fetch` in the webapp.** Almost all traffic goes through `lib/api.ts`, but not all. `components/dashboard/chart-element-view.tsx`,
  `components/dashboard/dashboard-filter-widgets.tsx` (public-mode map and region data) and `components/connectors/google-picker.ts`
  call `fetch` directly. Never say "never".
- **Where dbt is pinned.** There is no `prefect-proxy/docker/dbt-*` directory. dbt-core, dbt-postgres and dbt-bigquery are pinned in
  `prefect-proxy/pyproject.toml` and `backend/pyproject.toml`. The dbt section of `backend/README.md` is stale.
- **Alert list `page_size`.** It is not rejected outside 1–100. An out-of-range value silently falls back to 10 (`api/alert_api.py`).

## Out of scope

Prototype builds under `harness/prototypes/`, seed data and anything under `.claude/agent-memory/` are not
architecture. Never describe their contents, and never quote values from any env file.
