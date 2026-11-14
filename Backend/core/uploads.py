"""File upload helpers and supported-type tables."""

import os
from typing import List, Optional

import httpx
from fastapi import UploadFile

from core.config import (
    GROQ_TRANSCRIBE_MODEL,
    GROQ_TRANSCRIBE_URL,
    MAX_TEXT_CHARS,
)
from core.provider import provider_error
from core.security import keys

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt", ".csv",
    ".xlsx", ".pptx", ".json", ".zip",
    ".png", ".jpg", ".jpeg", ".gif",
    ".webp", ".bmp",
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".html", ".css", ".c", ".cpp", ".h",
    ".java", ".go", ".rs", ".rb", ".php",
    ".sh", ".md", ".sql",
    ".mp3", ".wav", ".ogg", ".m4a",
}

TEXT_EXTENSIONS = {
    ".txt", ".csv", ".json", ".md",
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".html", ".css", ".c", ".cpp", ".h",
    ".java", ".go", ".rs", ".rb", ".php",
    ".sh", ".sql",
}

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".webm"}


async def read_limited_upload(file: UploadFile, max_bytes: int) -> Optional[bytes]:
    """Read an upload fully, returning None as soon as it exceeds the cap."""
    chunks: List[bytes] = []
    total = 0

    while True:
        chunk = await file.read(1024 * 1024)

        if not chunk:
            break

        total += len(chunk)

        if total > max_bytes:
            return None

        chunks.append(chunk)

    return b"".join(chunks)


def describe_upload(name: str, data: bytes, content_type: str) -> dict:
    ext = os.path.splitext(name)[1].lower()

    meta = {
        "name": os.path.basename(name),
        "size": len(data),
        "ext": ext,
        "type": content_type or "",
        "readable": ext in TEXT_EXTENSIONS,
    }

    if ext in TEXT_EXTENSIONS:
        text = data.decode("utf-8", errors="replace")
        meta["text"] = text[:MAX_TEXT_CHARS]
        meta["truncated"] = len(text) > MAX_TEXT_CHARS
    else:
        meta["parsed"] = False

    return meta


async def transcribe_audio(filename: str, data: bytes, content_type: str):
    """Transcribe with the first healthy key; returns (payload, error_code)."""
    last_error = "UNKNOWN_ERROR"

    for key in keys.iter_keys():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                response = await client.post(
                    GROQ_TRANSCRIBE_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    data={"model": GROQ_TRANSCRIBE_MODEL, "language": "id"},
                    files={"file": (filename, data, content_type or "audio/webm")},
                )
        except httpx.HTTPError as error:
            last_error = f"network_error:{error.__class__.__name__}"
            continue

        if response.status_code == 200:
            return response.json(), None

        if provider_error(response.status_code):
            keys.skip(key)
            last_error = f"provider_error:{response.status_code}"
            continue

        last_error = f"upstream_error:{response.status_code}"

    return None, last_error
