"""Plain data contracts shared across the workflow (no behavior, no deps)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VerifiedPatient(BaseModel):
    """Result of a successful identity check. `patient_id` is an opaque synthetic
    id — never a name/DOB — so it is safe to place in audit events."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str
    display_name: str


class SlotOffer(BaseModel):
    """A single offered appointment slot (synthetic)."""

    model_config = ConfigDict(extra="forbid")

    slot_id: str
    provider_name: str
    location: str
    date: str  # YYYY-MM-DD (synthetic)
    time: str  # HH:MM (synthetic)


class BookingDraft(BaseModel):
    """A non-final booking draft. Nothing is actually booked; staff finalize it."""

    model_config = ConfigDict(extra="forbid")

    draft_id: str
    patient_id: str
    slot_id: str
    provider_name: str
    location: str
    date: str
    time: str
    status: Literal["draft"] = "draft"


class AuditEvent(BaseModel):
    """A sanitized, append-only audit record. `detail` must carry only opaque
    tokens (ids, counts, coarse flags) — never names, DOB, phone, or free-text
    reasons."""

    model_config = ConfigDict(extra="forbid")

    event_type: str
    session_id: str
    from_state: str
    to_state: str
    detail: dict[str, str] = Field(default_factory=dict)
