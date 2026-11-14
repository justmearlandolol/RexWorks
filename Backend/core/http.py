"""Small HTTP helpers shared by every route."""

import json
from typing import Any, Dict

from fastapi.responses import JSONResponse


def error_response(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": error, "message": message},
    )


def sse(data: Dict[str, Any]) -> str:
    """Serialise one server-sent-event frame."""
    return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

ERROR_CODES = {
    400: "BAD_REQUEST",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
    429: "RATE_LIMITED",
}


def http_error_code(status: int) -> str:
    return ERROR_CODES.get(status, f"HTTP_{status}")
