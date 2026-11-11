"""FastAPI application entrypoint.

One deployable service (section 5):

* ``/api/*``      - the JSON API
* everything else - the built React SPA from ``frontend/dist``, with SPA
  fallback so a deep link such as ``/orders/1`` still returns ``index.html``.

If ``frontend/dist`` has not been built yet, the SPA routes return a clear
404 explaining how to build it, rather than a confusing blank page.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from app.api.router import api_router
from app.core.config import get_settings
from app.services.actions import ActionError, InvalidActionType
from app.core.logging_config import configure_logging
from app.db.base import get_session_factory, init_db
from app.db.seed import seed_if_needed

logger = logging.getLogger(__name__)

#: backend/app/main.py -> backend/app -> backend -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()

    if not settings.demo_mode_was_explicit:
        logger.warning(
            "DEMO_MODE is not set. Treating it as false: no demo data will be "
            "seeded and /api/demo/* routes are disabled. Set DEMO_MODE=true "
            "explicitly if you want the demo dataset."
        )

    logger.info("Starting MerchantShield AI with config: %s", settings.safe_dump())

    init_db()

    # Phase 3: train the ML estimate on first boot if the model file is missing.
    # It is a prototype on SYNTHETIC data; the About page prints its metrics.
    try:
        from app.services.risk_model import ensure_model

        if ensure_model():
            logger.info("ML estimate trained on synthetic data at startup")
    except Exception:  # pragma: no cover - training must never block the API
        logger.exception("ML training failed; /api/about/methodology will say so")

    session = get_session_factory()()
    try:
        seeded = seed_if_needed(session)
        if seeded:
            logger.info("Startup seeding inserted %d order(s).", seeded)
    finally:
        session.close()

    yield


#: API responses must never be cached by the browser. Every GET here reflects
#: mutable server state, and a cached draft status would show "DRAFT" for a
#: draft the merchant has just approved.
NO_STORE_HEADERS = {"Cache-Control": "no-store"}


def create_app() -> FastAPI:
    app = FastAPI(
        title="MerchantShield AI",
        description=(
            "Sandbox-first dispute prevention for small PayPal merchants. "
            "Every record is labelled PAYPAL_SANDBOX, SIMULATED or MOCK."
        ),
        version="1.0.0-phase7",
        lifespan=lifespan,
    )

    @app.exception_handler(ActionError)
    async def _action_error_handler(_request: Request, exc: ActionError) -> JSONResponse:
        """Every engine refusal is a clean 4xx with the reason, never a 500."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc), "error_type": type(exc).__name__},
        )

    @app.exception_handler(InvalidActionType)
    async def _invalid_type_handler(_request: Request, exc: InvalidActionType) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.include_router(api_router)
    _mount_spa(app)
    return app


def _mount_spa(app: FastAPI) -> None:
    """Serve the built SPA, with a fallback to index.html for client routes."""
    index_file = FRONTEND_DIST / "index.html"

    if (FRONTEND_DIST / "assets").is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=FRONTEND_DIST / "assets"),
            name="spa-assets",
        )

    @app.middleware("http")
    async def no_store(request: Request, call_next):  # type: ignore[no-untyped-def]
        """No-store on every /api response; static assets keep their own headers."""
        response = await call_next(request)
        if request.url.path.startswith(API_PREFIX):
            response.headers.update(NO_STORE_HEADERS)
        return response

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(request: Request, full_path: str) -> Response:
        # Never let the SPA shadow the API: an unmatched /api/* path is a real 404.
        if request.url.path.startswith(API_PREFIX):
            return JSONResponse(
                status_code=404,
                content={"detail": f"No API route for {request.url.path}"},
            )

        # Serve a real static file when one exists (favicon, robots.txt, ...).
        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            try:
                candidate.relative_to(FRONTEND_DIST.resolve())
            except ValueError:
                # Path traversal attempt - fall through to index.html.
                candidate = index_file
            if candidate.is_file():
                return FileResponse(candidate)

        if index_file.is_file():
            return FileResponse(index_file)

        return JSONResponse(
            status_code=404,
            content={
                "detail": (
                    "Frontend has not been built. Run 'npm ci' then 'npm run build' "
                    "in the frontend/ folder, or use the Vite dev server on port 5173."
                )
            },
        )


app = create_app()
