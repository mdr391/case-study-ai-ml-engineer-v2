"""The appointment workflow state machine.

`AppointmentWorkflow.handle(ctx, text)` consumes one text turn, mutates the
typed `ConversationContext`, emits sanitized audit events, and returns a `Reply`.
Booking only ever happens on an explicit confirmation, and re-confirming an
already-booked session never creates a second draft.
"""

from __future__ import annotations

from appointment import intents
from appointment.dto import AuditEvent
from appointment.interfaces import (
    AuditSink,
    HandoffService,
    PatientDirectory,
    SchedulingProvider,
)
from appointment.state import ConversationContext, ConversationState, Reply

MAX_VERIFICATION_ATTEMPTS = 2
SLOT_LIMIT = 3

S = ConversationState


class AppointmentWorkflow:
    def __init__(
        self,
        *,
        directory: PatientDirectory,
        scheduling: SchedulingProvider,
        handoff: HandoffService,
        audit: AuditSink,
    ) -> None:
        self._directory = directory
        self._scheduling = scheduling
        self._handoff = handoff
        self._audit = audit

    # -- public entry point ------------------------------------------------

    def handle(self, ctx: ConversationContext, text: str) -> Reply:
        text = text.strip()
        dispatch = {
            S.START: self._on_start,
            S.AWAITING_VERIFICATION: self._on_verification,
            S.AWAITING_REASON: self._on_reason,
            S.AWAITING_SLOT_SELECTION: self._on_slot_selection,
            S.AWAITING_CONFIRMATION: self._on_confirmation,
            S.BOOKED: self._on_booked,
            S.HANDOFF: self._on_handoff,
        }
        return dispatch[ctx.state](ctx, text)

    # -- per-state handlers ------------------------------------------------

    def _on_start(self, ctx: ConversationContext, text: str) -> Reply:
        if not intents.is_appointment_request(text):
            return self._say(ctx, "Let me know if you'd like to book an appointment.")
        self._transition(ctx, S.AWAITING_VERIFICATION, "appointment_requested")
        return self._say(
            ctx,
            "I can help you book an appointment. To verify your identity, reply "
            "with your last name and date of birth, e.g. 'Nguyen 1990-02-14'.",
        )

    def _on_verification(self, ctx: ConversationContext, text: str) -> Reply:
        parsed = intents.parse_identity(text)
        if parsed is None:
            return self._fail_verification(
                ctx,
                "verification_unparseable",
                "I couldn't read that. Please send it as 'Lastname YYYY-MM-DD'.",
            )
        last_name, dob = parsed
        patient = self._directory.verify(last_name=last_name, date_of_birth=dob)
        if patient is None:
            return self._fail_verification(
                ctx,
                "verification_failed",
                "That didn't match our records. Please try again.",
            )
        ctx.patient_id = patient.patient_id
        self._transition(ctx, S.AWAITING_REASON, "identity_verified",
                         {"patient_id": patient.patient_id})
        return self._say(
            ctx,
            "Thanks, you're verified. In a few words, what's the general "
            "(non-emergency) reason for your visit?",
        )

    def _on_reason(self, ctx: ConversationContext, text: str) -> Reply:
        if not text:
            return self._say(ctx, "Please tell me the general reason for your visit.")
        if intents.is_emergency(text):
            return self._to_handoff(
                ctx,
                "possible_emergency",
                "This may be urgent, so I'm connecting you to a person. If this is "
                "a medical emergency, call your local emergency number now.",
            )
        ctx.reason = text
        slots = self._scheduling.find_slots(patient_id=ctx.patient_id or "", limit=SLOT_LIMIT)
        if not slots:
            return self._to_handoff(
                ctx, "no_availability",
                "I don't see open times right now — I'll connect you to a person.",
            )
        ctx.offered_slots = slots
        self._transition(
            ctx, S.AWAITING_SLOT_SELECTION, "slots_offered",
            {"reason": "provided", "count": str(len(slots)),
             "slots": ",".join(s.slot_id for s in slots)},
        )
        lines = [
            f"{i}) {s.provider_name} — {s.location} — {s.date} at {s.time}"
            for i, s in enumerate(slots, start=1)
        ]
        return self._say(
            ctx,
            "Here are the available times:\n" + "\n".join(lines)
            + "\nReply with the number of the time you'd like.",
        )

    def _on_slot_selection(self, ctx: ConversationContext, text: str) -> Reply:
        choice = intents.parse_slot_choice(text, len(ctx.offered_slots))
        if choice is None:
            return self._say(
                ctx,
                f"Please reply with a number between 1 and {len(ctx.offered_slots)}.",
            )
        slot = ctx.offered_slots[choice - 1]
        ctx.selected_slot_id = slot.slot_id
        self._transition(ctx, S.AWAITING_CONFIRMATION, "slot_selected",
                         {"slot_id": slot.slot_id})
        return self._say(
            ctx,
            "Please confirm this appointment:\n"
            f"Provider: {slot.provider_name}\n"
            f"Location: {slot.location}\n"
            f"Date: {slot.date}\n"
            f"Time: {slot.time}\n"
            "Reply 'yes' to confirm or 'no' to choose another time.",
        )

    def _on_confirmation(self, ctx: ConversationContext, text: str) -> Reply:
        decision = intents.parse_confirmation(text)
        if decision is None:
            return self._say(
                ctx, "Please reply 'yes' to confirm or 'no' to choose another time."
            )
        if decision is False:
            self._transition(ctx, S.AWAITING_SLOT_SELECTION, "confirmation_declined")
            return self._say(ctx, "No problem — reply with the number of another time.")
        slot = next(s for s in ctx.offered_slots if s.slot_id == ctx.selected_slot_id)
        idempotency_key = f"{ctx.session_id}:{ctx.selected_slot_id}"
        draft = self._scheduling.create_draft(
            patient_id=ctx.patient_id or "", slot=slot, idempotency_key=idempotency_key
        )
        ctx.booking_draft_id = draft.draft_id
        self._transition(ctx, S.BOOKED, "booking_draft_created",
                         {"draft_id": draft.draft_id, "slot_id": slot.slot_id})
        return self._say(
            ctx,
            f"Confirmed. Your appointment draft {draft.draft_id} is set: "
            f"{slot.provider_name} at {slot.location} on {slot.date} at {slot.time}. "
            "A staff member will finalize it.",
            done=True,
        )

    def _on_booked(self, ctx: ConversationContext, text: str) -> Reply:
        # Duplicate confirmation: acknowledge, but never create a second draft.
        self._emit(ctx, ctx.state, "duplicate_confirmation_ignored",
                   {"draft_id": ctx.booking_draft_id or ""})
        return self._say(
            ctx,
            f"Your appointment draft {ctx.booking_draft_id} is already confirmed; "
            "I won't create another. A staff member will finalize it.",
            done=True,
        )

    def _on_handoff(self, ctx: ConversationContext, text: str) -> Reply:
        return self._say(ctx, "A staff member will continue to assist you.", done=True)

    # -- helpers -----------------------------------------------------------

    def _fail_verification(
        self, ctx: ConversationContext, reason_code: str, retry_message: str
    ) -> Reply:
        ctx.verification_attempts += 1
        self._emit(ctx, ctx.state, reason_code,
                   {"attempt": str(ctx.verification_attempts)})
        if ctx.verification_attempts >= MAX_VERIFICATION_ATTEMPTS:
            return self._to_handoff(
                ctx, reason_code,
                "I couldn't verify your identity, so I'm connecting you to a person.",
            )
        return self._say(ctx, retry_message)

    def _to_handoff(
        self, ctx: ConversationContext, reason_code: str, message: str
    ) -> Reply:
        self._handoff.escalate(session_id=ctx.session_id, reason_code=reason_code)
        self._transition(ctx, S.HANDOFF, "handoff", {"reason_code": reason_code})
        return self._say(ctx, message, done=True)

    def _transition(
        self,
        ctx: ConversationContext,
        to_state: ConversationState,
        event_type: str,
        detail: dict[str, str] | None = None,
    ) -> None:
        from_state = ctx.state
        ctx.state = to_state
        self._emit(ctx, from_state, event_type, detail, to_state=to_state)

    def _emit(
        self,
        ctx: ConversationContext,
        from_state: ConversationState,
        event_type: str,
        detail: dict[str, str] | None = None,
        *,
        to_state: ConversationState | None = None,
    ) -> None:
        self._audit.emit(
            AuditEvent(
                event_type=event_type,
                session_id=ctx.session_id,
                from_state=from_state.value,
                to_state=(to_state or ctx.state).value,
                detail=detail or {},
            )
        )

    def _say(self, ctx: ConversationContext, message: str, *, done: bool = False) -> Reply:
        return Reply(message=message, state=ctx.state, done=done)
