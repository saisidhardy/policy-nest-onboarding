# PolicyNest release status

## Implemented in the current release

- Phase 0: audited requirements and architecture baseline.
- Phase 1: PostgreSQL/Alembic foundation, secure authentication, sessions, CSRF, RBAC/ABAC, audit logs and administration.
- Phase 2: one durable applicant record per user, staged draft editing, deterministic eligibility checks, submission and status tracking.
- Phase 3: versioned uploads, magic-byte checks, 10 MB limit, private database storage and image quality inspection.
- Phase 4: deterministic submission rule result and review outcome workflow. Automated outcomes never issue a regulatory approval.
- Phase 5: durable provider-independent verification records. Live providers remain `NOT_CONFIGURED` until contracted credentials are supplied. Development requests are marked `SANDBOX` and never report a live verification.
- Phase 6: region/clearance-filtered review queue, assignment, consolidated correction requests, approval, rejection, escalation and immutable decisions.
- Phase 7: four-module 900-minute training record, 50-question assessment, 70% threshold and sealed PDF certificate.
- Phase 8: live application, review, correction, verification and certification aggregates.
- Phase 9: existing authentication hardening plus validation, upload controls, ownership enforcement and append-only domain events. External penetration testing and production load testing remain release gates.
- Phase 10: container definitions exist. Production deployment requires a managed PostgreSQL service, runtime secrets, an SMTP provider and optional regulated verification-provider credentials.

## Verified release evidence

The current branch includes a PostgreSQL-backed integration suite and CI workflow rather than relying on the legacy browser simulation:

- Backend lint and format checks pass.
- All 29 backend tests pass against PostgreSQL 16.
- The integration test covers registration, email verification, draft creation, six document uploads, sandbox verification, submission, reviewer assignment, correction, resubmission, approval, four training modules, a 50-question passing assessment, certificate PDF download and operations metrics.
- Frontend ESLint and TypeScript checks pass locally.
- GitHub Actions runs backend lint/tests plus frontend lint, typecheck, tests and production build on every pull request and on pushes to `master`.

The Embarko URL is a hosted visual preview of `legacy/static`. It is useful for design review, but it is not the PostgreSQL-backed internal-pilot application and must not be treated as a production deployment.

## Production gates

The application is feature-complete for an internal pilot. The following are external operational dependencies rather than code simulations:

1. Configure managed PostgreSQL and execute both Alembic migrations.
2. Configure `SECRET_KEY`, HTTPS URLs/origins and SMTP credentials.
3. Contract and configure any live DigiLocker, PAN, penny-drop or biometric provider before enabling those adapters.
4. Have compliance approve the training content and assessment bank before treating generated certificates as regulatory evidence.
5. Perform penetration, accessibility, backup/restore and load tests in the selected production environment.
6. Deploy both the FastAPI service and Next.js application to a host with managed PostgreSQL, run migrations, and complete the authenticated smoke workflow.
