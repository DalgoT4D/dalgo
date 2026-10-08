#!/usr/bin/env bash
# Pull the latest commits from each individual GitHub repo and bring them into
# the monorepo with full commit history preserved.
#
# On each run the script:
#   1. Fetches the upstream repo (cached in .sync-cache/)
#   2. Counts new commits since the last sync
#   3. Creates a filter-repo'd clone (prefix = service/)
#   4. Cherry-picks the new commits onto the monorepo main branch
#   5. Records the upstream HEAD in .sync-state
#
# Prerequisites: brew install git-filter-repo
#
# Usage:
#   ./scripts/sync.sh                          # sync all services
#   ./scripts/sync.sh backend webapp           # sync specific services

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CACHE_DIR="$ROOT/.sync-cache"
STATE_FILE="$ROOT/.sync-state"

mkdir -p "$CACHE_DIR"

if ! command -v git-filter-repo &>/dev/null; then
  echo "ERROR: git-filter-repo not found. Install with: brew install git-filter-repo" >&2
  exit 1
fi

sync_service() {
  local dest_name="$1" remote_url="$2"
  local cache="$CACHE_DIR/$dest_name"

  echo ""
  echo "==> $dest_name"

  # 1. Update cache
  if [ -d "$cache/.git" ]; then
    git -C "$cache" fetch --quiet origin
    git -C "$cache" reset --quiet --hard origin/HEAD
  else
    git clone --quiet "$remote_url" "$cache"
  fi

  local new_head
  new_head="$(git -C "$cache" rev-parse HEAD)"

  # 2. Check for prior sync state
  local last_hash
  last_hash="$(grep "^$dest_name " "$STATE_FILE" 2>/dev/null | awk '{print $2}')"

  if [ -z "$last_hash" ]; then
    echo "    no prior sync state — run bootstrap.sh first" >&2
    return 1
  fi

  if [ "$new_head" = "$last_hash" ]; then
    echo "    already up to date @ ${new_head:0:12}"
    return
  fi

  # 3. Count new upstream commits
  local new_count
  new_count="$(git -C "$cache" rev-list --count "${last_hash}..HEAD")"
  echo "    $new_count new commit(s) to import"

  # 4. Build a filter-repo'd clone (all history prefixed with dest_name/)
  local filtered_dir
  filtered_dir="$(mktemp -d)"
  git clone --no-local --quiet "$cache" "$filtered_dir"
  git -C "$filtered_dir" filter-repo --to-subdirectory-filter "${dest_name}/" --quiet

  # 5. Fetch filtered objects into the monorepo; FETCH_HEAD points to the tip
  local remote_name="_sync_${dest_name}_$$"
  git -C "$ROOT" remote add "$remote_name" "$filtered_dir"
  git -C "$ROOT" fetch --quiet "$remote_name"
  git -C "$ROOT" remote remove "$remote_name"
  rm -rf "$filtered_dir"

  # 6. Cherry-pick new commits oldest-first
  local commits
  commits="$(git -C "$ROOT" log FETCH_HEAD --reverse --oneline -n "$new_count" | awk '{print $1}')"

  local picked=0
  while IFS= read -r hash; do
    if ! git -C "$ROOT" cherry-pick "$hash"; then
      echo ""
      echo "    ERROR: cherry-pick $hash failed. Resolve conflicts then re-run." >&2
      git -C "$ROOT" cherry-pick --abort 2>/dev/null || true
      return 1
    fi
    picked=$((picked + 1))
  done <<< "$commits"

  # 7. Update state
  grep -v "^$dest_name " "$STATE_FILE" 2>/dev/null > "$STATE_FILE.tmp" || true
  echo "$dest_name $new_head $remote_url" >> "$STATE_FILE.tmp"
  mv "$STATE_FILE.tmp" "$STATE_FILE"

  echo "    imported $picked commit(s) @ ${new_head:0:12}"
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
echo "==> Done. Synced state:"
awk '{printf "    %-20s %s\n", $1, $2}' "$STATE_FILE" 2>/dev/null
