# Phase 6 — Training & Certification

## Implemented Scope

Phase 6 integrates PolicyNest with an external Learning Management System (LMS) via a provider-independent adapter to track IRDAI POSP 15-hour training eligibility, module progress, proctored exam outcomes, certification issuance, and synchronization retries.

### Backend (`backend/`)
- **Database Migration (`alembic/versions/0006_phase6_training_lms.py`, `app/models/training.py`):**
  - Created `training_records` (1:1 per application tracking `eligibility_status`, `external_enrollment_id`, `enrollment_status`, `completed_hours`, `progress_pct`, `module_progress`, `exam_status`, `exam_score_pct`, `next_exam_eligible_at`, `certification_status`, `certificate_number`, `sync_status`, `sync_attempts`, `next_retry_at`, and `last_error_code`/`last_error_message`).
  - Created append-only `lms_sync_logs` recording every enroll, status sync, retry, and signed webhook event with adapter origin and HTTP status.
- **LMS Integration Adapter (`app/services/lms_adapter.py`, `app/core/config.py`):**
  - Supports `not_configured` (honestly surfaces `NOT_CONFIGURED` without fabricating progress or certificates), `http_api` (REST calls using `LMS_API_BASE_URL` and Bearer `LMS_API_KEY`), and non-production `sandbox` (blocked automatically when `APP_ENV=production`, explicitly marked `is_simulated=True`).
  - Exposes live LMS status inside `GET /api/v1/admin/system/health`.
- **Training Service & API (`app/services/training.py`, `app/api/routes/training.py`):**
  - Unlocks eligibility on `KYC_APPROVED` via hooks in `rules_engine.py`.
  - Enforces statutory IRDAI rules (§5–§6): `15.0` training hours across the 6 POSP curriculum modules before exam pass/certification (`>= 50%` score) and a 24-hour retake cooldown on exam failure.
  - Endpoints:
    - `GET /api/v1/applications/{id}/training`
    - `POST /api/v1/applications/{id}/training/enroll`
    - `POST /api/v1/applications/{id}/training/sync`
    - `POST /api/v1/applications/{id}/training/retry`
    - `GET /api/v1/training/overview` and `POST /api/v1/training/retry-due` (Operations/Admin monitor)
    - `POST /api/v1/training/webhooks/lms` (HMAC-SHA256 verified via `X-LMS-Signature`)

### Frontend (`frontend/`)
- **`TrainingStatusPanel` (`src/components/training/TrainingStatusPanel.tsx`):** Displays LMS adapter provenance banner, eligibility, 15h curriculum progress bar, 6-module checklist, exam/cooldown status, POSP certificate details, retry error controls, sync audit log, and non-production sandbox controls (rendered only in `SANDBOX` mode).
- **`/app/training` (`src/app/app/training/page.tsx`):** Role-aware portal showing the applicant's personal training & certification tracker or the Operations/Admin LMS pipeline and batch retry dashboard.
- Embedded `TrainingStatusPanel` on eligible application tracking (`/app/applications/[id]`) and reviewer workspace (`/app/review/[id]`) pages.

### Remaining Limitations
- Full Administrator configuration UI for integrations, LMS URLs/credentials, and platform settings belongs to **Phase 7** and **Phase 8**.
- Background worker automation (`Redis`/cron scheduling of `next_retry_at` syncs and live external provider hardening) belongs to **Phase 8**.
