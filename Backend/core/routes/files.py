"""Upload and audio-transcription endpoints."""

import os

from fastapi import APIRouter, File, UploadFile

from core.config import MAX_FILE_BYTES, MAX_TRANSCRIPTION_BYTES
from core.http import error_response
from core.security import has_keys
from core.uploads import (
    ALLOWED_EXTENSIONS,
    AUDIO_EXTENSIONS,
    describe_upload,
    read_limited_upload,
    transcribe_audio,
)

router = APIRouter()


@router.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return error_response(
            400,
            "UNSUPPORTED_TYPE",
            f"File type {ext or '(none)'} is not supported.",
        )

    data = await read_limited_upload(file, MAX_FILE_BYTES)
    await file.close()

    if data is None:
        return error_response(413, "TOO_LARGE", "File exceeds the 25 MB limit.")

    return describe_upload(filename, data, file.content_type or "")


@router.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not has_keys():
        return error_response(503, "NO_KEYS", "No Groq API keys configured.")

    filename = file.filename or "audio.webm"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in AUDIO_EXTENSIONS:
        return error_response(400, "UNSUPPORTED_AUDIO", "Unsupported audio format.")

    data = await read_limited_upload(file, MAX_TRANSCRIPTION_BYTES)
    await file.close()

    if data is None:
        return error_response(413, "TOO_LARGE", "Audio file exceeds the size limit.")

    payload, last_error = await transcribe_audio(
        filename,
        data,
        file.content_type or "audio/webm",
    )

    if payload is not None:
        return payload

    return error_response(502, "TRANSCRIPTION_FAILED", last_error)
