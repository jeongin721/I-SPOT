#!/usr/bin/env bash
# Per-boot startup: ensure PostgreSQL is running and the app database exists.
# Idempotent: safe to run on every environment start.
set -euo pipefail

PG_VERSION="$(ls /etc/postgresql 2>/dev/null | sort -V | tail -1 || true)"
PG_VERSION="${PG_VERSION:-16}"

echo "==> Starting PostgreSQL cluster ${PG_VERSION}/main"
sudo pg_ctlcluster "${PG_VERSION}" main start 2>/dev/null || true

# Wait for the server to accept connections.
for _ in $(seq 1 20); do
  if sudo -u postgres pg_isready -q; then break; fi
  sleep 1
done

echo "==> Ensuring role and database 'ispot' exist"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='ispot') THEN
    CREATE ROLE ispot LOGIN PASSWORD 'ispot';
  END IF;
END $$;
SQL
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='ispot'" \
  | grep -q 1 || sudo -u postgres createdb -O ispot ispot

echo "==> start.sh complete (PostgreSQL ready on 127.0.0.1:5432)"
