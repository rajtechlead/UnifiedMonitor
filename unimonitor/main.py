"""UniMonitor FastAPI application factory."""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from unimonitor.config import get_settings
from unimonitor.exceptions import (
    AuthenticationError,
    GraphAPIError,
    GraphPermissionError,
    NotFoundError,
    UniMonitorError,
)

logger = structlog.get_logger(__name__)

APP_VERSION = "1.0.0"


class SpaFallbackMiddleware:
    """Serve the built frontend around the API.

    Existing files under the build root are served directly; any other navigation
    path gets index.html so client-side routes survive a refresh. API paths are
    passed straight through, and a missing file (e.g. a stale hashed asset) is a
    real 404 rather than the HTML shell.

    This is middleware rather than a catch-all route because an APIRoute matching
    `/{path}` competes with FastAPI's lazily included sub-routers and can shadow
    legitimate endpoints such as `GET /api/v1/tenants`.
    """

    _PASSTHROUGH = {"api", "static", "docs", "redoc", "openapi.json"}

    def __init__(self, app: Any, static_dir: Path) -> None:
        self.app = app
        self.root = static_dir.resolve()
        self.index = self.root / "index.html"

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["method"] not in ("GET", "HEAD"):
            await self.app(scope, receive, send)
            return

        path = scope["path"].lstrip("/")
        if path.split("/", 1)[0] in self._PASSTHROUGH:
            await self.app(scope, receive, send)
            return

        if path:
            candidate = (self.root / path).resolve()
            if candidate.is_file() and candidate.is_relative_to(self.root):
                await FileResponse(candidate)(scope, receive, send)
                return
            # a missing asset must not be answered with the HTML shell
            if "." in path.rsplit("/", 1)[-1]:
                await self.app(scope, receive, send)
                return

        swallowed = False

        async def relay(message: Any) -> None:
            nonlocal swallowed
            if message["type"] == "http.response.start":
                if message["status"] == 404:
                    swallowed = True
                    return
            elif swallowed:
                return
            await send(message)

        await self.app(scope, receive, relay)
        if swallowed:
            await FileResponse(self.index)(scope, receive, send)


def _spa_directory() -> Path | None:
    """Locate the built frontend, if one was bundled.

    CI and the installers copy the Vite output to `unimonitor/static`; Docker
    images do the same. `UNIMONITOR_STATIC_DIR` overrides it for tests.
    """
    candidates: list[Path] = []
    override = os.environ.get("UNIMONITOR_STATIC_DIR")
    if override:
        candidates.append(Path(override))
    candidates.extend([Path(__file__).parent / "static", Path("static")])
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown."""
    settings = get_settings()
    logger.info("UniMonitor starting", version=APP_VERSION, env=settings.UNIMONITOR_ENV)

    # Initialise database
    from unimonitor.db.base import init_db

    await init_db()
    logger.info("Database initialised")

    # Initialise Redis cache
    from unimonitor.core.cache import init_cache

    await init_cache()
    logger.info("Cache initialised")

    # Instrument OpenTelemetry if enabled
    if settings.OTEL_ENABLED:
        _setup_otel(app, settings)
        logger.info("OpenTelemetry instrumentation active")

    logger.info("UniMonitor ready", version=APP_VERSION)
    yield

    # Shutdown
    from unimonitor.core.cache import close_cache

    await close_cache()
    logger.info("UniMonitor shutdown complete")


def _setup_otel(app: FastAPI, settings) -> None:
    """Configure OpenTelemetry SDK."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource(attributes={"service.name": settings.OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument()
    except Exception as exc:
        logger.warning("OpenTelemetry setup failed", error=str(exc))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="UniMonitor",
        description=(
            "Unified Monitoring and GRC Solution for Microsoft 365 — continuous monitoring, compliance automation, and security operations."
        ),
        version=APP_VERSION,
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────
    if settings.UNIMONITOR_ALLOWED_HOSTS != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.UNIMONITOR_ALLOWED_HOSTS)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.UNIMONITOR_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def access_log_middleware(request: Request, call_next) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
            client=request.client.host if request.client else "unknown",
        )
        return response

    # ── Exception handlers ───────────────────────────────────
    @app.exception_handler(GraphAPIError)
    async def graph_api_error_handler(request: Request, exc: GraphAPIError) -> JSONResponse:
        logger.error("Graph API error", path=request.url.path, error=str(exc))
        return JSONResponse(status_code=502, content={"detail": str(exc), "error_code": "GRAPH_API_ERROR"})

    @app.exception_handler(GraphPermissionError)
    async def graph_perm_error_handler(request: Request, exc: GraphPermissionError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc), "error_code": "GRAPH_PERMISSION_DENIED"})

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc), "error_code": "AUTHENTICATION_FAILED"})

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc), "error_code": "NOT_FOUND"})

    @app.exception_handler(UniMonitorError)
    async def unimonitor_error_handler(request: Request, exc: UniMonitorError) -> JSONResponse:
        logger.error("UniMonitor error", path=request.url.path, error=str(exc))
        return JSONResponse(status_code=500, content={"detail": str(exc), "error_code": "INTERNAL_ERROR"})

    # ── Health endpoints ─────────────────────────────────────
    @app.get("/health", tags=["health"], include_in_schema=False)
    @app.get("/api/v1/health", tags=["health"])
    async def health_check() -> dict:
        return {"status": "ok", "version": APP_VERSION}

    # ── Static files (branding) ──────────────────────────────
    static_path = Path("branding")
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # ── API routers ──────────────────────────────────────────
    from unimonitor.api.v1.router import api_v1_router

    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # ── Bundled single-page frontend ─────────────────────────
    # Assets are mounted under their real prefix; navigation is handled by a
    # catch-all route. Mounting at "/" is deliberately avoided: a mount matches
    # partial paths and answers 404/405 for API routes that live beneath it.
    spa_dir = _spa_directory()
    if spa_dir is not None:
        app.add_middleware(SpaFallbackMiddleware, static_dir=spa_dir)
        logger.info("spa_served", directory=str(spa_dir))

    return app


app = create_app()
