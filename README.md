# Third Way Health - Engineering Case Study

## Scheduling Engine Challenge (30 minutes)

**Timebox:** 30 minutes  
**Format:** live screenshare, think out loud  
**AI tools:** allowed and expected

## Scenario

Build a small scheduling engine service that an agent can use for slot search and troubleshooting.

The project includes a light scaffold, and you can shape the service contract as you see fit.

## What is provided

- Minimal folder scaffold under `app/`, `tests/`, and `skills/`.
- Placeholder files with TODOs.

## What to build

By the end of the session, we should be able to:

- run a FastAPI service,
- send a scheduling query from an agent-facing workflow,
- inspect an explain/diagnostics response (or equivalent),
- review your skill draft and eval proposal.

You can decide the exact interface, payloads, and internal logic.

## Real-world requirements (high-level)

Use these as initial assumptions:

- The service should support typical scheduling constraints (time windows, duration, provider/resource preferences).
- Responses should be useful for both humans and agents, including enough context to troubleshoot "no availability."
- The design should be extensible so new constraints can be added without major rewrites.
- Invalid or conflicting requests should return clear, actionable errors.
- Performance should be appropriate for interactive usage (low-latency responses for normal query sizes).
- Include a basic approach for testing both API correctness and agent behavior.

## How you'll be evaluated

We evaluate both your solution and your working approach:

- **Planning and decisions:** clarity of assumptions, decomposition, and trade-offs.
- **API and query design:** whether your interface is understandable and usable by an agent.
- **Execution quality:** ability to deliver a working thin slice within the timebox.
- **Diagnostics and testing approach:** ability to explain outcomes and define practical checks.
- **Agent collaboration:** effective use of AI tools with validation.

Minimum expectations:

- You present a clear plan.
- You demo at least one working end-to-end query path.
- You show one diagnostics/no-results explanation path (or equivalent).
- Your `SKILL.md` and eval proposal match your actual contract.

## GitHub Codespaces

- Open this repository in GitHub Codespaces.
- The devcontainer setup runs automatically on first start.
- `ANTHROPIC_API_KEY` will be provided for the session (via Codespaces secret/interviewer setup).

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python verify_setup.py
uvicorn app.main:app --reload
```

## Project docs

- [`DESIGN.md`](DESIGN.md) — design of the read-only scheduling slice.
- [`REPORTS.md`](REPORTS.md) — chronological build reports (files, commands, test results, assumptions, risks) for every phase.

## Session Service (first runnable skeleton)

A minimal, in-memory agent-session API. **Target runtime: Python 3.12** (the
code is 3.12-compatible and also runs on 3.11). Scope is deliberately tiny — no
LLM, audio, STT/TTS, telephony, EHR, real database, real patient data, or
appointment booking.

Endpoints:

- `GET /health` → `{"status": "ok"}`
- `POST /sessions` → creates a session, returns `session_id` + `trace_id`
- `POST /sessions/{session_id}/messages` → appends a text-transcript turn

Run:

```bash
pip install -r requirements.txt
uvicorn session_service.main:app --reload
```

Test (one smoke test):

```bash
python -m pytest tests/test_session_smoke.py -q
```

Manually test health:

```bash
curl -s http://127.0.0.1:8000/health          # {"status":"ok"}
# or open http://127.0.0.1:8000/docs in a browser
```

