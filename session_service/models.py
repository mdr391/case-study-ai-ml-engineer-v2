"""Typed request/response models for the session service (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["caller", "agent", "system"]


# --- Requests --------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    """Optional metadata for a new session. All fields optional so an empty
    ``POST /sessions`` body is valid."""

    model_config = ConfigDict(extra="forbid")

    channel: str | None = Field(
        default=None,
        description="Origin channel label, e.g. 'voice' or 'chat' (synthetic; informational only).",
    )
    metadata: dict[str, str] | None = Field(
        default=None, description="Arbitrary string key/value tags."
    )


class MessageRequest(BaseModel):
    """A single text-transcript turn appended to a session."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, description="Transcript text for this turn.")
    role: Role = Field(default="caller", description="Who produced this turn.")


# --- Responses -------------------------------------------------------------


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"


class SessionCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    trace_id: str = Field(description="Correlation id for logs/traces of this session.")
    status: Literal["open"] = "open"
    created_at: datetime


class MessageAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    trace_id: str
    message_id: str
    index: int = Field(ge=0, description="Zero-based position of this turn in the session.")
    role: Role
    text: str
    received_at: datetime


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str
    message: str
