"""Narrow interfaces for the workflow's collaborators.

Each is a small Protocol so the engine depends on behavior, not concrete
implementations. Real adapters (EHR, scheduling system, paging, log sink) can be
substituted later without touching the state machine.
"""

from __future__ import annotations

from typing import Protocol

from appointment.dto import AuditEvent, BookingDraft, SlotOffer, VerifiedPatient


class PatientDirectory(Protocol):
    def verify(self, *, last_name: str, date_of_birth: str) -> VerifiedPatient | None:
        """Return the patient iff both synthetic fields match, else None."""
        ...


class SchedulingProvider(Protocol):
    def find_slots(self, *, patient_id: str, limit: int) -> list[SlotOffer]:
        """Return at most `limit` synthetic slots."""
        ...

    def create_draft(
        self, *, patient_id: str, slot: SlotOffer, idempotency_key: str
    ) -> BookingDraft:
        """Create (or return the existing) booking draft for `idempotency_key`.

        Calling twice with the same key MUST return the same draft and create no
        second draft.
        """
        ...


class HandoffService(Protocol):
    def escalate(self, *, session_id: str, reason_code: str) -> None:
        """Hand the conversation to a human."""
        ...


class AuditSink(Protocol):
    def emit(self, event: AuditEvent) -> None:
        """Record a sanitized audit event."""
        ...
