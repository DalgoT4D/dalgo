#!/usr/bin/env bash
# Install the Dalgo monorepo git hooks. Run once after cloning.
#
# Usage:  ./scripts/install-hooks.sh

set -euo pipefail

REPO=$(git rev-parse --show-toplevel)
HOOKS_SRC="$REPO/scripts/hooks"
HOOKS_DST="$REPO/.git/hooks"

for hook in "$HOOKS_SRC"/*; do
  name=$(basename "$hook")
  chmod +x "$hook"
  ln -sf "$hook" "$HOOKS_DST/$name"
  echo "✓ installed $name"
done

echo ""
echo "Git hooks installed. They will run automatically on each commit."
