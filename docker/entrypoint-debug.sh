#!/bin/sh
set -e

ODOO_BIN="$(command -v odoo || true)"
if [ -z "$ODOO_BIN" ]; then
    echo "odoo executable not found in PATH" >&2
    exit 1
fi

DB_HOST="${HOST:-db}"
DB_PORT="${PORT:-5432}"
DB_USER="${USER:-odoo}"
DB_PASSWORD="${PASSWORD:-odoo}"

set -- --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASSWORD" \
    --dev=all --proxy-mode "$@"

if [ -f /etc/odoo/odoo.conf ]; then
    set -- -c /etc/odoo/odoo.conf "$@"
fi

if python3 -c "import debugpy" 2>/dev/null; then
    exec python3 -m debugpy --listen 0.0.0.0:5678 "$ODOO_BIN" "$@"
fi

echo "debugpy is not installed, starting Odoo without the debugger" >&2
exec "$ODOO_BIN" "$@"
