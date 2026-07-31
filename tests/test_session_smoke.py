"""One smoke test: health -> create session -> post a transcript message."""

from __future__ import annotations

from fastapi.testclient import TestClient

from session_service.main import app

client = TestClient(app)


def test_session_service_smoke() -> None:
    # health
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    # create session -> session_id + trace_id
    created = client.post("/sessions", json={"channel": "chat"})
    assert created.status_code == 201
    body = created.json()
    session_id = body["session_id"]
    assert session_id.startswith("sess_")
    assert body["trace_id"].startswith("trace_")
    assert body["status"] == "open"

    # post a text-transcript message
    msg = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "I would like to book an appointment.", "role": "caller"},
    )
    assert msg.status_code == 200
    mbody = msg.json()
    assert mbody["session_id"] == session_id
    assert mbody["trace_id"] == body["trace_id"]
    assert mbody["index"] == 0
    assert mbody["text"] == "I would like to book an appointment."

    # unknown session -> structured 404
    missing = client.post("/sessions/sess_does_not_exist/messages", json={"text": "hi"})
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"] == "session_not_found"
