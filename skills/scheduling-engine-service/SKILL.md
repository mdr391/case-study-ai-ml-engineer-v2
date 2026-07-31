---
name: scheduling-engine-service
description: Search appointment slots and troubleshoot "no availability" via the scheduling engine API.
disable-model-invocation: true
---

# Scheduling Engine Service

Search bookable appointment slots and explain why a search returned nothing.
The service is deterministic and backed by synthetic data (no PHI).

## API Contract

Base URL (local): `http://127.0.0.1:8000`

### `POST /schedule/search`

Request body (`SearchRequest`):

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `time_window.start` | ISO-8601 datetime | yes | Naive datetimes are treated as UTC. |
| `time_window.end` | ISO-8601 datetime | yes | Must be strictly after `start`. |
| `duration_minutes` | int (1–480) | yes | Must fit within the window. |
| `specialty` | string | no | Case-insensitive exact match. |
| `location_id` | string | no | Exact match. |
| `provider_ids` | string[] | no | Any-of filter. |
| `max_results` | int (1–100) | no | Default 10. |

Unknown fields are rejected.

Response body (`SearchResponse`):

```json
{
  "results": [
    {
      "slot_id": "prov-alice:20260803T0900",
      "provider_id": "prov-alice",
      "provider_name": "Dr. Alice Nguyen",
      "specialty": "cardiology",
      "location_id": "clinic-north",
      "start": "2026-08-03T09:00:00Z",
      "end": "2026-08-03T09:30:00Z"
    }
  ],
  "diagnostics": {
    "summary": "Found 12 matching slot(s); returning the earliest 10.",
    "total_slots_considered": 36,
    "matched": 12,
    "filter_trace": [
      {"constraint": "specialty", "candidates_before": 36, "candidates_after": 24}
    ],
    "relaxation_hints": [],
    "suggestions": []
  }
}
```

The `diagnostics` block is built for both humans and agents:

- `summary` — a one-line, human-readable explanation of the outcome (always present).
- `filter_trace` — constraints in applied order with candidate counts before/after
  each; the machine-readable backbone for diagnosing "no availability".
- `relaxation_hints` — per-constraint counterfactuals ("relax `location_id` →
  12 slots"). Emitted when the caller gets fewer than a full page
  (`matched < max_results`), and only for constraints whose removal would
  actually increase the count. Each hint drops exactly one filter and keeps the
  rest, so an agent can decide which single constraint to loosen.
- `suggestions` — actionable prose, populated only when `matched == 0`.

### `GET /health`

Returns `{"status": "ok"}`.

## Query grammar (constraints)

Constraints are optional and combine with logical AND. `provider_ids` is
any-of. `specialty`/`location_id` are exact match. `time_window` and
`duration_minutes` always apply. Missing optional fields mean "no restriction".

## Workflows

### 1. Happy path — find slots
Send a `time_window`, `duration_minutes`, and any filters. Read `results`
(earliest first, capped at `max_results`).

```bash
python skills/scheduling-engine-service/scripts/search.py \
  --start 2026-08-03T09:00:00Z --end 2026-08-03T12:00:00Z \
  --duration 30 --specialty cardiology --max-results 3
```

### 2. Diagnostics — "why no results?"
When `results` is empty or sparse, read `diagnostics.summary` for the one-line
explanation, use `diagnostics.relaxation_hints` to tell the user which single
constraint to loosen (and how many slots that would surface), and relay
`diagnostics.suggestions` when present. `filter_trace` gives the exact
constraint whose `candidates_after` dropped to 0.

```bash
python skills/scheduling-engine-service/scripts/search.py \
  --start 2026-08-03T09:00:00Z --end 2026-08-03T12:00:00Z --duration 60
# -> matched: 0; duration_minutes emptied the set; suggestion: try a shorter appointment.
```

### 3. Failure — invalid / conflicting request
On a bad request the service returns HTTP `422` with a structured error:

```json
{"error": "invalid_request", "message": "...", "field": "time_window"}
```

Example (window end before start):

```bash
python skills/scheduling-engine-service/scripts/search.py \
  --start 2026-08-03T12:00:00Z --end 2026-08-03T09:00:00Z --duration 30
```

## Output format expectations (for agents)

- On success: report the earliest 1–3 slots as `provider_name @ start (location_id)`.
- On empty or sparse results: relay `diagnostics.summary`, name the limiting
  constraint from `filter_trace`, and offer the top `relaxation_hints` entry
  ("relax X to reach N slots") plus any `suggestions` verbatim.
- On `422`: relay `message` and name the offending `field`.
- Never invent slots, providers, or clinical advice. Only report what the API returns.
