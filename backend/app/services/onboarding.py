import hashlib
import io
import re
import secrets
from datetime import date, datetime, timezone
from typing import Any

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Application, ApplicationEvent, Document, User, Verification

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
DOCUMENT_TYPES = {"PAN", "AADHAAR", "EDUCATION_10TH", "PHOTO", "SIGNATURE", "BANK_PROOF"}
REQUIRED_DOCUMENTS = DOCUMENT_TYPES
EDITABLE_STATUSES = {"DRAFT", "CORRECTION_REQUIRED"}

STATUS_TRANSITIONS = {
    "DRAFT": {"SUBMITTED"},
    "CORRECTION_REQUIRED": {"SUBMITTED"},
    "SUBMITTED": {"UNDER_REVIEW", "CORRECTION_REQUIRED", "REJECTED", "ESCALATED"},
    "UNDER_REVIEW": {"CORRECTION_REQUIRED", "KYC_APPROVED", "REJECTED", "ESCALATED"},
    "ESCALATED": {"CORRECTION_REQUIRED", "KYC_APPROVED", "REJECTED"},
    "KYC_APPROVED": {"TRAINING_IN_PROGRESS"},
    "TRAINING_IN_PROGRESS": {"EXAM_ELIGIBLE"},
    "EXAM_ELIGIBLE": {"CERTIFIED"},
}


def new_reference() -> str:
    return f"PN-{datetime.now(timezone.utc):%Y%m}-{secrets.token_hex(4).upper()}"


def transition(
    db: Session, application: Application, to_status: str, actor: User, event_type: str, details=None
) -> None:
    allowed = STATUS_TRANSITIONS.get(application.status, set())
    if to_status not in allowed:
        raise AppError(409, "INVALID_TRANSITION", f"Cannot move from {application.status} to {to_status}.")
    previous = application.status
    application.status = to_status
    db.add(
        ApplicationEvent(
            application_id=application.id,
            actor_user_id=actor.id,
            event_type=event_type,
            from_status=previous,
            to_status=to_status,
            details=details or {},
        )
    )


def current_documents(db: Session, application_id) -> list[Document]:
    latest = (
        select(Document.document_type, func.max(Document.version).label("version"))
        .where(Document.application_id == application_id)
        .group_by(Document.document_type)
        .subquery()
    )
    return list(
        db.scalars(
            select(Document)
            .join(
                latest,
                (Document.document_type == latest.c.document_type) & (Document.version == latest.c.version),
            )
            .where(Document.application_id == application_id)
            .order_by(Document.document_type)
        )
    )


def validate_submission(db: Session, application: Application) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if not application.date_of_birth:
        errors.append({"field": "date_of_birth", "message": "Date of birth is required."})
    else:
        today = date.today()
        age = (
            today.year
            - application.date_of_birth.year
            - ((today.month, today.day) < (application.date_of_birth.month, application.date_of_birth.day))
        )
        if age < 18:
            errors.append({"field": "date_of_birth", "message": "Applicant must be at least 18 years old."})
    if not application.pan_number or not PAN_RE.fullmatch(application.pan_number):
        errors.append({"field": "pan_number", "message": "Enter a valid PAN."})
    elif application.pan_number[3] != "P":
        errors.append({"field": "pan_number", "message": "PAN must belong to an individual."})
    if not application.aadhaar_last4:
        errors.append({"field": "aadhaar_last4", "message": "Aadhaar last four digits are required."})
    if not application.region:
        errors.append({"field": "region", "message": "Operating region is required."})
    for field in ("address", "education", "bank_details", "declarations"):
        if not getattr(application, field):
            errors.append({"field": field, "message": f"{field.replace('_', ' ').title()} details are required."})
    if application.bank_details and not IFSC_RE.fullmatch(str(application.bank_details.get("ifsc", "")).upper()):
        errors.append({"field": "bank_details.ifsc", "message": "Enter a valid IFSC code."})
    docs = current_documents(db, application.id)
    present = {d.document_type for d in docs if d.status not in {"REJECTED", "REUPLOAD_REQUESTED"}}
    for missing in sorted(REQUIRED_DOCUMENTS - present):
        errors.append({"field": f"documents.{missing}", "message": f"Upload the required {missing} document."})
    failed_quality = [d.document_type for d in docs if d.status == "REUPLOAD_REQUESTED"]
    for item in failed_quality:
        errors.append({"field": f"documents.{item}", "message": "Document quality checks require a re-upload."})
    return {"passed": not errors, "errors": errors, "checked_at": datetime.now(timezone.utc).isoformat()}


def inspect_file(content: bytes, content_type: str) -> dict[str, Any]:
    if content_type == "application/pdf":
        if not content.startswith(b"%PDF-"):
            raise AppError(422, "FILE_SIGNATURE_MISMATCH", "The file is not a valid PDF.")
        return {"passed": True, "format": "PDF", "checks": {"signature": "PASS"}}
    try:
        image = Image.open(io.BytesIO(content))
        image.verify()
        image = Image.open(io.BytesIO(content)).convert("L")
    except (UnidentifiedImageError, OSError):
        raise AppError(422, "INVALID_IMAGE", "The uploaded file is not a valid image.") from None
    width, height = image.size
    stat = ImageStat.Stat(image)
    brightness = round(stat.mean[0], 2)
    contrast = round(stat.stddev[0], 2)
    edges = ImageStat.Stat(image.filter(ImageFilter.FIND_EDGES)).var[0]
    glare = sum(1 for px in image.resize((128, 128)).getdata() if px >= 250) / (128 * 128)
    reasons = []
    if width < 480 or height < 320:
        reasons.append("RESOLUTION_TOO_LOW")
    if contrast < 18:
        reasons.append("LOW_CONTRAST_OR_BLUR")
    if edges < 80:
        reasons.append("LIKELY_BLUR")
    if glare >= 0.15:
        reasons.append("EXCESSIVE_GLARE")
    return {
        "passed": not reasons,
        "format": image.format or content_type,
        "width": width,
        "height": height,
        "brightness": brightness,
        "contrast": contrast,
        "edge_variance": round(edges, 2),
        "glare_ratio": round(glare, 4),
        "reasons": reasons,
    }


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def application_payload(db: Session, application: Application) -> dict[str, Any]:
    verifications = list(
        db.scalars(
            select(Verification)
            .where(Verification.application_id == application.id)
            .order_by(Verification.requested_at.desc())
        )
    )
    return {
        "id": application.id,
        "applicant_id": application.applicant_id,
        "reference": application.reference,
        "status": application.status,
        "current_step": application.current_step,
        "region": application.region,
        "sensitivity": application.sensitivity,
        "date_of_birth": application.date_of_birth,
        "pan_number": application.pan_number,
        "aadhaar_last4": application.aadhaar_last4,
        "address": application.address,
        "education": application.education,
        "bank_details": application.bank_details,
        "declarations": application.declarations,
        "rule_result": application.rule_result,
        "submitted_at": application.submitted_at,
        "decided_at": application.decided_at,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
        "documents": current_documents(db, application.id),
        "verifications": verifications,
        "applicant_name": application.applicant.full_name,
        "applicant_email": application.applicant.email,
    }
