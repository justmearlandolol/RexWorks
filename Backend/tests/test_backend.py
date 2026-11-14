"""Regression tests for the RexWork backend.

Run with:  cd Backend && python -m pytest -q
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.chat as chat_mod  # noqa: E402
import core.provider as provider_mod  # noqa: E402
from core.security import KeyManager  # noqa: E402
from core.validation import strip_ui_noise, validate_messages  # noqa: E402


def collect(frames):
    return "".join(frames)


def test_main_is_small():
    """main.py must stay a thin wiring layer (< 500 lines)."""
    main_py = Path(__file__).resolve().parents[1] / "main.py"
    assert len(main_py.read_text().splitlines()) < 500


def test_strip_ui_noise_removes_placeholder():
    assert strip_ui_noise("*(empty response)*") == ""
    assert strip_ui_noise("**SOMETHING WENT WRONG.**\n\nboom\n\n[ TRY AGAIN ]") == ""
    assert strip_ui_noise("hello\n\n[ TRY AGAIN ]") == "hello\n\n[ TRY AGAIN ]"


def test_validate_messages_rejects_bad_payloads():
    cleaned, err = validate_messages("nope")
    assert cleaned is None and err == "MESSAGES_MUST_BE_ARRAY"

    cleaned, err = validate_messages([{"role": "user", "content": "hi"}])
    assert err is None and cleaned[0]["content"] == "hi"


def test_key_manager_loads_and_rotates(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY_1", "gsk_one")
    monkeypatch.setenv("GROQ_API_KEY_2", "gsk_two")
    manager = KeyManager()
    assert manager.count() == 2
    assert sorted(manager.iter_keys()) == ["gsk_one", "gsk_two"]


def patch_keys(monkeypatch):
    monkeypatch.setattr(chat_mod.keys, "keys", ["gsk_test"])
    monkeypatch.setattr(chat_mod.keys, "count", lambda: 1)
    monkeypatch.setattr(chat_mod.keys, "iter_keys", lambda: ["gsk_test"])
    monkeypatch.setattr(chat_mod.keys, "skip", lambda key: None)


def run(coro):
    return asyncio.run(coro)


def test_empty_stream_is_repaired(monkeypatch):
    """A whitespace-only stream must turn into real text, not an empty bubble."""

    async def fake_stream_once(key, payload, outcome):
        outcome["finish"] = "length"
        if False:
            yield ""
        return

    async def fake_retry(payload, finish):
        return "Recovered answer", ""

    patch_keys(monkeypatch)
    monkeypatch.setattr(chat_mod, "stream_once", fake_stream_once)
    monkeypatch.setattr(chat_mod, "retry_for_text", fake_retry)

    frames = run(_drive(chat_mod.make_stream("chat", [{"role": "user", "content": "hi"}], {})))
    text = collect(frames)

    assert "Recovered answer" in text
    assert "(empty response)" not in text
    assert '"done": true' in text


def test_only_reasoning_is_surfaced(monkeypatch):
    """If the model only emits hidden reasoning we show it instead of nothing."""

    async def fake_stream_once(key, payload, outcome):
        outcome["finish"] = "stop"
        outcome["reasoning"] = "step by step thinking"
        if False:
            yield ""

    async def fake_retry(payload, finish):
        return "", "model wrote nothing"

    patch_keys(monkeypatch)
    monkeypatch.setattr(chat_mod, "stream_once", fake_stream_once)
    monkeypatch.setattr(chat_mod, "retry_for_text", fake_retry)

    frames = run(_drive(chat_mod.make_stream("chat", [{"role": "user", "content": "hi"}], {})))
    text = collect(frames)

    assert "step by step thinking" in text


def test_provider_failure_is_reported(monkeypatch):
    async def fake_stream_once(key, payload, outcome):
        outcome["failure"] = provider_mod.GroqFailure("provider_error:401", "bad key")
        if False:
            yield ""

    patch_keys(monkeypatch)
    monkeypatch.setattr(chat_mod, "stream_once", fake_stream_once)

    frames = run(_drive(chat_mod.make_stream("chat", [{"role": "user", "content": "hi"}], {})))
    text = collect(frames)

    assert "bad key" in text
    assert '"done": true' in text


def test_repair_payload_raises_budget_for_reasoning_models():
    payload = {"model": "openai/gpt-oss-120b", "max_tokens": 256, "stream": True}
    repaired = provider_mod.repair_payload(payload, "length", 0)

    assert "stream" not in repaired
    assert repaired["max_tokens"] >= 512
    assert repaired["reasoning_effort"] == "low"


async def _drive(gen_factory):
    frames = []
    async for frame in gen_factory():
        frames.append(frame)
    return frames
