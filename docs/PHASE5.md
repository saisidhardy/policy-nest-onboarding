# Phase 5 — Reviewer & Operations Portal

## Implemented Scope

Phase 5 delivers the complete operations cockpit for `REVIEWER` and `SENIOR_REVIEWER` staff, enforcing ABAC regional and clearance isolation, mandatory decision reasons, Fraud Desk workflows, immutable review history, and live PostgreSQL operational analytics.

### Backend (`backend/`)
- **Database Migration (`alembic/versions/0005_phase5_reviewer_ops.py`, `app/models/application.py`):**
  - Added `assigned_reviewer_id`, `assigned_at`, `escalated_at`, `escalated_by_user_id`, `escalation_reason`, `fraud_flag`, `fraud_reason`, and `fraud_escalated_at` to `applications`.
  - Updated `rules_engine.py` to record escalation metadata on `ESCALATE` decisions and automatically raise `fraud_flag` when applications hit repeated rework escalation (`rework_count >= max_rework_cycles_before_human`).
- **Reviewer Operations API (`app/api/routes/review.py`, `app/services/review.py`, `app/schemas/review.py`):**
  - `GET /api/v1/review/queue`: ABAC-scoped queue with live KPIs (`pending_review_count`, `in_review_count`, `escalated_count`, `fraud_flagged_count`, `open_appeals_count`, `assigned_to_me_count`, `unassigned_pending_count`, `kyc_approved_count`, `rejected_count`), preset views (`pending`, `assigned_to_me`, `unassigned`, `escalated`, `fraud`, `open_appeals`, `all`), text search, status/region/rule-outcome filters, urgency/FIFO sorting, and pagination.
  - `GET /api/v1/review/reviewers`: Active reviewers within regional scope for assignment controls.
  - `POST /api/v1/review/applications/{id}/claim`: Claim (`IN_REVIEW`), release, or reassign (restricted to `application:decide_escalated`).
  - `POST /api/v1/review/applications/{id}/fraud-escalate`: Escalates suspicious cases to the Fraud Desk (`application:escalate` / `fraud:review`), recording `ApplicationDecision`, `ApplicationEvent`, notification, and `AuditLog`.
  - `POST /api/v1/review/applications/{id}/fraud-resolve`: Senior Reviewer Fraud Desk resolution (`CLEAR_FLAG` or `CONFIRM_FRAUD_REJECT`) gated by `fraud:review`.
  - `GET /api/v1/review/history`: Filterable (`mine_only`, `decision`) paginated reviewer decision history with authenticated actor names, roles, override indicators, timestamps, and reasons.
  - `GET /api/v1/review/analytics`: Live PostgreSQL operational & productivity metrics gated by `analytics:read` (`SENIOR_REVIEWER` and `ADMIN` only).

### Frontend (`frontend/`)
- **Reviewer Queue Dashboard (`/app/review`):** Live KPI summary cards, preset queue tabs (`Pending Queue`, `Assigned to Me`, `Unassigned`, `Escalated`, `Fraud Desk`, `Open Appeals`, `All Records`), search, status/outcome filters, urgency sorting, quick claim/release buttons, and pagination.
- **Reviewer Workspace (`/app/review/[id]`):** Claim/release/reassign controls, Fraud Desk escalation & Senior Reviewer resolution panel, side-by-side `FieldComparisonCard` (Submitted Baseline vs Extracted/Corrected OCR fields), private document/redacted Aadhaar viewer + field corrections (`VerificationReportPanel`), and `DecisionHistoryPanel` for approve/rework/reject/escalate and appeals.
- **Review History (`/app/review/history`):** Auditable list of reviewer decisions with `Show my decisions only` toggle and action filter.
- **Operational Analytics (`/app/review/analytics`):** Gated by `analytics:read`, displaying STP rate, rework & escalation rates, turnaround time, status/rule distributions, appeals summary, and per-reviewer productivity table.

### Remaining Limitations
- LMS training eligibility, enrollment sync, and certification callbacks belong to **Phase 6**.
- Full Administrator configuration panels for integrations, LMS, and global analytics belong to **Phase 7** and **Phase 8**.
