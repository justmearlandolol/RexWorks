"""Static pages, health and capability endpoints."""

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

from core.config import APP_NAME, APP_VERSION, INDEX_FILE, LOGIN_FILE
from core.http import error_response
from core.modes import MODES, VISION_MODE_KEY, vision_available
from core.security import has_keys, keys

router = APIRouter()


@router.get("/")
@router.get("/api/index")
@router.get("/index")
async def root():
    if os.path.exists(INDEX_FILE):
        return FileResponse(INDEX_FILE)

    return {
        "app": APP_NAME,
        "status": "online",
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/api/health",
        "keys_loaded": keys.count(),
        "vision_available": vision_available(),
        "note": "RexWork Backend is online and ready.",
    }


@router.get("/Main.html")
async def login_page():
    if os.path.exists(LOGIN_FILE):
        return FileResponse(LOGIN_FILE)

    return error_response(
        404,
        "LOGIN_NOT_FOUND",
        "Frontend/Main.html tidak ditemukan.",
    )


@router.get("/api/status")
async def status():
    return {
        "app": APP_NAME,
        "status": "running",
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }


@router.get("/api/health")
@router.get("/health")
@router.get("/api/index/api/health")
@router.get("/api/index/health")
async def health():
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
        "keys_loaded": keys.count(),
        "memory_enabled": True,
        "vision_available": vision_available(),
    }


@router.get("/api/models")
async def models():
    output = []

    for key, mode in MODES.items():
        available = vision_available() if key == VISION_MODE_KEY else has_keys()

        output.append({
            "key": key,
            "name": mode["name"],
            "desc": mode["desc"],
            "modelLabel": mode["modelLabel"],
            "purpose": mode["purpose"],
            "available": available,
        })

    return {"modes": output}
