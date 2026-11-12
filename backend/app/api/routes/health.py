from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.config import get_settings
from app.core.db import get_engine

router = APIRouter(tags=["health"])

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"


@lru_cache
def migration_head() -> str | None:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def database_status() -> dict:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception as exc:  # noqa: BLE001
        return {"connected": False, "error": type(exc).__name__}
    head = migration_head()
    return {"connected": True, "migration": current, "migration_head": head, "migrations_current": current == head}


@router.get("/health", summary="Liveness probe")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "service": "policynest-api", "version": s.app_version}


@router.get("/health/ready", summary="Readiness probe (database + migrations)")
def ready() -> JSONResponse:
    db = database_status()
    ok = db.get("connected") and db.get("migrations_current")
    return JSONResponse(
        status_code=200 if ok else 503, content={"status": "ready" if ok else "not_ready", "database": db}
    )
