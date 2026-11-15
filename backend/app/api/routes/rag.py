"""RAG & AI Chatbot routes grounded in POSP Recovery & Quick-Start Manuals."""

import uuid
from fastapi import APIRouter, Depends, Request

from app.api.deps import DB, AuthContext, get_optional_auth, require_permission
from app.core.errors import AppError
from app.models.application import Application
from app.schemas.rag import (
    ApplicantLiveState,
    RAGChatRequest,
    RAGChatResponse,
    RAGChunkOut,
)
from app.schemas.rules import AppealCreateRequest, ApplicationAppealOut
from app.services import rag as rag_service
from app.services import rules_engine

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/chat", response_model=RAGChatResponse, summary="Query RAG Assistant with live state monitoring")
def chat_with_rag_copilot(
    req: RAGChatRequest,
    db: DB,
    auth: AuthContext | None = Depends(get_optional_auth),
) -> RAGChatResponse:
    """Blend RAG retrieval across POSP manuals with real-time applicant state and blocker resolution."""
    user = auth.user if auth else None
    return rag_service.generate_rag_chat_response(
        db=db,
        query=req.query,
        user=user,
        application_id=req.application_id,
        language=req.language,
    )


@router.get("/state/{application_id}", response_model=ApplicantLiveState, summary="Inspect applicant live recovery state")
def get_applicant_live_state(
    application_id: uuid.UUID,
    db: DB,
    auth: AuthContext | None = Depends(get_optional_auth),
) -> ApplicantLiveState:
    """Inspect active blockers, missing documents, and 6-group manual priority for an application."""
    user = auth.user if auth else None
    return rag_service.inspect_applicant_live_state(db=db, user=user, application_id=application_id)


@router.get("/manuals", response_model=list[RAGChunkOut], summary="List all indexed manual chapters")
def list_manual_chapters() -> list[RAGChunkOut]:
    """Retrieve all structured manual chunks indexed in the RAG corpus."""
    return [
        RAGChunkOut(
            id=c.id,
            source=c.source,
            section=c.section,
            stage=c.stage,
            title=c.title,
            text=c.text,
            citations=c.citations,
            actionable_steps=c.actionable_steps,
            sample_script=c.sample_script,
            is_escalation_indicator=c.is_escalation_indicator,
        )
        for c in rag_service.MANUAL_CHUNKS
    ]


@router.post("/applications/{application_id}/chat-appeal", response_model=ApplicationAppealOut, summary="Submit 1-click appeal from AI Chatbot")
def submit_chat_appeal(
    application_id: uuid.UUID,
    body: AppealCreateRequest,
    request: Request,
    db: DB,
    auth: AuthContext = Depends(require_permission("application:create")),
) -> ApplicationAppealOut:
    """Escalate an unresolvable blocker directly to a Human Reviewer via the AI Chatbot."""
    app = db.get(Application, application_id)
    if app is None:
        raise AppError(404, "APPLICATION_NOT_FOUND", "Application not found.")
    if app.user_id != auth.user.id and "application:review" not in auth.permissions:
        raise AppError(403, "FORBIDDEN", "You can only appeal your own application.")

    appeal = rules_engine.submit_appeal(db, app, body, auth, request)
    return ApplicationAppealOut.model_validate(appeal)
