"""PostgreSQL cutover, connectivity validation, and automated Alembic migration runner.

Usage:
    python -m app.scripts.postgres_cutover [--dry-run] [--seed-admin] [--json]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path when invoked directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Ensure settings loads even if CLI is called standalone with explicit --database-url
os.environ.setdefault("SECRET_KEY", "cutover-verification-ephemeral-key-min-32-chars")
os.environ.setdefault("DATABASE_URL", "sqlite:///./policynest_local.db")

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.base import utcnow
from app.models.user import Role, User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("postgres_cutover")

CORE_REQUIRED_TABLES = [
    "users",
    "user_sessions",
    "applications",
    "documents",
    "audit_trail",
    "rulesets",
    "rule_executions",
    "lms_courses",
    "lms_enrollments",
    "outbound_webhooks",
]


def mask_db_url(url: str) -> str:
    """Mask credentials in database URL for safe logging/auditing."""
    if "@" not in url:
        return url
    try:
        prefix, remainder = url.split("://", 1)
        if "@" in remainder:
            auth, rest = remainder.rsplit("@", 1)
            user = auth.split(":", 1)[0]
            return f"{prefix}://{user}:***@{rest}"
        return url
    except Exception:
        return "<masked-db-url>"


def run_cutover(
    *,
    db_url: str | None = None,
    dry_run: bool = False,
    seed_admin: bool = False,
    admin_email: str = "admin@policynest.internal",
    admin_name: str = "PolicyNest Production Admin",
    admin_password: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    target_url = db_url or settings.database_url

    # Normalize url prefix for psycopg
    for prefix in ("postgres://", "postgresql://"):
        if target_url.startswith(prefix):
            target_url = "postgresql+psycopg://" + target_url[len(prefix) :]

    masked_url = mask_db_url(target_url)
    is_postgres = "postgres" in target_url

    logger.info("Starting database cutover check against %s (dry_run=%s)", masked_url, dry_run)

    engine_kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
    if is_postgres:
        engine_kwargs.update(
            {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 1800,
            }
        )

    t0 = time.perf_counter()
    engine = create_engine(target_url, **engine_kwargs)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1;"))
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info("TCP/Database ping OK in %sms", latency_ms)

    # 2. Alembic migration runner
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_ini = backend_dir / "alembic.ini"
    alembic_dir = backend_dir / "alembic"

    from alembic import command
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory

    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(alembic_dir))
    alembic_cfg.attributes["configure_logger"] = False

    script = ScriptDirectory.from_config(alembic_cfg)
    head_revision = script.get_current_head()

    with engine.connect() as conn:
        migration_context = MigrationContext.configure(conn)
        initial_revision = migration_context.get_current_revision()

    logger.info("Current DB revision: %s (Head target: %s)", initial_revision, head_revision)

    if not is_postgres and not dry_run:
        logger.warning(
            "Target dialect is '%s'. PolicyNest production constraints (JSONB, POSIX regex ~, "
            "citext) require PostgreSQL. Alembic upgrade may require PostgreSQL.",
            engine.dialect.name,
        )

    migration_executed = False
    if not dry_run:
        logger.info("Applying Alembic migrations up to head...")
        # Override connection attribute so migrations run on the verified target engine
        alembic_cfg.attributes["connection"] = engine
        command.upgrade(alembic_cfg, "head")
        migration_executed = True

        with engine.connect() as conn:
            migration_context = MigrationContext.configure(conn)
            current_revision = migration_context.get_current_revision()
        logger.info("Post-upgrade DB revision: %s", current_revision)
    else:
        current_revision = initial_revision

    # 3. Schema verification
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    missing_tables = [t for t in CORE_REQUIRED_TABLES if t not in existing_tables]

    # 4. Baseline Admin verification / seeding
    admin_count = 0
    admin_seeded = False
    admin_details: dict[str, Any] = {}

    if "users" in existing_tables:
        with Session(engine) as session:
            admin_count = int(
                session.scalar(select(User.id).where(User.role == Role.ADMIN).limit(1)) is not None
            )
            if admin_count == 0 and (seed_admin or settings.app_env != "production"):
                pwd = admin_password or os.environ.get("ADMIN_INITIAL_PASSWORD") or "Admin@PolicyNest2026!Strong"
                admin_user = User(
                    email=admin_email.strip().lower(),
                    full_name=admin_name,
                    password_hash=hash_password(pwd),
                    role=Role.ADMIN,
                    clearance_level=3,
                    region="ALL",
                    is_active=True,
                    email_verified_at=utcnow(),
                )
                session.add(admin_user)
                session.commit()
                admin_count = 1
                admin_seeded = True
                admin_details = {
                    "email": admin_email.strip().lower(),
                    "seeded": True,
                }
                logger.info("Baseline admin user provisioned: %s", admin_email)

    status = "SUCCESS" if not missing_tables else "MISSING_TABLES"

    result = {
        "status": status,
        "dialect": engine.dialect.name,
        "is_postgres": is_postgres,
        "masked_url": masked_url,
        "ping_latency_ms": latency_ms,
        "initial_revision": initial_revision,
        "head_revision": head_revision,
        "current_revision": current_revision,
        "migration_executed": migration_executed,
        "dry_run": dry_run,
        "tables_found": len(existing_tables),
        "missing_required_tables": missing_tables,
        "admin_count": admin_count,
        "admin_seeded": admin_seeded,
        "admin_details": admin_details,
        "connection_pool": {
            "pool_size": getattr(engine.pool, "_pool", None) and engine.pool.size(),
            "max_overflow": getattr(engine.pool, "_max_overflow", None),
            "pool_timeout": getattr(engine.pool, "_timeout", None),
        }
        if is_postgres
        else "default_single_process",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="PolicyNest PostgreSQL cutover & migration CLI")
    parser.add_argument("--database-url", default=None, help="Database target URL")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without executing migrations")
    parser.add_argument("--seed-admin", action="store_true", help="Seed baseline admin user if missing")
    parser.add_argument("--admin-email", default="admin@policynest.internal", help="Admin email")
    parser.add_argument("--admin-password", default=None, help="Admin initial password")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args()
    try:
        res = run_cutover(
            db_url=args.database_url,
            dry_run=args.dry_run,
            seed_admin=args.seed_admin,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("\n=== PolicyNest Database Cutover Report ===")
            print(f"Status:            {res['status']}")
            print(f"Dialect:           {res['dialect']} (is_postgres={res['is_postgres']})")
            print(f"Target URL:        {res['masked_url']}")
            print(f"Ping Latency:      {res['ping_latency_ms']} ms")
            print(f"Alembic Revision:  {res['current_revision']} (Head: {res['head_revision']})")
            print(f"Tables Found:      {res['tables_found']}")
            print(f"Missing Required:  {res['missing_required_tables'] or 'None (All Present)'}")
            print(f"Admin Accounts:    {res['admin_count']} (seeded={res['admin_seeded']})")
            print("==========================================\n")
        return 0 if res["status"] == "SUCCESS" else 1
    except Exception as exc:
        logger.exception("Database cutover runner encountered a critical error: %s", exc)
        if args.json:
            print(json.dumps({"status": "FAILED", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
