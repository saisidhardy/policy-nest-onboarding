"""Inbound signed webhook endpoints for asynchronous verification providers."""

from fastapi import APIRouter, Request

from app.api.deps import DB
from app.services import webhooks as webhook_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/verification/{source}")
async def receive_verification_webhook(source: str, request: Request, db: DB):
    raw_body = await request.body()
    sig = request.headers.get("x-policynest-signature") or request.headers.get("x-webhook-signature")
    return webhook_service.process_verification_webhook(
        db,
        request,
        source=source,
        raw_body=raw_body,
        signature=sig,
    )
