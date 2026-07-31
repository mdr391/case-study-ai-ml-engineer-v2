"""Smallest complete text-based appointment workflow (deterministic, no LLM).

An explicit typed state machine (`ConversationState`) drives a synthetic patient
from request -> identity verification -> reason -> <=3 slot offers -> selection
-> read-back -> explicit confirmation -> idempotent booking draft. All I/O is
behind narrow interfaces with in-memory fakes; audit events are sanitized (no
PHI). No real LLM, voice, telephony, EHR, or DB.
"""
