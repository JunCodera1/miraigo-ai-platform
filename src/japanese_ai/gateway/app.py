"""FastAPI application factory: middleware, error mapping, routes, lifecycle."""

from __future__ import annotations

import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from japanese_ai import __version__
from japanese_ai.core import errors
from japanese_ai.core.config import Settings, get_settings
from japanese_ai.core.envelope import error_response
from japanese_ai.core.errors import AppError
from japanese_ai.core.logging import configure_logging, get_logger, principal_var, request_id_var
from japanese_ai.gateway.container import Container
from japanese_ai.gateway.routes import language, speech, stream, system

log = get_logger("gateway")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = container or Container.build(settings)
        if settings.warmup:
            primaries = {
                chain[0].id: chain[0]
                for route in ("asr", "pronunciation")
                if (chain := app.state.container.router.chain(route))
            }
            for spec in primaries.values():
                provider = app.state.container.pool.get(spec)
                if provider.availability()[0]:
                    started = time.perf_counter()
                    await provider.warm_up()
                    log.info(
                        "model warmed up",
                        extra={"model": spec.id, "ms": int((time.perf_counter() - started) * 1000)},
                    )
        log.info("started", extra={"version": __version__, "env": settings.env, "auth": settings.auth_mode})
        yield
        await app.state.container.aclose()

    app = FastAPI(
        title="MiraiGo Japanese AI Platform",
        version=__version__,
        description="Speech, pronunciation and Japanese-language services for MiraiGo clients. "
        "Every JSON response uses the MiraiGo envelope: {status, message, errorCode?, data?, errors?, path, timestamp, requestId}.",
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-Id", "X-Client-Type"],
        expose_headers=["X-Request-Id", "Retry-After", "X-Model"],
        allow_credentials=False,
        max_age=3600,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        request_id_var.set(request_id)
        principal_var.set(None)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "ms": int((time.perf_counter() - started) * 1000),
                },
            )
        response.headers["X-Request-Id"] = request_id
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return error_response(
            request,
            status=exc.status_code,
            code=exc.code,
            message=exc.message,
            errors=exc.errors,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [
            {
                "field": ".".join(str(part) for part in err.get("loc", ())[1:]) or None,
                "message": err.get("msg"),
            }
            for err in exc.errors()
        ]
        return error_response(
            request, status=422, code=errors.VALIDATION_FAILED, message="Validation failed", errors=details
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return error_response(
            request,
            status=exc.status_code,
            code=errors.code_for_status(exc.status_code),
            message=str(exc.detail),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error")
        return error_response(request, status=500, code=errors.INTERNAL_ERROR, message="Internal error")

    app.include_router(system.router)
    app.include_router(language.router)
    app.include_router(speech.router)
    app.include_router(stream.router)
    return app
