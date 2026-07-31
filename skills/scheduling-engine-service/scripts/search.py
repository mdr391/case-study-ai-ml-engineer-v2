"""Call the scheduling engine's slot-search endpoint from the command line.

Builds a SearchRequest from CLI flags, POSTs it to ``/schedule/search``, and
prints the JSON response (results + diagnostics). Uses ``httpx`` (a project
dependency); no invented SDK calls.

Example:
    python skills/scheduling-engine-service/scripts/search.py \\
        --base-url http://127.0.0.1:8000 \\
        --start 2026-08-03T09:00:00Z --end 2026-08-03T12:00:00Z \\
        --duration 30 --specialty cardiology --max-results 3
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx


def _build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "time_window": {"start": args.start, "end": args.end},
        "duration_minutes": args.duration,
        "max_results": args.max_results,
    }
    if args.specialty:
        payload["specialty"] = args.specialty
    if args.location:
        payload["location_id"] = args.location
    if args.provider:
        payload["provider_ids"] = args.provider
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Search scheduling slots.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--start", required=True, help="Window start, ISO-8601 (e.g. 2026-08-03T09:00:00Z).")
    parser.add_argument("--end", required=True, help="Window end, ISO-8601.")
    parser.add_argument("--duration", type=int, required=True, help="Appointment length in minutes.")
    parser.add_argument("--specialty", default=None)
    parser.add_argument("--location", default=None, help="location_id filter.")
    parser.add_argument("--provider", action="append", default=None, help="provider_id filter (repeatable).")
    parser.add_argument("--max-results", type=int, default=10)
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/schedule/search"
    payload = _build_payload(args)

    try:
        resp = httpx.post(url, json=payload, timeout=10.0)
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    print(f"HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except ValueError:
        print(resp.text)
    # Non-2xx (e.g. 422 validation errors) is a valid, informative outcome, not
    # a script crash — surface it but exit non-zero so callers can detect it.
    return 0 if resp.is_success else 2


if __name__ == "__main__":
    raise SystemExit(main())
