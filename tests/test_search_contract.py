"""Contract + workflow tests for the scheduling engine.

- API-level tests exercise the real HTTP contract via TestClient.
- Unit tests exercise the pure scheduler directly (no transport layer).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.data import get_slots
from app.main import app
from app.models import SearchRequest
from app.scheduler import search_slots

client = TestClient(app)

FULL_DAY = {"start": "2026-08-03T09:00:00Z", "end": "2026-08-03T12:00:00Z"}


# --- API contract ----------------------------------------------------------


def test_search_happy_path_returns_sorted_matches() -> None:
    resp = client.post(
        "/schedule/search",
        json={"time_window": FULL_DAY, "duration_minutes": 30, "specialty": "cardiology"},
    )
    assert resp.status_code == 200
    body = resp.json()
    diag = body["diagnostics"]
    assert diag["matched"] == 12
    assert len(body["results"]) == 10  # default max_results
    starts = [slot["start"] for slot in body["results"]]
    assert starts == sorted(starts)  # earliest-first ordering
    assert all(slot["specialty"] == "cardiology" for slot in body["results"])
    # Full page returned -> summary present, no relaxation noise.
    assert diag["summary"]
    assert diag["relaxation_hints"] == []


def test_search_respects_max_results() -> None:
    resp = client.post(
        "/schedule/search",
        json={"time_window": FULL_DAY, "duration_minutes": 30, "max_results": 3},
    )
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 3


def test_search_no_availability_returns_diagnostics() -> None:
    resp = client.post(
        "/schedule/search",
        json={"time_window": FULL_DAY, "duration_minutes": 60},
    )
    assert resp.status_code == 200
    diag = resp.json()["diagnostics"]
    assert resp.json()["results"] == []
    assert diag["matched"] == 0
    # The duration filter should be the one that emptied the candidate set.
    duration_step = next(s for s in diag["filter_trace"] if s["constraint"] == "duration_minutes")
    assert duration_step["candidates_before"] == 36
    assert duration_step["candidates_after"] == 0
    assert diag["suggestions"]  # at least one actionable suggestion
    # Human-readable summary names the limiting constraint.
    assert "duration_minutes" in diag["summary"]
    # Relaxation hint quantifies what dropping the duration filter would surface.
    dur_hint = next(h for h in diag["relaxation_hints"] if h["constraint"] == "duration_minutes")
    assert dur_hint["would_match"] == 15


def test_search_sparse_results_include_relaxation_hints() -> None:
    resp = client.post(
        "/schedule/search",
        json={
            "time_window": FULL_DAY,
            "duration_minutes": 30,
            "specialty": "cardiology",
            "location_id": "clinic-south",
        },
    )
    assert resp.status_code == 200
    diag = resp.json()["diagnostics"]
    assert diag["matched"] == 6  # fewer than the default max_results of 10
    # Dropping the location filter would double the matches -> actionable hint.
    loc_hint = next(h for h in diag["relaxation_hints"] if h["constraint"] == "location_id")
    assert loc_hint["would_match"] == 12
    assert "location_id" in diag["summary"]


def test_search_zero_location_hint_points_to_alternative() -> None:
    resp = client.post(
        "/schedule/search",
        json={
            "time_window": FULL_DAY,
            "duration_minutes": 30,
            "specialty": "cardiology",
            "location_id": "clinic-nowhere",
        },
    )
    assert resp.status_code == 200
    diag = resp.json()["diagnostics"]
    assert diag["matched"] == 0
    loc_hint = next(h for h in diag["relaxation_hints"] if h["constraint"] == "location_id")
    assert loc_hint["would_match"] == 12
    assert diag["summary"].startswith("No matching slots")


def test_search_unknown_specialty_suggests_relaxing_filter() -> None:
    resp = client.post(
        "/schedule/search",
        json={"time_window": FULL_DAY, "duration_minutes": 30, "specialty": "oncology"},
    )
    assert resp.status_code == 200
    diag = resp.json()["diagnostics"]
    assert diag["matched"] == 0
    assert any("specialty" in s for s in diag["suggestions"])


def test_conflicting_time_window_returns_structured_error() -> None:
    resp = client.post(
        "/schedule/search",
        json={
            "time_window": {"start": "2026-08-03T12:00:00Z", "end": "2026-08-03T09:00:00Z"},
            "duration_minutes": 30,
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "invalid_request"
    assert body["field"] == "time_window"
    assert "message" in body


def test_missing_required_field_returns_structured_error() -> None:
    resp = client.post("/schedule/search", json={"duration_minutes": 30})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "invalid_request"
    assert body["field"] == "time_window"


def test_unknown_field_is_rejected() -> None:
    resp = client.post(
        "/schedule/search",
        json={"time_window": FULL_DAY, "duration_minutes": 30, "bogus": True},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "invalid_request"


# --- Pure scheduler workflow ----------------------------------------------


def test_scheduler_provider_filter_narrows_results() -> None:
    req = SearchRequest.model_validate(
        {
            "time_window": FULL_DAY,
            "duration_minutes": 30,
            "provider_ids": ["prov-alice"],
        }
    )
    resp = search_slots(req, get_slots())
    assert resp.diagnostics.matched == 6  # one provider, one day, six 30-min slots
    assert all(slot.provider_id == "prov-alice" for slot in resp.results)


def test_scheduler_filter_trace_records_each_constraint() -> None:
    req = SearchRequest.model_validate(
        {
            "time_window": FULL_DAY,
            "duration_minutes": 30,
            "specialty": "cardiology",
            "location_id": "clinic-north",
        }
    )
    resp = search_slots(req, get_slots())
    applied = [r.constraint for r in resp.diagnostics.filter_trace]
    assert applied == ["specialty", "location_id", "duration_minutes", "time_window"]
    assert resp.diagnostics.total_slots_considered == 36
