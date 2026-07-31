"""Optional LLM adapter: natural language -> structured SearchRequest.

This is an *adapter*, fully isolated from the scheduler workflow and the API
transport. Nothing in the core slice imports it, so the service runs and the
tests pass with no API key. It turns a free-text request (e.g. "cardiology
opening tomorrow morning, 30 min") into a validated ``SearchRequest`` using the
Anthropic SDK's structured-output parsing.

Verified against the Anthropic SDK reference (anthropic 0.120.2):
- ``client.messages.parse(model=..., output_format=<PydanticModel>, ...)``
- the result exposes ``.parsed_output`` (a validated instance, or ``None``).

Structured outputs are supported on ``claude-opus-5``, Opus 4.8, Sonnet 5,
Haiku 4.5 (and legacy Opus 4.5/4.1) — **not** on ``claude-sonnet-4-20250514``
(the placeholder in ``.env.example``). Default model is ``claude-opus-5``.

No diagnosis, medication, or clinical advice is produced — extraction only.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Protocol

from app.models import SearchRequest

DEFAULT_MODEL = "claude-opus-5"

_SYSTEM_PROMPT = (
    "You extract structured appointment-search parameters from a user's request. "
    "You do NOT provide diagnosis, triage, medication, or any clinical advice — "
    "extraction only.\n"
    "Rules:\n"
    "- Output datetimes as UTC ISO-8601 (e.g. 2026-08-03T09:00:00Z).\n"
    "- Resolve relative dates/times against the provided reference date.\n"
    "- If no duration is stated, use 30 minutes.\n"
    "- If no time window is stated, use the reference date's 09:00–17:00 UTC.\n"
    "- Only fill provider_ids/specialty/location_id when the user names them; "
    "otherwise leave them empty/null."
)


class MessagesParser(Protocol):
    """Minimal structural type for the piece of the SDK client we use."""

    class _Messages(Protocol):
        def parse(self, **kwargs: Any) -> Any: ...

    messages: _Messages


class LLMConfigError(RuntimeError):
    """Raised when the LLM adapter cannot run (missing/placeholder credentials)."""


class LLMParseError(RuntimeError):
    """Raised when the model output could not be parsed into a SearchRequest."""


_PLACEHOLDER_KEYS = {"", "your-key-here", "your-key-will-be-pre-loaded"}


def _default_client() -> MessagesParser:
    """Construct a real Anthropic client, failing clearly if unusable."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key in _PLACEHOLDER_KEYS:
        raise LLMConfigError(
            "ANTHROPIC_API_KEY is not set (or is a placeholder); the LLM adapter "
            "is optional and the rest of the service runs without it."
        )
    try:
        import anthropic
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency is declared
        raise LLMConfigError("The 'anthropic' package is not installed.") from exc
    return anthropic.Anthropic()


def parse_query(
    text: str,
    *,
    reference_date: date,
    client: MessagesParser | None = None,
    model: str | None = None,
) -> SearchRequest:
    """Parse free text into a validated ``SearchRequest``.

    ``client`` is injectable so this is unit-testable without network access.
    Raises ``LLMConfigError`` if no usable client can be built, or
    ``LLMParseError`` if the model returns nothing parseable.
    """
    if not text.strip():
        raise LLMParseError("Query text is empty.")

    active = client if client is not None else _default_client()
    active_model = model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL

    result = active.messages.parse(
        model=active_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Reference date: {reference_date.isoformat()}\nRequest: {text}",
            }
        ],
        output_format=SearchRequest,
    )

    parsed = result.parsed_output
    if parsed is None:
        raise LLMParseError("Model did not return a parseable SearchRequest.")
    return parsed
