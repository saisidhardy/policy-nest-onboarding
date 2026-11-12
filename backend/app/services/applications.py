"""Applicant onboarding application lifecycle, draft saving, completeness checks, and submission."""

import uuid

from fastapi import Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from app.api.deps import AuthContext
from app.core.crypto import encrypt_sensitive, mask_account_number
from app.core.errors import AppError
from app.models import Application, ApplicationDocument, ApplicationEvent
from app.models.application import ACTIVE_APPLICATION_STATUSES, EDITABLE_STATUSES, REQUIRED_DOC_TYPES
from app.models.base import utcnow
from app.rbac.policy import Resource
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationDetailOut,
    ApplicationDraftUpdate,
    ApplicationEventOut,
    ApplicationSubmitRequest,
    ApplicationSummaryOut,
    CompletenessOut,
    DocumentOut,
    SectionCompleteness,
)
from app.services import audit
from app.services.india_geo import region_for_state
from app.services.notifications import create_notification

PERSONAL_REQUIRED = (
    ("full_name", "Full name"),
    ("date_of_birth", "Date of birth"),
    ("gender", "Gender"),
    ("father_or_spouse_name", "Father or spouse name"),
    ("mobile", "Mobile number"),
    ("email", "Email address"),
    ("pan_number", "PAN number"),
    ("aadhaar_last4", "Aadhaar last 4 digits"),
)

ADDRESS_REQUIRED = (
    ("address_line1", "Residential address line 1"),
    ("city", "City"),
    ("district", "District"),
    ("state", "State"),
    ("pincode", "PIN code"),
)

PERMANENT_ADDRESS_REQUIRED = (
    ("permanent_address_line1", "Permanent address line 1"),
    ("permanent_city", "Permanent city"),
    ("permanent_state", "Permanent state"),
    ("permanent_pincode", "Permanent PIN code"),
)

EDUCATION_REQUIRED = (
    ("education_level", "Education level"),
    ("board_name", "Board or university"),
    ("school_or_university", "School or institution name"),
    ("passing_year", "Passing year"),
    ("roll_number", "Roll or registration number"),
    ("result_status", "Result status"),
)

BANK_REQUIRED = (
    ("account_holder_name", "Account holder name"),
    ("bank_name", "Bank name"),
    ("ifsc_code", "IFSC code"),
    ("account_number_last4", "Bank account number"),
    ("account_type", "Account type"),
)

_SENSITIVE_AUDIT_FIELDS = {"pan_number", "aadhaar_last4", "mobile", "email", "account_number"}


def _generate_reference_code(db: Session) -> str:
    seq_val = db.execute(text("SELECT nextval('app_reference_seq')")).scalar_one()
    return f"APP-{int(seq_val)}"


def application_resource(app: Application) -> Resource:
    return Resource(
        type="application",
        id=str(app.id),
        owner_id=app.user_id,
        region=app.region,
        sensitivity=app.sensitivity,
    )


def resolve_read_permission(auth: AuthContext) -> str:
    return "application:read_any" if "application:read_any" in auth.permissions else "application:read_own"


def get_application(db: Session, application_id: uuid.UUID) -> Application:
    stmt = (
        select(Application)
        .options(selectinload(Application.documents), selectinload(Application.events))
        .where(Application.id == application_id)
    )
    app = db.scalar(stmt)
    if app is None:
        raise AppError(404, "APPLICATION_NOT_FOUND", "Onboarding application not found.")
    return app


def _current_docs(app: Application) -> list[ApplicationDocument]:
    return [d for d in app.documents if d.is_current]


def compute_completeness(app: Application) -> CompletenessOut:
    missing_fields: list[str] = []

    def check_group(fields: tuple[tuple[str, str], ...]) -> bool:
        ok = True
        for attr, label in fields:
            val = getattr(app, attr)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing_fields.append(label)
                ok = False
        return ok

    personal_ok = check_group(PERSONAL_REQUIRED)
    address_ok = check_group(ADDRESS_REQUIRED)
    if not app.same_as_permanent:
        address_ok = check_group(PERMANENT_ADDRESS_REQUIRED) and address_ok
    education_ok = check_group(EDUCATION_REQUIRED)
    bank_ok = check_group(BANK_REQUIRED)

    current_types = {d.doc_type for d in _current_docs(app)}
    missing_docs = [doc_type for doc_type in REQUIRED_DOC_TYPES if doc_type not in current_types]
    documents_ok = len(missing_docs) == 0
    declarations_ok = bool(app.consent_terms and app.consent_kyc_processing and app.declaration_no_other_posp)

    sections = SectionCompleteness(
        personal=personal_ok,
        address=address_ok,
        education=education_ok,
        bank=bank_ok,
        documents=documents_ok,
        declarations=declarations_ok,
    )
    completed = sum([personal_ok, address_ok, education_ok, bank_ok, documents_ok, declarations_ok])
    return CompletenessOut(
        sections=sections,
        missing_fields=missing_fields,
        missing_documents=missing_docs,
        uploaded_document_count=len(REQUIRED_DOC_TYPES) - len(missing_docs),
        required_document_count=len(REQUIRED_DOC_TYPES),
        completed_sections=completed,
        total_sections=6,
        ready_to_submit=personal_ok and address_ok and education_ok and bank_ok and documents_ok,
    )


def to_summary(app: Application) -> ApplicationSummaryOut:
    return ApplicationSummaryOut(
        id=app.id,
        reference_code=app.reference_code,
        status=app.status,
        current_step=app.current_step,
        region=app.region,
        preferred_language=app.preferred_language,
        full_name=app.full_name,
        submitted_at=app.submitted_at,
        last_saved_at=app.last_saved_at,
        created_at=app.created_at,
        updated_at=app.updated_at,
        completeness=compute_completeness(app),
    )


def to_detail(app: Application) -> ApplicationDetailOut:
    current = _current_docs(app)
    return ApplicationDetailOut(
        id=app.id,
        reference_code=app.reference_code,
        user_id=app.user_id,
        status=app.status,
        current_step=app.current_step,
        region=app.region,
        sensitivity=app.sensitivity,
        preferred_language=app.preferred_language,
        channel=app.channel,
        full_name=app.full_name,
        date_of_birth=app.date_of_birth,
        gender=app.gender,
        father_or_spouse_name=app.father_or_spouse_name,
        mobile=app.mobile,
        email=app.email,
        pan_number=app.pan_number,
        aadhaar_last4=app.aadhaar_last4,
        address_line1=app.address_line1,
        address_line2=app.address_line2,
        city=app.city,
        district=app.district,
        state=app.state,
        pincode=app.pincode,
        same_as_permanent=app.same_as_permanent,
        permanent_address_line1=app.permanent_address_line1,
        permanent_address_line2=app.permanent_address_line2,
        permanent_city=app.permanent_city,
        permanent_state=app.permanent_state,
        permanent_pincode=app.permanent_pincode,
        education_level=app.education_level,
        board_name=app.board_name,
        school_or_university=app.school_or_university,
        passing_year=app.passing_year,
        roll_number=app.roll_number,
        result_status=app.result_status,
        percentage_or_cgpa=app.percentage_or_cgpa,
        account_holder_name=app.account_holder_name,
        bank_name=app.bank_name,
        branch_name=app.branch_name,
        ifsc_code=app.ifsc_code,
        account_number_last4=app.account_number_last4,
        account_number_masked=app.account_number_masked,
        has_account_number=bool(app.account_number_encrypted),
        account_type=app.account_type,
        is_joint_account=app.is_joint_account,
        is_primary_holder=app.is_primary_holder,
        consent_terms=app.consent_terms,
        consent_kyc_processing=app.consent_kyc_processing,
        declaration_no_other_posp=app.declaration_no_other_posp,
        declared_at=app.declared_at,
        submitted_at=app.submitted_at,
        last_saved_at=app.last_saved_at,
        created_at=app.created_at,
        updated_at=app.updated_at,
        documents=[DocumentOut.model_validate(d) for d in current],
        document_history=[DocumentOut.model_validate(d) for d in app.documents],
        events=[ApplicationEventOut.model_validate(e) for e in app.events],
        completeness=compute_completeness(app),
    )


def create_application(
    db: Session,
    body: ApplicationCreateRequest,
    auth: AuthContext,
    request: Request,
) -> Application:
    existing = db.scalar(
        select(Application).where(
            Application.user_id == auth.user.id,
            Application.status.in_(ACTIVE_APPLICATION_STATUSES),
        )
    )
    if existing is not None:
        raise AppError(
            409,
            "ACTIVE_APPLICATION_EXISTS",
            f"You already have an active application ({existing.reference_code}). Resume it instead.",
        )

    now = utcnow()
    ref = _generate_reference_code(db)
    app = Application(
        id=uuid.uuid4(),
        reference_code=ref,
        user_id=auth.user.id,
        status="DRAFT",
        current_step=1,
        preferred_language=body.preferred_language or auth.user.preferred_language or "EN",
        full_name=auth.user.full_name,
        email=auth.user.email,
        mobile=auth.user.mobile,
        account_holder_name=auth.user.full_name,
        last_saved_at=now,
    )
    db.add(app)
    db.flush()

    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type="APPLICATION_CREATED",
            from_status=None,
            to_status="DRAFT",
            summary=f"POSP onboarding application {ref} started.",
            details={"reference_code": ref},
        )
    )
    create_notification(
        db,
        user_id=auth.user.id,
        application_id=app.id,
        category="APPLICATION",
        title=f"Application {ref} started",
        body="Complete your personal, address, education, and bank details and upload all 6 required documents to submit.",
        action_url=f"/app/onboarding/{app.id}",
    )
    audit.add(
        db,
        request,
        "application.created",
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details={"reference_code": ref},
    )
    db.flush()
    return get_application(db, app.id)


def update_draft(
    db: Session,
    app: Application,
    body: ApplicationDraftUpdate,
    auth: AuthContext,
    request: Request,
) -> Application:
    if app.status not in EDITABLE_STATUSES:
        raise AppError(
            409,
            "APPLICATION_LOCKED",
            "Submitted applications cannot be edited unless rework is requested.",
        )

    fields_set = body.model_fields_set
    updated_keys: list[str] = []

    for field_name in fields_set:
        if field_name == "account_number":
            acct = body.account_number
            if acct is not None:
                last4, masked = mask_account_number(acct)
                app.account_number_last4 = last4
                app.account_number_masked = masked
                app.account_number_encrypted = encrypt_sensitive(acct)
                updated_keys.append("account_number")
            continue

        val = getattr(body, field_name)
        if getattr(app, field_name) != val:
            setattr(app, field_name, val)
            updated_keys.append(field_name)

    if "state" in fields_set:
        app.region = region_for_state(app.state)

    if app.same_as_permanent:
        app.permanent_address_line1 = None
        app.permanent_address_line2 = None
        app.permanent_city = None
        app.permanent_state = None
        app.permanent_pincode = None

    app.last_saved_at = utcnow()

    if updated_keys:
        safe_keys = [k if k not in _SENSITIVE_AUDIT_FIELDS else f"{k}_updated" for k in updated_keys]
        db.add(
            ApplicationEvent(
                application_id=app.id,
                actor_user_id=auth.user.id,
                actor_role=auth.user.role.code,
                event_type="DRAFT_SAVED",
                from_status=app.status,
                to_status=app.status,
                summary=f"Draft saved at step {app.current_step}.",
                details={"step": app.current_step, "fields": safe_keys},
            )
        )
        audit.add(
            db,
            request,
            "application.draft_saved",
            actor=auth.user,
            resource_type="application",
            resource_id=str(app.id),
            details={"reference_code": app.reference_code, "step": app.current_step, "fields": safe_keys},
        )
    db.flush()
    return get_application(db, app.id)


def submit_application(
    db: Session,
    app: Application,
    body: ApplicationSubmitRequest,
    auth: AuthContext,
    request: Request,
) -> Application:
    if app.status not in EDITABLE_STATUSES:
        raise AppError(409, "ALREADY_SUBMITTED", "This application has already been submitted.")

    if not (body.consent_terms and body.consent_kyc_processing and body.declaration_no_other_posp):
        raise AppError(
            422,
            "DECLARATIONS_REQUIRED",
            "Accept all three onboarding declarations before submitting your application.",
        )

    completeness = compute_completeness(app)
    if not completeness.ready_to_submit:
        raise AppError(
            422,
            "APPLICATION_INCOMPLETE",
            "Complete all required profile sections and upload all 6 documents before submitting.",
            {
                "missing_fields": completeness.missing_fields,
                "missing_documents": completeness.missing_documents,
            },
        )

    now = utcnow()
    prev_status = app.status
    next_status = "REWORK_SUBMITTED" if prev_status == "NEEDS_MORE_INFO" else "SUBMITTED"

    app.consent_terms = True
    app.consent_kyc_processing = True
    app.declaration_no_other_posp = True
    app.declared_at = now
    app.submitted_at = now
    app.last_saved_at = now
    app.current_step = 6
    app.status = next_status

    event_type = "REWORK_SUBMITTED" if next_status == "REWORK_SUBMITTED" else "APPLICATION_SUBMITTED"
    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type=event_type,
            from_status=prev_status,
            to_status=next_status,
            summary=f"Application {app.reference_code} submitted for document processing and review.",
            details={
                "uploaded_documents": completeness.uploaded_document_count,
                "region": app.region,
            },
        )
    )
    create_notification(
        db,
        user_id=app.user_id,
        application_id=app.id,
        category="APPLICATION",
        title=f"Application {app.reference_code} submitted",
        body="Your details and 6 documents have been received. Track status updates on your application timeline.",
        action_url=f"/app/applications/{app.id}",
    )
    audit.add(
        db,
        request,
        "application.submitted",
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details={"reference_code": app.reference_code, "from_status": prev_status, "to_status": next_status},
    )
    db.flush()
    from app.services import verification as verification_service

    verification_service.run_document_intelligence(db, app, auth, request)
    return get_application(db, app.id)


def withdraw_application(
    db: Session,
    app: Application,
    reason: str | None,
    auth: AuthContext,
    request: Request,
) -> Application:
    if app.status != "DRAFT":
        raise AppError(409, "CANNOT_WITHDRAW", "Only draft applications can be withdrawn.")

    prev_status = app.status
    app.status = "WITHDRAWN"
    app.last_saved_at = utcnow()
    clean_reason = reason.strip() if reason and reason.strip() else "Withdrawn by applicant"

    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type="APPLICATION_WITHDRAWN",
            from_status=prev_status,
            to_status="WITHDRAWN",
            summary=f"Draft application {app.reference_code} withdrawn.",
            details={"reason": clean_reason},
        )
    )
    create_notification(
        db,
        user_id=app.user_id,
        application_id=app.id,
        category="APPLICATION",
        title=f"Application {app.reference_code} withdrawn",
        body="Your draft application was withdrawn. You can start a new application anytime from your dashboard.",
        action_url="/app",
    )
    audit.add(
        db,
        request,
        "application.withdrawn",
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details={"reference_code": app.reference_code},
    )
    db.flush()
    return get_application(db, app.id)
