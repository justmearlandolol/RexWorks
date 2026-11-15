

import asyncio
import base64
import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.agent as agent_mod  # noqa: E402
import core.chat as chat_mod  # noqa: E402
import core.provider as provider_mod  # noqa: E402
import core.security as security_mod  # noqa: E402
import main as main_mod  # noqa: E402
from core.security import KeyManager  # noqa: E402
from core.validation import strip_ui_noise, validate_messages  # noqa: E402


def _fake_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"ES256","typ":"JWT"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "user-123", "exp": exp}).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.sig_part"


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


def test_token_guard_open_routes_and_rejects_missing_auth(monkeypatch):
    monkeypatch.setattr(security_mod, "APP_TOKEN", "top-secret")
    client = TestClient(main_mod.app)

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/status").status_code == 200

    res = client.get("/api/models")
    assert res.status_code == 401
    assert res.json()["error"] == "UNAUTHORIZED"


def test_token_guard_accepts_app_token_and_supabase_jwt(monkeypatch):
    monkeypatch.setattr(security_mod, "APP_TOKEN", "top-secret")
    monkeypatch.setattr(security_mod, "accepted_logins", {})
    monkeypatch.setattr(security_mod, "rejected_logins", {})

    class FakeResp:
        status_code = 200

        def json(self):
            return {"id": "user-123"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers=None):
            assert headers["Authorization"].startswith("Bearer ")
            assert headers["apikey"]
            return FakeResp()

    monkeypatch.setattr(security_mod.httpx, "AsyncClient", FakeClient)

    client = TestClient(main_mod.app)

    assert client.get("/api/models", headers={"X-App-Token": "top-secret"}).status_code == 200
    assert client.get("/api/models", headers={"X-App-Token": "wrong"}).status_code == 401

    jwt_tok = _fake_jwt(int(time.time()) + 3600)
    assert client.get(
        "/api/models",
        headers={"Authorization": f"Bearer {jwt_tok}", "X-App-Token": ""},
    ).status_code == 200

    expired_tok = _fake_jwt(int(time.time()) - 60)
    expired_res = client.get(
        "/api/models",
        headers={"Authorization": f"Bearer {expired_tok}"},
    )
    assert expired_res.status_code == 401
    assert expired_res.json()["error"] == "LOGIN_EXPIRED"

    monkeypatch.setattr(security_mod, "APP_TOKEN", "")
    assert client.get("/api/models").status_code == 401
    assert client.get("/api/models").json()["error"] == "LOGIN_REQUIRED"
    assert client.get(
        "/api/models",
        headers={"Authorization": f"Bearer {jwt_tok}"},
    ).status_code == 200


def test_coding_agent_does_not_require_sandbox_for_plain_reply(monkeypatch):
    async def fake_groq_json(payload):
        return {
            "choices": [
                {
                    "message": {"content": "Hello from coding agent!"},
                    "finish_reason": "stop",
                }
            ]
        }, None

    def fail_if_called():
        raise AssertionError("Sandbox should not be created when no bash tool is called")

    monkeypatch.setattr(agent_mod, "groq_json", fake_groq_json)
    monkeypatch.setattr(agent_mod, "_create_sandbox", fail_if_called)

    frames = run(_drive(agent_mod.make_agent_stream("coding", [{"role": "user", "content": "hi"}], {})))
    text = collect(frames)

    assert "Hello from coding agent!" in text
    assert '"done": true' in text


def test_coding_agent_handles_unavailable_sandbox_gracefully(monkeypatch):
    calls = {"n": 0}

    async def fake_groq_json(payload):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "bash",
                                        "arguments": '{"command": "ls"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }, None
        return {
            "choices": [
                {
                    "message": {"content": "Sandbox unavailable, answering directly."},
                    "finish_reason": "stop",
                }
            ]
        }, None

    def fail_sandbox():
        raise RuntimeError("Missing credentials")

    monkeypatch.setattr(agent_mod, "groq_json", fake_groq_json)
    monkeypatch.setattr(agent_mod, "_create_sandbox", fail_sandbox)

    frames = run(_drive(agent_mod.make_agent_stream("coding", [{"role": "user", "content": "ls"}], {})))
    text = collect(frames)

    assert "sandbox_unavailable:RuntimeError" in text
    assert "Sandbox unavailable, answering directly." in text
    assert '"done": true' in text


async def _drive(gen_factory):
    frames = []
    async for frame in gen_factory():
        frames.append(frame)
    return frames
