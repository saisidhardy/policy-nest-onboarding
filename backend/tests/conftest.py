import os
import re
import secrets

os.environ.setdefault("TEST_DATABASE_URL", "postgresql+psycopg://policynest:policynest@localhost:5432/policynest_test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["SMTP_HOST"] = ""
os.environ["REQUIRE_EMAIL_VERIFICATION"] = "true"
os.environ["EMAIL_RESEND_COOLDOWN_SECONDS"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import get_engine, get_sessionmaker  # noqa: E402
from app.services import email as email_service  # noqa: E402

get_settings.cache_clear()

STRONG_PASSWORD = "Onboard2026secure"


class CapturingEmailProvider:
    name = "test-capture"
    configured = True

    def __init__(self) -> None:
        self.sent: list[email_service.OutgoingEmail] = []

    def send(self, message: email_service.OutgoingEmail) -> None:
        self.sent.append(message)

    def last_token(self, to: str) -> str:
        for msg in reversed(self.sent):
            if msg.to == to:
                match = re.search(r"token=([A-Za-z0-9_\-]+)", msg.text)
                assert match
                return match.group(1)
        raise AssertionError(f"No email sent to {to}")


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config("alembic.ini")
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables(migrated_db):
    yield
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "TRUNCATE users, user_sessions, user_action_tokens, email_deliveries, audit_logs RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def mailbox():
    provider = CapturingEmailProvider()
    email_service.set_provider_override(provider)
    yield provider
    email_service.set_provider_override(None)


@pytest.fixture
def client(mailbox):
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def make_client(mailbox):
    from app.main import create_app

    clients = []

    def factory() -> TestClient:
        c = TestClient(create_app())
        clients.append(c)
        return c

    yield factory
    for c in clients:
        c.close()


def csrf(c: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": c.cookies.get("pn_csrf", "")}


def register(c: TestClient, email: str = "asha@example.com", name: str = "Asha Verma", password: str = STRONG_PASSWORD):
    return c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": name,
            "mobile": "+91 98765 43210",
            "accept_terms": True,
        },
    )


def login(c: TestClient, email: str, password: str = STRONG_PASSWORD):
    return c.post("/api/v1/auth/login", json={"email": email, "password": password})


def create_staff(role: str, email: str, name: str = "Staff Member", region: str | None = None, clearance: int = 1):
    """Create a verified staff user directly (equivalent to an accepted invitation)."""
    import uuid

    from sqlalchemy import select

    from app.core.security import hash_password
    from app.models import Role, User
    from app.models.base import utcnow

    with get_sessionmaker()() as db:
        role_obj = db.scalar(select(Role).where(Role.code == role))
        user = User(
            id=uuid.uuid4(),
            email=email,
            full_name=name,
            role=role_obj,
            password_hash=hash_password(STRONG_PASSWORD),
            email_verified_at=utcnow(),
            region=region,
            clearance_level=clearance,
        )
        db.add(user)
        db.commit()
        return user.id
