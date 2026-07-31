"""FastAPI entrypoint for the session service.

`POST /sessions/{id}/messages` drives the deterministic appointment workflow:
each transcript turn advances the session's typed ConversationState and returns
the agent's reply. No real LLM/voice — the workflow uses deterministic rules and
in-memory fakes.

Run:  uvicorn session_service.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from appointment.engine import AppointmentWorkflow
from appointment.fakes import (
    FakeHandoffService,
    FakePatientDirectory,
    FakeSchedulingProvider,
    InMemoryAuditSink,
)
from session_service.models import (
    CreateSessionRequest,
    HealthResponse,
    MessageRequest,
    SessionCreatedResponse,
    TurnResponse,
)
from session_service.repository import InMemorySessionRepository

app = FastAPI(title="Agent Session Service", version="0.2.0")

# In-memory singletons for the skeleton/demo.
repository = InMemorySessionRepository()
audit_sink = InMemoryAuditSink()
workflow = AppointmentWorkflow(
    directory=FakePatientDirectory(),
    scheduling=FakeSchedulingProvider(),
    handoff=FakeHandoffService(),
    audit=audit_sink,
)


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


@app.post("/sessions/{session_id}/messages", response_model=TurnResponse)
def add_message(session_id: str, request: MessageRequest) -> TurnResponse:
    session = repository.get(session_id)
    context = repository.get_context(session_id)
    if session is None or context is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "session_not_found", "message": f"No session '{session_id}'."},
        )
    # Record the caller's transcript turn, then advance the workflow.
    stored = repository.add_message(session_id, role=request.role, text=request.text)
    assert stored is not None
    reply = workflow.handle(context, request.text)
    return TurnResponse(
        session_id=session.session_id,
        trace_id=session.trace_id,
        state=reply.state,
        reply=reply.message,
        done=reply.done,
        turn_index=stored.index,
    )
