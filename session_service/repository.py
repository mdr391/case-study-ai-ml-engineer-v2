"""In-memory session repository.

Not durable — state lives in the process and is lost on restart. This stands in
for a real store; the API layer depends only on this class's methods, so a real
backend can replace it without touching the endpoints.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from session_service.models import Role


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class StoredMessage(BaseModel):
    message_id: str
    index: int
    role: Role
    text: str
    received_at: datetime


class Session(BaseModel):
    session_id: str
    trace_id: str
    created_at: datetime
    channel: str | None = None
    metadata: dict[str, str] | None = None
    messages: list[StoredMessage] = Field(default_factory=list)


class InMemorySessionRepository:
    """Thread-safe in-memory store keyed by ``session_id``."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(
        self,
        *,
        channel: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Session:
        session = Session(
            session_id=_new_id("sess"),
            trace_id=_new_id("trace"),
            created_at=_now(),
            channel=channel,
            metadata=metadata,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def add_message(self, session_id: str, *, role: Role, text: str) -> StoredMessage | None:
        """Append a message; returns ``None`` if the session does not exist."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            message = StoredMessage(
                message_id=_new_id("msg"),
                index=len(session.messages),
                role=role,
                text=text,
                received_at=_now(),
            )
            session.messages.append(message)
            return message
