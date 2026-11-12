# PolicyNest Operations Runbook

## 1. Health & Readiness Endpoints
- **Liveness (`GET /health`):** Fast process check returning `200 OK` without touching external dependencies.
- **Readiness (`GET /health/ready`):** Confirms PostgreSQL connectivity (`SELECT 1`), checks `alembic_version` currency (`migrations_current: true`), and reports application readiness. Load balancers should probe `/health/ready`.
- **Admin System Console (`/app/admin/system`, `GET /api/v1/admin/system/health`):** Surfaces effective statuses (`CONFIGURED`, `NOT_CONFIGURED`, `DEGRADED`) and provenance (`LIVE`, `LOCAL_DEVELOPMENT`, `SANDBOX`, `NONE`) for database, local/S3 document storage, SMTP email, OCR, advisory AI, IFSC lookup, PAN, bank penny-drop, DigiLocker, face match, SMS gateway, inbound webhooks, and LMS training sync.

---

## 2. Managing External Integrations & Secrets
Administrators configure adapters in PostgreSQL via `/app/admin/integrations` (requires `config:manage`) or environment variables:
- **Database Overrides vs `.env`:** Any section saved in `system_configs` (`lms`, `integrations`, `platform`) takes precedence over `.env`. Use `"Reset to defaults"` on a tab (`POST /api/v1/admin/config/reset/{section}`) to revert cleanly.
- **Secret Storage:** Bearer keys, client secrets, and HMAC shared secrets are encrypted with Fernet at rest and masked as 4-character hints (`••••1234`) in API responses. Secret changes record field names in `audit_logs` without plaintext values.
- **Active Probes:** Run `"Run health probes"` (`POST /api/v1/admin/integrations/probe`) to verify live TCP/HTTP/SMTP reachability and measure round-trip `latency_ms` persisted in `integration_probes`.

---

## 3. Monitoring Deliveries & Retrying Transient Failures
Navigate to `/app/admin/integrations` -> **Deliveries & Webhooks** (`GET /api/v1/admin/integrations/monitor`):
- **SMS Gateway:** Review `NOT_CONFIGURED`, `SANDBOX_SIMULATED`, `SENT`, and `FAILED` rows in `sms_deliveries`. Trigger batch retries for failed rows using `"Retry failed SMS"` (`POST /api/v1/admin/integrations/sms/retry-failed`).
- **Inbound Signed Webhooks (`POST /api/v1/webhooks/verification/{pan|bank|digilocker}` & `/api/v1/training/webhooks/lms`):** Inspect signature validation results (`REJECTED_SIGNATURE` vs `PROCESSED` vs `DUPLICATE_IGNORED`). Vendors must sign raw JSON request bytes with HMAC-SHA256 using `X-PolicyNest-Signature: sha256=<hex>` (or `X-LMS-Signature` for LMS).
- **Email Deliveries:** Transient SMTP failures retry automatically up to `EMAIL_MAX_ATTEMPTS` with attempt counts recorded on `email_deliveries`.
- **LMS Sync Retries:** Staff with `application:review` or `system:read` can execute due training sync retries from `/app/training` or `POST /api/v1/training/retry-due`.

---

## 4. Security & Governance Guarantees
- **Append-Only Audit Trail:** PostgreSQL trigger blocks `UPDATE`/`DELETE` on `audit_logs`. Inspect logs at `/app/admin/audit`.
- **Separation of Duties:** `ADMIN` users cannot approve/reject KYC applications or resolve Fraud Desk flags (`SEPARATION_OF_DUTIES` enforced on both decision endpoints and `PUT /api/v1/admin/roles/{role}/permissions`).
- **Aadhaar Data Minimisation:** Aadhaar uploads store only masked last-4 digits in extracted text and raster-redacted copies for visual review.
- **AI Advisory Constraint:** Gemini / local AI outputs are strictly advisory (`advisory_only=true`); deterministic rules (`PS-01`) and authorized human reviewers govern all status transitions.
