import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    account,
    admin,
    admin_ops,
    applications,
    auth,
    health,
    notifications,
    review,
    rules,
    training,
    verifications,
)
from app.core.config import get_settings
from app.core.errors import register_error_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PolicyNest API",
        version=settings.app_version,
        description="AI-first POSP onboarding platform. Authentication uses an HttpOnly session cookie; "
        "state-changing requests must send the `X-CSRF-Token` header matching the `pn_csrf` cookie.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request.state.request_id = incoming[:64] if incoming else uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path.startswith("/api/v1"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(health.router)
    app.include_router(health.router, prefix="/api", include_in_schema=False)
    for module in (
        auth,
        account,
        admin,
        admin_ops,
        applications,
        notifications,
        verifications,
        rules,
        review,
        training,
    ):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
