# Phase 7 — Administrator Portal

**Status:** Complete

Phase 7 expands the PolicyNest Administrator Portal into a complete operational control plane wired PostgreSQL <-> FastAPI <-> Next.js, preserving strict RBAC/ABAC boundaries, Separation of Duties (`ADMIN` cannot decide KYC applications or clear fraud flags), Fernet-encrypted database secret storage, and append-only audit logging.

---

## Implemented Capabilities

### 1. Administrator Operational Dashboard
- **Backend:** `GET /api/v1/admin/dashboard` ([`get_admin_dashboard`](backend/app/services/admin_ops.py)) combining user/security metrics with live onboarding pipeline counts (`total_applications`, `applications_by_status`, `escalated_applications`), certification/sync telemetry (`training_certified_count`, `training_sync_failed_count`), reviewer capacity (`reviewer_count`, `senior_reviewer_count`), and live integration adapter statuses.
- **Frontend:** Upgraded `AdminOverview` on `/app` ([`page.tsx`](frontend/src/app/app/page.tsx)) linking directly to Admin queues, reviewers, integrations, and filtered audit queries.

### 2. Reviewer Management & Workload Reassignment
- **Backend:**
  - `GET /api/v1/admin/reviewers` ([`list_reviewers_workload`](backend/app/services/admin_ops.py)) aggregates per-reviewer active queue counts, escalated queue counts, lifetime decisions, overrides, and field corrections without N+1 queries.
  - `POST /api/v1/admin/reviewers/{user_id}/reassign-workload` moves active cases to an eligible active reviewer or returns them to the unassigned pool. Enforces `SENIOR_REVIEWER_REQUIRED` when any active case is escalated, records an `ApplicationEvent` on every moved case, and emits an `AuditLog` entry.
- **Frontend:** `/app/admin/reviewers` ([`page.tsx`](frontend/src/app/app/admin/reviewers/page.tsx)) with capacity summary cards, region/role filters, scope/clearance/status editor (`PATCH /api/v1/admin/users/{id}`), and bulk workload reassignment modal.

### 3. Global Application Oversight & Assignment
- **Backend:**
  - `GET /api/v1/admin/applications` searches across `reference_code`, applicant name, and applicant email with filters for `status`, `region`, `escalated_only`, and `unassigned_only` plus global `counts_by_status`.
  - `POST /api/v1/admin/applications/{application_id}/assign` assigns or unassigns reviewers with mandatory reason, conflict-of-interest guard (an applicant cannot review their own application), escalated senior-reviewer enforcement, `ApplicationEvent`, and `AuditLog`.
- **Frontend:** `/app/admin/applications` ([`page.tsx`](frontend/src/app/app/admin/applications/page.tsx)) displaying searchable pipeline records, status filter chips, and reviewer assignment dialog.

### 4. Role & Permission Customization
- **Backend:** `PUT /api/v1/admin/roles/{role_code}/permissions` ([`update_role_permissions`](backend/app/services/admin_ops.py)) enforces hard server-side invariants:
  - `APPLICANT` role permissions are immutable (`ROLE_PROTECTED`).
  - Separation of Duties (`SEPARATION_OF_DUTIES`): `ADMIN` cannot be granted `application:decide`, `application:decide_escalated`, `fraud:review`, or `application:escalate`.
  - Admin lockout prevention (`REQUIRED_ADMIN_PERMISSION`): `ADMIN` cannot strip core user, role, audit, system, or config management permissions.
- **Frontend:** Upgraded `/app/admin/roles` ([`page.tsx`](frontend/src/app/app/admin/roles/page.tsx)) with permission editor dialog for staff roles (`REVIEWER`, `SENIOR_REVIEWER`, `ADMIN`) gated by `config:manage`.

### 5. Persistent Database Configuration, Integrations & LMS Console
- **Migration:** [`0007_phase7_admin_config.py`](backend/alembic/versions/0007_phase7_admin_config.py) creates the `system_configs` PostgreSQL table (`key`, `config_json`, `secrets_encrypted`, `updated_by_user_id`, timestamps).
- **Encryption & Provenance:** [`platform_config.py`](backend/app/services/platform_config.py) derives a Fernet cipher from `SECRET_KEY` (SHA-256 -> URL-safe base64), encrypts API keys/secrets before PostgreSQL persistence, exposes only boolean presence flags + 4-character masked hints (`••••9876`) in API responses, and never writes secret values into `audit_logs`.
- **Endpoints:** `GET /api/v1/admin/config`, `PUT /api/v1/admin/config/lms`, `PUT /api/v1/admin/config/integrations`, `PUT /api/v1/admin/config/platform`, and `POST /api/v1/admin/config/reset/{section}`. Enforces `SANDBOX_FORBIDDEN_IN_PROD` when `APP_ENV=production`.
- **Adapter Integration:** `lms_adapter.py`, `training.py`, `verification_providers.py`, and `GET /api/v1/admin/system/health` resolve live configuration from PostgreSQL with automatic `.env` fallback.
- **Frontend:** `/app/admin/integrations` ([`page.tsx`](frontend/src/app/app/admin/integrations/page.tsx)) displaying live adapter health snapshot and tabbed LMS, Verification & AI, and Platform & Security settings forms.

---

## Remaining Limitations (Scheduled for Phases 8 & 9)
- **External KYC & Biometric HTTP Calls (Phase 8):** DB configuration for Protean/Cashfree/RazorpayX/NeGD DigiLocker/AWS Rekognition persists provider selection and health state, while outbound live vendor transaction boundaries and webhook retries complete in Phase 8.
- **SMS Gateway & Retry Queues (Phase 8):** Email SMTP and LMS retry queues are operational; transactional SMS gateway adapters and worker orchestration complete in Phase 8.
- **Production Container Hardening & Deployment Validation (Phase 9):** Full multi-service container/backup/migration runbooks and extended load/E2E verification complete in Phase 9.
