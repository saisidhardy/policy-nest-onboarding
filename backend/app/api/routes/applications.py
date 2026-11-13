import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, AuthContext, enforce_policy, require_any_permission, require_permission
from app.core.errors import AppError
from app.models import Application, ApplicationDocument
from app.rbac.policy import Resource
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationDetailOut,
    ApplicationDraftUpdate,
    ApplicationEventOut,
    ApplicationSubmitRequest,
    ApplicationSummaryOut,
    DocumentOut,
    WithdrawApplicationRequest,
)
from app.schemas.common import Message
from app.services import applications as app_service
from app.services import documents as doc_service
from app.services.india_geo import INDIAN_STATES

router = APIRouter(prefix="/applications", tags=["applications"])


def _app_resource(app: Application) -> Resource:
    return app_service.application_resource(app)


def _read_perm(auth: AuthContext) -> str:
    return app_service.resolve_read_permission(auth)


@router.get("/metadata/states", summary="Authoritative Indian states and UTs list")
def list_states() -> dict[str, list[str]]:
    return {"states": INDIAN_STATES}


@router.get("", response_model=list[ApplicationSummaryOut])
def list_applications(
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any")),
):
    stmt = select(Application).options(selectinload(Application.documents))
    if "application:read_any" in auth.permissions:
        if auth.user.region not in (None, "ALL"):
            stmt = stmt.where(Application.region == auth.user.region)
        stmt = stmt.where(Application.sensitivity <= auth.user.clearance_level)
    else:
        stmt = stmt.where(Application.user_id == auth.user.id)

    rows = db.scalars(stmt.order_by(Application.created_at.desc())).all()
    return [app_service.to_summary(a) for a in rows]


@router.post("", response_model=ApplicationDetailOut, status_code=status.HTTP_201_CREATED)
def create_application(
    body: ApplicationCreateRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:create")),
):
    app = app_service.create_application(db, body, auth, request)
    return app_service.to_detail(app)


@router.get("/current", response_model=ApplicationDetailOut | None)
def get_current_application(
    db: DB,
    auth: AuthContext = Depends(require_permission("application:read_own")),
):
    app = db.scalar(
        select(Application)
        .options(selectinload(Application.documents), selectinload(Application.events))
        .where(Application.user_id == auth.user.id, Application.status != "WITHDRAWN")
        .order_by(Application.created_at.desc())
        .limit(1)
    )
    if app is None:
        return None
    return app_service.to_detail(app)


@router.get("/{application_id}", response_model=ApplicationDetailOut)
def get_application_detail(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, _read_perm(auth), _app_resource(app))
    return app_service.to_detail(app)


@router.patch("/{application_id}", response_model=ApplicationDetailOut)
def update_application_draft(
    application_id: uuid.UUID,
    body: ApplicationDraftUpdate,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:create")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "application:create", _app_resource(app))
    updated = app_service.update_draft(db, app, body, auth, request)
    return app_service.to_detail(updated)


@router.post("/{application_id}/submit", response_model=ApplicationDetailOut)
def submit_application(
    application_id: uuid.UUID,
    body: ApplicationSubmitRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:create")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "application:create", _app_resource(app))
    submitted = app_service.submit_application(db, app, body, auth, request)
    return app_service.to_detail(submitted)


@router.post("/{application_id}/withdraw", response_model=ApplicationDetailOut)
def withdraw_application(
    application_id: uuid.UUID,
    body: WithdrawApplicationRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:create")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "application:create", _app_resource(app))
    withdrawn = app_service.withdraw_application(db, app, body.reason, auth, request)
    return app_service.to_detail(withdrawn)


@router.get("/{application_id}/history", response_model=list[ApplicationEventOut])
def get_application_history(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, _read_perm(auth), _app_resource(app))
    return [ApplicationEventOut.model_validate(e) for e in app.events]


@router.get("/{application_id}/documents", response_model=list[DocumentOut])
def list_application_documents(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any")),
    include_history: bool = Query(default=False),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, _read_perm(auth), _app_resource(app))
    docs = app.documents if include_history else [d for d in app.documents if d.is_current]
    return [DocumentOut.model_validate(d) for d in docs]


@router.post("/{application_id}/documents/{doc_type}", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_application_document(
    application_id: uuid.UUID,
    doc_type: str,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:create")),
    file: UploadFile = File(...),
    notes: str | None = Form(default=None),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "application:create", _app_resource(app))
    data, content_type, safe_name, sha256_hex = await doc_service.read_validated_upload(file, doc_type)
    from app.services import verification as verification_service

    precomputed = verification_service.validate_upload_classification(
        db,
        doc_type=doc_type,
        content_type=content_type,
        raw_bytes=data,
    )
    doc = doc_service.save_document_upload(
        db,
        app=app,
        doc_type=doc_type,
        data=data,
        content_type=content_type,
        original_filename=safe_name,
        sha256_hex=sha256_hex,
        notes=notes,
        auth=auth,
        request=request,
    )
    ext_out = verification_service.process_uploaded_document(
        db,
        app,
        doc,
        auth,
        request,
        precomputed_res=precomputed,
    )
    out = DocumentOut.model_validate(doc)
    out.extraction = ext_out
    return out


@router.get("/{application_id}/documents/{document_id}/content")
def download_document_content(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any")),
    download: bool = Query(default=False),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, _read_perm(auth), _app_resource(app))
    doc = db.scalar(
        select(ApplicationDocument).where(
            ApplicationDocument.id == document_id,
            ApplicationDocument.application_id == app.id,
        )
    )
    if doc is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    data = doc_service.fetch_document_bytes(db, app=app, doc=doc, auth=auth, request=request, download=download)
    disposition = "attachment" if download else "inline"
    return Response(
        content=data,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{doc.original_filename}"',
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{application_id}/documents/{document_id}", response_model=Message)
def delete_draft_document(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:create")),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, "application:create", _app_resource(app))
    doc = db.scalar(
        select(ApplicationDocument).where(
            ApplicationDocument.id == document_id,
            ApplicationDocument.application_id == app.id,
        )
    )
    if doc is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    doc_service.remove_draft_document(db, app=app, doc=doc, auth=auth, request=request)
    return Message(message="Document removed from draft.")
