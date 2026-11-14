"""RexWork backend entrypoint.

This file is intentionally tiny: it wires the FastAPI app, middleware,
exception handlers and route modules together. All real logic lives in
`core/`:

    core/config.py      constants, limits, file locations
    core/security.py    API-key pool, redaction, app-token guard
    core/modes.py       mode personas + safety rules
    core/validation.py  request validation, message building
    core/provider.py    Groq client, retries, empty-answer repair
    core/chat.py        chat SSE pipeline
    core/agent.py       sandboxed coding agent
    core/uploads.py     upload/transcription helpers
    core/routes/        HTTP routes (meta, chat, files)
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import APP_NAME, APP_VERSION
from core.http import error_response, http_error_code
from core.routes import chat as chat_routes
from core.routes import files as file_routes
from core.routes import meta as meta_routes
from core.security import token_guard

logger = logging.getLogger("rexwork")

app = FastAPI(title=APP_NAME, version=APP_VERSION)


# --- Middleware ---------------------------------------------------------

@app.middleware("http")
async def app_token_middleware(request: Request, call_next):
    return await token_guard(request, call_next)


@app.middleware("http")
async def vercel_routing_middleware(request: Request, call_next):
    """Rewrite Vercel's `/api/index` fallback back to the real path."""
    orig_path = request.headers.get("x-matched-path") or request.headers.get("x-forwarded-uri")

    if orig_path:
        clean = orig_path.split("?")[0]

        if request.scope.get("path") in ("/api/index", "/api/index.py", "/index", "/index.py"):
            request.scope["path"] = clean

    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception handlers -------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, error: StarletteHTTPException):
    response = error_response(
        error.status_code,
        http_error_code(error.status_code),
        f"{error.detail}: {request.method} {request.url.path}",
    )

    for name, value in (error.headers or {}).items():
        response.headers[name] = value

    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, error: RequestValidationError):
    return error_response(
        422,
        "INVALID_REQUEST",
        "The request is missing a required field or has an invalid one.",
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, error: Exception):
    logger.error(
        "unhandled %s on %s %s",
        error.__class__.__name__,
        request.method,
        request.url.path,
    )

    return error_response(500, "INTERNAL_ERROR", "The server hit an unexpected error.")


# --- Routes -------------------------------------------------------------

app.include_router(meta_routes.router)
app.include_router(chat_routes.router)
app.include_router(file_routes.router)
