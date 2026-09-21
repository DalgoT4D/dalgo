# Dalgo Monorepo

Monorepo for all Dalgo services. Service code lives in top-level directories; all Docker configuration is centralised under `docker/`.

```
dalgo/
├── backend/           Django/Ninja API + Celery workers
├── webapp/            Next.js frontend
├── prefect-proxy/     FastAPI proxy for Prefect orchestration
├── ai-llm-service/    FastAPI LLM service + Celery worker
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.backend.dev
│   ├── Dockerfile.webapp
│   ├── Dockerfile.prefect-proxy
│   ├── Dockerfile.prefect-proxy.dev
│   ├── Dockerfile.ai-llm-service
│   ├── docker-compose.yml        ← production
│   └── docker-compose.dev.yml    ← local dev
└── scripts/
    └── sync.sh        ← pull latest from individual repos (transition period)
```

---

## Docker setup

All compose commands run from the `docker/` directory.

### Production

```bash
cd docker/

# Copy and fill in env files for each service
cp ../backend/.env.template ../backend/.env        # edit with prod values
cp ../prefect-proxy/.env.template ../prefect-proxy/.env
cp ../webapp/.env.example ../webapp/.env
cp ../ai-llm-service/.env.example ../ai-llm-service/.env

# Build and start
docker compose build
docker compose up -d

# Single service
docker compose up -d backend
docker compose logs -f backend
```

### Local dev (hot reload)

```bash
cd docker/

# Same env setup as above (point DBHOST at your local Postgres)
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up -d

# Rebuild after a dependency change (pyproject.toml / uv.lock)
docker compose -f docker-compose.dev.yml build backend
docker compose -f docker-compose.dev.yml up -d --no-deps backend
```

**Notes:**
- Postgres runs on the host; backend containers reach it via `host.docker.internal`.
- Prefect server starts as a compose service in dev; in prod it is external.
- Next.js webapp is built as a standalone image in both modes (no hot reload — rebuild on code change).

---

## Updating service code (transition period)

Two scripts handle keeping the monorepo in sync with the individual repos while they're still active.

### `scripts/bootstrap.sh` — full re-import with complete git history

Rebuilds the monorepo from scratch: clones all four repos, rewrites their history into the correct subdirectory paths, merges them together, and commits the monorepo Docker infra on top.

```bash
# Rebuild locally
./scripts/bootstrap.sh

# Rebuild and force-push to origin/main in one step
./scripts/bootstrap.sh --push
```

After a `--push`, teammates sync with:
```bash
git fetch --force && git reset --hard origin/main
```

**When to use:** when you want the monorepo to fully reflect the latest commits (and history) from all individual repos — e.g. before archiving the individual repos, or after a batch of changes has landed across multiple services.

**Requires:** `brew install git-filter-repo`

---

### `scripts/sync.sh` — lightweight code sync (no history rewrite)

Pulls the latest code from each repo via rsync. Faster than bootstrap — caches clones in `.sync-cache/` so subsequent runs only fetch new commits. Does **not** touch `docker/`.

```bash
# Sync all services
./scripts/sync.sh

# Sync one service
./scripts/sync.sh backend

# Review what changed, then commit
git diff --stat
git add -A && git commit -m "sync: $(date +%Y-%m-%d)"
```

**When to use:** for routine day-to-day syncing between bootstraps — pulls latest code and `.env` files without rewriting history.

---

### Which to use when

| Scenario | Script |
|---|---|
| Catch up on a batch of changes, preserve per-commit history | `bootstrap.sh --push` |
| Quick pull of latest code between bootstraps | `sync.sh` |
| Final sync before archiving individual repos | `bootstrap.sh --push` |

### Source repo → monorepo directory mapping

| Source repo | Monorepo dir |
|---|---|
| `DalgoT4D/DDP_backend` | `backend/` |
| `DalgoT4D/webapp_v2` | `webapp/` |
| `DalgoT4D/prefect-proxy` | `prefect-proxy/` |
| `DalgoT4D/ai-llm-service` | `ai-llm-service/` |

---

## Adding / changing Docker config

All Dockerfiles and compose files live in `docker/`. Changes here do not affect the individual repos.

| File | Purpose |
|---|---|
| `Dockerfile.backend` | Production image for backend + celery workers |
| `Dockerfile.backend.dev` | Dev image (venv at `/opt/venv`, bind-mount code) |
| `Dockerfile.prefect-proxy` | Production prefect-proxy image |
| `Dockerfile.prefect-proxy.dev` | Dev image with hot reload |
| `Dockerfile.webapp` | Next.js standalone image (used in both prod and dev) |
| `Dockerfile.ai-llm-service` | Production + dev image for LLM service |
| `docker-compose.yml` | Full prod stack |
| `docker-compose.dev.yml` | Dev stack with bind mounts and Prefect server |
