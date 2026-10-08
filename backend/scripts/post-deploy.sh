#!/usr/bin/env bash
# Post-deploy steps: migrate, load seeds, system user, refresh role cache.
# For a one-off org + admin user, run `python manage.py createorganduser <org> <email>`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "==> migrate"
python manage.py migrate

echo "==> loaddata seeds"
python manage.py loaddata seed/*.json

echo "==> create-system-orguser"
python manage.py create-system-orguser

echo "==> clear redis permission key"
python manage.py clear_role_permissions

echo "Done."
