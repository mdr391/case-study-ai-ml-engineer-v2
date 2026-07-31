# Build Reports

A durable, chronological record of the work done on this case study — files
changed, commands run, test results, assumptions, and risks per phase. Newest
context at the bottom of each phase. This complements `DESIGN.md` (the design)
and the git history (the diffs).

## Environment
- Runtime in this container: **Python 3.11.15** (project target is 3.12).
- Installed: FastAPI 0.141.1, uvicorn 0.52.0, pydantic 2.13.4, pytest 9.1.1, httpx 0.28.1, anthropic 0.120.2.
- Dependency manager: pip via `requirements.txt`.
- A cosmetic `StarletteDeprecationWarning` ("install httpx2") is emitted by FastAPI's `TestClient` in every run; harmless, suite stays green.

## Test-count progression
| After phase | Result |
|---|---|
| Baseline (scaffold) | 2 skipped |
| Scheduling slice steps 1–4 | 10 passed |
| LLM adapter (step 7) | 16 passed |
| Diagnostics enhancement | 18 passed |
| Session service skeleton | 19 passed |
| Appointment workflow | 24 passed |
| Workflow wired into session API | **26 passed** |

---

## Phase 0 — Repository inspection (read-only)
- **Findings:** Python 3.11 devcontainer; pip/`requirements.txt`; entry points `app/main.py` (FastAPI `/health`), `verify_setup.py`, a skill stub. Only `anthropic` as an AI dep; no voice frameworks. Tests were two skipped placeholders.
- **Risks flagged:** installed package versions far ahead of `requirements.txt` floors; `.env.example` model id `claude-sonnet-4-20250514` possibly stale; everything net-new; SKILL/eval stubs must stay in lockstep with the contract.
- No files changed.

## Phase 1 — Read-only scheduling engine slice (steps 1–7)
Committed as `83258e5`.

- **Step 1 — contract (`app/models.py`):** Pydantic v2 models — `TimeWindow`, `SearchRequest` (UTC-normalized, cross-field validators), `Slot`, `ConstraintReport`, `Diagnostics`, `SearchResponse`, `ErrorDetail`; `extra="forbid"` throughout. Smoke-tested validation/coercion.
- **Step 2 — data + scheduler (`app/data.py`, `app/scheduler.py`):** deterministic 36-slot synthetic inventory (3 providers × 2 specialties × 2 locations × 2 days, 30-min slots); pure `search_slots()` with an ordered, extensible `(name, predicate)` constraint chain producing a per-constraint `filter_trace`.
- **Step 3 — API (`app/main.py`):** `POST /schedule/search`; a `RequestValidationError` handler reshapes validation/semantic conflicts into a compact `ErrorDetail` at HTTP 422. Verified happy/diagnostics/conflict/schema paths via `TestClient`.
- **Step 4 — tests (`tests/`):** rewrote the two placeholders into real contract + workflow tests (10 passed).
- **Step 5 — skill + CLI:** `SKILL.md` documents the real contract; `scripts/search.py` became a working `httpx` client. Verified against a live uvicorn server.
- **Step 6 — evals:** filled `evals.proposal.json` (service/skill/e2e sections); cross-checked service evals against live responses.
- **Step 7 — optional LLM adapter (`app/llm.py`):** NL → structured `SearchRequest` via `anthropic` `messages.parse(output_format=...)` (verified the method + `.parsed_output` exist in SDK 0.120.2 before writing). Key-optional, injectable, default model `claude-opus-5`. 6 offline unit tests via a fake client (16 passed).
- **Assumptions:** datetimes normalized to UTC; slots not sub-divided; `search_slots` takes injected slots; `.env.example` Sonnet-4 id does not support structured outputs → adapter defaults to `claude-opus-5`.
- **Risks:** LLM path unverified against the live API (no key here); `get_slots()` rebuilds per request (trivial at this scale).

## Phase 2 — Diagnostics enhancement ("useful for humans and agents")
Part of commit `83258e5`.

- Added `RelaxationHint` and extended `Diagnostics` with `summary` (human one-liner) and `relaxation_hints` (per-constraint counterfactual: drop one filter, keep the rest → `would_match`), emitted when `matched < max_results`.
- Updated scheduler, tests (+2 → 18 passed), `SKILL.md`, and evals (+ `svc-sparse-relaxation-hint`); cross-checked all 5 service evals against live behavior.
- **Verified numbers:** duration-zero → relax `duration_minutes` → 15; location-zero → relax `location_id` → 12; sparse cardiology@clinic-south → matched 6, relax `location_id` → 12.
- **Assumptions:** "sparse" = `matched < max_results`; hints are a mechanical single-filter counterfactual.
- **Risks:** hint cost O(constraints × slots) — fine at demo scale; `Diagnostics` gained a required field `summary`.

## Phase 3 — DESIGN.md
Committed as `2ada9ba`. Concise design doc, **scoped to the read-only search/diagnostics slice** per direction: primary user, problem statement, in/out-of-scope, stateless query-workflow states, read-only tool surface (no writes), verification/safety/handoff boundaries, synthetic integrations, demo acceptance criteria, assumptions, limitations. Describes exactly the implemented contract (no new behavior).

## Phase 4 — Session service skeleton
Committed as `a822c20`. First runnable skeleton (`session_service/`), separate from the scheduling app.

- **Files:** `session_service/{__init__,models,repository,main}.py`, `tests/test_session_smoke.py`, README section.
- **Endpoints:** `GET /health`, `POST /sessions` (returns `session_id` + `trace_id`), `POST /sessions/{session_id}/messages` (typed transcript turn; structured 404). Typed Pydantic v2 models; thread-safe in-memory repository.
- **Excluded (by requirement):** LLM, audio/STT/TTS, telephony, EHR, real DB, real PHI, booking.
- **Results:** smoke test passed; full suite 19 passed. Verified live via curl on `0.0.0.0:8000`.
- **Limitations:** target Python 3.12 but tests ran on 3.11; in-memory only; no auth; `trace_id` returned but not yet propagated to logs; separate from the scheduling app.

## Phase 5 — Ops: Codespaces port exposure
- Started `uvicorn session_service.main:app --host 0.0.0.0 --port 8000` (background); confirmed `LISTEN 0.0.0.0:8000` and `GET /health` → 200.
- Forwarded URL: `https://<CODESPACE_NAME>-8000.app.github.dev`.
- Installed `gh` 2.97.0 to a throwaway temp dir (not committed) and toggled port 8000 **public** then back to **private** via `gh codespace ports visibility`. Security note recorded: a public port is unauthenticated; only synthetic data is served.

## Phase 6 — Text-based appointment workflow
Deterministic state machine (`appointment/`), not yet committed at time of writing.

- **Files:** `appointment/{__init__,dto,state,interfaces,intents,fakes,engine}.py`, `tests/test_appointment_workflow.py`.
- **Design:** explicit typed `ConversationState` (`START → AWAITING_VERIFICATION → AWAITING_REASON → AWAITING_SLOT_SELECTION → AWAITING_CONFIRMATION → BOOKED`; terminal `HANDOFF`); narrow Protocols for patient directory, scheduling, handoff, audit; deterministic in-memory fakes; deterministic keyword/regex intent rules.
- **Requirement mapping:** request → verify (last name + DOB) → broad non-clinical reason (emergency phrasing → safety handoff) → ≤3 slots → choose → read-back (provider/location/date/time) → explicit confirm → idempotent draft (`create_draft` keyed by `session_id:slot_id`).
- **Invariants tested:** no draft before explicit confirmation (no silent booking); duplicate confirmation creates no second draft; failed verification (2 attempts) → handoff; audit events sanitized (raw name/DOB absent from serialized events); ordered state list and ordered audit event-type list asserted end-to-end.
- **Results:** 5 workflow tests passed; full suite **24 passed** (Python 3.11.15).
- **Limitations:** standalone engine — not yet wired into the `POST /sessions/{id}/messages` endpoint; `parse_identity` expects `Lastname YYYY-MM-DD`; verification retry limit 2; booking is a draft only (no real scheduling/EHR write); no real LLM/voice.

## Phase 7 — Wire appointment workflow into the session API
- **Changed:** `session_service/repository.py` (owns a `ConversationContext` per session, `get_context()`), `session_service/models.py` (echo `MessageAcceptedResponse` → `TurnResponse` carrying `state`/`reply`/`done`/`turn_index`), `session_service/main.py` (module-level `AppointmentWorkflow` + fakes; `POST /sessions/{id}/messages` records the caller turn then advances the workflow), `tests/test_session_smoke.py` (rewritten + HTTP e2e and failed-verification tests).
- **Behavior:** each posted transcript turn drives the typed state machine; the response returns the agent reply and current `ConversationState`. Full request→verify→reason→slots→read-back→confirm→booked conversation now works over HTTP; duplicate confirmation stays `booked` with no second draft; failed verification hands off.
- **Results:** session tests 3 passed; full suite **26 passed** (Python 3.11.15).
- **Limitations:** in-memory singletons (workflow, repository, audit) — state resets on restart; transcript stores caller turns only; a single shared workflow instance across sessions (isolation is via per-session `ConversationContext` + `session_id`-scoped idempotency keys).

## Phase 8 — Live demo runs (over HTTP)
Ran `uvicorn session_service.main:app --host 0.0.0.0 --port 8000` and drove real
conversations via `POST /sessions/{id}/messages` (server stopped afterward; port
never made public).

- **Happy path + duplicate confirm:** request → `awaiting_verification` → verify (`Nguyen 1990-02-14`) → `awaiting_reason` → reason → `awaiting_slot_selection` (3 slots offered) → choose `1` → `awaiting_confirmation` (read-back: Dr. Alice Nguyen / Clinic North / 2026-08-03 / 09:00) → `yes` → `booked` (draft_001) → `yes` again → still `booked`, same `draft_001`, no second draft.
- **Failed verification → handoff:** wrong creds twice → terminal `handoff`; no patient verified, nothing booked.
- **Emergency reason → safety handoff:** after verifying, "chest pain" → terminal `handoff` with a non-clinical safety message; no slots offered, nothing booked.

All three matched the automated tests; behavior confirmed against a live server, not just `TestClient`.

---

## Git / commits (fork `origin`, branch `main`)
| Commit | Summary |
|---|---|
| `83258e5` | Read-only scheduling engine slice with search + diagnostics |
| `2ada9ba` | DESIGN.md for the read-only scheduling slice |
| `a822c20` | First runnable session service skeleton |
| (pending) | Appointment workflow + this REPORTS.md |

Branch is on the personal fork (`origin`, not `upstream`); nothing pushed to the parent repo.

## Consolidated standing assumptions
- Single clinic; all datetimes UTC; synthetic data only; no secrets; core demo needs no API key.
- The calling agent owns NLU/conversation orchestration; services expose typed tools.
- Deterministic intent rules and fakes stand in for LLM, voice, telephony, EHR, and real storage.

## Consolidated known limitations
- No persistence across restart; no auth/rate limiting; no real PHI or booking.
- LLM path unit-tested via injection but unverified against the live API in this environment.
- Two FastAPI apps coexist (`app.main` scheduling, `session_service.main` sessions); the appointment workflow is a third, standalone module not yet wired to HTTP.
- Target runtime is Python 3.12; tests were executed on 3.11.15.
