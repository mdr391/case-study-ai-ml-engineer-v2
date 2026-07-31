"""Deterministic in-memory fakes for the four interfaces. Synthetic data only."""

from __future__ import annotations

from appointment.dto import AuditEvent, BookingDraft, SlotOffer, VerifiedPatient


class FakePatientDirectory:
    """One existing synthetic patient. Identity = last name + date of birth."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], VerifiedPatient] = {
            ("nguyen", "1990-02-14"): VerifiedPatient(
                patient_id="pat_001", display_name="Alex Nguyen"
            )
        }

    def verify(self, *, last_name: str, date_of_birth: str) -> VerifiedPatient | None:
        return self._by_key.get((last_name.strip().lower(), date_of_birth.strip()))


class FakeSchedulingProvider:
    """Fixed synthetic slots; idempotent draft store keyed by idempotency_key."""

    def __init__(self) -> None:
        self._slots = [
            SlotOffer(slot_id="slot_1", provider_name="Dr. Alice Nguyen", location="Clinic North", date="2026-08-03", time="09:00"),
            SlotOffer(slot_id="slot_2", provider_name="Dr. Ben Carter", location="Clinic South", date="2026-08-03", time="09:30"),
            SlotOffer(slot_id="slot_3", provider_name="Dr. Alice Nguyen", location="Clinic North", date="2026-08-04", time="10:00"),
            SlotOffer(slot_id="slot_4", provider_name="Dr. Carol Diaz", location="Clinic North", date="2026-08-04", time="11:00"),
            SlotOffer(slot_id="slot_5", provider_name="Dr. Ben Carter", location="Clinic South", date="2026-08-05", time="09:00"),
        ]
        self.drafts: dict[str, BookingDraft] = {}  # idempotency_key -> draft

    def find_slots(self, *, patient_id: str, limit: int) -> list[SlotOffer]:
        return list(self._slots[: max(0, limit)])

    def create_draft(
        self, *, patient_id: str, slot: SlotOffer, idempotency_key: str
    ) -> BookingDraft:
        existing = self.drafts.get(idempotency_key)
        if existing is not None:
            return existing
        draft = BookingDraft(
            draft_id=f"draft_{len(self.drafts) + 1:03d}",
            patient_id=patient_id,
            slot_id=slot.slot_id,
            provider_name=slot.provider_name,
            location=slot.location,
            date=slot.date,
            time=slot.time,
        )
        self.drafts[idempotency_key] = draft
        return draft


class FakeHandoffService:
    def __init__(self) -> None:
        self.escalations: list[tuple[str, str]] = []  # (session_id, reason_code)

    def escalate(self, *, session_id: str, reason_code: str) -> None:
        self.escalations.append((session_id, reason_code))


class InMemoryAuditSink:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        self.events.append(event)
