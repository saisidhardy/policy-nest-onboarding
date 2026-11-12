# Phase 4 — Rules Engine & Decision Management

## Implemented Scope

Phase 4 replaces ad-hoc status updates with a versioned, deterministic PS-01 v3.2.0 policy rule engine, reviewer override controls, and separated Correction, Reapplication, and Appeal lifecycles connected end-to-end across PostgreSQL, FastAPI, and Next.js.

### Backend (`backend/`)
- **Database Schema (`alembic/versions/0004_phase4_rules_engine.py`, `app/models/rules.py`, `app/models/application.py`):**
  - `rule_sets`: Versioned policy configurations with a partial unique index enforcing at most one active `RuleSet`, seeded initially with `v3.2.0` (`PS-01 POSP Onboarding Rulebook v3.2.0`).
  - `rule_executions`: Immutable evaluation records storing `outcome`, `recommended_status`, sub-statuses (`eligibility_status`, `completeness_status`, `consistency_status`, `risk_level`), `rule_results`, consolidated bilingual `rework_items`, `risk_indicators`, and `reason_codes`.
  - `application_decisions`: Explicit reviewer and Senior Reviewer decisions/overrides with mandatory `reason_text`, `reason_codes`, `is_override`, and audit trails.
  - `application_appeals`: Formal appeals against `REJECTED` applications with Senior Reviewer resolution workflow (`UPHOLD_REJECTION`, `REOPEN_FOR_REVIEW`, `APPROVE_KYC`).
  - `applications` columns added: `parent_application_id`, `resolution_kind`, `reapplication_reason`, `rework_count`.
- **Deterministic Policy Engine (`app/services/rules_engine.py`, `app/schemas/rules.py`):**
  - **Eligibility Checks:** Statutory age `>= 18` (`UNDERAGE`), strict PAN format & 4th-char `'P'` Individual check (`PAN_FORMAT_INVALID`, `PAN_NOT_INDIVIDUAL`), Class 10+ & recognized board verification (`EDU_NOT_ELIGIBLE` or `HUMAN_REVIEW` for unlisted boards), and IRDAI single-intermediary exclusivity / duplicate active PAN detection (`ALREADY_REGISTERED`).
  - **Completeness & Quality Checks:** All 6 mandatory documents uploaded, document type classification match, OpenCV quality checks (`IMAGE_BLURRY`, `IMAGE_GLARE`, `IMAGE_CROPPED`, `FACE_MATCH_LOW`), and `0.75` OCR confidence floor.
  - **Cross-Document Consistency & Biometric Boundary:** Declared vs extracted PAN, 8-tier Indian name consistency (`NAME_SPELLING_VARIANT`, Tier 6 post-marriage surname change, Tier 7 `NAME_MISMATCH`), DOB comparison with Aadhaar year-of-birth tolerance (`DOB_MISMATCH`), RBI IFSC format + primary account holder + banking truncation tolerance, and biometric score banding (`>= 0.75` pass, `0.60-0.75` human, `< 0.60` rework) with honest `NOT_EVALUATED` / `EXTERNAL_PROVIDERS_UNCONFIGURED` reporting when external biometric/PAN/bank APIs are unconfigured.
  - **Risk Indicators (Informational / Escalation):** PAN 5th-character surname initial mismatch (`PAN_5TH_CHAR_SURNAME`), permanent/Aadhaar vs residential state mismatch (`STATE_DIFFERENCE`), and repeated rework escalation (`rework_count >= 2` -> Fraud/Ops `HUMAN_REVIEW`).
  - **Guardrails & Conflict Resolution:**
    - Rejection trumps rework: `rework_items` are suppressed whenever a hard statutory disqualification applies.
    - Non-auto-reject guardrail: `never_auto_reject_name_mismatch` is enforced as `Literal[True] = True` on `RuleConfigSchema`; Tier 7 `NAME_MISMATCH` always routes to `HUMAN_REVIEW` (`IN_REVIEW`) and requires `SENIOR_REVIEWER` (`application:decide_escalated`) confirmation.
    - Single-pass consolidated bilingual (English + Hindi) rework templates.
- **API Routes (`app/api/routes/rules.py`):**
  - `GET /api/v1/rulesets`, `POST /api/v1/rulesets`, `POST /api/v1/rulesets/{ruleset_id}/activate`
  - `GET /api/v1/applications/{application_id}/decisions`
  - `POST /api/v1/applications/{application_id}/evaluate`
  - `POST /api/v1/applications/{application_id}/decide`
  - `POST /api/v1/applications/{application_id}/reapply`
  - `POST /api/v1/applications/{application_id}/appeal`
  - `POST /api/v1/applications/{application_id}/appeals/{appeal_id}/resolve`
  - Wired `POST /api/v1/applications/{application_id}/submit` to track `rework_count` and run initial `AUTO_SUBMIT` rule evaluation.

### Frontend (`frontend/`)
- `DecisionHistoryPanel` (`src/components/verification/DecisionHistoryPanel.tsx`): Consolidated EN/HI rework checklist, guardrail warnings, rule breakdown, risk indicators, reviewer/Senior Reviewer decision & override controls, and separated Appeal vs Linked Reapplication forms.
- Wired automatic rule evaluation into `OnboardingWizard` submission and integrated `DecisionHistoryPanel` into `/app/applications/[id]` and `/app/review/[id]`.
- Added Administrator Business Rules Management portal (`/app/admin/rules` + `AppShell` navigation entry gated by `config:manage`).

### Remaining Limitations
- Full reviewer queue filters, batch operations, and operational productivity dashboards remain in Phase 5.
- External verification adapters (`PAN_REGISTRY`, `BANK_PENNY_DROP`, `DIGILOCKER`, `FACE_MATCH`) remain unconfigured and transparently report `NOT_CONFIGURED` / `NOT_EVALUATED` until Phase 8 integrations.
