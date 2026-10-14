# Dalgo — Claude Code Guide

Dalgo is an open-source data platform for NGOs. It replaces manual Excel/Google Sheets
workflows with automated data ingestion (Airbyte), transformation (dbt), orchestration
(Prefect), and visualization (Superset + custom dashboards).

## Repository layout

Monorepo. Each service is a top-level directory. The AI/engineering harness (specs,
skills, commands, agents, scripts) lives under `harness/`.

| Path | Tech | CLAUDE.md |
|------|------|-----------|
| `backend/` | Django + Django Ninja | `backend/.claude/CLAUDE.md` |
| `webapp/` | Next.js 15, React 19, Shadcn UI | `webapp/CLAUDE.md` |
| `prefect-proxy/` | FastAPI | — |
| `ai-llm-service/` | FastAPI | — |
| `docs/` | Docusaurus (user-facing docs) | — |
| `harness/` | specs, scripts, prototypes (no application code) | this file |

To work on backend or frontend code, `cd` into the service directory and follow its own
CLAUDE.md for run/test/lint commands and conventions.

## Knowledge Base

Deep reference — always accessible without loading a skill:

| File | Contents |
|------|----------|
| `harness/domain-map.md` | Product entity graph — source of truth for blast radius analysis |
| `openwiki/` (start at `openwiki/quickstart.md`) | Generated code wiki: architecture per area, workflows, operations, testing — each claim pinned to source lines. Open the page for an unfamiliar area; don't preload it. In Claude Code, `openwiki_search` / `openwiki_read` (`.mcp.json`) return just the section. Source wins when they disagree. |

The wiki is generated, never hand-edited. Run `make wiki-update` before opening a PR that changes an
endpoint, model, flow or service boundary; fix a wrong page with `make wiki-fix MSG="..."` and steer
coverage through `openwiki/INSTRUCTIONS.md`. The scheduled `openwiki-update` workflow opens a PR on
`openwiki/update` daily (needs the `ANTHROPIC_API_KEY` repo secret); it never merges on its own.

---

## Development Workflow

### Fast track — prototype → validate → promote

```
/product/prototype "feature idea"    → harness/prototypes/{name}/brief.md + working build
```

Skip the full pipeline. Get something in front of NGO partners quickly.
PM artifacts live in `harness/prototypes/`, separate from `harness/features/`.

---

### Standard track

#### 1. Spec

```
/product/write-spec "feature idea"        → harness/features/{name}/spec.md
/product/write-spec harness/features/{name}       → harness/features/{name}/v1/spec.md
```

#### 2. Design *(UI features only)*

```
/design/design-handoff harness/features/{name}/v1/spec.md
```

Gets designer direction, generates Figma frames, runs design review, writes `design.md`
+ `FIGMA.md` + `## Design` section back into the spec. Engineering starts after this.
Skip for backend-only features.

#### 3. Plan

```
/product/write-spec "feature idea"          → harness/features/{name}/spec.md
/product/write-spec harness/features/{name}         → harness/features/{name}/v1/spec.md (scope a version)
/engineering/plan-feature harness/features/{name}/v1/spec.md → harness/features/{name}/v1/plan.md
/engineering/plan-enhancement harness/features/{name}/v1/spec.md  → harness/features/{name}/v1.1/plan.md (minor bump)
/engineering/plan-enhancement "paragraph describing the enhancement" → asks which feature, then plans a v{N}.{M+1}
/engineering/execute-plan harness/features/{name}/v1/plan.md → implements the code
/engineering/validate-spec harness/features/{name}/v1/spec.md → validate implementation against spec
/engineering/review-pr <PR#>                → structured code review
/engineering/debug-issue <Sentry URL>       → diagnose production bugs
```

#### 4. Build

```
/engineering/execute-plan  harness/features/{name}/v1/plan.md   → implements the code
```

Execution follows the **executing-feature-plans** skill: branch first, then build the
feature in one session with red-green-refactor (one test at a time), reading each repo's
CLAUDE.md before working in it. Progress is tracked in
`harness/features/{name}/{version}/tasks.md`; re-run to resume after an interruption.

### Other commands

```
/engineering/validate-spec harness/features/{name}/v1/spec.md   → validates implementation
/engineering/review-pr     <PR# or URL>                 → structured code review
/engineering/debug-issue   <Sentry URL or description>  → diagnose production bugs
```

---

## Agents

| Agent | What it does | Spawned by | Model |
|-------|-------------|------------|-------|
| `debugger` | Diagnoses bugs from Sentry URL, stack trace, or description | direct | Opus |
| `senior-product-manager` | Feature strategy, specs, prioritization | direct | Sonnet |
| `ux-design-expert` | UI/UX decisions, design system | direct | Sonnet |
| `ngo-data-platform-consultant` | Priya lens — NGO user perspective | direct | Sonnet |

---

## Skills (evaluation lenses — available at any stage)

- **design-review** — UX + NGO user lens on any UI component or screen
- **backend-architecture** — patterns and templates for Django/Ninja layer architecture
- **frontend-architecture** — patterns for Next.js components, hooks, and state
- **documentation** — generate, update, or review Dalgo user-facing docs

---

## Feature Artifacts

Every feature lives in `harness/features/{name}/{version}/`:

| File | Produced by | Purpose |
|------|-------------|---------|
| `spec.md` | `/product/write-spec` | What to build and why |
| `design.md` | `/design/design-handoff` | UX decisions, terminology, interaction states |
| `FIGMA.md` | `/design/design-handoff` | Figma frame references, component specs |
| `research.md` | `/engineering/plan-feature` | Codebase and external findings |
| `plan.md` | `/engineering/plan-feature` | Implementation plan with milestones |
| `tasks.md` | `/engineering/execute-plan` | Milestone task checklist — resume checkpoint |

---

## Key Constraints

- Users are non-technical NGO staff (program managers, data coordinators, field staff)
- ~20 partner NGOs, ~₹2L/year budgets, small engineering team
- Users on slow internet and old devices — performance and simplicity matter
- Open source (AGPL-3.0)

<!-- OPENWIKI:START -->

## OpenWiki

@AGENTS.md

<!-- OPENWIKI:END -->
