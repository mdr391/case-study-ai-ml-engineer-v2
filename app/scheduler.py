"""Pure scheduling workflow logic.

No I/O, no network, no LLM — this module only turns a ``SearchRequest`` plus a
list of candidate ``Slot`` objects into a ``SearchResponse``. Adapters (API,
data source, LLM) live elsewhere so this logic stays deterministic and
unit-testable.

Extensibility
-------------
Constraints are modeled as an ordered list of ``(name, predicate)`` pairs built
from the request. Adding a new constraint means appending one entry to
``_build_constraints`` — the filter loop and diagnostics trace pick it up
automatically, with no changes to the search algorithm.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Callable

from app.models import (
    ConstraintReport,
    Diagnostics,
    RelaxationHint,
    SearchRequest,
    SearchResponse,
    Slot,
)

Predicate = Callable[[Slot], bool]
Constraint = tuple[str, Predicate]


def _fits_window(slot: Slot, request: SearchRequest) -> bool:
    """Appointment starts within the window and ends at/before the window end."""
    appt_end = slot.start + timedelta(minutes=request.duration_minutes)
    return slot.start >= request.time_window.start and appt_end <= request.time_window.end


def _build_constraints(request: SearchRequest) -> list[Constraint]:
    """Build the ordered constraint chain for this request.

    Optional filters are only included when the caller supplied them, so the
    diagnostics trace reflects exactly what was applied. ``duration_minutes``
    and ``time_window`` always apply.
    """
    constraints: list[Constraint] = []

    if request.specialty is not None:
        wanted = request.specialty.strip().lower()
        constraints.append(("specialty", lambda s: s.specialty.lower() == wanted))

    if request.location_id is not None:
        loc = request.location_id
        constraints.append(("location_id", lambda s: s.location_id == loc))

    if request.provider_ids:
        allowed = set(request.provider_ids)
        constraints.append(("provider_ids", lambda s: s.provider_id in allowed))

    constraints.append(
        (
            "duration_minutes",
            lambda s: (s.end - s.start).total_seconds() / 60 >= request.duration_minutes,
        )
    )
    constraints.append(("time_window", lambda s: _fits_window(s, request)))

    return constraints


_SUGGESTIONS: dict[str, str] = {
    "specialty": "No slots match this specialty; try removing or changing the specialty filter.",
    "location_id": "No slots at this location; try another location or remove the location filter.",
    "provider_ids": "None of the requested providers have openings; widen or drop the provider filter.",
    "duration_minutes": "No slot is long enough for the requested duration; try a shorter appointment.",
    "time_window": "No openings fall inside the time window; try widening it or choosing another day.",
}


def _relaxation_hints(
    slots: list[Slot],
    constraints: list[Constraint],
    matched: int,
    max_results: int,
) -> list[RelaxationHint]:
    """For each applied constraint, count matches if only that one is dropped.

    Emitted only when the caller got fewer than a full page (`matched <
    max_results`), and only for constraints whose removal actually increases the
    match count — so the happy path stays quiet and every hint is actionable.
    """
    if matched >= max_results:
        return []

    hints: list[RelaxationHint] = []
    for i, (name, _predicate) in enumerate(constraints):
        others = [pred for j, (_, pred) in enumerate(constraints) if j != i]
        would_match = sum(1 for s in slots if all(pred(s) for pred in others))
        if would_match > matched:
            hints.append(
                RelaxationHint(
                    constraint=name,
                    would_match=would_match,
                    hint=f"Relax or remove '{name}' to reach {would_match} slot(s).",
                )
            )
    hints.sort(key=lambda h: (-h.would_match, h.constraint))
    return hints


def _summary(
    trace: list[ConstraintReport],
    matched: int,
    returned: int,
    hints: list[RelaxationHint],
) -> str:
    """One-line, human-readable explanation of the outcome."""
    if matched > 0:
        text = f"Found {matched} matching slot(s)"
        if returned < matched:
            text += f"; returning the earliest {returned}"
        text += "."
        if hints:
            top = hints[0]
            text += f" Relaxing '{top.constraint}' would surface {top.would_match}."
        return text

    culprit = next(
        (r for r in trace if r.candidates_before > 0 and r.candidates_after == 0),
        None,
    )
    if culprit is not None:
        text = (
            f"No matching slots: the '{culprit.constraint}' filter removed the last "
            f"{culprit.candidates_before} candidate(s)."
        )
    else:
        text = "No matching slots; the schedule has no candidate slots for this request."
    if hints:
        top = hints[0]
        text += f" Relaxing '{top.constraint}' would surface {top.would_match}."
    return text


def _suggestions(trace: list[ConstraintReport], matched: int) -> list[str]:
    """Actionable next steps, only when there is nothing (useful) to return."""
    if matched > 0:
        return []
    # Blame the constraint(s) that emptied a previously non-empty candidate set.
    culprits = [
        r.constraint
        for r in trace
        if r.candidates_before > 0 and r.candidates_after == 0
    ]
    suggestions = [_SUGGESTIONS[c] for c in culprits if c in _SUGGESTIONS]
    if not suggestions:
        suggestions.append(
            "No candidate slots exist in the schedule; try a different day or provider."
        )
    return suggestions


def search_slots(request: SearchRequest, slots: list[Slot]) -> SearchResponse:
    """Filter ``slots`` by the request's constraints and build a diagnostics trace."""
    total = len(slots)
    constraints = _build_constraints(request)
    current = list(slots)
    trace: list[ConstraintReport] = []

    for name, predicate in constraints:
        before = len(current)
        current = [s for s in current if predicate(s)]
        trace.append(
            ConstraintReport(
                constraint=name,
                candidates_before=before,
                candidates_after=len(current),
            )
        )

    matched = len(current)
    current.sort(key=lambda s: (s.start, s.provider_id))
    results = current[: request.max_results]

    hints = _relaxation_hints(slots, constraints, matched, request.max_results)
    diagnostics = Diagnostics(
        summary=_summary(trace, matched, len(results), hints),
        total_slots_considered=total,
        matched=matched,
        filter_trace=trace,
        relaxation_hints=hints,
        suggestions=_suggestions(trace, matched),
    )
    return SearchResponse(results=results, diagnostics=diagnostics)
