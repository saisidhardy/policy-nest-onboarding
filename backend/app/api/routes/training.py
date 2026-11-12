import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import func, select

from app.api.deps import DB, AuthContext, CurrentAuth, require_permission
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Application, Certificate, ExamAttempt, TrainingProgress
from app.schemas.domain import ExamAttemptOut, ExamSubmitIn, TrainingModuleOut, TrainingUpdateIn
from app.services import audit
from app.services.onboarding import transition
from app.services.training import MODULES, QUESTIONS, certificate_seal, public_question, randomized_order

router = APIRouter(prefix="/training", tags=["training and certification"])


def _simple_certificate_pdf(lines: list[str]) -> bytes:
    """Create a dependency-free, single-page PDF with built-in Helvetica."""

    def escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    commands = ["BT", "/F1 20 Tf", "72 760 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.extend(["0 -42 Td", "/F1 12 Tf"])
        commands.append(f"({escape(line)}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


def _application(db: DB, auth: CurrentAuth) -> Application:
    application = db.scalar(
        select(Application).where(Application.applicant_id == auth.user.id).with_for_update(of=Application)
    )
    if application is None:
        raise AppError(404, "APPLICATION_NOT_FOUND", "Start an application first.")
    if application.status not in {"KYC_APPROVED", "TRAINING_IN_PROGRESS", "EXAM_ELIGIBLE", "CERTIFIED"}:
        raise AppError(409, "TRAINING_LOCKED", "Training opens after KYC approval.")
    if application.status == "KYC_APPROVED":
        transition(db, application, "TRAINING_IN_PROGRESS", auth.user, "TRAINING_STARTED")
    return application


def _ensure_modules(db: DB, application: Application) -> list[TrainingProgress]:
    rows = list(db.scalars(select(TrainingProgress).where(TrainingProgress.application_id == application.id)))
    by_code = {row.module_code: row for row in rows}
    for code, (_, minutes) in MODULES.items():
        if code not in by_code:
            row = TrainingProgress(application_id=application.id, module_code=code, required_minutes=minutes)
            db.add(row)
            by_code[code] = row
    db.flush()
    return [by_code[code] for code in MODULES]


@router.get("/modules", response_model=list[TrainingModuleOut])
def modules(db: DB, auth: CurrentAuth, _: AuthContext = Depends(require_permission("application:read_own"))):
    application = _application(db, auth)
    rows = _ensure_modules(db, application)
    db.commit()
    return [
        {
            "code": row.module_code,
            "title": MODULES[row.module_code][0],
            "required_minutes": row.required_minutes,
            "minutes_completed": row.minutes_completed,
            "completed": row.completed_at is not None,
        }
        for row in rows
    ]


@router.put("/modules/{module_code}", response_model=TrainingModuleOut)
def update_module(module_code: str, body: TrainingUpdateIn, request: Request, db: DB, auth: CurrentAuth):
    application = _application(db, auth)
    rows = _ensure_modules(db, application)
    row = next((item for item in rows if item.module_code == module_code.upper()), None)
    if row is None:
        raise AppError(404, "MODULE_NOT_FOUND", "Training module not found.")
    row.minutes_completed = min(body.minutes_completed, row.required_minutes)
    if row.minutes_completed >= row.required_minutes and row.completed_at is None:
        row.completed_at = datetime.now(timezone.utc)
    if all(item.completed_at is not None for item in rows) and application.status == "TRAINING_IN_PROGRESS":
        transition(db, application, "EXAM_ELIGIBLE", auth.user, "TRAINING_COMPLETED")
    audit.add(
        db,
        request,
        "training.progress",
        actor=auth.user,
        resource_type="application",
        resource_id=str(application.id),
        details={"module": row.module_code, "minutes": row.minutes_completed},
    )
    db.commit()
    return {
        "code": row.module_code,
        "title": MODULES[row.module_code][0],
        "required_minutes": row.required_minutes,
        "minutes_completed": row.minutes_completed,
        "completed": row.completed_at is not None,
    }


@router.post("/exam/start", response_model=ExamAttemptOut, status_code=201)
def start_exam(request: Request, db: DB, auth: CurrentAuth):
    application = _application(db, auth)
    if application.status != "EXAM_ELIGIBLE":
        raise AppError(409, "EXAM_LOCKED", "Complete all 15 training hours before starting the exam.")
    open_attempt = db.scalar(
        select(ExamAttempt).where(ExamAttempt.application_id == application.id, ExamAttempt.submitted_at.is_(None))
    )
    if open_attempt:
        attempt = open_attempt
    else:
        count = (
            db.scalar(select(func.count()).select_from(ExamAttempt).where(ExamAttempt.application_id == application.id))
            or 0
        )
        attempt = ExamAttempt(
            application_id=application.id,
            attempt_number=count + 1,
            question_order=randomized_order(f"{application.id}:{count + 1}"),
        )
        db.add(attempt)
        db.flush()
        audit.add(
            db, request, "exam.started", actor=auth.user, resource_type="exam_attempt", resource_id=str(attempt.id)
        )
        db.commit()
        db.refresh(attempt)
    return {
        "id": attempt.id,
        "attempt_number": attempt.attempt_number,
        "questions": [public_question(qid) for qid in attempt.question_order],
        "started_at": attempt.started_at,
    }


@router.post("/exam/{attempt_id}/submit")
def submit_exam(attempt_id: uuid.UUID, body: ExamSubmitIn, request: Request, db: DB, auth: CurrentAuth):
    application = _application(db, auth)
    attempt = db.scalar(
        select(ExamAttempt)
        .where(ExamAttempt.id == attempt_id, ExamAttempt.application_id == application.id)
        .with_for_update()
    )
    if attempt is None:
        raise AppError(404, "EXAM_NOT_FOUND", "Exam attempt not found.")
    if attempt.submitted_at:
        raise AppError(409, "EXAM_ALREADY_SUBMITTED", "This exam has already been submitted.")
    if set(body.answers) != set(attempt.question_order):
        raise AppError(422, "ANSWERS_INCOMPLETE", "Answer all 50 questions before submitting.")
    correct = sum(int(body.answers[qid] == QUESTIONS[qid]["answer"]) for qid in attempt.question_order)
    score = round(correct * 100 / len(attempt.question_order), 2)
    passed = score >= 70
    now = datetime.now(timezone.utc)
    attempt.answers = body.answers
    attempt.score_percent = score
    attempt.passed = passed
    attempt.submitted_at = now
    certificate = None
    if passed:
        existing = db.scalar(select(Certificate).where(Certificate.application_id == application.id))
        if existing is None:
            number = f"IRDAI-POSP-{now:%Y}-{str(application.id).replace('-', '')[:10].upper()}"
            seal = certificate_seal(number, str(application.id), now.isoformat(), get_settings().secret_key)
            certificate = Certificate(
                application_id=application.id, certificate_number=number, issued_at=now, seal_sha256=seal
            )
            db.add(certificate)
        transition(db, application, "CERTIFIED", auth.user, "EXAM_PASSED", {"score": score})
    audit.add(
        db,
        request,
        "exam.submitted",
        actor=auth.user,
        resource_type="exam_attempt",
        resource_id=str(attempt.id),
        details={"score": score, "passed": passed},
    )
    db.commit()
    return {
        "score_percent": score,
        "passed": passed,
        "certificate_number": certificate.certificate_number if certificate else None,
    }


@router.get("/certificate.pdf")
def certificate_pdf(db: DB, auth: CurrentAuth):
    application = db.scalar(select(Application).where(Application.applicant_id == auth.user.id))
    certificate = (
        db.scalar(select(Certificate).where(Certificate.application_id == application.id)) if application else None
    )
    if certificate is None or certificate.revoked_at:
        raise AppError(404, "CERTIFICATE_NOT_FOUND", "No active certificate is available.")
    output = _simple_certificate_pdf(
        [
            "PolicyNest - Certificate of Completion",
            f"This certifies that {auth.user.full_name}",
            "completed the recorded POSP training and assessment.",
            f"Certificate: {certificate.certificate_number}",
            f"Issued: {certificate.issued_at:%d %B %Y}",
            f"SHA-256 seal: {certificate.seal_sha256}",
            "Subject to verification and the regulated entity's approval process.",
        ]
    )
    return Response(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{certificate.certificate_number}.pdf"'},
    )
