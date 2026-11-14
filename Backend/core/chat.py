"""Chat streaming pipeline.

`make_stream` turns a validated conversation into a server-sent-event
stream. It is defensive on purpose:

* every key in the pool is tried before giving up,
* a stream that produces only whitespace is repaired with a second,
  non-streaming request,
* the client always receives either real text or a readable failure notice
  — never a silent `(empty response)`.
"""

import logging
from contextlib import aclosing
from typing import Any, Dict, List, Optional

import httpx

from core.config import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from core.http import sse
from core.modes import MODES
from core.provider import network_failure, retry_for_text, stream_once
from core.security import keys, redact_secrets
from core.validation import build_messages

logger = logging.getLogger("rexwork")

FAILURE_TITLE = "**SOMETHING WENT WRONG.**"
FAILURE_FOOTER = "[ TRY AGAIN ]"


def failure_notice(reason: str, after_text: bool = False) -> str:
    logger.warning("chat failed: %s", reason)
    lead = "\n\n" if after_text else ""

    return sse({"delta": f"{lead}{FAILURE_TITLE}\n\n{reason}\n\n{FAILURE_FOOTER}"})


def build_payload(mode: str, messages: List[Dict[str, Any]], extra: Dict[str, Any], stream: bool = True) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": MODES[mode]["model"],
        "messages": build_messages(mode, messages, MODES),
        "temperature": extra.get("temperature", DEFAULT_TEMPERATURE),
        "max_tokens": extra.get("max_tokens", DEFAULT_MAX_TOKENS),
    }

    if stream:
        payload["stream"] = True

    return payload


def _clean(text: str) -> str:
    return text if text.strip() else ""


async def _ensure_text(
    payload: Dict[str, Any],
    outcome: Dict[str, Any],
    shown: bool,
    problem: Optional[str],
    refusal: str,
):
    """Decide what to emit when the model produced no usable delta text.

    Yields SSE frames (if any) and the final reasoning string.
    """
    if refusal.strip():
        yield sse({"delta": redact_secrets(refusal.strip())})
        return

    if problem:
        logger.warning("stream stopped early: %s", problem)

    text, reason = await retry_for_text(payload, outcome.get("finish"))

    if text.strip():
        yield sse({"delta": redact_secrets(text)})
        return

    # Last resort: if the model only produced hidden reasoning, show it so
    # the user is not staring at an empty bubble.
    reasoning = (outcome.get("reasoning") or "").strip()

    if reasoning:
        yield sse({
            "delta": (
                "> *The model returned only internal reasoning, not a final "
                "answer. Showing the raw reasoning below:*\n\n"
                + redact_secrets(reasoning)
            )
        })
        return

    if problem:
        yield failure_notice(f"The answer was cut off: {problem}", after_text=shown)
        return

    yield failure_notice(reason, after_text=shown)


def make_stream(mode: str, messages: List[Dict[str, Any]], extra: Dict[str, Any]):
    async def generator():
        order = keys.iter_keys()

        if not order:
            yield sse({"error": "NO_KEYS", "message": "No Groq API keys configured."})
            yield sse({"done": True})
            return

        shown = False

        try:
            payload = build_payload(mode, messages, extra, stream=True)
            outcome: Dict[str, Any] = {}

            for key in order:
                outcome = {}

                try:
                    async with aclosing(stream_once(key, payload, outcome)) as pieces:
                        async for piece in pieces:
                            clean = _clean(piece)

                            if not clean:
                                continue

                            shown = True
                            yield sse({"delta": redact_secrets(clean)})
                except httpx.HTTPError as error:
                    outcome["failure"] = network_failure(error)

                failure = outcome.get("failure")

                if failure is None or shown:
                    break

                if failure.code.startswith("provider_error"):
                    keys.skip(key)
                    continue

                if failure.code.startswith("network_error"):
                    continue

                break

            failure = outcome.get("failure")
            problem = failure.reason if failure else outcome.get("problem")
            refusal = outcome.get("refusal") or ""

            if shown:
                if problem:
                    yield failure_notice(f"The answer was cut off: {problem}", after_text=True)
            elif failure:
                yield failure_notice(failure.reason)
            else:
                async for frame in _ensure_text(payload, outcome, shown, problem, refusal):
                    yield frame

        except Exception as error:  # pragma: no cover - defensive
            logger.exception("chat stream failed")
            yield failure_notice(
                f"The chat backend failed ({error.__class__.__name__}).",
                after_text=shown,
            )

        yield sse({"done": True})

    return generator
