#!/usr/bin/env bash
set -euo pipefail

# Verified restore of a compressed PolicyNest PostgreSQL backup followed by Alembic check.
# Usage:
#   ./scripts/db_restore.sh ./backups/policynest_20261112T120000Z.dump

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <path-to-dump-file>" >&2
  exit 1
fi

DUMP_FILE="$1"
POSTGRES_USER="${POSTGRES_USER:-policynest}"
POSTGRES_DB="${POSTGRES_DB:-policynest}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

if [ ! -f "$DUMP_FILE" ]; then
  echo "Backup file not found: $DUMP_FILE" >&2
  exit 1
fi

if [ -f "${DUMP_FILE}.sha256" ] && command -v sha256sum >/dev/null 2>&1; then
  echo "Verifying SHA-256 checksum..."
  (cd "$(dirname "$DUMP_FILE")" && sha256sum -c "$(basename "${DUMP_FILE}.sha256")")
fi

echo "Restoring ${DUMP_FILE} into PostgreSQL database ${POSTGRES_DB}..."
docker compose -f "$COMPOSE_FILE" exec -T db pg_restore \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl < "$DUMP_FILE"

echo "Checking Alembic migration revision..."
docker compose -f "$COMPOSE_FILE" exec -T backend alembic current

echo "Restore complete."
