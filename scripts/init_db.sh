#!/usr/bin/env bash
set -euo pipefail

# Intended for local dev bootstrapping of the default database.
# This script is safe to run after the PostgreSQL service is healthy.

if ! docker ps | grep -q internship_postgres; then
  echo "PostgreSQL container is not running. Start the stack first: docker compose up -d"
  exit 1
fi

# Create a default Odoo database if the container is already running.
# The actual database can be created from the web UI in development.

echo "Odoo database initialization is handled through the Odoo web UI on http://localhost:8069"
echo "Use admin / admin for the local development login."
