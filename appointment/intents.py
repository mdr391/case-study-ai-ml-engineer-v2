"""Deterministic intent rules for this phase (no LLM).

Every function is pure and keyword/regex based, so transitions are reproducible
and testable.
"""

from __future__ import annotations

import re

_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

_APPOINTMENT_KEYWORDS = (
    "appointment",
    "appt",
    "book",
    "schedule",
    "see a doctor",
    "see the doctor",
    "see a provider",
    "visit",
    "come in",
)

# Broad safety net: emergency/clinical-urgency phrases route to a human.
_EMERGENCY_KEYWORDS = (
    "emergency",
    "chest pain",
    "can't breathe",
    "cant breathe",
    "cannot breathe",
    "suicid",
    "bleeding",
    "overdose",
    "911",
    "stroke",
    "unconscious",
    "heart attack",
)

_YES = {"yes", "y", "yep", "yeah", "sure", "confirm", "confirmed", "correct", "ok", "okay", "book"}
_NO = {"no", "n", "nope", "cancel", "wrong", "nah"}

_ORDINALS = {"first": 1, "second": 2, "third": 3, "one": 1, "two": 2, "three": 3}


def is_appointment_request(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _APPOINTMENT_KEYWORDS)


def is_emergency(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _EMERGENCY_KEYWORDS)


def parse_identity(text: str) -> tuple[str, str] | None:
    """Extract (last_name, date_of_birth) from e.g. 'Nguyen 1990-02-14'.

    Deterministic: the first ISO date is the DOB; the first alphabetic token is
    the last name. Returns None if either is missing.
    """
    match = _DATE.search(text)
    if match is None:
        return None
    dob = match.group(1)
    rest = text[: match.start()] + " " + text[match.end() :]
    names = re.findall(r"[A-Za-z]+", rest)
    if not names:
        return None
    return names[0], dob


def parse_slot_choice(text: str, n: int) -> int | None:
    """Return a 1-based slot index in [1, n], or None if unparseable."""
    t = text.strip().lower()
    match = re.search(r"\b(\d+)\b", t)
    if match is not None:
        value = int(match.group(1))
        return value if 1 <= value <= n else None
    for word in re.findall(r"[a-z]+", t):
        if word in _ORDINALS:
            value = _ORDINALS[word]
            return value if 1 <= value <= n else None
    return None


def parse_confirmation(text: str) -> bool | None:
    """True for an explicit yes, False for an explicit no, None if unclear."""
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    if tokens & _NO:
        return False
    if tokens & _YES:
        return True
    return None
