"""Offline tests for the optional LLM adapter.

These use an injected fake client so no API key or network call is needed.
The adapter's own logic (credential guard, empty-input guard, result
unwrapping, model selection) is what's under test — not the live model.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.llm import DEFAULT_MODEL, LLMConfigError, LLMParseError, parse_query
from app.models import SearchRequest

REF = date(2026, 7, 31)
VALID_REQUEST = SearchRequest.model_validate(
    {
        "time_window": {"start": "2026-08-03T09:00:00Z", "end": "2026-08-03T17:00:00Z"},
        "duration_minutes": 30,
        "specialty": "cardiology",
    }
)


class _FakeMessages:
    def __init__(self, parsed: object, recorder: dict) -> None:
        self._parsed = parsed
        self._recorder = recorder

    def parse(self, **kwargs: object) -> object:
        self._recorder.update(kwargs)
        return SimpleNamespace(parsed_output=self._parsed)


class _FakeClient:
    def __init__(self, parsed: object, recorder: dict | None = None) -> None:
        self.messages = _FakeMessages(parsed, recorder if recorder is not None else {})


def test_parse_query_returns_validated_request() -> None:
    result = parse_query("cardiology, 30 min", reference_date=REF, client=_FakeClient(VALID_REQUEST))
    assert isinstance(result, SearchRequest)
    assert result.specialty == "cardiology"


def test_parse_query_uses_default_model() -> None:
    recorder: dict = {}
    parse_query("x", reference_date=REF, client=_FakeClient(VALID_REQUEST, recorder))
    assert recorder["model"] == DEFAULT_MODEL
    assert recorder["output_format"] is SearchRequest


def test_parse_query_honors_explicit_model() -> None:
    recorder: dict = {}
    parse_query("x", reference_date=REF, client=_FakeClient(VALID_REQUEST, recorder), model="claude-haiku-4-5")
    assert recorder["model"] == "claude-haiku-4-5"


def test_parse_query_empty_text_raises() -> None:
    with pytest.raises(LLMParseError):
        parse_query("   ", reference_date=REF, client=_FakeClient(VALID_REQUEST))


def test_parse_query_none_output_raises() -> None:
    with pytest.raises(LLMParseError):
        parse_query("something", reference_date=REF, client=_FakeClient(None))


def test_missing_api_key_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "your-key-here")
    with pytest.raises(LLMConfigError):
        parse_query("cardiology", reference_date=REF)  # no injected client -> builds default
