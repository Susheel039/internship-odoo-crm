#!/usr/bin/env bash
set -euo pipefail

for _ in {1..60}; do
  if curl -fsS http://localhost:8069 >/dev/null 2>&1; then
    echo "Odoo is responding on http://localhost:8069"
    exit 0
  fi
  sleep 2
done

echo "Timed out while waiting for Odoo to respond on http://localhost:8069"
exit 1
