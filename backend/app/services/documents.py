"""Secure document upload validation, private storage persistence, and versioning."""

import hashlib
import re
import uuid
from pathlib import Path

from fastapi import Request, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import AuthContext
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Application, ApplicationDocument, ApplicationEvent
from app.models.application import EDITABLE_STATUSES, REQUIRED_DOC_TYPES
from app.services import audit
from app.services.storage import get_storage

MIN_UPLOAD_BYTES = 100

MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
}

ALLOWED_MIME_BY_TYPE: dict[str, set[str]] = {
    "PAN_CARD": {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    "AADHAAR_FRONT": {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    "AADHAAR_BACK": {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    "CLASS_10_MARKSHEET": {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    "BANK_DOCUMENT": {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    "APPLICANT_SELFIE": {"image/jpeg", "image/png", "image/webp"},
}

DOC_LABELS: dict[str, str] = {
    "PAN_CARD": "PAN card",
    "AADHAAR_FRONT": "Aadhaar front",
    "AADHAAR_BACK": "Aadhaar back",
    "CLASS_10_MARKSHEET": "Class 10 marksheet",
    "BANK_DOCUMENT": "Cancelled cheque / bank proof",
    "APPLICANT_SELFIE": "Applicant selfie",
}


def sniff_mime_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def sanitize_filename(filename: str | None, ext: str) -> str:
    raw = Path(filename or "").name.strip()
    cleaned = re.sub(r"[^A-Za-z0-9._\- ]+", "_", raw).strip(" .")
    if not cleaned:
        return f"document.{ext}"
    return cleaned[:150]


async def read_validated_upload(file: UploadFile, doc_type: str) -> tuple[bytes, str, str, str]:
    if doc_type not in REQUIRED_DOC_TYPES:
        raise AppError(400, "INVALID_DOC_TYPE", "Unsupported document type.")

    max_bytes = get_settings().max_upload_size_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 256)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise AppError(
                413,
                "FILE_TOO_LARGE",
                f"File exceeds the maximum upload size of {get_settings().max_upload_size_mb} MB.",
            )
        chunks.append(chunk)

    data = b"".join(chunks)
    if len(data) < MIN_UPLOAD_BYTES:
        raise AppError(422, "FILE_TOO_SMALL", "The uploaded file is empty or corrupted.")

    detected_mime = sniff_mime_type(data)
    allowed = ALLOWED_MIME_BY_TYPE[doc_type]
    if detected_mime is None or detected_mime not in allowed:
        expected = "JPG, PNG, or WebP image" if doc_type == "APPLICANT_SELFIE" else "JPG, PNG, WebP, or PDF"
        raise AppError(415, "UNSUPPORTED_FILE_TYPE", f"Upload a valid {expected} file.")

    ext = MIME_TO_EXT[detected_mime]
    safe_name = sanitize_filename(file.filename, ext)
    sha256_hex = hashlib.sha256(data).hexdigest()
    return data, detected_mime, safe_name, sha256_hex


def save_document_upload(
    db: Session,
    *,
    app: Application,
    doc_type: str,
    data: bytes,
    content_type: str,
    original_filename: str,
    sha256_hex: str,
    notes: str | None,
    auth: AuthContext,
    request: Request,
) -> ApplicationDocument:
    if app.status not in EDITABLE_STATUSES:
        raise AppError(
            409, "APPLICATION_LOCKED", "Documents cannot be modified after submission unless rework is requested."
        )

    # Lock parent application row to serialize version numbering per (application, doc_type).
    db.execute(select(Application.id).where(Application.id == app.id).with_for_update())
    max_version = (
        db.scalar(
            select(func.coalesce(func.max(ApplicationDocument.version), 0)).where(
                ApplicationDocument.application_id == app.id,
                ApplicationDocument.doc_type == doc_type,
            )
        )
        or 0
    )
    next_version = max_version + 1

    db.execute(
        update(ApplicationDocument)
        .where(
            ApplicationDocument.application_id == app.id,
            ApplicationDocument.doc_type == doc_type,
            ApplicationDocument.is_current.is_(True),
        )
        .values(is_current=False)
    )

    doc_id = uuid.uuid4()
    ext = MIME_TO_EXT[content_type]
    storage = get_storage()
    storage_key = f"applications/{app.id}/{doc_type}/{doc_id}.{ext}"
    storage.put_object(storage_key, data, content_type)

    doc = ApplicationDocument(
        id=doc_id,
        application_id=app.id,
        uploaded_by_user_id=auth.user.id,
        doc_type=doc_type,
        version=next_version,
        is_current=True,
        status="UPLOADED",
        original_filename=original_filename,
        content_type=content_type,
        file_size_bytes=len(data),
        sha256_hash=sha256_hex,
        storage_provider=storage.provider_name,
        storage_key=storage_key,
        notes=notes.strip()[:500] if notes and notes.strip() else None,
    )
    db.add(doc)

    event_type = "DOCUMENT_REPLACED" if next_version > 1 else "DOCUMENT_UPLOADED"
    label = DOC_LABELS.get(doc_type, doc_type)
    summary = f"{label} uploaded (v{next_version})."
    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type=event_type,
            from_status=app.status,
            to_status=app.status,
            summary=summary,
            details={
                "doc_id": str(doc.id),
                "doc_type": doc_type,
                "version": next_version,
                "content_type": content_type,
                "file_size_bytes": len(data),
                "sha256_hash": sha256_hex,
            },
        )
    )
    audit.add(
        db,
        request,
        f"document.{event_type.lower()}",
        actor=auth.user,
        resource_type="document",
        resource_id=str(doc.id),
        details={
            "application_id": str(app.id),
            "doc_type": doc_type,
            "version": next_version,
            "sha256_hash": sha256_hex,
        },
    )
    db.flush()
    return doc


def remove_draft_document(
    db: Session,
    *,
    app: Application,
    doc: ApplicationDocument,
    auth: AuthContext,
    request: Request,
) -> None:
    if app.status != "DRAFT":
        raise AppError(409, "APPLICATION_LOCKED", "Only draft documents can be removed.")
    if not doc.is_current:
        raise AppError(400, "NOT_CURRENT_DOCUMENT", "Only the current document version can be removed.")
    doc.is_current = False
    label = DOC_LABELS.get(doc.doc_type, doc.doc_type)
    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type="DOCUMENT_REMOVED",
            from_status=app.status,
            to_status=app.status,
            summary=f"{label} (v{doc.version}) removed from draft.",
            details={"doc_id": str(doc.id), "doc_type": doc.doc_type, "version": doc.version},
        )
    )
    audit.add(
        db,
        request,
        "document.removed",
        actor=auth.user,
        resource_type="document",
        resource_id=str(doc.id),
        details={"application_id": str(app.id), "doc_type": doc.doc_type, "version": doc.version},
    )
    db.flush()


def fetch_document_bytes(
    db: Session,
    *,
    app: Application,
    doc: ApplicationDocument,
    auth: AuthContext,
    request: Request,
    download: bool = False,
) -> bytes:
    storage = get_storage()
    try:
        data = storage.get_object(doc.storage_key)
    except FileNotFoundError as exc:
        raise AppError(404, "DOCUMENT_FILE_MISSING", "Stored document payload could not be located.") from exc

    audit.add(
        db,
        request,
        "document.downloaded" if download else "document.viewed",
        actor=auth.user,
        resource_type="document",
        resource_id=str(doc.id),
        details={"application_id": str(app.id), "doc_type": doc.doc_type, "version": doc.version},
    )
    return data
