# Database Backup, Restore & Migration Runbook

## 1. Automated & Ad-Hoc PostgreSQL Backups

PolicyNest stores all application records, RBAC roles, append-only `audit_logs`, Fernet-encrypted `system_configs`, verification records, and rule executions in PostgreSQL 16.

### Linux / macOS (`scripts/db_backup.sh`)
```bash
./scripts/db_backup.sh ./backups 30
```
- Runs `pg_dump --format=custom --no-owner --no-acl` against the `db` Compose service.
- Generates a `.sha256` checksum sidecar file.
- Validates the dump archive readability via `pg_restore --list`.
- Prunes `.dump` and `.sha256` files older than `30` days (configurable second argument).

### Windows PowerShell (`scripts\db_backup.ps1`)
```powershell
.\scripts\db_backup.ps1 -OutputDir .\backups -RetentionDays 30
```

> [!IMPORTANT]
> **Always back up uploaded documents (`/app/storage` volume or your S3 bucket) AND your `.env` `SECRET_KEY` alongside database backups.** Without the same `SECRET_KEY`, Fernet-encrypted secrets in `system_configs` cannot be decrypted and must be re-entered in `/app/admin/integrations`.

---

## 2. Verified Database Restore (`scripts/db_restore.sh`)

```bash
# Stop write traffic first if restoring live
docker compose stop backend
./scripts/db_restore.sh ./backups/policynest_20261112T120000Z.dump
docker compose start backend
```
`db_restore.sh` verifies the SHA-256 checksum sidecar (if present), restores tables with `--clean --if-exists`, and runs `alembic current` inside the backend container to confirm schema alignment.

---

## 3. Alembic Migration Procedures

Current schema chain: `0001_foundation` -> `0002_phase2_applications` -> `0003_phase3_doc_intelligence` -> `0004_phase4_rules_engine` -> `0005_phase5_reviewer_ops` -> `0006_phase6_training_lms` -> `0007_phase7_admin_config` -> `0008_phase8_integrations`.

### Standard Upgrade Workflow
```bash
# 1. Back up database first
./scripts/db_backup.sh

# 2. Check current revision and apply pending migrations
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head

# 3. Verify SQLAlchemy models match DB schema (no drift)
docker compose exec backend alembic check
```

### Emergency Rollback (Single Revision)
Only downgrade if application containers matching the previous schema version are deployed simultaneously:
```bash
docker compose exec backend alembic downgrade -1
```
Note: `audit_logs` immutability triggers (`prevent_audit_log_mutation`) remain enforced across downgrades unless the initial `0001_foundation` migration itself is reverted.
