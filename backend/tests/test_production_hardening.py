"""Unit tests for PostgreSQL pooling, S3 presigned URLs, Sentry telemetry & SLA monitoring."""

from unittest.mock import patch

from app.core.config import Settings
from app.core.db import get_engine
from app.scripts.postgres_cutover import mask_db_url
from app.scripts.verify_s3_storage import verify_storage
from app.services.storage import LocalPrivateStorage


def test_mask_db_url_masks_password():
    url = "postgresql+psycopg://admin_user:SuperSecretP@ss!@pg-cluster.internal:5432/policynest_prod"
    masked = mask_db_url(url)
    assert "SuperSecretP@ss!" not in masked
    assert "admin_user:***@pg-cluster.internal:5432/policynest_prod" in masked


def test_mask_db_url_safe_when_no_password():
    url = "sqlite:///./local.db"
    assert mask_db_url(url) == "sqlite:///./local.db"


def test_postgres_pooling_configuration(tmp_path):
    # Test that get_engine sets pool parameters when URL starts with postgresql
    custom_settings = Settings(
        database_url="postgresql+psycopg://test_user:test_pwd@localhost:5432/test_db",
        secret_key="a" * 32,
    )
    with patch("app.core.db.get_settings", return_value=custom_settings):
        get_engine.cache_clear()
        engine = get_engine()
        assert engine.dialect.name == "postgresql"
        assert engine.pool.size() == 10
        assert engine.pool._max_overflow == 20
        assert engine.pool._timeout == 30
        assert engine.pool._recycle == 1800
        get_engine.cache_clear()


def test_local_storage_presigned_url(tmp_path):
    storage = LocalPrivateStorage(tmp_path)
    # Save a test object
    key = "applications/app-123/pan_card.jpg"
    storage.put_object(key, b"fake_pan_bytes", "image/jpeg")

    assert storage.get_object(key) == b"fake_pan_bytes"
    presigned = storage.get_presigned_url(key)
    assert presigned == f"/api/v1/storage/documents/{key}"


def test_s3_verify_storage_simulation():
    res = verify_storage(force_mock=True, cleanup=True)
    assert res["status"] == "SUCCESS_MOCK"
    assert res["mode"] == "SIMULATION"
    assert res["put_latency_ms"] > 0
    assert res["get_latency_ms"] > 0
    assert "X-Amz-Signature" in res["presigned_sample_url"]
    assert res["cleanup_performed"] is True


def test_sla_review_data_structures():
    from datetime import datetime, timezone

    from app.schemas.review import BreachedApplicationOut, ReviewSlaStatusOut

    app_out = BreachedApplicationOut(
        id="11111111-1111-1111-1111-111111111111",
        reference_code="PN-TEST-001",
        status="IN_REVIEW",
        applicant_name="Test Applicant",
        submitted_at=datetime.now(timezone.utc),
        wait_time_minutes=45.5,
        region="NORTH",
    )
    status_out = ReviewSlaStatusOut(
        status="BREACHED",
        sla_threshold_minutes=30,
        total_pending_queue=5,
        total_unassigned=2,
        breach_count=1,
        max_wait_minutes=45.5,
        oldest_unassigned_application_id=app_out.id,
        oldest_unassigned_submitted_at=app_out.submitted_at,
        breached_applications=[app_out],
        alert_dispatched=True,
        timestamp=datetime.now(timezone.utc),
    )
    dumped = status_out.model_dump(mode="json")
    assert dumped["status"] == "BREACHED"
    assert dumped["breach_count"] == 1
    assert dumped["breached_applications"][0]["reference_code"] == "PN-TEST-001"


def test_rate_limiter_sliding_window():
    from fastapi import Request

    from app.core.rate_limit import InMemorySlidingWindowLimiter, RateLimitRule

    rule = RateLimitRule(path="/api/v1/auth/login", method="POST", max_requests=2, window_seconds=60)
    test_limiter = InMemorySlidingWindowLimiter(rules=(rule,))

    custom_settings = Settings(
        database_url="sqlite:///./test.db",
        secret_key="a" * 32,
        app_env="development",
    )

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": [],
        "client": ("192.168.1.100", 12345),
    }
    req = Request(scope)

    with patch("app.core.rate_limit.get_settings", return_value=custom_settings):
        # Call 1: Allowed
        assert test_limiter.check(req) is None
        # Call 2: Allowed
        assert test_limiter.check(req) is None
        # Call 3: Exceeded -> 429 Too Many Requests
        res3 = test_limiter.check(req)
        assert res3 is not None
        assert res3.status_code == 429
        assert res3.headers["Retry-After"] == "60"
        assert res3.headers["X-RateLimit-Remaining"] == "0"


if __name__ == "__main__":
    import pathlib
    import tempfile

    print("Running test_production_hardening tests...")
    test_mask_db_url_masks_password()
    print(" - test_mask_db_url_masks_password: OK")
    test_mask_db_url_safe_when_no_password()
    print(" - test_mask_db_url_safe_when_no_password: OK")
    test_postgres_pooling_configuration(pathlib.Path(tempfile.gettempdir()))
    print(" - test_postgres_pooling_configuration: OK")
    test_local_storage_presigned_url(pathlib.Path(tempfile.gettempdir()))
    print(" - test_local_storage_presigned_url: OK")
    test_s3_verify_storage_simulation()
    print(" - test_s3_verify_storage_simulation: OK")
    test_sla_review_data_structures()
    print(" - test_sla_review_data_structures: OK")
    test_rate_limiter_sliding_window()
    print(" - test_rate_limiter_sliding_window: OK")
    print("ALL TESTS PASSED!")
