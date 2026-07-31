"""API contract models for the scheduling engine.

These Pydantic v2 models define the *contract* only — no scheduling logic
lives here. The scheduler (see ``app/scheduler.py``) consumes ``SearchRequest``
and produces ``SearchResponse``; adapters (LLM, EHR, etc.) stay separate.

Datetime convention
-------------------
All datetimes are normalized to timezone-aware UTC. Naive datetimes are
interpreted as UTC. This keeps comparisons safe when an agent sends ISO-8601
strings (with or without an offset).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _to_utc(value: datetime) -> datetime:
    """Coerce a datetime to timezone-aware UTC (naive is assumed UTC)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# --- Requests --------------------------------------------------------------


class TimeWindow(BaseModel):
    """Inclusive-start, exclusive-end window an appointment may start within."""

    model_config = ConfigDict(extra="forbid")

    start: datetime = Field(description="Earliest acceptable appointment start (UTC).")
    end: datetime = Field(description="Latest boundary; appointment must end at/before this (UTC).")

    @model_validator(mode="after")
    def _normalize_and_check(self) -> "TimeWindow":
        object.__setattr__(self, "start", _to_utc(self.start))
        object.__setattr__(self, "end", _to_utc(self.end))
        if self.end <= self.start:
            raise ValueError("time_window.end must be strictly after time_window.start")
        return self


class SearchRequest(BaseModel):
    """An agent- or human-issued slot search.

    Constraints are intentionally explicit and optional so new ones can be
    added as fields without breaking existing callers. The scheduler applies
    them as an ordered, extensible filter chain.
    """

    model_config = ConfigDict(extra="forbid")

    time_window: TimeWindow
    duration_minutes: Annotated[int, Field(gt=0, le=8 * 60)] = Field(
        description="Requested appointment length in minutes (1..480)."
    )
    provider_ids: list[str] = Field(
        default_factory=list,
        description="Optional filter: only these providers are acceptable.",
    )
    specialty: str | None = Field(
        default=None, description="Optional filter: required provider specialty."
    )
    location_id: str | None = Field(
        default=None, description="Optional filter: required clinic location."
    )
    max_results: Annotated[int, Field(gt=0, le=100)] = Field(
        default=10, description="Maximum number of slots to return."
    )

    @model_validator(mode="after")
    def _check_duration_fits_window(self) -> "SearchRequest":
        window_minutes = (self.time_window.end - self.time_window.start).total_seconds() / 60
        if self.duration_minutes > window_minutes:
            raise ValueError(
                "duration_minutes ("
                f"{self.duration_minutes}) exceeds the time window "
                f"({int(window_minutes)} minutes)"
            )
        return self


# --- Responses -------------------------------------------------------------


class Slot(BaseModel):
    """A single bookable appointment opportunity."""

    model_config = ConfigDict(extra="forbid")

    slot_id: str
    provider_id: str
    provider_name: str
    specialty: str
    location_id: str
    start: datetime
    end: datetime


class ConstraintReport(BaseModel):
    """How one constraint narrowed the candidate set — the core of diagnostics."""

    model_config = ConfigDict(extra="forbid")

    constraint: str = Field(description="Constraint name, e.g. 'time_window'.")
    candidates_before: int = Field(ge=0)
    candidates_after: int = Field(ge=0)

    @property
    def removed(self) -> int:
        return self.candidates_before - self.candidates_after


class RelaxationHint(BaseModel):
    """Counterfactual: how many slots would match if one constraint were dropped.

    ``would_match`` is computed by removing exactly this constraint's predicate
    from the filter chain and keeping every other constraint as-is — a mechanical
    per-filter counterfactual an agent can act on ("relax X to reach N slots").
    """

    model_config = ConfigDict(extra="forbid")

    constraint: str = Field(description="The constraint that would be relaxed/removed.")
    would_match: int = Field(ge=0, description="Slots matching if this constraint is dropped.")
    hint: str = Field(description="Human- and agent-readable phrasing of the counterfactual.")


class Diagnostics(BaseModel):
    """Structured explanation so agents/humans can troubleshoot 'no availability'."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        description="Human-readable one-line explanation of the outcome."
    )
    total_slots_considered: int = Field(ge=0)
    matched: int = Field(ge=0)
    filter_trace: list[ConstraintReport] = Field(default_factory=list)
    relaxation_hints: list[RelaxationHint] = Field(
        default_factory=list,
        description="Per-constraint counterfactuals shown when the result is empty or sparse.",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Actionable next steps when results are empty or sparse.",
    )


class SearchResponse(BaseModel):
    """Result of a slot search: matches plus a diagnostics trace."""

    model_config = ConfigDict(extra="forbid")

    results: list[Slot]
    diagnostics: Diagnostics


# --- Errors ----------------------------------------------------------------


class ErrorDetail(BaseModel):
    """Structured, actionable error body for invalid/conflicting requests."""

    model_config = ConfigDict(extra="forbid")

    error: str = Field(description="Machine-readable error code, e.g. 'invalid_request'.")
    message: str = Field(description="Human- and agent-readable explanation.")
    field: str | None = Field(
        default=None, description="Offending field path, when applicable."
    )
