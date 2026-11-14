"""API-key rotation, secret redaction and request authentication."""

import os
import re
import secrets
import time
from typing import Dict, List

from fastapi import Request

from core.config import APP_TOKEN, KEY_COOLDOWN_SECONDS, MAX_API_KEYS, OPEN_PATHS
from core.http import error_response


class KeyManager:
    """Round-robin pool of Groq API keys with per-key cooldown."""

    COOLDOWN_SECONDS = KEY_COOLDOWN_SECONDS

    def __init__(self) -> None:
        self.keys: List[str] = []
        self.skipped: Dict[str, float] = {}
        self.index = 0
        self.load()

    def load(self) -> None:
        found: List[str] = []

        for i in range(1, MAX_API_KEYS + 1):
            value = (os.getenv(f"GROQ_API_KEY_{i}") or "").strip()

            if not value:
                # Also accept the un-suffixed name for the first key.
                if i == 1:
                    value = (os.getenv("GROQ_API_KEY") or "").strip()

            if value:
                found.append(value)

        self.keys = list(dict.fromkeys(found))

    def count(self) -> int:
        return len(self.keys)

    def skip(self, key: str) -> None:
        self.skipped[key] = time.time() + self.COOLDOWN_SECONDS

    def usable(self) -> List[str]:
        now = time.time()
        available = [k for k in self.keys if now >= self.skipped.get(k, 0)]

        return available or self.keys

    def iter_keys(self) -> List[str]:
        available = self.usable()

        if not available:
            return []

        count = len(available)
        start = self.index % count
        ordered = available[start:] + available[:start]
        self.index = (self.index + 1) % count

        return ordered


keys = KeyManager()


def has_keys() -> bool:
    return keys.count() > 0


# --- Secret redaction ---------------------------------------------------

GSK_PATTERN = re.compile(r"gsk_[A-Za-z0-9_\-]{16,}")
ORG_PATTERN = re.compile(r"\borg_[A-Za-z0-9]{6,}")


def redact_secrets(text: str) -> str:
    cleaned = GSK_PATTERN.sub("[REDACTED]", text)

    for secret in keys.keys:
        if secret and secret in cleaned:
            cleaned = cleaned.replace(secret, "[REDACTED]")

    return cleaned


def scrub(text, limit: int = 300) -> str:
    cleaned = ORG_PATTERN.sub("org_[REDACTED]", redact_secrets(str(text)))

    return " ".join(cleaned.split())[:limit]


# --- App-token guard ----------------------------------------------------

def _allowed_origins() -> List[str]:
    raw = os.getenv("ALLOWED_ORIGINS") or (
        "https://rexworks-backend.vercel.app,"
        "https://rexworks.vercel.app,"
        "http://localhost:8000,"
        "http://127.0.0.1:8000,"
        "http://localhost:3000,"
        "http://127.0.0.1:3000"
    )

    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def _origin_allowed(request: Request) -> bool:
    """Origin allow-list used when no APP_TOKEN is configured.

    Requests without an Origin header (curl, server-to-server, same-origin
    navigations) are allowed so the API stays usable from the CLI.
    """
    origin = (request.headers.get("origin") or "").rstrip("/")

    if not origin:
        return True

    if origin in _allowed_origins():
        return True

    # Vercel preview deployments of this project.
    if origin.endswith(".vercel.app"):
        return True

    # Any localhost / 127.0.0.1 port during development.
    if re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", origin):
        return True

    return False


async def token_guard(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"

    if (
        request.method == "OPTIONS"
        or not path.startswith("/api/")
        or path.endswith("/health")
        or path in OPEN_PATHS
    ):
        return await call_next(request)

    if not APP_TOKEN:
        # No shared secret configured: fall back to an origin allow-list so
        # the chat still works while random third-party sites cannot use the
        # API from a browser.
        if not _origin_allowed(request):
            return error_response(
                403,
                "ORIGIN_NOT_ALLOWED",
                "This origin is not allowed to use the API.",
            )

        return await call_next(request)

    supplied = request.headers.get("x-app-token", "")

    if not secrets.compare_digest(supplied.encode(), APP_TOKEN.encode()):
        return error_response(401, "UNAUTHORIZED", "Invalid or missing token.")

    return await call_next(request)
