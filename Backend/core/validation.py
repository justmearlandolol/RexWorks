"""Request/response validation and payload build helpers."""

from typing import Any, Dict, List, Optional, Tuple

from core.config import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    MAX_CONTENT_PARTS,
    MAX_MEMORY_ITEMS,
    MAX_MESSAGE_CHARS,
    MAX_MESSAGES,
    MAX_TOKENS_CAP,
)


def safe_mode(mode: Any, modes: Dict[str, Any]) -> str:
    if not isinstance(mode, str):
        return "chat"

    return mode if mode in modes else "chat"


def validate_messages(messages: Any) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    if not isinstance(messages, list):
        return None, "MESSAGES_MUST_BE_ARRAY"

    if len(messages) > MAX_MESSAGES:
        return None, "TOO_MANY_MESSAGES"

    cleaned: List[Dict[str, Any]] = []

    for message in messages:
        if not isinstance(message, dict):
            return None, "INVALID_MESSAGE"

        role = message.get("role")

        if role not in ("user", "assistant"):
            continue

        content = message.get("content", "")

        if isinstance(content, str):
            if len(content) > MAX_MESSAGE_CHARS:
                return None, "MESSAGE_TOO_LONG"
        elif isinstance(content, list):
            if len(content) > MAX_CONTENT_PARTS:
                return None, "TOO_MANY_CONTENT_PARTS"
        else:
            return None, "INVALID_MESSAGE_CONTENT"

        cleaned.append({"role": role, "content": content})

    # `_custom` / `_memory` ride along on the first message from the client.
    first = messages[0] if messages and isinstance(messages[0], dict) else {}

    if cleaned:
        for key in ("_custom", "_memory"):
            if key in first:
                cleaned[0][key] = first[key]

    return cleaned, None


def build_messages(mode: str, messages: List[Dict[str, Any]], modes: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Turn the client conversation into a provider-ready message list."""
    system = modes[mode]["system"]

    custom = None
    memory = None

    if messages and isinstance(messages[0], dict):
        custom = messages[0].get("_custom")
        memory = messages[0].get("_memory")

    if isinstance(memory, list):
        mem_items = []

        for item in memory[:MAX_MEMORY_ITEMS]:
            if not isinstance(item, (str, int, float)):
                continue

            text = str(item).strip()

            if text:
                mem_items.append(text[:300])

        if mem_items:
            system += (
                "\n\n--- USER MEMORY ---\n"
                "Facts the user explicitly asked you to remember. "
                "Use them when relevant, never quote this list back "
                "verbatim, and correct an item if the user updates it:\n"
                + "\n".join("- " + m for m in mem_items)
            )

    if isinstance(custom, str) and custom.strip():
        system += "\n\n--- USER PREFERENCES ---\n" + custom[:5000]

    output: List[Dict[str, Any]] = [{"role": "system", "content": system}]

    for message in messages:
        role = message.get("role")
        content = message.get("content", "")

        if role not in ("user", "assistant"):
            continue

        if role == "assistant" and isinstance(content, str):
            content = strip_ui_noise(content)

            if not content:
                continue

        output.append({"role": role, "content": content})

    return output


# --- UI noise filtering -------------------------------------------------

FAILURE_TITLE = "**SOMETHING WENT WRONG.**"
FAILURE_FOOTER = "[ TRY AGAIN ]"
UI_PLACEHOLDERS = ("*(empty response)*",)
UI_ERROR_TITLES = (FAILURE_TITLE, "**CONNECTION LOST.**")
NOTICE_MAX_CHARS = 700


def strip_ui_noise(content: str) -> str:
    """Drop placeholder/error bubbles so they are never replayed to the model."""
    text = content.strip()

    if text in UI_PLACEHOLDERS:
        return ""

    if text.endswith(FAILURE_FOOTER):
        for title in UI_ERROR_TITLES:
            start = text.rfind(title)

            if start != -1 and len(text) - start <= NOTICE_MAX_CHARS:
                return text[:start].strip()

    return content


def clamp_generation(extra: Any) -> Dict[str, Any]:
    if not isinstance(extra, dict):
        extra = {}

    temperature = extra.get("temperature", DEFAULT_TEMPERATURE)
    max_tokens = extra.get("max_tokens", DEFAULT_MAX_TOKENS)

    try:
        temperature = max(0.0, min(float(temperature), 2.0))
    except (TypeError, ValueError):
        temperature = DEFAULT_TEMPERATURE

    try:
        max_tokens = max(1, min(int(max_tokens), MAX_TOKENS_CAP))
    except (TypeError, ValueError):
        max_tokens = DEFAULT_MAX_TOKENS

    return {"temperature": temperature, "max_tokens": max_tokens}
