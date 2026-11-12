from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import DB, AuthContext, require_permission
from app.models import Application, Certificate, CorrectionRequest, Verification
from app.schemas.domain import OperationsSummary

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/summary", response_model=OperationsSummary)
def summary(db: DB, _: AuthContext = Depends(require_permission("analytics:read"))):
    by_status_rows = db.execute(select(Application.status, func.count()).group_by(Application.status)).all()
    verification_rows = db.execute(select(Verification.status, func.count()).group_by(Verification.status)).all()
    total = db.scalar(select(func.count()).select_from(Application)) or 0
    since = datetime.now(timezone.utc) - timedelta(days=30)
    recent = db.scalar(select(func.count()).select_from(Application).where(Application.submitted_at >= since)) or 0
    average_seconds = db.scalar(
        select(func.avg(func.extract("epoch", Application.decided_at - Application.submitted_at))).where(
            Application.decided_at.is_not(None), Application.submitted_at.is_not(None)
        )
    )
    pending = (
        db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.status.in_(["SUBMITTED", "UNDER_REVIEW", "ESCALATED"]))
        )
        or 0
    )
    corrections = (
        db.scalar(select(func.count()).select_from(CorrectionRequest).where(CorrectionRequest.status == "OPEN")) or 0
    )
    certificates = db.scalar(select(func.count()).select_from(Certificate).where(Certificate.revoked_at.is_(None))) or 0
    return {
        "total_applications": total,
        "by_status": dict(by_status_rows),
        "submitted_last_30_days": recent,
        "average_review_hours": round(float(average_seconds) / 3600, 2) if average_seconds is not None else None,
        "pending_review": pending,
        "corrections_open": corrections,
        "certificates_issued": certificates,
        "verification_statuses": dict(verification_rows),
    }
