import html
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, AuthContext, enforce_policy, require_any_permission, require_permission
from app.core.errors import AppError
from app.models import Application, ApplicationDocument, RuleExecution, TrainingRecord
from app.models.base import utcnow
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


@router.get("/{application_id}/dossier")
def get_application_dossier(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_any_permission("application:read_own", "application:read_any")),
    format: str = Query(default="html", pattern="^(html|json)$"),
):
    app = app_service.get_application(db, application_id)
    enforce_policy(request, auth, _read_perm(auth), _app_resource(app))

    training_rec = db.scalar(
        select(TrainingRecord).where(TrainingRecord.application_id == app.id)
    )
    rule_exec = db.scalar(
        select(RuleExecution)
        .where(RuleExecution.application_id == app.id)
        .order_by(RuleExecution.executed_at.desc())
        .limit(1)
    )

    dossier_data = {
        "reference_code": app.reference_code,
        "candidate_name": app.full_name or "N/A",
        "status": app.status,
        "dob": app.date_of_birth.isoformat() if app.date_of_birth else "N/A",
        "gender": app.gender or "N/A",
        "mobile": app.mobile or "N/A",
        "email": app.email or "N/A",
        "pan_number": app.pan_number or "N/A",
        "aadhaar_masked": f"XXXX-XXXX-{app.aadhaar_last4}" if app.aadhaar_last4 else "N/A",
        "address": f"{app.address_line1 or ''}, {app.city or ''}, {app.state or ''} - {app.pincode or ''}".strip(", "),
        "education": f"{app.education_level or 'N/A'} - {app.board_name or ''} (Passing Year: {app.passing_year or 'N/A'})",
        "bank": f"{app.bank_name or 'N/A'} (IFSC: {app.ifsc_code or 'N/A'}, Account: {app.account_number_masked or 'N/A'})",
        "rules_outcome": rule_exec.outcome if rule_exec else "PENDING",
        "training_status": training_rec.certification_status if training_rec else "NOT_ENROLLED",
        "certificate_number": training_rec.certificate_number if training_rec else "N/A",
        "certified_at": training_rec.certified_at.strftime("%d %B %Y") if training_rec and training_rec.certified_at else "N/A",
        "generated_at": utcnow().strftime("%d %B %Y %H:%M:%S UTC"),
    }

    if format == "json":
        return dossier_data

    safe_name = html.escape(dossier_data["candidate_name"])
    safe_ref = html.escape(dossier_data["reference_code"])
    safe_pan = html.escape(dossier_data["pan_number"])
    safe_aadhaar = html.escape(dossier_data["aadhaar_masked"])
    safe_cert = html.escape(str(dossier_data["certificate_number"]))

    statutory_text = (
        "The candidate named herein has completed the mandatory onboarding verification, "
        "background screening, and IRDAI 15-hour training curriculum. Under the Insurance Regulatory and "
        "Development Authority of India (Point of Sales Person) Guidelines, 2016, this individual is registered "
        "to solicit approved Point of Sales insurance products on behalf of PolicyNest Insurance Broking."
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>POSP Appointment Dossier - {safe_ref}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 40px; color: #1e293b; line-height: 1.5; }}
  .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0f172a; padding-bottom: 16px; margin-bottom: 24px; }}
  .brand {{ font-size: 24px; font-weight: 800; color: #102C57; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 700; background: #e0f2fe; color: #0369a1; text-transform: uppercase; }}
  .badge.approved {{ background: #dcfce7; color: #15803d; }}
  .section {{ margin-bottom: 24px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; background: #fafafa; }}
  .section-title {{ font-size: 14px; font-weight: 700; color: #475569; text-transform: uppercase; margin-bottom: 12px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 13px; }}
  .label {{ font-weight: 600; color: #64748b; }}
  .val {{ font-weight: 700; color: #0f172a; }}
  .declaration {{ font-size: 12px; color: #475569; line-height: 1.6; border-left: 4px solid #102C57; padding-left: 12px; margin-top: 16px; font-style: italic; }}
  .footer {{ margin-top: 40px; font-size: 11px; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 16px; }}
  @media print {{ body {{ margin: 20px; }} .no-print {{ display: none; }} }}
</style>
</head>
<body>
<div class="no-print" style="margin-bottom: 20px;">
  <button onclick="window.print()" style="padding: 8px 16px; background: #102C57; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer;">🖨️ Print / Save as PDF</button>
</div>
<div class="header">
  <div>
    <div class="brand">PolicyNest Insurance Broking</div>
    <div style="font-size: 13px; color: #64748b; margin-top: 4px;">IRDAI Registered Direct Insurance Broker (Life & General)</div>
  </div>
  <div style="text-align: right;">
    <div class="badge approved">{html.escape(dossier_data["status"])}</div>
    <div style="font-size: 12px; color: #64748b; margin-top: 4px;">Ref: <strong>{safe_ref}</strong></div>
  </div>
</div>

<h2 style="font-size: 18px; font-weight: 700; margin-bottom: 16px;">Form of Appointment & Onboarding Dossier — Point of Sales Person (POSP)</h2>

<div class="section">
  <div class="section-title">1. Candidate Identity & Personal Details</div>
  <div class="grid">
    <div><span class="label">Full Name:</span> <span class="val">{safe_name}</span></div>
    <div><span class="label">Date of Birth:</span> <span class="val">{html.escape(dossier_data["dob"])}</span></div>
    <div><span class="label">Gender:</span> <span class="val">{html.escape(dossier_data["gender"])}</span></div>
    <div><span class="label">PAN Number:</span> <span class="val">{safe_pan}</span></div>
    <div><span class="label">Aadhaar (DPDP Masked):</span> <span class="val">{safe_aadhaar}</span></div>
    <div><span class="label">Mobile Number:</span> <span class="val">{html.escape(dossier_data["mobile"])}</span></div>
    <div><span class="label">Email Address:</span> <span class="val">{html.escape(dossier_data["email"])}</span></div>
    <div><span class="label">Residential Address:</span> <span class="val">{html.escape(dossier_data["address"])}</span></div>
  </div>
</div>

<div class="section">
  <div class="section-title">2. Qualification & Banking Verification</div>
  <div class="grid">
    <div><span class="label">Minimum Education:</span> <span class="val">{html.escape(dossier_data["education"])}</span></div>
    <div><span class="label">Direct Bank Account:</span> <span class="val">{html.escape(dossier_data["bank"])}</span></div>
    <div><span class="label">Rules Engine Outcome:</span> <span class="val">{html.escape(str(dossier_data["rules_outcome"]))}</span></div>
  </div>
</div>

<div class="section">
  <div class="section-title">3. IRDAI 15-Hour POSP Training & Assessment Record</div>
  <div class="grid">
    <div><span class="label">Certification Status:</span> <span class="val">{html.escape(str(dossier_data["training_status"]))}</span></div>
    <div><span class="label">Certificate Number:</span> <span class="val">{safe_cert}</span></div>
    <div><span class="label">Mandatory Hours:</span> <span class="val">15.00 Hours Completed</span></div>
    <div><span class="label">Date Certified:</span> <span class="val">{html.escape(str(dossier_data["certified_at"]))}</span></div>
  </div>
</div>

<div class="declaration">
  <strong>Statutory Appointment Declaration:</strong> {statutory_text}
</div>

<div class="footer">
  This is a computer-generated official compliance dossier issued on {html.escape(dossier_data["generated_at"])}. Certificate authenticity can be verified at: /verify-certificate?number={safe_cert}
</div>
</body>
</html>"""

    return Response(content=html_content, media_type="text/html")
