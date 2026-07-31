"""Synthetic, in-memory schedule data.

This is a stand-in for what would otherwise come from an EHR / scheduling
adapter. It is deterministic (no randomness, no clock reads) so tests and demos
are reproducible. **Synthetic data only — no real patients or PHI.**

Slots are 30 minutes long, 09:00–12:00 UTC, on 2026-08-03 and 2026-08-04.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import Slot

# (provider_id, provider_name, specialty, location_id)
_PROVIDERS: tuple[tuple[str, str, str, str], ...] = (
    ("prov-alice", "Dr. Alice Nguyen", "cardiology", "clinic-north"),
    ("prov-ben", "Dr. Ben Carter", "cardiology", "clinic-south"),
    ("prov-carol", "Dr. Carol Diaz", "dermatology", "clinic-north"),
)

_DAYS: tuple[datetime, ...] = (
    datetime(2026, 8, 3, tzinfo=timezone.utc),
    datetime(2026, 8, 4, tzinfo=timezone.utc),
)

_SLOT_MINUTES = 30
_START_HOUR = 9
_END_HOUR = 12  # exclusive; last slot starts 11:30


def _build_slots() -> list[Slot]:
    slots: list[Slot] = []
    for provider_id, provider_name, specialty, location_id in _PROVIDERS:
        for day in _DAYS:
            cursor = day.replace(hour=_START_HOUR)
            day_end = day.replace(hour=_END_HOUR)
            while cursor < day_end:
                end = cursor + timedelta(minutes=_SLOT_MINUTES)
                slots.append(
                    Slot(
                        slot_id=f"{provider_id}:{cursor.strftime('%Y%m%dT%H%M')}",
                        provider_id=provider_id,
                        provider_name=provider_name,
                        specialty=specialty,
                        location_id=location_id,
                        start=cursor,
                        end=end,
                    )
                )
                cursor = end
    return slots


def get_slots() -> list[Slot]:
    """Return a fresh copy of the synthetic slot inventory."""
    return _build_slots()
