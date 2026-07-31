"""Session service tests: health/create smoke, and the appointment workflow
driven end-to-end over HTTP via POST /sessions/{id}/messages."""

from __future__ import annotations

from fastapi.testclient import TestClient

from session_service.main import app

client = TestClient(app)


def _new_session() -> str:
    created = client.post("/sessions", json={"channel": "chat"})
    assert created.status_code == 201
    return created.json()["session_id"]


def test_session_service_smoke() -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    created = client.post("/sessions", json={"channel": "chat"})
    assert created.status_code == 201
    body = created.json()
    assert body["session_id"].startswith("sess_")
    assert body["trace_id"].startswith("trace_")

    # First transcript turn advances the workflow (request -> verification).
    turn = client.post(
        f"/sessions/{body['session_id']}/messages",
        json={"text": "I'd like to book an appointment", "role": "caller"},
    )
    assert turn.status_code == 200
    tbody = turn.json()
    assert tbody["session_id"] == body["session_id"]
    assert tbody["trace_id"] == body["trace_id"]
    assert tbody["state"] == "awaiting_verification"
    assert tbody["done"] is False
    assert tbody["turn_index"] == 0
    assert tbody["reply"]  # non-empty agent reply

    # Unknown session -> structured 404.
    missing = client.post("/sessions/sess_nope/messages", json={"text": "hi"})
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"] == "session_not_found"


def test_appointment_conversation_end_to_end_over_http() -> None:
    sid = _new_session()

    def say(text: str) -> dict:
        r = client.post(f"/sessions/{sid}/messages", json={"text": text})
        assert r.status_code == 200
        return r.json()

    assert say("I want to book an appointment")["state"] == "awaiting_verification"
    assert say("Nguyen 1990-02-14")["state"] == "awaiting_reason"

    offered = say("annual check-up")
    assert offered["state"] == "awaiting_slot_selection"
    assert offered["reply"].count(") ") == 3  # no more than three slots

    readback = say("1")
    assert readback["state"] == "awaiting_confirmation"
    for field in ("Dr. Alice Nguyen", "Clinic North", "2026-08-03", "09:00"):
        assert field in readback["reply"]

    booked = say("yes")
    assert booked["state"] == "booked"
    assert booked["done"] is True
    assert "draft" in booked["reply"].lower()

    # Duplicate confirmation over HTTP: still booked, no error, no second draft.
    again = say("yes")
    assert again["state"] == "booked"
    assert again["done"] is True
    assert "already" in again["reply"].lower()


def test_failed_verification_over_http_hands_off() -> None:
    sid = _new_session()

    def say(text: str) -> dict:
        return client.post(f"/sessions/{sid}/messages", json={"text": text}).json()

    say("book an appointment")
    assert say("Wrong 2000-01-01")["state"] == "awaiting_verification"  # attempt 1
    handed = say("Wrong 2000-01-01")  # attempt 2 -> handoff
    assert handed["state"] == "handoff"
    assert handed["done"] is True
