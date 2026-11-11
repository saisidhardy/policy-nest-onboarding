# PolicyNest

AI-first POSP (Point of Sales Person) onboarding platform for an insurance intermediary.

This repository implements **Phase 1 (Platform Foundation)** and **Phase 2 (Applicant Portal & Onboarding)**:
authentication, sessions, RBAC/ABAC, audit logging, admin user management, applicant onboarding wizard,
private document upload/retrieval, tracking, application history, and notifications. Document intelligence/OCR,
rules engine, reviewer cockpit, LMS sync, and external KYC/banking providers follow in Phases 3–8. The original
single-file prototype is kept unchanged in [`legacy/`](legacy/).

| Path | Contents |
| --- | --- |
| `backend/` | FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · Argon2id · Local/S3 private document storage |
| `frontend/` | Next.js 15 (App Router) · TypeScript · Tailwind CSS 4 · Vitest |
| `docs/PHASE1.md` | Phase 1 scope, acceptance checklist, security model, known limitations |
| `docs/PHASE2.md` | Phase 2 applicant onboarding, document storage, tracking, notifications, acceptance checklist |
| `docs/phase0/` | Audit, requirements and architecture plan |
| `docs/source_materials/` | Business source package (rulebook, regulatory matrix, specs, datasets) |
| `legacy/` | Original single-file prototype and SQLite backend |

## Run with Docker

```bash
cp .env.example .env            # then set POSTGRES_PASSWORD and SECRET_KEY (openssl rand -base64 48)
docker compose up --build
docker compose exec backend python -m app.cli create-admin --email you@example.com --name "Your Name"
```

- App: http://localhost:3000
- API docs: http://localhost:8000/api/docs (also proxied at http://localhost:3000/api/docs)
- Mailpit (captures verification / reset / invite emails): http://localhost:8025
- MinIO Console (optional S3 storage when `STORAGE_PROVIDER=s3`): http://localhost:9001

The backend container runs `alembic upgrade head` before starting.

## Local development

```bash
docker compose up -d db mailpit redis

cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# backend/.env: DATABASE_URL=postgresql+psycopg://policynest:<pw>@localhost:5432/policynest, SECRET_KEY=..., SMTP_HOST=localhost, SMTP_PORT=1025
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli create-admin --email you@example.com --name "Your Name"
.venv/bin/uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev                     # proxies /api/* to BACKEND_URL (default http://localhost:8000)
```

## Tests and checks

```bash
# backend (needs a PostgreSQL database it may drop/recreate the schema of)
cd backend
TEST_DATABASE_URL=postgresql+psycopg://policynest:<pw>@localhost:5432/policynest_test .venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .

# frontend
cd frontend
npm run lint && npm run typecheck && npm test && npm run build
```

## Configuration

All configuration is via environment variables (see `.env.example`). No credentials are hard-coded.
In `APP_ENV=production` the backend refuses to start with a weak `SECRET_KEY` and forces `Secure` cookies.
If `SMTP_HOST` is empty, email delivery reports `NOT_CONFIGURED` instead of pretending to send.
Document uploads default to `STORAGE_PROVIDER=local` (`./storage` outside web root) and support S3-compatible storage (`STORAGE_PROVIDER=s3`).
