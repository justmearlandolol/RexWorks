"""Ad-hoc end-to-end smoke check (no network, fake provider)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.chat as chat  # noqa: E402


async def fake_stream_once(key, payload, outcome):
    outcome["finish"] = "length"
    for piece in ["", "  ", "\n"]:
        yield piece


async def fake_retry(payload, finish):
    return "Real answer from the model.", ""


chat.stream_once = fake_stream_once
chat.retry_for_text = fake_retry
chat.keys.keys = ["gsk_fake"]
chat.keys.iter_keys = lambda: ["gsk_fake"]
chat.keys.skip = lambda key: None
chat.keys.count = lambda: 1

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

c = TestClient(main.app)

r = c.post("/api/chat", json={"mode": "chat", "messages": [{"role": "user", "content": "halo"}]})
print("chat status:", r.status_code)
print(r.text)
assert "Real answer from the model." in r.text
assert "empty response" not in r.text

for path in ["/api/health", "/api/status", "/api/models"]:
    print(path, c.get(path).status_code)

print("bad json ->", c.post("/api/chat", content=b"xx", headers={"Content-Type": "application/json"}).status_code)
print("empty msgs ->", c.post("/api/chat", json={"messages": []}).status_code)
print("unknown mode ->", c.post("/api/chat", json={"mode": "nope", "messages": [{"role": "user", "content": "a"}]}).status_code)
print("canvas empty ->", c.post("/api/canvas", json={"content": "  "}).status_code)
print("404 shape ->", c.get("/api/does-not-exist").json())
print("OK")
