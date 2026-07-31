"""Tests for the text-based appointment workflow.

Cover the complete happy-path conversation, failed verification -> handoff, and
duplicate confirmation (no second draft), plus safety handoff and the
no-silent-booking invariant.
"""

from __future__ import annotations

import json

import pytest

from appointment.engine import AppointmentWorkflow
from appointment.fakes import (
    FakeHandoffService,
    FakePatientDirectory,
    FakeSchedulingProvider,
    InMemoryAuditSink,
)
from appointment.state import ConversationContext, ConversationState

S = ConversationState

# Synthetic identity that exists in FakePatientDirectory.
GOOD_IDENTITY = "Nguyen 1990-02-14"
BAD_IDENTITY = "Wrong 2000-01-01"


def _build() -> tuple[AppointmentWorkflow, ConversationContext, dict]:
    directory = FakePatientDirectory()
    scheduling = FakeSchedulingProvider()
    handoff = FakeHandoffService()
    audit = InMemoryAuditSink()
    engine = AppointmentWorkflow(
        directory=directory, scheduling=scheduling, handoff=handoff, audit=audit
    )
    ctx = ConversationContext(session_id="sess_test")
    return engine, ctx, {"scheduling": scheduling, "handoff": handoff, "audit": audit}


def _event_types(audit: InMemoryAuditSink) -> list[str]:
    return [e.event_type for e in audit.events]


def test_complete_conversation_end_to_end() -> None:
    engine, ctx, dep = _build()
    scheduling, audit = dep["scheduling"], dep["audit"]
    states: list[ConversationState] = []

    r = engine.handle(ctx, "Hi, I'd like to book an appointment")
    states.append(r.state)
    assert r.state == S.AWAITING_VERIFICATION

    r = engine.handle(ctx, GOOD_IDENTITY)
    states.append(r.state)
    assert r.state == S.AWAITING_REASON

    r = engine.handle(ctx, "annual check-up")
    states.append(r.state)
    assert r.state == S.AWAITING_SLOT_SELECTION
    # No more than three synthetic slots are offered.
    assert len(ctx.offered_slots) == 3
    assert r.message.count(") ") == 3
    # Nothing booked yet — offering slots must not create a draft.
    assert scheduling.drafts == {}

    r = engine.handle(ctx, "1")
    states.append(r.state)
    assert r.state == S.AWAITING_CONFIRMATION
    # Read-back contains provider, location, date, and time.
    for field in ("Dr. Alice Nguyen", "Clinic North", "2026-08-03", "09:00"):
        assert field in r.message
    # Still not booked until explicit confirmation.
    assert scheduling.drafts == {}

    r = engine.handle(ctx, "yes")
    states.append(r.state)
    assert r.state == S.BOOKED
    assert r.done is True
    assert ctx.booking_draft_id is not None
    assert len(scheduling.drafts) == 1

    assert states == [
        S.AWAITING_VERIFICATION,
        S.AWAITING_REASON,
        S.AWAITING_SLOT_SELECTION,
        S.AWAITING_CONFIRMATION,
        S.BOOKED,
    ]
    assert _event_types(audit) == [
        "appointment_requested",
        "identity_verified",
        "slots_offered",
        "slot_selected",
        "booking_draft_created",
    ]
    # Audit is sanitized: no raw PII (name/DOB) anywhere in the events.
    blob = json.dumps([e.model_dump() for e in audit.events])
    assert "Nguyen" not in blob
    assert "1990-02-14" not in blob


def test_failed_verification_hands_off() -> None:
    engine, ctx, dep = _build()
    handoff, audit = dep["handoff"], dep["audit"]

    engine.handle(ctx, "I want an appointment")
    assert ctx.state == S.AWAITING_VERIFICATION

    r1 = engine.handle(ctx, BAD_IDENTITY)  # attempt 1 -> retry
    assert r1.state == S.AWAITING_VERIFICATION
    assert ctx.verification_attempts == 1
    assert handoff.escalations == []

    r2 = engine.handle(ctx, BAD_IDENTITY)  # attempt 2 -> handoff
    assert r2.state == S.HANDOFF
    assert r2.done is True
    assert handoff.escalations == [("sess_test", "verification_failed")]
    assert "handoff" in _event_types(audit)
    # A failed identity check never verifies a patient.
    assert ctx.patient_id is None


def test_duplicate_confirmation_does_not_create_second_draft() -> None:
    engine, ctx, dep = _build()
    scheduling, audit = dep["scheduling"], dep["audit"]

    for turn in ("book an appointment", GOOD_IDENTITY, "checkup", "1", "yes"):
        engine.handle(ctx, turn)
    assert ctx.state == S.BOOKED
    first_draft_id = ctx.booking_draft_id
    assert len(scheduling.drafts) == 1

    # Confirm again — must not create another draft.
    r = engine.handle(ctx, "yes")
    assert r.state == S.BOOKED
    assert ctx.booking_draft_id == first_draft_id
    assert len(scheduling.drafts) == 1
    assert "duplicate_confirmation_ignored" in _event_types(audit)


def test_emergency_reason_triggers_safety_handoff() -> None:
    engine, ctx, dep = _build()
    handoff, scheduling = dep["handoff"], dep["scheduling"]

    engine.handle(ctx, "appointment")
    engine.handle(ctx, GOOD_IDENTITY)
    r = engine.handle(ctx, "I have chest pain")
    assert r.state == S.HANDOFF
    assert handoff.escalations == [("sess_test", "possible_emergency")]
    # No slots offered, nothing booked on a safety handoff.
    assert ctx.offered_slots == []
    assert scheduling.drafts == {}


def test_declining_returns_to_slot_selection() -> None:
    engine, ctx, dep = _build()
    scheduling = dep["scheduling"]

    for turn in ("appointment", GOOD_IDENTITY, "checkup", "2"):
        engine.handle(ctx, turn)
    assert ctx.state == S.AWAITING_CONFIRMATION

    r = engine.handle(ctx, "no")
    assert r.state == S.AWAITING_SLOT_SELECTION
    assert scheduling.drafts == {}  # declining never books
