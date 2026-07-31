# DESIGN.md — Agent-Facing Appointment Scheduling (read-only slice)

## Primary user
An **AI scheduling agent** (voice or chat) that queries the service on behalf of a patient contacting the clinic. Secondary: clinic staff who read the responses to understand availability.

## Problem statement
Give an agent a reliable, low-latency, read-only service to find appointment slots under real-world constraints and explain "no availability" well enough for the agent to recover — without any booking, writes, or clinical reasoning.

## In-scope behavior
- Constraint-based slot **search** (time window, duration, provider/specialty/location).
- Structured **diagnostics** for empty/sparse results: `summary`, `filter_trace`, `relaxation_hints`, `suggestions`.
- Optional natural-language → structured `SearchRequest` parsing (LLM adapter, key-optional).
- Clear, structured **errors** for invalid or conflicting requests.

## Out-of-scope behavior
- Any write: booking, holding, reschedule, cancel, waitlist.
- Patient identity verification and any exposure of existing-appointment / PHI data.
- Any clinical function: triage, diagnosis, medication, symptom advice.
- Real EHR / telephony / voice / payment integration; real PHI; production auth; durable storage; multi-clinic routing.

## Workflow states and transitions
The read-only lifecycle is a stateless per-request query loop (no session, no patient state):
```
RECEIVE_QUERY ──> VALIDATE ──> SEARCH ──> RESULTS
                     │             │
                     │             └──> NO_AVAILABILITY ──(agent relaxes constraints)──> RECEIVE_QUERY
                     v
                 INVALID_REQUEST (structured 422; agent corrects and retries)
```
- Each request is independent; the service holds no cross-request state.
- `NO_AVAILABILITY` is a normal `200` outcome (empty `results` + diagnostics), not an error.

## Read-only and write-capable tools
- **Read-only:** `search_slots` — returns ranked slots plus a diagnostics block (search + "why no availability" in one call).
- **Write-capable:** **none.** All mutation (booking, verification, handoff records) is explicitly deferred to a later phase and is out of scope here.

## Patient verification boundary
No verification is required or performed in this slice. The service exposes **only open, non-identifying slot inventory** and performs **no writes**, so there is no PHI to protect and no state to mutate. Identity verification is a prerequisite of the (out-of-scope) write phase and is deliberately excluded here.

## Safety and human-handoff rules
- The service returns **scheduling data only** — never diagnosis, medication, triage, or any clinical advice, in any field (including `summary`/`suggestions`).
- It never fabricates slots, providers, or availability; every value in a response is derived from the synthetic inventory.
- Clinical, emergency, or otherwise out-of-scope intent is **not** interpreted by the service; recognizing such input and handing off to a human is the calling agent's responsibility. The service's contribution to safety is to stay strictly within scheduling and to fail loudly (structured errors) rather than guess.

## Synthetic and mocked integrations
- **Slot inventory:** in-memory synthetic data (`app/data.py`), deterministic, no PHI.
- **EHR (read):** the inventory stands in for an EHR availability feed, behind the pure scheduler; a real feed would replace `get_slots()` without touching the workflow.
- **LLM:** Anthropic structured outputs via `app/llm.py` (optional, key-optional, injectable for tests).
- **Telephony/voice/booking store:** none — a text/JSON request stands in for the channel.

## Acceptance criteria for the live demonstration
1. FastAPI service starts; `GET /health` returns `{"status": "ok"}`.
2. Happy path: a `POST /schedule/search` query returns ranked slots (earliest first, capped at `max_results`) with a human-readable `summary`.
3. No-availability: the response is `200` with empty `results`, a `filter_trace` naming the limiting constraint, at least one `relaxation_hint` (quantified), and a suggestion.
4. Sparse results (fewer than a full page) also carry actionable `relaxation_hints`.
5. Invalid/conflicting request returns a structured `422` (`{error, message, field}`).
6. The core demo runs with **no API key**; the optional LLM parse path is shown separately or via its injected unit tests.
7. `SKILL.md` and `evals.proposal.json` match the live contract.

## Assumptions
- Single clinic; all datetimes normalized to UTC.
- The calling agent owns natural-language understanding and conversation state; the service exposes a typed, stateless tool.
- Synthetic data only; no secrets; demo needs no API key.

## Known limitations
- No persistence, no writes, and therefore no booking, reschedule, or cancel.
- No auth, rate limiting, or per-caller isolation.
- Relaxation hints are a mechanical single-filter counterfactual, not a global optimum, and cost O(constraints × slots) — fine at demo scale, would need indexing at production scale.
- The LLM parse path is unit-tested via injection but unverified against the live API in this environment.
- The synthetic inventory is fixed and small; contract tests pin its exact counts.
