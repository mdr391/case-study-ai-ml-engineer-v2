"""FastAPI entrypoint for the session service skeleton.

Run:  uvicorn session_service.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from session_service.models import (
    CreateSessionRequest,
    HealthResponse,
    MessageAcceptedResponse,
    MessageRequest,
    SessionCreatedResponse,
)
from session_service.repository import InMemorySessionRepository

app = FastAPI(title="Agent Session Service (skeleton)", version="0.1.0")

# Module-level singleton is fine for the in-memory skeleton.
repository = InMemorySessionRepository()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/sessions", response_model=SessionCreatedResponse, status_code=201)
def create_session(request: CreateSessionRequest | None = None) -> SessionCreatedResponse:
    request = request or CreateSessionRequest()
    session = repository.create(channel=request.channel, metadata=request.metadata)
    return SessionCreatedResponse(
        session_id=session.session_id,
        trace_id=session.trace_id,
        created_at=session.created_at,
    )


@app.post(
    "/sessions/{session_id}/messages",
    response_model=MessageAcceptedResponse,
)
def add_message(session_id: str, request: MessageRequest) -> MessageAcceptedResponse:
    session = repository.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "session_not_found", "message": f"No session '{session_id}'."},
        )
    message = repository.add_message(session_id, role=request.role, text=request.text)
    assert message is not None  # session existed under the same repository lock scope
    return MessageAcceptedResponse(
        session_id=session.session_id,
        trace_id=session.trace_id,
        message_id=message.message_id,
        index=message.index,
        role=message.role,
        text=message.text,
        received_at=message.received_at,
    )
