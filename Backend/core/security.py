import base64
import hashlib
import json
import logging
import os
import re
import secrets
import time
from typing import Dict, List, Optional

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from core.config import (
    APP_TOKEN,
    KEY_COOLDOWN_SECONDS,
    MAX_API_KEYS,
    OPEN_PATHS,
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
)
from core.http import error_response

logger = logging.getLogger("rexwork")


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


# --- Request authentication (APP_TOKEN or Supabase JWT) -----------------

LOGIN_CACHE_SECONDS = 300
LOGIN_REJECT_SECONDS = 30
LOGIN_CACHE_LIMIT = 2000
MAX_LOGIN_TOKEN_CHARS = 8192

LOGIN_TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"
)
LOGIN_KEY_PATTERN = re.compile(r"[A-Za-z0-9._\-]{20,512}")

accepted_logins: Dict[str, float] = {}
rejected_logins: Dict[str, float] = {}


def _is_open_path(path: str) -> bool:
    clean = path.rstrip("/") or "/"

    return (
        not clean.startswith("/api/")
        or clean.endswith("/health")
        or clean in OPEN_PATHS
    )


def open_request(request: Request) -> bool:
    if request.method == "OPTIONS":
        return True

    path = request.scope.get("path", "") or request.url.path
    root = request.scope.get("root_path", "")

    if root and path.startswith(root) and not _is_open_path(path[len(root):]):
        return False

    return _is_open_path(path)


def login_token(request: Request) -> str:
    scheme, _, value = request.headers.get("authorization", "").partition(" ")

    if scheme.lower() != "bearer":
        return ""

    return value.strip()


def token_expiry(token: str) -> Optional[float]:
    if (
        len(token) > MAX_LOGIN_TOKEN_CHARS
        or not LOGIN_TOKEN_PATTERN.fullmatch(token)
    ):
        return None

    payload = token.split(".")[1]

    try:
        claims = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
        expiry = float(claims["exp"])
    except (ValueError, KeyError, TypeError):
        return None

    if not 0 < expiry < 1e12:
        return None

    return expiry


def _remember_login(cache: Dict[str, float], digest: str, until: float) -> None:
    if len(cache) >= LOGIN_CACHE_LIMIT:
        now = time.time()

        for key in [k for k, v in cache.items() if v <= now]:
            del cache[key]

        if len(cache) >= LOGIN_CACHE_LIMIT:
            cache.clear()

    cache[digest] = until


def _login_required() -> JSONResponse:
    return error_response(
        401,
        "LOGIN_REQUIRED",
        "You are not logged in. Reload the page and log in again.",
    )


def _login_expired() -> JSONResponse:
    return error_response(
        401,
        "LOGIN_EXPIRED",
        "Your login was not accepted or has expired. Reload the page and log in again.",
    )


def _login_unavailable() -> JSONResponse:
    return error_response(
        503,
        "AUTH_UNAVAILABLE",
        "Could not check your login right now. Try again in a moment.",
    )


async def check_login(request: Request, token: str) -> Optional[JSONResponse]:
    expiry = token_expiry(token) if token else None

    if expiry is None:
        return _login_required()

    now = time.time()

    if expiry <= now:
        return _login_expired()

    digest = hashlib.sha256(token.encode()).hexdigest()

    if accepted_logins.get(digest, 0) > now:
        return None

    if rejected_logins.get(digest, 0) > now:
        return _login_expired()

    apikey = SUPABASE_ANON_KEY or request.headers.get("apikey", "").strip()

    if not SUPABASE_URL or not LOGIN_KEY_PATTERN.fullmatch(apikey):
        return error_response(
            503,
            "AUTH_NOT_CONFIGURED",
            "Supabase authentication is not configured on this server.",
        )

    auth_user_url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/user"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.get(
                auth_user_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": apikey,
                },
            )
    except httpx.HTTPError as error:
        logger.warning("login check failed: %s", error.__class__.__name__)
        return _login_unavailable()

    try:
        body = response.json()
    except ValueError:
        body = None

    if not isinstance(body, dict):
        body = {}

    user = body.get("user") if isinstance(body.get("user"), dict) else body

    if response.status_code == 200 and isinstance(user.get("id"), str) and user["id"]:
        _remember_login(
            accepted_logins,
            digest,
            min(now + LOGIN_CACHE_SECONDS, expiry),
        )
        return None

    if response.status_code in (401, 403):
        if "error_code" in body or "msg" in body:
            _remember_login(
                rejected_logins,
                digest,
                now + LOGIN_REJECT_SECONDS,
            )
            return _login_expired()

        logger.warning("login service rejected the Supabase key")
        return error_response(
            401,
            "AUTH_KEY_REJECTED",
            "The login service did not accept this app's key.",
        )

    logger.warning("login check answered HTTP %s", response.status_code)
    return _login_unavailable()


async def token_guard(request: Request, call_next):
    if open_request(request):
        return await call_next(request)

    supplied = request.headers.get("x-app-token", "").strip()

    if supplied:
        if APP_TOKEN and secrets.compare_digest(supplied.encode(), APP_TOKEN.encode()):
            return await call_next(request)

        return error_response(401, "UNAUTHORIZED", "Invalid or missing token.")

    bearer = login_token(request)

    if bearer:
        failure = await check_login(request, bearer)

        if failure is not None:
            return failure

        return await call_next(request)

    if APP_TOKEN:
        return error_response(401, "UNAUTHORIZED", "Invalid or missing token.")

    return _login_required()
