"""Groq provider client: retries, key rotation and empty-answer repair.

The old implementation could end a request with *no text at all* — the
frontend then rendered `*(empty response)*`. Reasoning models (gpt-oss)
sometimes spend the entire token budget on hidden reasoning and return an
empty `content`, or stream only whitespace. Everything in this module is
about guaranteeing that we always come back with either real text or a
clear, actionable failure message.
"""

import json
import logging
from typing import Any, AsyncIterator, Dict, NamedTuple, Optional, Tuple

import httpx

from core.config import (
    GROQ_CHAT_URL,
    MAX_TOKENS_CAP,
    REASONING_MODEL_PREFIXES,
    RETRY_REASONING_EFFORT,
)
from core.security import keys, scrub

logger = logging.getLogger("rexwork")


class GroqFailure(NamedTuple):
    code: str
    reason: str
    groq_code: str = ""


def provider_error(status: int) -> bool:
    return status in (401, 403, 429)


def groq_failure(status: int, body: str) -> GroqFailure:
    kind = "provider_error" if provider_error(status) else "upstream_error"
    message: Any = body
    groq_code = ""

    try:
        error = json.loads(body).get("error")
    except (ValueError, AttributeError):
        error = None

    if isinstance(error, dict):
        message = error.get("message") or body
        groq_code = str(error.get("code") or "")

    return GroqFailure(
        f"{kind}:{status}",
        f"The model provider answered HTTP {status}: {scrub(message)}",
        groq_code,
    )


def network_failure(error: Exception) -> GroqFailure:
    name = error.__class__.__name__

    return GroqFailure(
        f"network_error:{name}",
        f"Could not reach the model provider ({name}).",
    )


def first_choice(data: Any) -> Tuple[Dict[str, Any], Optional[str]]:
    choices = data.get("choices") if isinstance(data, dict) else None
    choice = choices[0] if choices and isinstance(choices[0], dict) else {}

    message = choice.get("message")

    return (message if isinstance(message, dict) else {}), choice.get("finish_reason")


def message_text(message: Dict[str, Any]) -> str:
    for field in ("content", "refusal"):
        value = message.get(field)

        if isinstance(value, str) and value.strip():
            return value

    return ""


def empty_reason(finish: Optional[str]) -> str:
    if finish == "length":
        return (
            "The model spent its whole token budget on hidden reasoning "
            "and never wrote an answer (`finish_reason=length`)."
        )

    return (
        "The model finished without writing an answer "
        f"(`finish_reason={finish or 'unknown'}`)."
    )


def _is_reasoning_model(model: str) -> bool:
    return str(model or "").startswith(REASONING_MODEL_PREFIXES)


async def groq_json(payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[GroqFailure]]:
    """POST a non-streaming completion, rotating through the key pool."""
    failure = GroqFailure("NO_KEYS", "No Groq API keys configured.")

    for key in keys.iter_keys():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=20.0)) as client:
                response = await client.post(
                    GROQ_CHAT_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    json=payload,
                )
        except httpx.HTTPError as error:
            failure = network_failure(error)
            continue

        if response.status_code == 200:
            try:
                return response.json(), None
            except ValueError:
                return None, GroqFailure("bad_json", "The provider returned invalid JSON.")

        failure = groq_failure(response.status_code, response.text)

        if provider_error(response.status_code):
            keys.skip(key)
            continue

        break

    return None, failure


def repair_payload(payload: Dict[str, Any], finish: Optional[str], attempt: int) -> Dict[str, Any]:
    """Build a request that is much more likely to produce visible text."""
    retry = {k: v for k, v in payload.items() if k not in ("stream", "stream_options")}

    model = str(retry.get("model") or "")

    if _is_reasoning_model(model):
        retry["reasoning_effort"] = RETRY_REASONING_EFFORT
        retry["include_reasoning"] = False

    budget = int(retry.get("max_tokens") or 0) or 2048

    if finish == "length":
        budget = min(budget * 2, MAX_TOKENS_CAP)
    elif attempt > 0:
        budget = min(budget * 2, MAX_TOKENS_CAP)

    retry["max_tokens"] = max(budget, 512)

    return retry


async def retry_for_text(payload: Dict[str, Any], finish: Optional[str]) -> Tuple[str, str]:
    """Ask the model again (without streaming) until it actually writes text.

    Returns ``(text, reason)``. ``text`` is empty only when every attempt
    failed, in which case ``reason`` explains why.
    """
    last_reason = empty_reason(finish)

    for attempt in range(2):
        retry = repair_payload(payload, finish, attempt)
        logger.warning(
            "no answer text from the model (finish_reason=%s); repair attempt %d",
            finish,
            attempt + 1,
        )

        data, failure = await groq_json(retry)

        if failure:
            last_reason = failure.reason
            continue

        message, next_finish = first_choice(data)
        text = message_text(message)

        if text.strip():
            return text, ""

        last_reason = empty_reason(next_finish)

    return "", last_reason


async def stream_once(
    key: str,
    payload: Dict[str, Any],
    outcome: Dict[str, Any],
) -> AsyncIterator[str]:
    """Stream one completion with a single key, recording state in `outcome`."""
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    timeout = httpx.Timeout(300.0, connect=20.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", GROQ_CHAT_URL, headers=headers, json=payload) as response:
            if response.status_code != 200:
                body = await response.aread()
                outcome["failure"] = groq_failure(
                    response.status_code,
                    body.decode(errors="ignore"),
                )
                return

            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue

                data = line[5:].strip()

                if data == "[DONE]":
                    return

                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                if not isinstance(chunk, dict):
                    continue

                x_groq = chunk.get("x_groq")
                problem = chunk.get("error") or (
                    x_groq.get("error") if isinstance(x_groq, dict) else None
                )

                if problem:
                    if isinstance(problem, dict):
                        problem = problem.get("message") or problem

                    outcome["problem"] = scrub(problem)
                    return

                choices = chunk.get("choices") or []

                if not choices or not isinstance(choices[0], dict):
                    continue

                choice = choices[0]
                delta = choice.get("delta") or {}
                finish = choice.get("finish_reason")

                if finish:
                    outcome["finish"] = finish

                reasoning = delta.get("reasoning") or delta.get("reasoning_content")

                if isinstance(reasoning, str) and reasoning:
                    outcome["reasoning"] = outcome.get("reasoning", "") + reasoning

                if isinstance(delta.get("refusal"), str):
                    outcome["refusal"] = outcome.get("refusal", "") + delta["refusal"]

                content = delta.get("content")

                if isinstance(content, str) and content:
                    yield content
