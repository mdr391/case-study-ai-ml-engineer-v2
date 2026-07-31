"""Explicit conversation state, per-session context, and the turn reply type."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from appointment.dto import SlotOffer


class ConversationState(str, Enum):
    START = "start"
    AWAITING_VERIFICATION = "awaiting_verification"
    AWAITING_REASON = "awaiting_reason"
    AWAITING_SLOT_SELECTION = "awaiting_slot_selection"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    BOOKED = "booked"
    HANDOFF = "handoff"


class ConversationContext(BaseModel):
    """Mutable per-session workflow state. Holds only what the machine needs;
    `reason` is kept for slot search but is never written to audit verbatim."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    state: ConversationState = ConversationState.START
    verification_attempts: int = 0
    patient_id: str | None = None
    reason: str | None = None
    offered_slots: list[SlotOffer] = Field(default_factory=list)
    selected_slot_id: str | None = None
    booking_draft_id: str | None = None


class Reply(BaseModel):
    """What the workflow says back on a single text turn."""

    model_config = ConfigDict(extra="forbid")

    message: str
    state: ConversationState
    done: bool = False
