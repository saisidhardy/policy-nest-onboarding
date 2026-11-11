# Phase 2 – Applicant Portal & Onboarding

## Acceptance criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Applicant information persists in PostgreSQL | Met | `applications`, `application_documents`, `application_events`, `notifications` in Alembic migration `0002_phase2_applications`; `tests/test_applications.py` |
| Drafts can be resumed | Met | `PATCH /api/v1/applications/{id}` persists `current_step` + partial sections; `GET /api/v1/applications/current` resumes where left off across sessions |
| Documents can be uploaded and retrieved securely | Met | Magic-byte validation, SHA-256 checksums, versioned `application_documents`, private storage (`LocalPrivateStorage` / `S3StorageBackend`), authenticated streaming `GET .../content` with `document.viewed` audit log |
| Applicants cannot access other applicants' private records | Met | ABAC `enforce_policy` ownership checks on every application, document, history, and notification endpoint (`403 FORBIDDEN` + `access.denied` audit logs) |
| Submission changes the actual application status | Met | `POST /api/v1/applications/{id}/submit` validates completeness of all 4 sections, 6 required documents, and 3 declarations, transitioning `DRAFT` -> `SUBMITTED` and locking draft edits |
| Every important transition is recorded | Met | `application_events` timeline + `audit_logs` + persistent `notifications` recorded on creation, draft saves, uploads/replacements/removals, submission, and withdrawal |

## Implemented capabilities

### Backend (`backend/`)
- **Migrations & ORM (`0002_phase2_applications`):**
  - Added `preferred_language` (`EN` / `HI`) on `users`.
  - Created `app_reference_seq` PostgreSQL sequence (`APP-260001`, `APP-260002`, ...) and tables `applications`, `application_documents` (with partial unique index `uq_current_application_doc`), `application_events`, and `notifications`.
- **Privacy & Security:**
  - `aadhaar_last4` accepts only 4 digits (with PostgreSQL regex check constraint and Pydantic rejection of 12-digit inputs).
  - Bank account numbers are encrypted at rest via `app.core.crypto` (Fernet key derived from `SECRET_KEY`); API responses expose only `account_number_last4`, `account_number_masked`, and `has_account_number`.
  - Draft save audit/event details record field names only without raw PAN, mobile, or account numbers.
- **Document Storage & Validation (`app/services/storage.py`, `app/services/documents.py`):**
  - Supports all 6 required document types: `PAN_CARD`, `AADHAAR_FRONT`, `AADHAAR_BACK`, `CLASS_10_MARKSHEET`, `BANK_DOCUMENT`, and `APPLICANT_SELFIE`.
  - Validates magic bytes (`JPEG`, `PNG`, `WebP`, `PDF`; selfie restricted to images), size bounds (`100 B` to `MAX_UPLOAD_SIZE_MB`), sanitized filenames, and SHA-256 digests.
  - Supports `STORAGE_PROVIDER=local` (private backend filesystem) and `STORAGE_PROVIDER=s3` (`boto3` for AWS S3 / MinIO), surfaced on `/api/v1/admin/system/health`.
- **API Endpoints (`/api/v1`):**
  - `GET /applications/metadata/states`
  - `GET /applications`, `POST /applications`, `GET /applications/current`, `GET /applications/{id}`, `PATCH /applications/{id}`
  - `POST /applications/{id}/submit`, `POST /applications/{id}/withdraw`, `GET /applications/{id}/history`
  - `GET /applications/{id}/documents`, `POST /applications/{id}/documents/{doc_type}`, `GET /applications/{id}/documents/{doc_id}/content`, `DELETE /applications/{id}/documents/{doc_id}`
  - `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`

### Frontend (`frontend/`)
- **Applicant Dashboard (`/app`):** Shows onboarding progress, resume step CTA, submitted tracking link, recent notifications, and account summary.
- **6-Step Onboarding Wizard (`/app/onboarding`, `/app/onboarding/[id]`):**
  - Step 1: Personal details (`PAN`, `aadhaar_last4`, `preferred_language`)
  - Step 2: Address details (Indian states/UTs + permanent address toggle)
  - Step 3: Education details
  - Step 4: Bank payout details (masked account preservation)
  - Step 5: Document Upload Centre (6 required slots, live camera selfie capture, secure preview modal, version history, replace/remove)
  - Step 6: Review & Submit (section edit jumps, completeness validation, 3 declarations)
- **Tracking, History & Notifications:** `/app/applications`, `/app/applications/[id]`, `/app/notifications`, plus preferred language management on `/app/account`.

## Known limitations (deferred to Phases 3–8)
- Uploaded documents remain in `UPLOADED` status until Phase 3 implements OCR extraction, image quality checks, and Aadhaar visual masking.
- Deterministic policy rules and automated STP vs. human review routing run in Phase 4.
- Reviewer queue/cockpit (`REVIEWER`, `SENIOR_REVIEWER`) opens in Phase 5.
- External PAN, bank penny-drop, DigiLocker, face comparison, SMS, and LMS integrations remain `NOT_CONFIGURED` until Phases 6 & 8.
