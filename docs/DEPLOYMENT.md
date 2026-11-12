# PolicyNest Deployment Guide

This guide covers containerized development and hardened production deployments using Docker Compose, PostgreSQL 16, Redis 7, S3-compatible object storage (MinIO or AWS S3), and the FastAPI + Next.js standalone containers.

---

## 1. Prerequisites
- Docker Engine 24+ and Docker Compose v2.20+
- Domain name with TLS termination (via Nginx/Caddy/cloud load balancer) for production
- PostgreSQL 16 (managed or Compose `db` service)
- S3 bucket or MinIO instance for private KYC document storage (`STORAGE_PROVIDER=s3` recommended in multi-replica deployments)
- Authenticated SMTP relay for transactional email

---

## 2. Environment Configuration

Copy `.env.example` to `.env` and populate secrets before starting containers:

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Mandatory Production Variables (`APP_ENV=production`)
- `POSTGRES_PASSWORD`: Strong database password.
- `SECRET_KEY`: High-entropy random key (used for session/CSRF signing and **Fernet encryption** of secrets persisted in `system_configs`). Do not change casually without re-saving encrypted secrets.
- `PUBLIC_APP_URL` & `ALLOWED_ORIGINS`: Exact HTTPS portal origin (e.g., `https://posp.yourdomain.com`).
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_STARTTLS` / `SMTP_SSL`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`.
- `STORAGE_PROVIDER=s3`, `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` (or persistent volume on `/app/storage` if running single-node `local` storage).

### Production Safety Guards Enforced by Backend Startup
When `APP_ENV=production`, [`Settings`](../backend/app/core/config.py) enforces:
- Weak/default `SECRET_KEY` is rejected at startup.
- `Secure` cookie attributes are mandatory.
- Sandbox adapters (`PAN_VERIFICATION_PROVIDER=sandbox`, `BANK_VERIFICATION_PROVIDER=sandbox`, `DIGILOCKER_PROVIDER=sandbox`, `FACE_MATCH_PROVIDER=sandbox`, `SMS_PROVIDER=sandbox`, `LMS_PROVIDER=sandbox`) are rejected at startup AND blocked in `PUT /api/v1/admin/config/*` (`SANDBOX_FORBIDDEN_IN_PROD`).

---

## 3. Running in Development vs Production

### Development Stack (includes Mailpit + MinIO + local ports)
```bash
docker compose up -d --build
docker compose exec backend python -m app.cli create-admin --email admin@yourdomain.com --name "Platform Admin"
```
Services exposed locally on `127.0.0.1`:
- Portal UI: `http://localhost:3000`
- FastAPI OpenAPI Docs: `http://localhost:8000/api/docs`
- Mailpit Inbox: `http://localhost:8025`
- MinIO Console: `http://localhost:9001`

### Production Overlay (`docker-compose.prod.yml`)
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
Optional Nginx reverse proxy (`deploy/nginx.conf`, front-ending port 80 for TLS/load balancer termination):
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile with-proxy up -d --build
```

The backend container automatically executes `alembic upgrade head` on boot and passes container health checks at `GET /health/ready` before `frontend` (and `proxy`) start routing traffic.

---

## 4. Non-Root Containers & Health Checks
- [`backend/Dockerfile`](../backend/Dockerfile) runs under non-root UID `10001` (`app`), owns `/app/storage`, includes `tesseract-ocr`, and exposes a Docker `HEALTHCHECK` against `/health/ready`.
- [`frontend/Dockerfile`](../frontend/Dockerfile) uses multi-stage Node 22 Alpine standalone build and runs as non-root `app`.
- [`docker-compose.yml`](../docker-compose.yml) defines healthchecks across `db`, `redis`, `minio`, `backend`, and `frontend` with `restart: unless-stopped`.
