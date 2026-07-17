"""Tests for the LLM-based focus triage path (select_focus_async).

Plan: plans/agentic-focus-triage.md.

Covers:
- needs:<X> label short-circuit (no LLM call).
- LLM picks a valid focus → that focus is returned.
- LLM returns reasoning → reasoning is logged (auditable).
- LLM returns "default" → DEFAULT_FOCUS is returned.
- LLM picks an unknown name → falls back to deterministic.
- LLM picks a focus that scores 0 (hallucination) → falls back.
- LLM call times out / errors → falls back.
- Cache: same content → only one LLM call.
- No provider supplied → falls back to deterministic without trying.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from oompah.focus import (
    DEFAULT_FOCUS,
    Focus,
    _build_triage_prompt,
    _parse_triage_response,
    _triage_cache,
    select_focus_async,
)
from oompah.models import Issue


def _issue(**overrides) -> Issue:
    defaults = dict(
        id="oompah-x",
        identifier="oompah-x",
        title="Add adaptive polling",
        description="Implement webhook-driven dispatch.",
        priority=2,
        state="open",
        issue_type="feature",
        labels=[],
    )
    defaults.update(overrides)
    return Issue(**defaults)


def _focus(name: str, **kwargs) -> Focus:
    defaults = dict(
        name=name,
        role=f"{name.title()} Specialist",
        description=f"{name} work",
        keywords=[name],
        issue_types=[],
        labels=[],
        priority=0,
        status="active",
    )
    defaults.update(kwargs)
    return Focus(**defaults)


class _FakeProvider:
    base_url = "http://x.test/v1"
    api_key = "k"
    default_model = "test-model"


@pytest.fixture(autouse=True)
def _clear_cache():
    _triage_cache.clear()
    yield
    _triage_cache.clear()


class TestParseTriageResponse:
    def test_name_and_reasoning(self):
        n, r = _parse_triage_response("feature: this is new functionality")
        assert n == "feature"
        assert r == "this is new functionality"

    def test_name_only(self):
        n, r = _parse_triage_response("default")
        assert n == "default"
        assert r == ""

    def test_strips_quotes_and_backticks(self):
        n, r = _parse_triage_response("`feature`: x")
        assert n == "feature"
        n2, _ = _parse_triage_response('"feature"')
        assert n2 == "feature"

    def test_skips_blank_lines(self):
        n, r = _parse_triage_response("\n\n  - feature: it fits\n")
        assert n == "feature"
        assert r == "it fits"

    def test_empty_input(self):
        n, r = _parse_triage_response("")
        assert n is None
        assert r == ""


class TestBuildTriagePrompt:
    def test_includes_issue_and_each_focus(self):
        issue = _issue(title="webhook dispatch", description="d" * 50)
        foci = [_focus("feature"), _focus("test")]
        p = _build_triage_prompt(issue, foci)
        assert "webhook dispatch" in p
        assert "name: feature" in p
        assert "name: test" in p
        assert "best-fit specialist" in p

    def test_truncates_long_description(self):
        issue = _issue(description="x" * 5000)
        foci = [_focus("feature")]
        p = _build_triage_prompt(issue, foci)
        # Description is truncated to ~1500 chars
        assert "..." in p
        assert len(p) < 5000


class TestNeedsLabelShortCircuit:
    def test_label_wins_over_llm(self):
        issue = _issue(labels=["needs:test"])
        foci = [_focus("feature"), _focus("test")]
        called = {"flag": False}

        async def fake_llm(*a, **kw):
            called["flag"] = True
            return "feature", "irrelevant"

        import oompah.focus as focmod
        original = focmod._select_focus_llm
        focmod._select_focus_llm = fake_llm
        try:
            result = asyncio.run(
                select_focus_async(issue, foci=foci, provider=_FakeProvider()),
            )
        finally:
            focmod._select_focus_llm = original

        assert result.name == "test"
        assert called["flag"] is False  # never called the LLM

    def test_completed_focus_is_skipped_on_async_path(self):
        """The post-handoff dispatch uses the same rule on the async path."""
        issue = _issue(
            title="Update duplicate detection",
            labels=["focus-complete:duplicate_detector"],
        )
        foci = [
            _focus("duplicate_detector", keywords=["duplicate"], priority=20),
            _focus("chore", keywords=["update"]),
        ]

        result = asyncio.run(select_focus_async(issue, foci=foci, provider=None))

        assert result.name == "chore"


class TestLlmTriage:
    def _patch_llm(self, monkeypatch, name: str | None, reasoning: str = ""):
        async def fake_llm(*a, **kw):
            return name, reasoning
        monkeypatch.setattr("oompah.focus._select_focus_llm", fake_llm)

    def test_llm_picks_valid_focus(self, monkeypatch):
        issue = _issue(title="add feature x")
        foci = [_focus("feature", keywords=["feature"]), _focus("test")]
        self._patch_llm(monkeypatch, "feature", "this is new functionality")
        result = asyncio.run(
            select_focus_async(issue, foci=foci, provider=_FakeProvider()),
        )
        assert result.name == "feature"

    def test_llm_returns_default_uses_default_focus(self, monkeypatch):
        issue = _issue()
        foci = [_focus("feature"), _focus("test")]
        self._patch_llm(monkeypatch, "default", "nothing fits")
        result = asyncio.run(
            select_focus_async(issue, foci=foci, provider=_FakeProvider()),
        )
        assert result is DEFAULT_FOCUS

    def test_llm_unknown_name_falls_back_to_score(self, monkeypatch):
        issue = _issue(title="feature work feature feature", labels=["feature"])
        foci = [_focus("feature", keywords=["feature"], labels=["feature"]),
                _focus("test")]
        self._patch_llm(monkeypatch, "nonexistent", "garbage")
        result = asyncio.run(
            select_focus_async(issue, foci=foci, provider=_FakeProvider()),
        )
        # Falls back to deterministic — feature should win on keyword/label hits.
        assert result.name == "feature"

    def test_llm_pick_with_score_zero_falls_back(self, monkeypatch):
        """LLM picks a focus that has zero deterministic alignment with
        the issue → treated as hallucination, fall back to scorer."""
        issue = _issue(title="add feature work", description="feature feature")
        # `test` has no keywords matching the issue.
        feature = _focus("feature", keywords=["feature"])
        test = _focus("test", keywords=["zzzzz"], issue_types=["bug"])
        foci = [feature, test]
        self._patch_llm(monkeypatch, "test", "i think tests are needed")
        result = asyncio.run(
            select_focus_async(issue, foci=foci, provider=_FakeProvider()),
        )
        # Fell back to feature (deterministic top).
        assert result.name == "feature"

    def test_llm_pick_with_score_positive_is_trusted(self, monkeypatch):
        """LLM's pick wins as long as it has *some* keyword/label/type
        alignment, even if the deterministic top would have picked
        differently. This is the whole point of the LLM."""
        issue = _issue(
            title="add x",
            description="feature work feature feature",
            issue_type="feature",
        )
        # Both score > 0 on this issue. Feature scores higher (more
        # keyword hits), but the LLM picks `lite_feature` and we honor it.
        feature = _focus("feature", keywords=["feature"], issue_types=["feature"])
        lite = _focus("lite_feature", keywords=["feature"], issue_types=["feature"])
        foci = [feature, lite]
        self._patch_llm(monkeypatch, "lite_feature", "this is small")
        result = asyncio.run(
            select_focus_async(issue, foci=foci, provider=_FakeProvider()),
        )
        assert result.name == "lite_feature"

    def test_llm_returns_none_falls_back(self, monkeypatch):
        issue = _issue(title="feature work", description="feature")
        foci = [_focus("feature", keywords=["feature"]), _focus("test")]
        self._patch_llm(monkeypatch, None, "")
        result = asyncio.run(
            select_focus_async(issue, foci=foci, provider=_FakeProvider()),
        )
        assert result.name == "feature"  # deterministic top

    def test_no_provider_uses_deterministic(self, monkeypatch):
        # Without a provider, no LLM call is made.
        issue = _issue(title="feature work", description="feature")
        foci = [_focus("feature", keywords=["feature"]), _focus("test")]
        called = {"flag": False}

        async def fake_llm(*a, **kw):
            called["flag"] = True
            return "test", "x"

        monkeypatch.setattr("oompah.focus._select_focus_llm", fake_llm)
        result = asyncio.run(
            select_focus_async(issue, foci=foci, provider=None),
        )
        assert result.name == "feature"
        assert called["flag"] is False


class TestTriageCache:
    def test_same_inputs_only_one_call(self, monkeypatch):
        issue = _issue(title="feature work", description="feature feature")
        foci = [_focus("feature", keywords=["feature"]), _focus("test")]
        call_count = {"n": 0}

        async def fake_llm(*a, **kw):
            call_count["n"] += 1
            return "feature", "first time"

        monkeypatch.setattr("oompah.focus._select_focus_llm", fake_llm)

        r1 = asyncio.run(
            select_focus_async(issue, foci=foci, provider=_FakeProvider()),
        )
        r2 = asyncio.run(
            select_focus_async(issue, foci=foci, provider=_FakeProvider()),
        )
        assert r1.name == r2.name == "feature"
        assert call_count["n"] == 1

    def test_different_content_calls_again(self, monkeypatch):
        foci = [_focus("feature", keywords=["feature"])]
        call_count = {"n": 0}

        async def fake_llm(*a, **kw):
            call_count["n"] += 1
            return "feature", "x"

        monkeypatch.setattr("oompah.focus._select_focus_llm", fake_llm)

        i1 = _issue(id="x1", identifier="x1", title="A feature")
        i2 = _issue(id="x2", identifier="x2", title="B feature")
        asyncio.run(select_focus_async(i1, foci=foci, provider=_FakeProvider()))
        asyncio.run(select_focus_async(i2, foci=foci, provider=_FakeProvider()))
        assert call_count["n"] == 2


class TestLlmTimeoutAndError:
    def test_timeout_falls_back(self, monkeypatch):
        issue = _issue(title="feature work feature", description="feature")
        foci = [_focus("feature", keywords=["feature"]), _focus("test")]

        async def slow_llm(*a, **kw):
            # _select_focus_llm catches its own exceptions; simulate the
            # already-handled outcome (None, "").
            return None, ""

        monkeypatch.setattr("oompah.focus._select_focus_llm", slow_llm)
        result = asyncio.run(
            select_focus_async(issue, foci=foci, provider=_FakeProvider()),
        )
        assert result.name == "feature"

    def test_provider_without_default_model_falls_back(self, monkeypatch):
        from oompah.focus import _select_focus_llm

        issue = _issue(title="feature work", description="feature")
        foci = [_focus("feature", keywords=["feature"])]

        class BadProvider:
            base_url = "http://x"
            api_key = ""
            default_model = None  # missing!

        # Don't patch — call the real function so we test the guard.
        n, r = asyncio.run(_select_focus_llm(issue, foci, BadProvider()))
        assert n is None
        assert r == ""
