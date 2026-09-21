#!/usr/bin/env bash
# Rebuild the monorepo from scratch by importing the full git history from each
# individual repo, then committing the monorepo-specific Docker infra on top.
#
# Safe to re-run: creates a fresh orphan branch, replaces main, then force-pushes.
# Team members should run `git fetch --force && git reset --hard origin/main` after.
#
# Prerequisites:
#   brew install git-filter-repo
#
# Usage:
#   ./scripts/bootstrap.sh            # import all services
#   ./scripts/bootstrap.sh --push     # also force-push to origin/main after rebuilding

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PUSH=false
[[ "${1:-}" == "--push" ]] && PUSH=true

# ── 1. Verify prerequisites ────────────────────────────────────────────────
if ! command -v git-filter-repo &>/dev/null; then
  echo "ERROR: git-filter-repo not found. Install with: brew install git-filter-repo" >&2
  exit 1
fi

if [[ -n "$(git -C "$ROOT" status --porcelain)" ]]; then
  echo "ERROR: Working tree has uncommitted changes. Commit or stash them first." >&2
  exit 1
fi

# ── 2. Save monorepo-specific files ────────────────────────────────────────
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "==> Saving monorepo-specific files to $TMP"
cp -r "$ROOT/docker"    "$TMP/"
cp -r "$ROOT/scripts"   "$TMP/"
cp    "$ROOT/README.md" "$TMP/"
cp    "$ROOT/.gitignore" "$TMP/"

# ── 3. Clone and filter each repo ──────────────────────────────────────────
remote_for() {
  case "$1" in
    backend)        echo "https://github.com/DalgoT4D/DDP_backend.git" ;;
    webapp)         echo "https://github.com/DalgoT4D/webapp_v2.git" ;;
    prefect-proxy)  echo "https://github.com/DalgoT4D/prefect-proxy.git" ;;
    ai-llm-service) echo "https://github.com/DalgoT4D/ai-llm-service.git" ;;
  esac
}

for svc in backend webapp prefect-proxy ai-llm-service; do
  remote="$(remote_for "$svc")"
  clone_dir="$TMP/${svc}-clone"
  echo ""
  echo "==> Cloning $svc from $remote"
  git clone --quiet "$remote" "$clone_dir"
  echo "    Filtering history to $svc/ subdirectory"
  git -C "$clone_dir" filter-repo --to-subdirectory-filter "${svc}/" --quiet
done

# ── 4. Switch to a fresh orphan branch ─────────────────────────────────────
echo ""
echo "==> Creating fresh orphan branch"
ORPHAN="import-$(date +%s)"
git -C "$ROOT" checkout --orphan "$ORPHAN" --quiet
git -C "$ROOT" rm -rf . --quiet 2>/dev/null || true

# ── 5. Merge all filtered repos in ─────────────────────────────────────────
for svc in backend webapp prefect-proxy ai-llm-service; do
  remote="$(remote_for "$svc")"
  clone_dir="$TMP/${svc}-clone"
  echo ""
  echo "==> Merging $svc history"
  git -C "$ROOT" remote add "_import_${svc}" "$clone_dir"
  git -C "$ROOT" fetch --quiet "_import_${svc}"
  git -C "$ROOT" merge --allow-unrelated-histories "_import_${svc}/main" \
      --quiet -m "import: $(basename "$remote" .git) full history as ${svc}/"
  git -C "$ROOT" remote remove "_import_${svc}"
done

# ── 6. Add monorepo-specific files ─────────────────────────────────────────
echo ""
echo "==> Adding monorepo Docker infra and tooling"
cp -r "$TMP/docker"    "$ROOT/"
cp -r "$TMP/scripts"   "$ROOT/"
cp    "$TMP/README.md" "$ROOT/"
cp    "$TMP/.gitignore" "$ROOT/"
git -C "$ROOT" add docker/ scripts/ README.md .gitignore
git -C "$ROOT" commit --quiet -m "add: monorepo Docker infra, sync tooling, and docs"

# ── 7. Replace main ────────────────────────────────────────────────────────
echo ""
echo "==> Replacing main branch"
git -C "$ROOT" branch -D main 2>/dev/null || true
git -C "$ROOT" branch -m "$ORPHAN" main

TOTAL="$(git -C "$ROOT" log --oneline | wc -l | tr -d ' ')"
echo ""
echo "==> Done. $TOTAL commits in monorepo."
echo "    git log --oneline -10     to verify"
echo "    git log --oneline -- backend/   to check per-service history"

# ── 8. Optionally push ─────────────────────────────────────────────────────
if $PUSH; then
  echo ""
  echo "==> Force-pushing to origin/main"
  git -C "$ROOT" push --force origin main
  echo "    Team: git fetch --force && git reset --hard origin/main"
fi
