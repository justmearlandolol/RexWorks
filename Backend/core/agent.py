import json
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List

from core.chat import failure_notice
from core.http import sse
from core.modes import MODES
from core.provider import first_choice, groq_json, message_text, retry_for_text
from core.security import redact_secrets
from core.validation import build_messages

logger = logging.getLogger("rexwork")

AGENT_MAX_STEPS = 6
AGENT_OUTPUT_CHARS = 4000
AGENT_PREVIEW_CHARS = 800
AGENT_COMMAND_TIMEOUT = 60
AGENT_SANDBOX_LIMIT = 240

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a bash command in an isolated Linux sandbox.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}


def _create_sandbox():
    """Import the Vercel sandbox lazily so chat never depends on it."""
    from vercel import sandbox as vsandbox

    return vsandbox.create_sandbox(
        persistent=False,
        execution_time_limit=AGENT_SANDBOX_LIMIT,
    )


async def run_bash(box, command: str) -> str:
    try:
        result = await box.run_command(
            "bash",
            ["-c", command],
            capture_output=True,
            kill_after=AGENT_COMMAND_TIMEOUT,
        )
    except Exception as error:  # pragma: no cover - sandbox specific
        return f"sandbox_error:{error.__class__.__name__}"

    stdout = (result.stdout or b"").decode(errors="replace")
    stderr = (result.stderr or b"").decode(errors="replace")

    return f"exit={result.returncode}\n{stdout}{stderr}"[:AGENT_OUTPUT_CHARS]


def text_only(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Strip tools so the final step answers in plain text."""
    request = dict(payload)

    if any(m.get("role") == "tool" for m in request["messages"]):
        request["tool_choice"] = "none"
    else:
        request.pop("tools", None)
        request.pop("tool_choice", None)

    return request


def _command_from_call(call: Dict[str, Any]) -> str:
    try:
        return str(json.loads(call["function"]["arguments"])["command"])
    except (KeyError, TypeError, ValueError):
        return ""


def make_agent_stream(mode: str, messages: List[Dict[str, Any]], extra: Dict[str, Any]):
    async def generator():
        shown = False
        answered = False
        box = None

        try:
            convo = build_messages(mode, messages, MODES)

            async with AsyncExitStack() as stack:
                for step in range(AGENT_MAX_STEPS):
                    final_step = step == AGENT_MAX_STEPS - 1

                    payload = {
                        "model": MODES[mode]["model"],
                        "messages": convo,
                        "tools": [BASH_TOOL],
                        "tool_choice": "none" if final_step else "auto",
                        "temperature": extra.get("temperature", 0.7),
                        "max_tokens": extra.get("max_tokens", 2048),
                    }

                    data, failure = await groq_json(payload)

                    if failure and failure.groq_code != "tool_use_failed":
                        yield failure_notice(failure.reason, after_text=shown)
                        answered = True
                        break

                    if failure:
                        logger.warning("tool call rejected: %s", failure.reason)

                    message, finish = first_choice(data)
                    calls = message.get("tool_calls") or []

                    if not calls:
                        text = message_text(message)

                        if not text.strip():
                            text, reason = await retry_for_text(text_only(payload), finish)
                        else:
                            reason = ""

                        if text.strip():
                            yield sse({"delta": redact_secrets(text)})
                        else:
                            yield failure_notice(reason, after_text=shown)

                        answered = True
                        break

                    convo.append({
                        "role": "assistant",
                        "content": message.get("content") or "",
                        "tool_calls": calls,
                    })

                    for call in calls:
                        command = _command_from_call(call)
                        label = " ".join(command.split())[:120].replace("]", ")")

                        yield sse({"delta": f"[bash: {label}]\n"})
                        shown = True

                        if not command:
                            output = "invalid_arguments"
                        else:
                            if box is None:
                                try:
                                    box = await stack.enter_async_context(_create_sandbox())
                                except Exception as error:
                                    logger.warning("sandbox unavailable: %s", error.__class__.__name__)
                                    output = f"sandbox_unavailable:{error.__class__.__name__}"
                                else:
                                    output = await run_bash(box, command)
                            else:
                                output = await run_bash(box, command)

                        output = redact_secrets(output)

                        yield sse({"delta": f"```\n{output[:AGENT_PREVIEW_CHARS]}\n```\n\n"})

                        convo.append({
                            "role": "tool",
                            "tool_call_id": call.get("id"),
                            "content": output,
                        })

        except Exception as error:  # pragma: no cover - defensive
            logger.exception("coding agent failed")

            if not answered:
                yield failure_notice(
                    f"The coding agent failed ({error.__class__.__name__}).",
                    after_text=shown,
                )

        yield sse({"done": True})

    return generator
