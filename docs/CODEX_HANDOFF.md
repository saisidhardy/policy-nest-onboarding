# PolicyNest MVP status and Codex handoff

**Repository:** `https://github.com/saisidhardy/policy-nest-onboarding`  
**Baseline:** `master` at merge commit `2abdade` (includes MVP commit `d599212`)  
**Prepared:** 12 November 2026  
**Audience:** The next developer and their Codex session

## Executive status

PolicyNest is **feature-complete for an internal pilot**, but it is not yet a production-certified POSP platform.

- Internal-pilot MVP: approximately **90% complete / 10% pending**.
- Full Phase 0-10 production roadmap: approximately **65% complete / 35% pending**.
- Core workflows implemented: authentication, applicant record, draft/save/submit, document uploads, deterministic validation, review decisions, training, exam, certificate, operations aggregates, RBAC/ABAC, and audit/domain events.
- Main gaps: browser E2E coverage, real OCR and cross-document reasoning, contracted external verification providers, deeper reviewer and analytics experiences, security/load/accessibility testing, approved regulatory content, and production deployment of the database-backed stack.

## Latest verification snapshot

- PostgreSQL 16 integration environment created and both Alembic migrations exercised.
- Backend Ruff lint and format checks pass.
- Backend tests: **29 passed**, including a complete applicant/reviewer/training/certificate integration journey.
- Frontend ESLint and TypeScript checks pass locally.
- Frontend Vitest and production build are defined in CI; the local managed Windows sandbox blocks `esbuild` child-process startup with `spawn EPERM`, so those two results must be taken from GitHub Actions rather than reported as locally passing.
- `.github/workflows/ci.yml` provides PostgreSQL 16 and runs the complete backend and frontend check matrix.
- `https://policynest-saisidhardy-mvp.embarko.app` hosts only the legacy static visual preview. It is not the secure FastAPI/Next.js/PostgreSQL application.

These percentages are delivery estimates based on the original acceptance criteria, not source-line counts. A phase with a working vertical slice is not marked 100% when the original plan requires external validation, richer algorithms, or production evidence.

## Phase-by-phase assessment

| Phase | Estimated done | What is implemented | What remains |
| --- | ---: | --- | --- |
| 0 — Audit and architecture | 100% | Requirements, source inventory, architecture, implementation plan | Keep documents synchronized with future changes |
| 1 — Database and core auth | 95% | PostgreSQL, Alembic, authentication, sessions, CSRF, roles, ABAC foundations, audit logs, administration, PostgreSQL integration tests and CI configuration | Confirm the new workflow on GitHub Actions and verify every acceptance statement against deployed behavior |
| 2 — Applicant lifecycle | 75% | One application per applicant, draft persistence, personal/address/education/bank data, eligibility checks, submission and status | Convert the current form into the full guided multi-step experience; add stronger inline validation, autosave/resume UX, biometric/e-sign steps, and browser tests |
| 3 — Document processing | 50% | Versioned private uploads, 10 MB limit, magic-byte/MIME checks, PDF/image validation, deterministic image-quality checks | Real OCR with confidence values, orientation/cropping handling, production object storage, malware scanning, and benchmarked OpenCV-quality thresholds |
| 4 — Rulebook and entity reasoning | 30% | Deterministic submission validation and durable outcomes | Eight-tier name matching, cross-document DOB/name/entity reasoning, complete Rulebook v3.2, benchmark evaluation, and governed ML inference if still required |
| 5 — External verification | 30% | Provider-independent durable verification records and strict `SANDBOX`/`NOT_CONFIGURED` behavior | Contracted DigiLocker, PAN, penny-drop, and liveness adapters; credentials; callback/retry handling; provider conformance tests |
| 6 — Corrections and review cockpit | 70% | Region/clearance-filtered queue, assignment, consolidated correction requests, approval, rejection, escalation, immutable decisions | Split-screen document viewer, OCR override UI, richer filters/SLA views, bilingual notification templates, and reviewer productivity tests |
| 7 — Training, exam, certificate | 70% | Four 225-minute modules, 50-question assessment, 70% pass threshold, gated access, sealed PDF certificate | Compliance-approved curriculum/question bank, retake/cooldown policy, stronger anti-cheating controls, certificate verification page, and official visual/signature assets |
| 8 — Operations and telemetry | 40% | Database-backed application/review/correction/verification/certificate aggregates | Active-session telemetry, conversion/drop-off analytics, reviewer utilization, queue aging/SLA alerts, model observatory, exports, and alerting |
| 9 — Security and QA | 60% | Secure cookie/config checks, ownership enforcement, upload controls, validation, audit/domain events, PostgreSQL integration coverage, lint/type checks and CI configuration | Browser E2E, IDOR/XSS/SQLi/rate-limit testing, penetration test, accessibility audit, load test, backup/restore exercise, and dependency monitoring |
| 10 — Deployment and handover | 45% | Docker definitions, environment template, runbook basics, release-status document, merged MVP code and an explicitly labelled static visual preview | Managed PostgreSQL, database-backed HTTPS hosting, runtime secrets, SMTP, migrations, monitoring, backups, rollback, smoke tests, and final production runbook |

## Implemented source map

- `backend/app/models/domain.py`: application, documents, verifications, corrections, decisions, training, exam, and certificate data.
- `backend/alembic/versions/0002_onboarding_domain.py`: onboarding-domain migration.
- `backend/app/api/routes/applications.py`: applicant lifecycle and uploads.
- `backend/app/api/routes/reviews.py`: reviewer queue and actions.
- `backend/app/api/routes/training.py`: modules, assessment, and certificate.
- `backend/app/api/routes/operations.py`: operations summary.
- `backend/app/services/onboarding.py`: eligibility and document-quality rules.
- `backend/app/services/training.py`: assessment bank, scoring, and PDF generation.
- `frontend/src/app/app/application/page.tsx`: applicant experience.
- `frontend/src/app/app/reviews/page.tsx`: reviewer experience.
- `frontend/src/app/app/training/page.tsx`: training and exam experience.
- `frontend/src/app/app/operations/page.tsx`: operational metrics.
- `docs/RELEASE_STATUS.md`: implemented release and production gates.

The `legacy/` directory is reference material from the earlier prototype. Do not mistake its simulated interactions for production functionality or copy unsafe mock behavior into the current application.

## Instructions for the next Codex session

Give Codex this file and the repository, then use the following prompt:

> Continue PolicyNest from `docs/CODEX_HANDOFF.md`. Inspect the current `master` before changing anything. Work only on the pending production gaps in priority order. Preserve PostgreSQL, FastAPI, Next.js, RBAC/ABAC, CSRF, audit events, and the rule that sandbox/external-provider responses must never be represented as live verification. Implement one bounded milestone at a time, add tests, run the relevant checks, update this handoff and `docs/RELEASE_STATUS.md`, commit on a feature branch, push it, and provide a pull-request link. Do not claim regulatory or production readiness without evidence.

Codex should first run:

```bash
git clone https://github.com/saisidhardy/policy-nest-onboarding.git
cd policy-nest-onboarding
git checkout master
git pull --ff-only origin master
git status
```

Then create a branch for the selected milestone:

```bash
git checkout -b codex/<short-milestone-name>
```

Do not work directly on `master`. Do not rewrite or delete user changes. Before implementation, inspect the relevant source, tests, migration history, `.env.example`, `README.md`, `docs/RELEASE_STATUS.md`, and the original acceptance criteria in `docs/phase0/IMPLEMENTATION_PLAN.md`.

## Recommended execution order

### Milestone 1 — Reproducible full-stack environment and CI

1. Run the application with Docker Compose and PostgreSQL 16.
2. Apply both Alembic migrations to an empty database.
3. Exercise registration, email verification through Mailpit, login, application creation, upload, submission, review, training, exam, and certificate download.
4. Add CI for backend lint/tests and frontend lint/typecheck/tests/build using a PostgreSQL service.
5. Fix failures without weakening security or replacing PostgreSQL with SQLite.

**Exit evidence:** CI link, migration log, test results, and a real full-stack screenshot/run record.

### Milestone 2 — Browser E2E and security regression suite

1. Add Playwright coverage for applicant, reviewer, administrator, and operations roles.
2. Test unauthorized access, cross-user IDOR, out-of-region reviewer access, CSRF, invalid uploads, and state-transition rules.
3. Add accessibility checks for primary workflows.

**Exit evidence:** passing browser suite and documented security cases.

### Milestone 3 — Complete document and rulebook engine

1. Implement OCR behind a provider-neutral interface and persist field confidence/provenance.
2. Implement and unit-test Rulebook v3.2 name, DOB, document-consistency, and rejection rules.
3. Evaluate against the supplied datasets; publish precision/recall and failure analysis.
4. Keep automated recommendations separate from human regulatory approval.

**Exit evidence:** deterministic tests, benchmark report, and reviewer-visible evidence/provenance.

### Milestone 4 — Reviewer and correction UX

1. Add split document/form comparison and version history.
2. Add consolidated English/Hindi correction communication.
3. Add queue filters, age/SLA indicators, and safe OCR overrides with mandatory justification.

**Exit evidence:** role-restricted E2E tests and immutable audit entries for every action.

### Milestone 5 — Training/compliance hardening

1. Replace draft content only after compliance approval.
2. Add retake policy, attempt limits/cooldowns, training-timer integrity, and certificate verification.
3. Make certificate wording/assets configurable and approved.

**Exit evidence:** signed content approval reference, exam-policy tests, and public verification flow.

### Milestone 6 — External providers

Implement only when contracts, credentials, sandbox endpoints, callback specifications, and data-processing approval exist. Keep each provider behind an adapter; store provider, environment, request correlation, timestamps, and evidence. Never fabricate successful live verification.

**Exit evidence:** sandbox conformance tests followed by separately authorized production smoke tests.

### Milestone 7 — Production deployment

1. Provision managed PostgreSQL, secret storage, SMTP, HTTPS, monitoring, and backups.
2. Deploy migrations and services through a repeatable pipeline.
3. Test restore, rollback, alerting, health endpoints, and smoke workflows.
4. Complete penetration, load, accessibility, and privacy reviews.

**Exit evidence:** public HTTPS endpoint, monitoring/backup evidence, rollback record, and approved release checklist.

## Local setup

Create `.env` from `.env.example` and set strong local values. Never commit `.env`, tokens, regulated-provider credentials, or real applicant PII.

```bash
docker compose up --build
docker compose exec backend python -m app.cli create-admin \
  --email you@example.com --name "Your Name"
```

Local endpoints:

- Frontend: `http://localhost:3000`
- API documentation: `http://localhost:8000/api/docs`
- Mailpit: `http://localhost:8025`

## Required validation before each pull request

```bash
# Backend — full suite requires a disposable PostgreSQL test database
cd backend
TEST_DATABASE_URL=postgresql+psycopg://policynest:<password>@localhost:5432/policynest_test pytest
ruff check .
ruff format --check .

# Frontend
cd ../frontend
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

Also run any new browser/integration/security tests introduced by the milestone. Record commands and results in the pull request. Do not say “all tests pass” if infrastructure prevented a test from running.

## Non-negotiable safety and compliance rules

1. Never store a full Aadhaar number; the current application stores only the last four digits.
2. Never expose raw documents publicly. Use private storage and authorized download paths.
3. Never log passwords, tokens, bank details, document bytes, or unnecessary PII.
4. Never label mock or sandbox provider data as live or verified.
5. Never allow an automated model to issue final regulatory approval without the authorized decision workflow.
6. Preserve application ownership checks, role checks, region/clearance ABAC, CSRF protection, rate limiting, and audit events.
7. Use new Alembic migrations for schema changes; do not edit a migration already used by another environment.
8. Treat the supplied training content and question bank as draft until compliance approves them.
9. Do not train or evaluate models on real applicant data without documented authorization and privacy controls.
10. Do not declare production readiness until deployment, security, compliance, backup/restore, accessibility, and load gates have evidence.

## Definition of production-ready

Production work is complete only when all of the following are true:

- The full test matrix passes in CI against PostgreSQL.
- Primary applicant, reviewer, administrator, training, and operations flows pass browser E2E.
- Approved external integrations are configured and environment-labelled.
- Training/exam/certificate content has documented compliance approval.
- Penetration, dependency, accessibility, privacy, and load reviews are accepted.
- Managed PostgreSQL backups and restore have been demonstrated.
- Monitoring, alerting, HTTPS, secrets, migrations, deployment, and rollback are operational.
- The production smoke checklist passes without simulated results.
- Documentation and support ownership are current.

Until then, describe the release as an **internal pilot**, not a production-certified regulatory platform.
