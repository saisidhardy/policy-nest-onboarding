import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.api.deps import DB, AuthContext, CurrentAuth, enforce_policy, require_permission
from app.core.errors import AppError
from app.models import Application, CorrectionRequest, ReviewDecision
from app.rbac.policy import Resource
from app.schemas.domain import ApplicationOut, ReviewActionIn
from app.services import audit
from app.services.onboarding import application_payload, transition

router = APIRouter(prefix="/reviews", tags=["review operations"])
QUEUE_STATUSES = {"SUBMITTED", "UNDER_REVIEW", "CORRECTION_REQUIRED", "ESCALATED"}


def _resource(application: Application) -> Resource:
    return Resource(
        type="application",
        id=str(application.id),
        owner_id=application.applicant_id,
        region=application.region,
        sensitivity=application.sensitivity,
    )


@router.get("/queue", response_model=list[ApplicationOut])
def review_queue(
    request: Request,
    db: DB,
    auth: CurrentAuth,
    status: str | None = Query(default=None),
    region: str | None = Query(default=None),
    _: AuthContext = Depends(require_permission("application:read_any")),
):
    query = (
        select(Application)
        .where(Application.status.in_(QUEUE_STATUSES))
        .order_by(Application.submitted_at.asc().nullslast())
    )
    if status:
        if status not in QUEUE_STATUSES:
            raise AppError(422, "INVALID_STATUS", "Unsupported queue status.")
        query = query.where(Application.status == status)
    if region:
        query = query.where(Application.region == region)
    applications = []
    for application in db.scalars(query):
        try:
            enforce_policy(request, auth, "application:read_any", _resource(application))
        except AppError:
            continue
        applications.append(application_payload(db, application))
    return applications


@router.get("/{application_id}", response_model=ApplicationOut)
def review_detail(
    application_id: uuid.UUID,
    request: Request,
    db: DB,
    auth: CurrentAuth,
    _: AuthContext = Depends(require_permission("application:read_any")),
):
    application = db.get(Application, application_id)
    if application is None:
        raise AppError(404, "APPLICATION_NOT_FOUND", "Application not found.")
    enforce_policy(request, auth, "application:read_any", _resource(application))
    return application_payload(db, application)


@router.post("/{application_id}/actions", response_model=ApplicationOut)
def review_action(application_id: uuid.UUID, body: ReviewActionIn, request: Request, db: DB, auth: CurrentAuth):
    application = db.scalar(select(Application).where(Application.id == application_id).with_for_update(of=Application))
    if application is None:
        raise AppError(404, "APPLICATION_NOT_FOUND", "Application not found.")
    permission = {
        "ASSIGN_TO_ME": "application:review",
        "REQUEST_CORRECTION": "application:review",
        "APPROVE_KYC": "application:decide_escalated" if application.status == "ESCALATED" else "application:decide",
        "REJECT": "application:decide_escalated" if application.status == "ESCALATED" else "application:decide",
        "ESCALATE": "application:escalate",
    }[body.action]
    if permission not in auth.permissions:
        raise AppError(403, "FORBIDDEN", "You do not have permission for this review action.")
    enforce_policy(request, auth, permission, _resource(application))

    previous = application.status
    resulting = previous
    if body.action == "ASSIGN_TO_ME":
        if application.status == "SUBMITTED":
            transition(db, application, "UNDER_REVIEW", auth.user, "REVIEW_STARTED")
        elif application.status not in {"UNDER_REVIEW", "ESCALATED"}:
            raise AppError(409, "INVALID_TRANSITION", "This application cannot be assigned now.")
        if application.assigned_reviewer_id not in {None, auth.user.id}:
            raise AppError(409, "ALREADY_ASSIGNED", "This application is assigned to another reviewer.")
        application.assigned_reviewer_id = auth.user.id
        resulting = application.status
    elif body.action == "REQUEST_CORRECTION":
        if not body.issues:
            raise AppError(422, "ISSUES_REQUIRED", "Add at least one correction issue.")
        labels = [i.get("message", "Please correct the highlighted information.") for i in body.issues]
        message_en = "Please address all of the following in one resubmission:\n- " + "\n- ".join(labels)
        message_hi = "कृपया एक ही पुनः सबमिशन में सभी बताई गई कमियों को सुधारें।\n- " + "\n- ".join(labels)
        db.add(
            CorrectionRequest(
                application_id=application.id,
                reviewer_id=auth.user.id,
                issues=body.issues,
                message_en=message_en,
                message_hi=message_hi,
            )
        )
        transition(db, application, "CORRECTION_REQUIRED", auth.user, "CORRECTION_REQUESTED", {"issues": body.issues})
        resulting = application.status
    elif body.action == "APPROVE_KYC":
        transition(db, application, "KYC_APPROVED", auth.user, "KYC_APPROVED")
        application.decided_at = datetime.now(timezone.utc)
        resulting = application.status
    elif body.action == "REJECT":
        transition(db, application, "REJECTED", auth.user, "APPLICATION_REJECTED", {"reason": body.justification})
        application.decided_at = datetime.now(timezone.utc)
        resulting = application.status
    elif body.action == "ESCALATE":
        transition(db, application, "ESCALATED", auth.user, "APPLICATION_ESCALATED", {"reason": body.justification})
        application.sensitivity = max(application.sensitivity, 2)
        application.assigned_reviewer_id = None
        resulting = application.status

    db.add(
        ReviewDecision(
            application_id=application.id,
            reviewer_id=auth.user.id,
            action=body.action,
            justification=body.justification,
            previous_status=previous,
            resulting_status=resulting,
        )
    )
    audit.add(
        db,
        request,
        f"review.{body.action.lower()}",
        actor=auth.user,
        resource_type="application",
        resource_id=str(application.id),
        details={"previous_status": previous, "resulting_status": resulting, "justification": body.justification},
    )
    db.commit()
    db.refresh(application)
    return application_payload(db, application)
