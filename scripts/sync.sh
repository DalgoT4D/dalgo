#!/usr/bin/env bash
# Pull the latest code from each individual GitHub repo and sync it into the
# monorepo. Run this whenever changes land in the individual repos during the
# transition period.
#
# On each run the script:
#   1. Shallow-clones the repo (or fetches if already cached in .sync-cache/)
#   2. rsyncs everything except build artefacts into the service directory
#   3. Records the upstream HEAD so you can see what was last synced
#
# Nothing in docker/ is touched — Dockerfiles and compose files are monorepo-owned.
#
# Usage:
#   ./scripts/sync.sh                          # sync all services
#   ./scripts/sync.sh backend webapp           # sync specific services
#
# After running:
#   git diff --stat
#   git add -A && git commit -m "sync: $(date +%Y-%m-%d)"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CACHE_DIR="$ROOT/.sync-cache"
STATE_FILE="$ROOT/.sync-state"

mkdir -p "$CACHE_DIR"

EXCLUDES=(
  --exclude='.git'
  --exclude='.venv'
  --exclude='node_modules'
  --exclude='__pycache__'
  --exclude='*.pyc'
  --exclude='.next'
  --exclude='celerybeat-schedule.db'
  --exclude='*.log'
  --exclude='.mypy_cache'
  --exclude='.pytest_cache'
  --exclude='*.egg-info'
)

sync_service() {
  local dest_name="$1" remote_url="$2"
  local cache="$CACHE_DIR/$dest_name"
  local dest="$ROOT/$dest_name"

  echo ""
  echo "==> $dest_name"

  if [ -d "$cache/.git" ]; then
    git -C "$cache" fetch --quiet origin
    git -C "$cache" reset --quiet --hard origin/HEAD
  else
    git clone --quiet "$remote_url" "$cache"
  fi

  local head
  head="$(git -C "$cache" rev-parse HEAD)"

  mkdir -p "$dest"
  rsync -a "${EXCLUDES[@]}" "$cache/" "$dest/"

  # Record last synced commit
  grep -v "^$dest_name " "$STATE_FILE" 2>/dev/null > "$STATE_FILE.tmp" || true
  echo "$dest_name $head $remote_url" >> "$STATE_FILE.tmp"
  mv "$STATE_FILE.tmp" "$STATE_FILE"

  echo "    synced @ ${head:0:12}"
}

if [ $# -eq 0 ]; then
  TARGETS=(backend webapp prefect-proxy ai-llm-service)
else
  TARGETS=("$@")
fi

for target in "${TARGETS[@]}"; do
  case "$target" in
    backend)        sync_service backend        https://github.com/DalgoT4D/DDP_backend.git ;;
    webapp)         sync_service webapp         https://github.com/DalgoT4D/webapp_v2.git ;;
    prefect-proxy)  sync_service prefect-proxy  https://github.com/DalgoT4D/prefect-proxy.git ;;
    ai-llm-service) sync_service ai-llm-service https://github.com/DalgoT4D/ai-llm-service.git ;;
    *) echo "Unknown service: $target" >&2; exit 1 ;;
  esac
done

echo ""
echo "==> Done. Last synced state:"
cat "$STATE_FILE" 2>/dev/null | awk '{printf "    %-20s %s\n", $1, $2}'
echo ""
echo "    Review:  git diff --stat"
echo "    Commit:  git add -A && git commit -m \"sync: \$(date +%Y-%m-%d)\""
