import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from app.api.deps import DB, AuthContext, enforce_policy, require_any_permission, require_permission
from app.core.errors import AppError
from app.models import ApplicationDocument
from app.schemas.verification import ApplicationVerificationOut, ReviewerFieldCorrectionRequest
from app.services import applications as app_service
from app.services import verification as verification_service

router = APIRouter(prefix="/applications", tags=["verifications"])


def _get_app_doc(db: DB, application_id: uuid.UUID, document_id: uuid.UUID) -> ApplicationDocument:
    doc = db.scalar(
        select(ApplicationDocument).where(
            ApplicationDocument.id == document_id,
            ApplicationDocument.application_id == application_id,
        )
    )
    if doc is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    return doc


@router.post("/{application_id}/process", response_model=ApplicationVerificationOut)
def process_application_documents(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:create", "application:review")),
):
    app = app_service.get_application(db, application_id)
    action = "application:review" if "application:review" in auth.permissions else "application:create"
    enforce_policy(request, auth, action, app_service.application_resource(app))
    return verification_service.run_document_intelligence(db, app, auth, request)


@router.get("/{application_id}/verification", response_model=ApplicationVerificationOut)
def get_application_verification(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(
        request,
        auth,
        app_service.resolve_read_permission(auth),
        app_service.application_resource(app),
    )
    return verification_service.build_verification_report(db, app)


@router.get("/{application_id}/documents/{document_id}/redacted")
def get_redacted_document_image(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(
        request,
        auth,
        app_service.resolve_read_permission(auth),
        app_service.application_resource(app),
    )
    doc = _get_app_doc(db, app.id, document_id)
    content = verification_service.get_redacted_document_bytes(db, app, doc, auth, request)
    return Response(
        content=content,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="redacted_{doc.doc_type.lower()}.png"',
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "Cache-Control": "private, no-store",
        },
    )


@router.patch("/{application_id}/documents/{document_id}/fields", response_model=ApplicationVerificationOut)
def correct_extracted_fields(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    body: ReviewerFieldCorrectionRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:review")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "application:review", app_service.application_resource(app))
    doc = _get_app_doc(db, app.id, document_id)
    return verification_service.apply_reviewer_field_corrections(db, app, doc, body, auth, request)
