"""Chat, search and canvas streaming endpoints."""

from typing import Dict

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from core.agent import make_agent_stream
from core.chat import make_stream
from core.config import (
    MAX_CANVAS_CHARS,
    MAX_MESSAGE_CHARS,
)
from core.http import SSE_HEADERS, error_response
from core.modes import MODES, VISION_MODE_KEY, vision_available
from core.security import has_keys
from core.validation import clamp_generation, safe_mode, validate_messages

router = APIRouter()


async def _json_object(request: Request):
    try:
        body = await request.json()
    except Exception:
        return None, error_response(400, "INVALID_JSON", "Request body must contain valid JSON.")

    if not isinstance(body, dict):
        return None, error_response(400, "INVALID_BODY", "Request body must be an object.")

    return body, None


def _stream_response(stream) -> StreamingResponse:
    return StreamingResponse(stream(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/api/chat")
async def chat(request: Request):
    body, error = await _json_object(request)

    if error:
        return error

    mode = safe_mode(body.get("mode", "chat"), MODES)
    messages, validation_error = validate_messages(body.get("messages", []))

    if validation_error:
        return error_response(400, validation_error, "Invalid messages payload.")

    if not messages:
        return error_response(400, "EMPTY_MESSAGES", "At least one message is required.")

    if not has_keys():
        return error_response(503, "NO_KEYS", "No Groq API keys configured.")

    if mode == VISION_MODE_KEY and not vision_available():
        return error_response(
            400,
            "VISION_MODEL_UNAVAILABLE",
            "No compatible Vision model is configured.",
        )

    extra = clamp_generation(body.get("extra"))
    factory = make_agent_stream if mode == "coding" else make_stream

    return _stream_response(factory(mode, messages, extra))


@router.post("/api/search")
async def search(request: Request):
    body, error = await _json_object(request)

    if error:
        return error

    query = body.get("query", "")

    if not isinstance(query, str):
        return error_response(400, "INVALID_QUERY", "Query must be a string.")

    query = query.strip()

    if not query:
        return error_response(400, "EMPTY_QUERY", "Search query cannot be empty.")

    if len(query) > MAX_MESSAGE_CHARS:
        return error_response(400, "QUERY_TOO_LONG", "Search query is too long.")

    if not has_keys():
        return error_response(503, "NO_KEYS", "No Groq API keys configured.")

    messages = [{"role": "user", "content": query}]
    extra = {"temperature": 0.4, "max_tokens": 2048}

    return _stream_response(make_stream("chat", messages, extra))


CANVAS_ACTIONS: Dict[str, str] = {
    "refine": "Improve and polish the following content. Keep its meaning and format:\n\n",
    "explain": "Explain the following code clearly:\n\n",
    "fix": "Find and fix bugs in the following code. Show the corrected code:\n\n",
    "expand": "Expand the following into a more complete version:\n\n",
}


@router.post("/api/canvas")
async def canvas(request: Request):
    body, error = await _json_object(request)

    if error:
        return error

    mode = safe_mode(body.get("mode", "chat"), MODES)
    action = body.get("action", "refine")
    content = body.get("content", "")

    if not isinstance(content, str):
        return error_response(400, "INVALID_CONTENT", "Canvas content must be a string.")

    content = content.strip()

    if not content:
        return error_response(400, "EMPTY_CONTENT", "Canvas content cannot be empty.")

    if len(content) > MAX_CANVAS_CHARS:
        return error_response(413, "CONTENT_TOO_LONG", "Canvas content exceeds the limit.")

    if not has_keys():
        return error_response(503, "NO_KEYS", "No Groq API keys configured.")

    if mode == VISION_MODE_KEY and not vision_available():
        return error_response(
            400,
            "VISION_MODEL_UNAVAILABLE",
            "No compatible Vision model is configured.",
        )

    prefix = CANVAS_ACTIONS.get(action, "Process the following:\n\n")
    messages = [{"role": "user", "content": prefix + content}]
    extra = {"temperature": 0.6, "max_tokens": 2048}

    return _stream_response(make_stream(mode, messages, extra))
