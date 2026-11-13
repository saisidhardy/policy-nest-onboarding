"""Phase 3 document intelligence orchestration, verification persistence, and reviewer corrections."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext
from app.core.errors import AppError
from app.models import (
    Application,
    ApplicationDocument,
    ApplicationEvent,
    DocumentExtraction,
    DocumentFieldCorrection,
    VerificationCheck,
)
from app.models.application import REQUIRED_DOC_TYPES
from app.models.base import utcnow
from app.schemas.verification import (
    ApplicationVerificationOut,
    DocumentExtractionOut,
    FieldCorrectionOut,
    ReviewerFieldCorrectionRequest,
    VerificationCheckOut,
    VerificationSummaryOut,
)
from app.services import audit
from app.services.ai_assistant import get_ai_assistant
from app.services.consistency import evaluate_cross_document_consistency
from app.services.ocr_pipeline import EXPECTED_FIELDS_BY_DOC, OcrPipelineResult, process_document_bytes
from app.services.storage import get_storage
from app.services.verification_providers import (
    ProviderCheckResult,
    check_bank_penny_drop_adapter,
    check_digilocker_adapter,
    check_face_match_adapter,
    check_pan_verification_adapter,
    evaluate_selfie_id_face_comparison,
    lookup_ifsc_directory,
)

DOC_ORDER = {doc_type: idx for idx, doc_type in enumerate(REQUIRED_DOC_TYPES)}


def _compute_missing_fields(doc_type: str, fields: dict[str, Any]) -> list[str]:
    expected = EXPECTED_FIELDS_BY_DOC.get(doc_type, [])
    return [f for f in expected if not fields.get(f) or (f == "face_detected" and str(fields[f]).lower() != "true")]


def _current_docs(db: Session, application_id: uuid.UUID) -> list[ApplicationDocument]:
    docs = list(
        db.scalars(
            select(ApplicationDocument).where(
                ApplicationDocument.application_id == application_id,
                ApplicationDocument.is_current.is_(True),
            )
        ).all()
    )
    docs.sort(key=lambda d: (DOC_ORDER.get(d.doc_type, 99), d.doc_type))
    return docs


def _recompute_checks(
    db: Session,
    app: Application,
    docs_with_ext: list[tuple[ApplicationDocument, DocumentExtraction]],
) -> list[VerificationCheck]:
    effective_by_type: dict[str, dict[str, Any]] = {
        doc.doc_type: dict(ext.effective_fields or {}) for doc, ext in docs_with_ext
    }
    selfie_ext = next((ext for doc, ext in docs_with_ext if doc.doc_type == "APPLICANT_SELFIE"), None)
    selfie_face_val = None
    if selfie_ext is not None:
        raw_face = (selfie_ext.effective_fields or {}).get("face_detected")
        if raw_face is not None:
            selfie_face_val = str(raw_face).lower() == "true"
        else:
            selfie_face_val = selfie_ext.face_detected

    outcomes = evaluate_cross_document_consistency(app, effective_by_type)

    ifsc_code = effective_by_type.get("BANK_DOCUMENT", {}).get("ifsc_code") or app.ifsc_code
    pan_number = effective_by_type.get("PAN_CARD", {}).get("pan_number") or app.pan_number
    holder_name = effective_by_type.get("BANK_DOCUMENT", {}).get("full_name") or app.account_holder_name

    provider_results: list[ProviderCheckResult] = [
        lookup_ifsc_directory(str(ifsc_code) if ifsc_code else None, db=db),
        check_pan_verification_adapter(
            str(pan_number) if pan_number else None,
            full_name=app.full_name,
            db=db,
        ),
        check_bank_penny_drop_adapter(
            str(ifsc_code) if ifsc_code else None,
            str(holder_name) if holder_name else None,
            account_last4=app.account_number_last4,
            db=db,
        ),
        check_digilocker_adapter(application_id=str(app.id), db=db),
        check_face_match_adapter(selfie_face_val, application_id=str(app.id), db=db),
        evaluate_selfie_id_face_comparison({doc.doc_type: doc for doc, _ in docs_with_ext}, db=db),
    ]

    db.execute(delete(VerificationCheck).where(VerificationCheck.application_id == app.id))

    created: list[VerificationCheck] = []
    for o in outcomes:
        row = VerificationCheck(
            application_id=app.id,
            check_type=o.check_type,
            target_doc_type=o.target_doc_type,
            status=o.status,
            origin=o.origin,
            provider_name="policynest_rules",
            provider_reference=None,
            is_simulated=False,
            confidence=o.confidence,
            details=o.details,
            explanation=o.explanation,
        )
        db.add(row)
        created.append(row)

    for p in provider_results:
        row = VerificationCheck(
            application_id=app.id,
            check_type=p.check_type,
            target_doc_type=p.target_doc_type,
            status=p.status,
            origin=p.origin,
            provider_name=p.provider_name,
            provider_reference=p.provider_reference,
            is_simulated=p.is_simulated,
            confidence=p.confidence,
            details=p.details,
            explanation=p.explanation,
        )
        db.add(row)
        created.append(row)

    db.flush()
    return created


def build_verification_report(db: Session, app: Application) -> ApplicationVerificationOut:
    docs = _current_docs(db, app.id)
    doc_by_id = {d.id: d for d in docs}
    extractions_raw = list(
        db.scalars(select(DocumentExtraction).where(DocumentExtraction.application_id == app.id)).all()
    )
    current_extractions = [e for e in extractions_raw if e.document_id in doc_by_id]
    current_extractions.sort(key=lambda e: DOC_ORDER.get(doc_by_id[e.document_id].doc_type, 99))

    checks = list(
        db.scalars(
            select(VerificationCheck)
            .where(VerificationCheck.application_id == app.id)
            .order_by(VerificationCheck.check_type.asc(), VerificationCheck.target_doc_type.asc())
        ).all()
    )
    corrections = list(
        db.scalars(
            select(DocumentFieldCorrection)
            .where(DocumentFieldCorrection.application_id == app.id)
            .order_by(DocumentFieldCorrection.created_at.desc(), DocumentFieldCorrection.id.desc())
        ).all()
    )

    extraction_outs = [
        DocumentExtractionOut(
            id=e.id,
            document_id=e.document_id,
            doc_type=doc_by_id[e.document_id].doc_type,
            application_id=e.application_id,
            ocr_engine=e.ocr_engine,
            ai_assistant_provider=e.ai_assistant_provider,
            predicted_doc_type=e.predicted_doc_type,
            classification_confidence=e.classification_confidence,
            classification_match=e.classification_match,
            quality_status=e.quality_status,
            blur_score=e.blur_score,
            glare_ratio=e.glare_ratio,
            edge_clip_ratio=e.edge_clip_ratio,
            face_detected=e.face_detected,
            ocr_confidence=e.ocr_confidence,
            raw_ocr_text_masked=e.raw_ocr_text_masked,
            extracted_fields=e.extracted_fields,
            missing_fields=e.missing_fields,
            ai_explanation=e.ai_explanation,
            aadhaar_masked_applied=e.aadhaar_masked_applied,
            has_redacted_image=bool(e.redacted_storage_key),
            reviewer_corrected_fields=e.reviewer_corrected_fields,
            effective_fields=e.effective_fields,
            corrected_by_user_id=e.corrected_by_user_id,
            corrected_at=e.corrected_at,
            processed_at=e.processed_at,
        )
        for e in current_extractions
    ]

    q_passed = sum(1 for e in extraction_outs if e.quality_status == "OK" and e.classification_match is not False)
    q_warn = sum(
        1
        for e in extraction_outs
        if (e.quality_status == "OK" and e.classification_match is False)
        or e.quality_status in ("IMAGE_GLARE", "IMAGE_CROPPED")
    )
    q_failed = len(extraction_outs) - q_passed - q_warn

    summary = VerificationSummaryOut(
        documents_processed=len(extraction_outs),
        quality_passed=q_passed,
        quality_warn=q_warn,
        quality_failed=q_failed,
        checks_passed=sum(1 for c in checks if c.status == "PASSED"),
        checks_warn=sum(1 for c in checks if c.status in ("WARN", "UNAVAILABLE")),
        checks_needs_info=sum(1 for c in checks if c.status == "NEEDS_INFO"),
        checks_failed=sum(1 for c in checks if c.status == "FAILED"),
        checks_not_configured=sum(1 for c in checks if c.status == "NOT_CONFIGURED"),
        advisory_note=(
            "OCR and AI outputs assist extraction and triage only; deterministic business rules and "
            "authorized human reviewers govern all onboarding decisions."
        ),
    )

    return ApplicationVerificationOut(
        application_id=app.id,
        reference_code=app.reference_code,
        status=app.status,
        extractions=extraction_outs,
        checks=[VerificationCheckOut.model_validate(c) for c in checks],
        corrections=[FieldCorrectionOut.model_validate(c) for c in corrections],
        summary=summary,
    )


def _to_extraction_out(ext: DocumentExtraction, doc_type: str) -> DocumentExtractionOut:
    return DocumentExtractionOut(
        id=ext.id,
        document_id=ext.document_id,
        doc_type=doc_type,
        application_id=ext.application_id,
        ocr_engine=ext.ocr_engine,
        ai_assistant_provider=ext.ai_assistant_provider,
        predicted_doc_type=ext.predicted_doc_type,
        classification_confidence=ext.classification_confidence,
        classification_match=ext.classification_match,
        quality_status=ext.quality_status,
        blur_score=ext.blur_score,
        glare_ratio=ext.glare_ratio,
        edge_clip_ratio=ext.edge_clip_ratio,
        face_detected=ext.face_detected,
        ocr_confidence=ext.ocr_confidence,
        raw_ocr_text_masked=ext.raw_ocr_text_masked,
        extracted_fields=ext.extracted_fields,
        missing_fields=ext.missing_fields,
        ai_explanation=ext.ai_explanation,
        aadhaar_masked_applied=ext.aadhaar_masked_applied,
        has_redacted_image=bool(ext.redacted_storage_key),
        reviewer_corrected_fields=ext.reviewer_corrected_fields,
        effective_fields=ext.effective_fields,
        corrected_by_user_id=ext.corrected_by_user_id,
        corrected_at=ext.corrected_at,
        processed_at=ext.processed_at,
    )


def inspect_document_payload(
    db: Session,
    *,
    doc_type: str,
    content_type: str,
    raw_bytes: bytes,
) -> OcrPipelineResult:
    """Run CV quality, OCR extraction, and optional Gemini Vision upgrade on raw bytes."""
    from app.services.gemini_vision import enhance_ocr_result_with_gemini_vision
    from app.services.platform_config import get_effective_integrations_config

    res = process_document_bytes(doc_type, content_type, raw_bytes, db=db)
    return enhance_ocr_result_with_gemini_vision(
        doc_type=doc_type,
        content_type=content_type,
        raw_bytes=raw_bytes,
        res=res,
        cfg=get_effective_integrations_config(db),
    )


def validate_upload_classification(
    db: Session,
    *,
    doc_type: str,
    content_type: str,
    raw_bytes: bytes,
) -> OcrPipelineResult:
    """Inspect an incoming upload before persistence and reject confident wrong-slot documents."""
    from app.services.documents import DOC_LABELS

    res = inspect_document_payload(db, doc_type=doc_type, content_type=content_type, raw_bytes=raw_bytes)
    if (
        res.predicted_doc_type not in (None, "UNKNOWN", doc_type)
        and (res.classification_confidence or 0.0) >= 0.55
    ):
        pred_label = DOC_LABELS.get(str(res.predicted_doc_type), str(res.predicted_doc_type))
        expected_label = DOC_LABELS.get(doc_type, doc_type)
        raise AppError(
            422,
            "DOCUMENT_TYPE_MISMATCH",
            f"Uploaded file appears to be {pred_label}, not {expected_label}. Please upload your {expected_label} in this slot.",
            details={
                "expected_doc_type": doc_type,
                "predicted_doc_type": res.predicted_doc_type,
                "confidence": res.classification_confidence,
            },
        )
    return res


def _process_single_document_record(
    db: Session,
    app: Application,
    doc: ApplicationDocument,
    assistant,
    storage,
    existing: DocumentExtraction | None,
    now,
    *,
    precomputed_res: OcrPipelineResult | None = None,
) -> DocumentExtraction:
    if precomputed_res is not None:
        res = precomputed_res
    else:
        try:
            raw_bytes = storage.get_object(doc.storage_key)
        except FileNotFoundError as exc:
            raise AppError(
                404,
                "DOCUMENT_FILE_MISSING",
                f"Stored file for {doc.doc_type} could not be located in private storage.",
            ) from exc

        res = inspect_document_payload(
            db,
            doc_type=doc.doc_type,
            content_type=doc.content_type,
            raw_bytes=raw_bytes,
        )

    redacted_key: str | None = None
    if res.redacted_image_bytes:
        redacted_key = f"applications/{app.id}/redacted/{doc.id}.png"
        storage.put_object(redacted_key, res.redacted_image_bytes, "image/png")

    ai_res = assistant.summarize_document(
        doc_type=doc.doc_type,
        quality_status=res.quality.quality_status,
        ocr_confidence=res.ocr_confidence,
        extracted_fields=res.extracted_fields,
        missing_fields=res.missing_fields,
        masked_ocr_text=res.raw_ocr_text_masked,
    )
    if res.classification_match is False and res.predicted_doc_type not in (None, "UNKNOWN", doc.doc_type):
        ai_res_explanation = (
            f"Document mismatch warning: uploaded file looks like {res.predicted_doc_type} instead of {doc.doc_type}. "
            + ai_res.explanation
        )
    elif res.ocr_engine == "OCR_UNAVAILABLE":
        ai_res_explanation = (
            f"Quality status: {res.quality.quality_status}. Automated text OCR could not run on this server "
            "(Tesseract binary is absent and GEMINI_API_KEY / HTTP OCR is not configured). "
            "Configure GEMINI_API_KEY for full AI document reading."
        )
    else:
        ai_res_explanation = ai_res.explanation

    if existing is not None:
        corrected = dict(existing.reviewer_corrected_fields or {})
        effective = {**res.extracted_fields, **corrected}
        missing = _compute_missing_fields(doc.doc_type, effective)
        existing.ocr_engine = res.ocr_engine
        existing.ai_assistant_provider = ai_res.provider
        existing.predicted_doc_type = res.predicted_doc_type
        existing.classification_confidence = res.classification_confidence
        existing.classification_match = res.classification_match
        existing.quality_status = res.quality.quality_status
        existing.blur_score = res.quality.blur_score
        existing.glare_ratio = res.quality.glare_ratio
        existing.edge_clip_ratio = res.quality.edge_clip_ratio
        existing.face_detected = res.quality.face_detected
        existing.ocr_confidence = res.ocr_confidence
        existing.raw_ocr_text_masked = res.raw_ocr_text_masked
        existing.extracted_fields = res.extracted_fields
        existing.missing_fields = missing
        existing.ai_explanation = ai_res_explanation
        existing.aadhaar_masked_applied = res.aadhaar_masked_applied
        existing.redacted_storage_key = redacted_key or existing.redacted_storage_key
        existing.effective_fields = effective
        existing.processed_at = now
        return existing

    ext_row = DocumentExtraction(
        document_id=doc.id,
        application_id=app.id,
        ocr_engine=res.ocr_engine,
        ai_assistant_provider=ai_res.provider,
        predicted_doc_type=res.predicted_doc_type,
        classification_confidence=res.classification_confidence,
        classification_match=res.classification_match,
        quality_status=res.quality.quality_status,
        blur_score=res.quality.blur_score,
        glare_ratio=res.quality.glare_ratio,
        edge_clip_ratio=res.quality.edge_clip_ratio,
        face_detected=res.quality.face_detected,
        ocr_confidence=res.ocr_confidence,
        raw_ocr_text_masked=res.raw_ocr_text_masked,
        extracted_fields=res.extracted_fields,
        missing_fields=res.missing_fields,
        ai_explanation=ai_res_explanation,
        aadhaar_masked_applied=res.aadhaar_masked_applied,
        redacted_storage_key=redacted_key,
        reviewer_corrected_fields=None,
        effective_fields=dict(res.extracted_fields),
        processed_at=now,
    )
    db.add(ext_row)
    return ext_row


def process_uploaded_document(
    db: Session,
    app: Application,
    doc: ApplicationDocument,
    auth: AuthContext,
    request: Request,
    *,
    precomputed_res: OcrPipelineResult | None = None,
) -> DocumentExtractionOut:
    """Immediately inspect quality, run OCR/vision extraction, and refresh verification checks on upload."""
    storage = get_storage()
    assistant = get_ai_assistant(db)
    existing = db.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == doc.id))
    ext_row = _process_single_document_record(
        db,
        app,
        doc,
        assistant,
        storage,
        existing,
        utcnow(),
        precomputed_res=precomputed_res,
    )
    db.flush()

    docs = _current_docs(db, app.id)
    ext_by_doc_id = {
        e.document_id: e
        for e in db.scalars(select(DocumentExtraction).where(DocumentExtraction.application_id == app.id)).all()
    }
    docs_with_ext = [(d, ext_by_doc_id[d.id]) for d in docs if d.id in ext_by_doc_id]
    _recompute_checks(db, app, docs_with_ext)
    db.flush()
    return _to_extraction_out(ext_row, doc.doc_type)


def run_document_intelligence(
    db: Session,
    app: Application,
    auth: AuthContext,
    request: Request,
    *,
    record_event: bool = True,
) -> ApplicationVerificationOut:
    docs = _current_docs(db, app.id)
    if not docs:
        raise AppError(
            400,
            "NO_DOCUMENTS_UPLOADED",
            "Upload at least one document before running document verification.",
        )

    storage = get_storage()
    assistant = get_ai_assistant(db)
    existing_by_doc_id = {
        ext.document_id: ext
        for ext in db.scalars(select(DocumentExtraction).where(DocumentExtraction.application_id == app.id)).all()
    }

    now = utcnow()
    docs_with_ext: list[tuple[ApplicationDocument, DocumentExtraction]] = []

    for doc in docs:
        ext_row = _process_single_document_record(
            db,
            app,
            doc,
            assistant,
            storage,
            existing_by_doc_id.get(doc.id),
            now,
        )
        docs_with_ext.append((doc, ext_row))

    db.flush()
    checks = _recompute_checks(db, app, docs_with_ext)

    if record_event:
        db.add(
            ApplicationEvent(
                application_id=app.id,
                actor_user_id=auth.user.id,
                actor_role=auth.user.role.code,
                event_type="DOCUMENT_INTELLIGENCE_RAN",
                from_status=app.status,
                to_status=app.status,
                summary=f"Document intelligence processed {len(docs_with_ext)} document(s) and recorded {len(checks)} verification check(s).",
                details={
                    "documents_processed": len(docs_with_ext),
                    "checks_recorded": len(checks),
                    "ocr_engine": docs_with_ext[0][1].ocr_engine if docs_with_ext else None,
                    "ai_provider": assistant.provider_name,
                },
            )
        )
    audit.add(
        db,
        request,
        "document.intelligence_ran",
        actor=auth.user,
        resource_type="application",
        resource_id=str(app.id),
        details={
            "reference_code": app.reference_code,
            "documents_processed": len(docs_with_ext),
            "checks_recorded": len(checks),
        },
    )
    db.flush()
    return build_verification_report(db, app)


def apply_reviewer_field_corrections(
    db: Session,
    app: Application,
    doc: ApplicationDocument,
    body: ReviewerFieldCorrectionRequest,
    auth: AuthContext,
    request: Request,
) -> ApplicationVerificationOut:
    ext = db.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == doc.id))
    if ext is None:
        raise AppError(
            409,
            "DOCUMENT_NOT_PROCESSED",
            "Run document processing on this application before correcting extracted fields.",
        )

    now = utcnow()
    existing_corrected = dict(ext.reviewer_corrected_fields or {})
    existing_effective = dict(ext.effective_fields or ext.extracted_fields or {})

    changed_fields: list[str] = []
    for field_name, new_val in body.fields.items():
        old_val = existing_effective.get(field_name)
        old_str = None if old_val is None else str(old_val)
        if old_str != new_val:
            changed_fields.append(field_name)
        db.add(
            DocumentFieldCorrection(
                extraction_id=ext.id,
                application_id=app.id,
                document_id=doc.id,
                field_name=field_name,
                old_value=old_str,
                new_value=new_val,
                reason=body.reason,
                corrected_by_user_id=auth.user.id,
            )
        )
        existing_corrected[field_name] = new_val
        existing_effective[field_name] = new_val

    ext.reviewer_corrected_fields = existing_corrected
    ext.effective_fields = existing_effective
    ext.missing_fields = _compute_missing_fields(doc.doc_type, existing_effective)
    ext.corrected_by_user_id = auth.user.id
    ext.corrected_at = now
    db.flush()

    docs = _current_docs(db, app.id)
    ext_by_doc_id = {
        e.document_id: e
        for e in db.scalars(select(DocumentExtraction).where(DocumentExtraction.application_id == app.id)).all()
    }
    docs_with_ext = [(d, ext_by_doc_id[d.id]) for d in docs if d.id in ext_by_doc_id]
    _recompute_checks(db, app, docs_with_ext)

    db.add(
        ApplicationEvent(
            application_id=app.id,
            actor_user_id=auth.user.id,
            actor_role=auth.user.role.code,
            event_type="EXTRACTED_FIELDS_CORRECTED",
            from_status=app.status,
            to_status=app.status,
            summary=f"Reviewer corrected {', '.join(body.fields.keys())} on {doc.doc_type}.",
            details={
                "document_id": str(doc.id),
                "doc_type": doc.doc_type,
                "corrected_fields": sorted(body.fields.keys()),
                "changed_fields": sorted(changed_fields),
                "reason": body.reason,
            },
        )
    )
    audit.add(
        db,
        request,
        "document.fields_corrected",
        actor=auth.user,
        resource_type="document",
        resource_id=str(doc.id),
        details={
            "reference_code": app.reference_code,
            "doc_type": doc.doc_type,
            "corrected_fields": sorted(body.fields.keys()),
            "reason": body.reason,
        },
    )
    db.flush()
    return build_verification_report(db, app)


def get_redacted_document_bytes(
    db: Session,
    app: Application,
    doc: ApplicationDocument,
    auth: AuthContext,
    request: Request,
) -> bytes:
    ext = db.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == doc.id))
    if ext is None or not ext.redacted_storage_key:
        raise AppError(404, "REDACTED_IMAGE_NOT_FOUND", "No redacted Aadhaar image is available for this document.")

    storage = get_storage()
    try:
        content = storage.get_object(ext.redacted_storage_key)
    except FileNotFoundError as exc:
        raise AppError(404, "REDACTED_FILE_MISSING", "Redacted image file not found in storage.") from exc

    audit.add(
        db,
        request,
        "document.redacted_viewed",
        actor=auth.user,
        resource_type="document",
        resource_id=str(doc.id),
        details={"reference_code": app.reference_code, "doc_type": doc.doc_type},
    )
    db.flush()
    return content
