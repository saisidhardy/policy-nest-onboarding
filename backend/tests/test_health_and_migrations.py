from sqlalchemy import select, text

from app.core.db import get_engine, get_sessionmaker
from app.models import Role
from app.rbac.catalog import PERMISSIONS, ROLE_PERMISSIONS, ROLES


def test_liveness(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "x-request-id" in r.headers


def test_readiness_reports_current_migration(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    db = r.json()["database"]
    assert db["connected"] and db["migrations_current"] and db["migration"] == "0002_onboarding_domain"


def test_seeded_roles_match_catalog():
    with get_sessionmaker()() as db:
        roles = {r.code: r for r in db.scalars(select(Role)).all()}
    assert set(roles) == {r.value for r in ROLES}
    for code, perms in ROLE_PERMISSIONS.items():
        assert roles[code.value].permission_codes == set(perms)
        assert set(perms) <= set(PERMISSIONS)


def test_audit_log_is_append_only(client):
    from tests.conftest import register

    register(client)
    with get_engine().connect() as conn:
        try:
            conn.execute(text("UPDATE audit_logs SET action = 'tampered'"))
            raise AssertionError("update should be blocked")
        except Exception as exc:  # noqa: BLE001
            assert "append-only" in str(exc)
            conn.rollback()
        try:
            conn.execute(text("DELETE FROM audit_logs"))
            raise AssertionError("delete should be blocked")
        except Exception as exc:  # noqa: BLE001
            assert "append-only" in str(exc)


def test_openapi_docs_available(client):
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200
