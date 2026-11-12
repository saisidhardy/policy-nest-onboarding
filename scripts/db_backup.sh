#!/usr/bin/env bash
set -euo pipefail

# Compressed PostgreSQL backup with SHA-256 checksum & retention pruning.
# Usage:
#   ./scripts/db_backup.sh [output_dir] [retention_days]

OUT_DIR="${1:-./backups}"
RETENTION_DAYS="${2:-30}"
POSTGRES_USER="${POSTGRES_USER:-policynest}"
POSTGRES_DB="${POSTGRES_DB:-policynest}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="${OUT_DIR}/policynest_${STAMP}.dump"

echo "Creating compressed backup: ${DUMP_FILE}"
docker compose -f "$COMPOSE_FILE" exec -T db pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom \
  --no-owner \
  --no-acl > "$DUMP_FILE"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$DUMP_FILE" > "${DUMP_FILE}.sha256"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$DUMP_FILE" > "${DUMP_FILE}.sha256"
fi

echo "Verifying archive integrity via pg_restore --list..."
docker compose -f "$COMPOSE_FILE" exec -T db pg_restore --list < "$DUMP_FILE" >/dev/null

echo "Pruning backups older than ${RETENTION_DAYS} days..."
find "$OUT_DIR" -type f \( -name "policynest_*.dump" -o -name "policynest_*.dump.sha256" \) -mtime +"$RETENTION_DAYS" -delete

echo "Backup complete: ${DUMP_FILE}"
