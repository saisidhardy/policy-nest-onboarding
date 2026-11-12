import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import DB, AuthContext, CurrentAuth, enforce_policy, require_permission
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Application, ApplicationEvent, Document, Verification
from app.rbac.policy import Resource
from app.schemas.domain import ApplicationOut, ApplicationPatch, DocumentOut, VerificationOut, VerificationRequestIn
from app.services import audit
from app.services.onboarding import (
    DOCUMENT_TYPES,
    EDITABLE_STATUSES,
    application_payload,
    inspect_file,
    new_reference,
    sha256,
    transition,
    validate_submission,
)

router = APIRouter(prefix="/applications", tags=["applications"])
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _mine(db: DB, auth: CurrentAuth, create: bool = False) -> Application:
    application = db.scalar(select(Application).where(Application.applicant_id == auth.user.id))
    if application is None and create:
        application = Application(applicant_id=auth.user.id, reference=new_reference())
        db.add(application)
        db.flush()
        db.add(
            ApplicationEvent(
                application_id=application.id,
                actor_user_id=auth.user.id,
                event_type="APPLICATION_CREATED",
                to_status="DRAFT",
            )
        )
    if application is None:
        raise AppError(404, "APPLICATION_NOT_FOUND", "Start an application first.")
    return application


def _owned_resource(application: Application) -> Resource:
    return Resource(
        type="application",
        id=str(application.id),
        owner_id=application.applicant_id,
        region=application.region,
        sensitivity=application.sensitivity,
    )


@router.post("/mine", response_model=ApplicationOut, status_code=201)
def start_application(
    request: Request,
    db: DB,
    auth: CurrentAuth,
    _: AuthContext = Depends(require_permission("application:create")),
):
    existing = db.scalar(select(Application).where(Application.applicant_id == auth.user.id))
    application = _mine(db, auth, create=True)
    if existing is None:
        audit.add(
            db,
            request,
            "application.created",
            actor=auth.user,
            resource_type="application",
            resource_id=str(application.id),
        )
        db.commit()
        db.refresh(application)
    return application_payload(db, application)


@router.get("/mine", response_model=ApplicationOut)
def get_my_application(
    request: Request,
    db: DB,
    auth: CurrentAuth,
    _: AuthContext = Depends(require_permission("application:read_own")),
):
    application = _mine(db, auth)
    enforce_policy(request, auth, "application:read_own", _owned_resource(application))
    return application_payload(db, application)


@router.patch("/mine", response_model=ApplicationOut)
def save_application(
    body: ApplicationPatch,
    request: Request,
    db: DB,
    auth: CurrentAuth,
    _: AuthContext = Depends(require_permission("application:create")),
):
    application = _mine(db, auth, create=True)
    enforce_policy(request, auth, "application:create", _owned_resource(application))
    if application.status not in EDITABLE_STATUSES:
        raise AppError(409, "APPLICATION_LOCKED", "This application is not currently editable.")
    values = body.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(application, key, value)
    audit.add(
        db,
        request,
        "application.saved",
        actor=auth.user,
        resource_type="application",
        resource_id=str(application.id),
        details={"step": application.current_step, "fields": sorted(values)},
    )
    db.commit()
    db.refresh(application)
    return application_payload(db, application)


@router.post("/mine/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    request: Request,
    db: DB,
    auth: CurrentAuth,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    _: AuthContext = Depends(require_permission("application:create")),
):
    application = _mine(db, auth, create=True)
    enforce_policy(request, auth, "application:create", _owned_resource(application))
    if application.status not in EDITABLE_STATUSES:
        raise AppError(409, "APPLICATION_LOCKED", "Documents cannot be changed at this stage.")
    document_type = document_type.upper()
    if document_type not in DOCUMENT_TYPES:
        raise AppError(422, "INVALID_DOCUMENT_TYPE", "Unsupported document type.")
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise AppError(415, "UNSUPPORTED_FILE_TYPE", "Upload a PDF, JPEG, PNG, or WebP file.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise AppError(413, "FILE_TOO_LARGE", "Files must be between 1 byte and 10 MB.")
    quality = inspect_file(content, content_type)
    previous = db.scalar(
        select(Document)
        .where(Document.application_id == application.id, Document.document_type == document_type)
        .order_by(Document.version.desc())
        .limit(1)
    )
    version = (previous.version + 1) if previous else 1
    if previous and previous.superseded_at is None:
        previous.superseded_at = datetime.now(timezone.utc)
    document = Document(
        application_id=application.id,
        document_type=document_type,
        version=version,
        filename=(file.filename or f"{document_type.lower()}.{content_type.split('/')[-1]}")[:255],
        content_type=content_type,
        byte_size=len(content),
        sha256=sha256(content),
        content=content,
        quality_result=quality,
        status="UPLOADED" if quality["passed"] else "REUPLOAD_REQUESTED",
    )
    db.add(document)
    audit.add(
        db,
        request,
        "document.uploaded",
        actor=auth.user,
        resource_type="document",
        resource_id=str(document.id),
        details={"application_id": str(application.id), "type": document_type, "version": version, "quality": quality},
    )
    db.commit()
    db.refresh(document)
    return document


@router.get("/mine/documents/{document_id}/content")
def download_document(document_id: uuid.UUID, request: Request, db: DB, auth: CurrentAuth):
    document = db.get(Document, document_id)
    if document is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    application = db.get(Application, document.application_id)
    permission = "application:read_own" if auth.user.role.code == "APPLICANT" else "application:read_any"
    enforce_policy(request, auth, permission, _owned_resource(application))
    safe_name = document.filename.replace('"', "")
    return Response(
        document.content,
        media_type=document.content_type,
        headers={"Content-Disposition": f'inline; filename="{safe_name}"', "Cache-Control": "private, no-store"},
    )


@router.post("/mine/verifications", response_model=VerificationOut, status_code=202)
def request_verification(
    body: VerificationRequestIn,
    request: Request,
    db: DB,
    auth: CurrentAuth,
    _: AuthContext = Depends(require_permission("application:create")),
):
    if not body.consent:
        raise AppError(422, "CONSENT_REQUIRED", "Consent is required before contacting a verification provider.")
    application = _mine(db, auth)
    enforce_policy(request, auth, "application:create", _owned_resource(application))
    settings = get_settings()
    # Production never invents a provider outcome. Until contracted credentials are configured,
    # the durable record explicitly says NOT_CONFIGURED.
    environment = "SANDBOX" if settings.app_env != "production" else "PRODUCTION"
    status = "SANDBOX_RECORDED" if environment == "SANDBOX" else "NOT_CONFIGURED"
    verification = Verification(
        application_id=application.id,
        verification_type=body.verification_type,
        provider="PolicyNest adapter",
        environment=environment,
        status=status,
        result={
            "verified": False,
            "disclaimer": "No live registry, bank, DigiLocker, or biometric provider was contacted.",
        },
    )
    db.add(verification)
    audit.add(
        db,
        request,
        "verification.requested",
        actor=auth.user,
        resource_type="verification",
        resource_id=str(verification.id),
        details={"type": body.verification_type, "environment": environment, "status": status},
    )
    db.commit()
    db.refresh(verification)
    return verification


@router.post("/mine/submit", response_model=ApplicationOut)
def submit_application(
    request: Request,
    db: DB,
    auth: CurrentAuth,
    _: AuthContext = Depends(require_permission("application:create")),
):
    application = _mine(db, auth)
    enforce_policy(request, auth, "application:create", _owned_resource(application))
    if application.status not in EDITABLE_STATUSES:
        raise AppError(409, "APPLICATION_LOCKED", "This application cannot be submitted from its current state.")
    result = validate_submission(db, application)
    application.rule_result = result
    if not result["passed"]:
        db.commit()
        raise AppError(422, "APPLICATION_INCOMPLETE", "Complete all required fields and documents.", result["errors"])
    transition(db, application, "SUBMITTED", auth.user, "APPLICATION_SUBMITTED", {"rule_result": result})
    application.current_step = 4
    application.submitted_at = datetime.now(timezone.utc)
    audit.add(
        db,
        request,
        "application.submitted",
        actor=auth.user,
        resource_type="application",
        resource_id=str(application.id),
    )
    db.commit()
    db.refresh(application)
    return application_payload(db, application)
