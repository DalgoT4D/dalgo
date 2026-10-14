---
type: testing guide
title: Webapp testing (Jest and Playwright)
description: How the Next.js webapp is tested. Jest and React Testing Library unit and component tests sit in colocated __tests__ folders with a global API mock. Playwright e2e specs need admin credentials from the environment. The page also covers the no-faked-tests rule and the CI workflow.
tags: [webapp, testing, jest, playwright, ci]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-14T16:46:05.062Z
sources:
  - id: openwiki-source-e624eff1062702fe071f6a9d
    resource: repo://.github/workflows/webapp.yml
  - id: openwiki-source-a186e524ce89044b158c7f8f
    resource: repo://webapp/.claude/rules/testing.md
  - id: openwiki-source-e379b0c7552965f6046e8178
    resource: repo://webapp/components/pipeline/orchestrate/__tests__/pipeline.integration.test.tsx
  - id: openwiki-source-85dd3bf8f63b4d2a4d01210a
    resource: repo://webapp/e2e/helpers/auth.ts
  - id: openwiki-source-40b92c8df87c14223f76a017
    resource: repo://webapp/e2e/login.spec.ts
  - id: openwiki-source-08b34411293e0410653d3519
    resource: repo://webapp/jest.config.ts
  - id: openwiki-source-2ebd39b577bf22bbf3c58cc9
    resource: repo://webapp/jest.setup.ts
  - id: openwiki-source-e61ef6bd61de27d84e51fc31
    resource: repo://webapp/lib/__tests__/feature-route-coverage.test.ts
  - id: openwiki-source-d37576b99068aa216271b039
    resource: repo://webapp/package.json
  - id: openwiki-source-6aab03665f0490dde6a32b29
    resource: repo://webapp/playwright.config.ts
  - id: openwiki-source-29956494fe39a17081adba6d
    resource: repo://webapp/test-utils/api.ts
  - id: openwiki-source-3d95313e38cf14a1ae78238a
    resource: repo://webapp/test-utils/render.tsx
generated: { by: "openwiki/0.7.2", at: "2026-10-14T16:46:05.062Z" }
---

# Webapp testing (Jest and Playwright)

The webapp (see [Webapp architecture](../architecture/webapp.md)) has two test layers:

- **Jest + React Testing Library** for unit, hook, and component tests. These make up almost all coverage.
- **Playwright** for a small set of browser e2e specs.

Both live under `webapp/`. Run them from that directory. The workflow for adding a feature, including its tests, is in [Add endpoint and webapp feature](../workflows/add-endpoint-and-webapp-feature.md).

## Rules that govern all tests

These come from `webapp/.claude/rules/testing.md`:

- **Never fake a test to make it pass.** Do not change expected values or assertions just to turn a test green. A failing test signals a bug or a misunderstanding. After about 4–5 failed attempts, stop and explain why rather than keep tweaking.
- Assertions must reflect real expected behaviour, not whatever the code currently outputs.
- If code cannot be tested or covered, state the specific reason and leave the decision to a human.
- If the cause is unclear, ask rather than apply a blind fix.

## Jest layout

### Configuration (`webapp/jest.config.ts`)

- Built with `next/jest`, `testEnvironment: 'jsdom'`, and `setupFilesAfterEnv` pointing at `jest.setup.ts`. The `@/` alias is mapped to the webapp root.
- There is no MSW and no separate integration config. Everything runs on Jest mocks through the global API mock.
- `testMatch` is an explicit allow-list of `__tests__` folders under:
  - `components/`
  - `app/`
  - `hooks/`
  - `lib/`
  - `__tests__/lib/` at the root
- `e2e/`, `.next/`, and `node_modules/` are ignored, so Playwright specs never run under Jest.
- Coverage is collected from `components`, `app`, `lib`, `hooks`, and `stores`. The global threshold is only 1% for branches, functions, lines, and statements, so coverage gating is nominal.

**Gotcha:** because `testMatch` is an allow-list, a test placed in a root `__tests__/` subfolder other than `__tests__/lib/` is silently not run. `webapp/__tests__/app/charts/chart-navigation.test.tsx` is in this position. It sits outside every pattern, whereas the copy under `app/charts/[id]/__tests__/` does run. Put new tests next to the code they cover.

### File conventions

- **Colocation:** tests live in a `__tests__/` directory inside the component, hook, or lib directory they cover, for example `components/charts/__tests__/ChartBuilder.test.tsx`. Integration-style tests also go in the component's own `__tests__/`, named `*.integration.test.tsx` (for example `notifications.integration.test.tsx`, `pipeline.integration.test.tsx`). The rules file says not to create separate `integration/` or `components/` test folders.
- **Mock-data factories:** a `*-mock-data.ts` file in the same `__tests__/` folder exports fixtures and factory functions such as `createMockPipeline()`. Examples are `pipeline-mock-data.ts`, `connections-mock-data.ts`, and `notification-mock-data.ts`. The rules file cites `components/pipeline/__tests__/pipeline-mock-data.ts`, but the pipeline one now lives in `components/pipeline/orchestrate/__tests__/`.
- **Imports:** siblings use relative paths (`../pipeline-list`), mock data uses `./*-mock-data`, and shared helpers use the `@/test-utils/...` alias.

### Global setup (`webapp/jest.setup.ts`)

Loaded for every test file. It does the following:

- Loads `@testing-library/jest-dom` matchers.
- Sets `NEXT_PUBLIC_DOCS_BASE_URL` to `https://docs.dalgo.org`. The `.env` file is gitignored and never reaches CI, so code such as `buildDocsUrl` would otherwise fail there.
- Polyfills `structuredClone` and `TextEncoder`/`TextDecoder` (the latter needed by jspdf).
- **Globally mocks `@/lib/api`.** `apiGet`, `apiPost`, `apiPut`, `apiPatch`, and `apiDelete` are bare `jest.fn()`s. No test performs a real network call unless it opts out. Each test sets its own responses.
- Stubs browser APIs missing from jsdom: `matchMedia`, `ResizeObserver`, `IntersectionObserver`, and the pointer-capture and `scrollIntoView` methods that Radix UI Select needs.

### Shared helpers (`webapp/test-utils`)

- `api.ts` exports typed references `mockApiGet`, `mockApiPost`, `mockApiPut`, and `mockApiDelete`, plus `resetApiMocks()`, which calls `jest.clearAllMocks()`. There is no `mockApiPatch` helper. For PATCH, import `apiPatch` from `@/lib/api` and cast it.
- `render.tsx` exports two SWR wrappers:
  - `TestWrapper` gives each render a fresh cache (`provider: () => new Map()`), with `dedupingInterval: 0` and `refreshInterval: 0`. This isolates tests from each other and disables polling.
  - `PollingTestWrapper` also resets the cache and dedupe interval but leaves `refreshInterval` unset. Use it with `jest.useFakeTimers()` to test components that poll.

### Typical test shape

Wrap the component in `TestWrapper`, then `mockApiGet.mockResolvedValue(...)` for the endpoints its hooks call, then render and drive it with `userEvent`. The consolidated integration tests exercise the real chain of component, hook, SWR, and mocked API module. `pipeline.integration.test.tsx` is a good reference. Other things such as `next/navigation`, `sonner` toasts, and confirmation dialogs are mocked per file.

### Permissions in tests

Mock `useRbac` from `@/lib/rbac`, and spread `jest.requireActual('@/lib/rbac')` so the `ROLES` and `PERMISSIONS` constants and the `RoleGuard`/`PermissionGuard` components keep working. Do not mock `useAuthStore` directly for permission checks. `lib/__tests__/rbac.test.tsx` covers the RBAC module itself.

### What is tested where

- **Unit:** pure utilities and hooks in isolation (`lib/__tests__`, `hooks/__tests__`, `hooks/api/__tests__`). Mock the API through the global mock or SWR.
- **Component:** RTL, user-centric (behaviour and interactions). Heavy dependencies such as chart libraries are mocked.
- **Guard tests that walk the filesystem:** `lib/__tests__/feature-route-coverage.test.ts` reads `app/settings/*/page.tsx` on disk and asserts that each route maps to a feature in `featureForPathname`. A new settings page without an analytics mapping fails the test instead of going unmeasured.

## Playwright e2e

- Config is `webapp/playwright.config.ts` and specs are in `webapp/e2e/`. Currently that is `login.spec.ts` plus `helpers/auth.ts`. Playwright is not wired into npm scripts or CI. Run it manually with `npx playwright test`.
- `.env` is loaded with `dotenv`. The default `baseURL` is `http://localhost:3001`, overridable with `E2E_BASE_URL`.
- When `E2E_BASE_URL` is unset, Playwright starts `npm run dev` itself (port 3001) and reuses an already-running server outside CI. When it is set (staging or production), no server is started.
- It runs `chromium`, `firefox`, and `webkit` projects, fully parallel. On CI (`CI` set) it uses `forbidOnly`, 2 retries, and 1 worker. Traces are collected on first retry and the reporter is HTML.

### Auth environment

Authenticated tests need `E2E_ADMIN_EMAIL` and `E2E_ADMIN_PASSWORD` in the environment, or in `webapp/.env`. They are read in two places:

- `login.spec.ts` skips the successful-login test via `test.skip` when either is missing. The unauthenticated checks still run: page elements, empty-field validation, password toggle, forgot-password link, and invalid credentials.
- `e2e/helpers/auth.ts` exports `requireCredentials()`, which throws if either is missing, and `login(page)`, which signs in through the UI and waits for `/impact`. Use it in specs that need an authenticated session.

## CI (`.github/workflows/webapp.yml`)

The "Webapp CI" workflow triggers on pushes and PRs to `main` that touch `webapp/**` or `docker/Dockerfile.webapp`. It also supports manual dispatch. In `webapp/` on Node 20, it runs in order:

1. `npm ci`
2. `npm run format:check` (Prettier)
3. `npm run lint` (`next lint`)
4. `npm run test:coverage` (Jest with coverage)
5. Upload to Codecov with the `webapp` flag
6. On pull requests only, a Docker build of `docker/Dockerfile.webapp` that verifies the image builds without pushing

Playwright is not run in CI. A husky pre-commit hook runs `npm run format:write`, so formatting is normally fixed before the Prettier check.

Local scripts: `npm test`, `npm run test:watch`, `npm run test:coverage`, and `npm run test:ci` (`jest --ci --coverage --watchAll=false`).
