# Phase 3 – Document Intelligence & Verification

## Acceptance criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Document classification & real OCR execution | Met | `app/services/ocr_pipeline.py` runs `LOCAL_TESSERACT` (`pytesseract` + Tesseract binary), `PYPDF_TEXT`, and `CV_FACE_DETECTOR`; classifies documents (`PAN_CARD`, `AADHAAR_FRONT`, `AADHAAR_BACK`, `CLASS_10_MARKSHEET`, `BANK_DOCUMENT`, `APPLICANT_SELFIE`, `UNKNOWN`) and records `classification_confidence` & `classification_match` |
| CV image quality checks & missing-field detection | Met | `app/services/cv_quality.py` computes Laplacian `blur_score`, localized specular glare (`glare_ratio`), border clipping (`edge_clip_ratio`), resolution bounds, and Haar cascade `face_detected`; flags `missing_fields` per expected document schema |
| Field normalization & cross-document consistency | Met | `app/services/consistency.py` implements 8-tier Indian name matching (exact, initials, token order, middle name delta, spelling/phonetic variant, marriage surname delta, different person routed to human review, bank truncation), PAN format + 4th-char Individual (`P`) rule, DOB/Aadhaar year-only check, and RBI IFSC format validation |
| Aadhaar data minimisation & masking | Met | `mask_aadhaar_numbers_in_text` masks 12-digit tokens in OCR output; `_redact_aadhaar_image` paints solid OpenCV black rectangles over detected 12-digit numbers & QR codes into private `redacted_storage_key` PNGs served via `GET .../redacted`; 12-digit Aadhaar inputs rejected on field corrections |
| Reviewer correction of extracted fields | Met | `PATCH /api/v1/applications/{id}/documents/{doc_id}/fields` (gated by `application:review` + regional/clearance ABAC) records immutable `document_field_corrections` rows, updates `effective_fields`, and recomputes deterministic checks |
| AI advisory assistance & honest provider boundaries | Met | `app/services/ai_assistant.py` (`GeminiAIAssistant` via `google-genai` Interactions API when configured, or `LocalHeuristicAIAssistant`) only summarizes extractions and never approves/rejects applications; `app/services/verification_providers.py` distinguishes `PUBLIC_DIRECTORY`, `SANDBOX` (blocked in `production`), `REAL_PROVIDER`, and `UNCONFIGURED` |

## Implemented capabilities

### Backend (`backend/`)
- **Migrations & ORM (`0003_phase3_doc_intelligence`):**
  - Added `document_extractions`, `document_field_corrections`, and `verification_checks`.
- **Services:**
  - `app/services/cv_quality.py`: PDF text + embedded raster image extraction, OpenCV quality analysis (`OK`, `IMAGE_BLURRY`, `IMAGE_GLARE`, `IMAGE_CROPPED`, `LOW_RESOLUTION`, `FACE_NOT_DETECTED`, `UNREADABLE`).
  - `app/services/ocr_pipeline.py`: Local Tesseract OCR execution, heuristic document classifier, field extraction/normalization, and OpenCV spatial redaction for Aadhaar front/back.
  - `app/services/ai_assistant.py`: Provider-independent advisory explanation generator (`LocalHeuristicAIAssistant`, `GeminiAIAssistant`).
  - `app/services/consistency.py`: 8-tier Indian name matcher (`match_indian_names`), PAN validation (`validate_pan_format`), DOB comparator (`compare_dob_values`), and cross-document checks.
  - `app/services/verification_providers.py`: Razorpay public IFSC directory adapter (`PUBLIC_DIRECTORY`), plus PAN, bank penny-drop, DigiLocker, and face-match adapters reporting honest configuration modes (`not_configured`, `sandbox` non-prod only, or `real` Phase 8 boundary).
  - `app/services/verification.py`: Orchestrates `run_document_intelligence` (auto-invoked on `POST /applications/{id}/submit` and callable via `POST /applications/{id}/process`) and `apply_reviewer_field_corrections`.
- **API Endpoints (`/api/v1`):**
  - `POST /applications/{id}/process`
  - `GET /applications/{id}/verification`
  - `GET /applications/{id}/documents/{doc_id}/redacted`
  - `PATCH /applications/{id}/documents/{doc_id}/fields`
  - Updated `GET /admin/system/health` to surface live statuses for `ocr`, `ai_assistant`, `ifsc_directory`, `pan_verification`, `bank_verification`, `digilocker`, and `face_match`.

### Frontend (`frontend/`)
- **Verification Report Panel (`VerificationReportPanel.tsx`):** Displays per-document quality metrics, classification match, masked OCR text drawer, redacted Aadhaar image dialog, deterministic consistency checks with provenance tags, and AI governance disclaimer.
- **Applicant Integration:** Draft pre-check trigger (`Pre-check quality & OCR`) on Onboarding Step 5 (`DocumentsStep.tsx`) and live verification report on `/app/applications/[id]`.
- **Reviewer Document Intelligence Desk (`/app/review`, `/app/review/[id]`):** Permission-gated (`application:review`) regional queue and document inspection view with interactive `FieldCorrectionDialog` and immutable correction history.

## Known limitations (deferred to Phases 4–8)
- Deterministic eligibility/completeness/risk rule configuration, versioning, and automated decision routing (`AUTO_PASSED` vs. `UNDER_REVIEW` vs. `NEEDS_MORE_INFO` vs. `REJECTED`) arrive in Phase 4.
- Full Reviewer/Senior Reviewer decision actions (approve, reject, request rework, fraud escalation) and operational SLA analytics arrive in Phase 5.
- LMS training/certification synchronization arrives in Phase 6; authorized commercial KYC/banking/biometric/SMS integrations complete in Phase 8.
