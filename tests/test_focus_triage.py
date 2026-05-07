"""Tests for the LLM-based focus triage path (select_focus_async).

Plan: docs/agentic-focus-triage.md.

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
    _fetch_recent_overrides,
    _format_override_corrections_section,
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


# ---------------------------------------------------------------------------
# Override-history few-shot section (oompah-zlz_2-saj, child C of focus-override)
# ---------------------------------------------------------------------------


def _override_event(
    issue_id: str = "trickle-6zi",
    issue_title: str = "CI-Speed 3: build-once + artifact reuse",
    issue_labels=None,
    issue_type: str = "task",
    original_focus: str = "devops",
    override_focus: str = "ci_fix",
    operator_reason: str = "this is a ci-fix bead, not devops infrastructure work.",
    timestamp: str = "2026-05-07T16:42:00Z",
    project_id: str = "proj-3e4e9214",
) -> dict:
    if issue_labels is None:
        issue_labels = ["ci-fix"]
    return {
        "issue_id": issue_id,
        "issue_title": issue_title,
        "issue_labels": issue_labels,
        "issue_type": issue_type,
        "issue_priority": 0,
        "original_focus": original_focus,
        "original_focus_score": 15,
        "original_focus_via": "llm",
        "override_focus": override_focus,
        "operator_reason": operator_reason,
        "timestamp": timestamp,
        "project_id": project_id,
    }


class _FakeTracker:
    """Minimal tracker double that returns canned memories."""

    def __init__(self, memories):
        self._memories = memories
        self.fetch_calls = 0

    def fetch_memories(self):
        self.fetch_calls += 1
        return self._memories


class TestFormatOverrideCorrectionsSection:
    def test_empty_returns_empty_string(self):
        assert _format_override_corrections_section([]) == ""

    def test_renders_header_and_bullet_for_one_event(self):
        events = [_override_event()]
        section = _format_override_corrections_section(events)
        assert "## Operator corrections (recent overrides)" in section
        assert "operator chose focus=ci_fix" in section
        assert "instead of triage-suggested devops" in section
        assert "labels=[ci-fix]" in section
        assert "type=task" in section
        # Reason quoted as operator text
        assert "\"this is a ci-fix bead" in section

    def test_renders_multiple_events(self):
        events = [
            _override_event(
                issue_id="trickle-6zi",
                issue_title="CI-Speed 3: build-once + artifact reuse",
                issue_labels=["ci-fix"],
                original_focus="devops",
                override_focus="ci_fix",
                operator_reason="this is a ci-fix bead, not devops infrastructure work.",
            ),
            _override_event(
                issue_id="trickle-c0w",
                issue_title="Resolve merge conflicts on PR #30",
                issue_labels=["merge-conflict"],
                original_focus="queue_api",
                override_focus="merge_conflict",
                operator_reason="merge-conflict specialist has the right rails.",
            ),
        ]
        section = _format_override_corrections_section(events)
        assert "ci_fix" in section
        assert "merge_conflict" in section
        assert "labels=[merge-conflict]" in section
        assert section.count("- On issue") == 2

    def test_handles_missing_optional_fields(self):
        # No reason — bullet should still render without a Reason: clause
        ev = _override_event(operator_reason="")
        section = _format_override_corrections_section([ev])
        assert "operator chose focus=ci_fix" in section
        assert "Reason:" not in section

    def test_truncates_long_titles(self):
        ev = _override_event(issue_title="x" * 200)
        section = _format_override_corrections_section([ev])
        # Title should be capped to ~80 chars including ellipsis
        assert "..." in section
        # 'x' run shouldn't be the full 200 chars
        assert "x" * 200 not in section

    def test_skips_non_dict_entries(self):
        section = _format_override_corrections_section([
            "not a dict",
            None,
            _override_event(),
        ])
        # Only one valid entry → exactly one bullet
        assert section.count("- On issue") == 1


class TestBuildTriagePromptWithOverrides:
    def test_no_overrides_produces_unchanged_prompt(self):
        issue = _issue(title="webhook dispatch")
        foci = [_focus("feature"), _focus("test")]
        baseline = _build_triage_prompt(issue, foci)
        with_empty = _build_triage_prompt(issue, foci, override_history=[])
        with_none = _build_triage_prompt(issue, foci, override_history=None)
        # All three identical when no history
        assert baseline == with_empty == with_none
        assert "Operator corrections" not in baseline

    def test_history_emits_section(self):
        issue = _issue(title="webhook dispatch")
        foci = [_focus("feature"), _focus("test")]
        history = [_override_event()]
        prompt = _build_triage_prompt(issue, foci, override_history=history)
        assert "## Operator corrections (recent overrides)" in prompt
        assert "operator chose focus=ci_fix" in prompt

    def test_section_appears_after_specialists_before_task(self):
        """The Operator corrections section MUST sit between SPECIALISTS
        and TASK. The LLM treats it as additional context, not as part
        of the response-format instructions."""
        issue = _issue(title="webhook dispatch")
        foci = [_focus("feature"), _focus("test")]
        history = [_override_event()]
        prompt = _build_triage_prompt(issue, foci, override_history=history)
        idx_specialists = prompt.index("SPECIALISTS")
        idx_overrides = prompt.index("## Operator corrections")
        idx_task = prompt.index("TASK")
        assert idx_specialists < idx_overrides < idx_task

    def test_renders_all_supplied_events(self):
        """The prompt builder itself does not truncate (caller does)
        — but it MUST render exactly the events it is given."""
        issue = _issue()
        foci = [_focus("feature")]
        history = [
            _override_event(issue_id=f"id-{i}", issue_title=f"Issue {i}")
            for i in range(15)
        ]
        prompt = _build_triage_prompt(issue, foci, override_history=history)
        # All 15 should appear because caller is responsible for truncation
        assert prompt.count("- On issue") == 15


class TestFetchRecentOverrides:
    def test_no_tracker_returns_empty(self):
        assert _fetch_recent_overrides(None) == []

    def test_filters_to_focus_override_keys(self):
        import json as _json
        memories = {
            "focus-override-trickle-6zi-20260507": _json.dumps(_override_event()),
            "some-other-memory": "irrelevant",
            "focus-override-bad-payload": "not-json",
        }
        events = _fetch_recent_overrides(_FakeTracker(memories))
        assert len(events) == 1
        assert events[0]["issue_id"] == "trickle-6zi"

    def test_filters_by_project_id(self):
        import json as _json
        memories = {
            "focus-override-a-1": _json.dumps(_override_event(project_id="proj-A")),
            "focus-override-b-1": _json.dumps(_override_event(project_id="proj-B")),
        }
        # No filter → both
        evs_all = _fetch_recent_overrides(_FakeTracker(memories))
        assert len(evs_all) == 2
        # Filter to A
        evs_a = _fetch_recent_overrides(_FakeTracker(memories), project_id="proj-A")
        assert len(evs_a) == 1
        assert evs_a[0]["project_id"] == "proj-A"

    def test_sorts_most_recent_first(self):
        import json as _json
        memories = {
            "focus-override-x-2026-05-01": _json.dumps(_override_event(
                issue_id="x", timestamp="2026-05-01T00:00:00Z",
            )),
            "focus-override-x-2026-05-07": _json.dumps(_override_event(
                issue_id="x", timestamp="2026-05-07T00:00:00Z",
            )),
            "focus-override-x-2026-05-03": _json.dumps(_override_event(
                issue_id="x", timestamp="2026-05-03T00:00:00Z",
            )),
        }
        events = _fetch_recent_overrides(_FakeTracker(memories))
        ts = [e["timestamp"] for e in events]
        assert ts == sorted(ts, reverse=True)
        assert ts[0] == "2026-05-07T00:00:00Z"

    def test_truncates_at_limit(self):
        import json as _json
        memories = {
            f"focus-override-x-{i:02d}": _json.dumps(_override_event(
                issue_id=f"x{i}", timestamp=f"2026-05-{i:02d}T00:00:00Z",
            ))
            for i in range(1, 21)  # 20 events
        }
        events = _fetch_recent_overrides(_FakeTracker(memories), limit=10)
        assert len(events) == 10
        # Should be the 10 most recent (days 11-20, in reverse)
        assert events[0]["timestamp"].startswith("2026-05-20")
        assert events[-1]["timestamp"].startswith("2026-05-11")

    def test_default_limit_is_ten(self):
        import json as _json
        memories = {
            f"focus-override-x-{i:02d}": _json.dumps(_override_event(
                issue_id=f"x{i}", timestamp=f"2026-05-{i:02d}T00:00:00Z",
            ))
            for i in range(1, 16)  # 15 events
        }
        events = _fetch_recent_overrides(_FakeTracker(memories))
        # Default _DEFAULT_OVERRIDE_HISTORY_N=10
        assert len(events) == 10

    def test_handles_tracker_exception(self):
        class BoomTracker:
            def fetch_memories(self):
                raise RuntimeError("bd unavailable")

        events = _fetch_recent_overrides(BoomTracker())
        assert events == []

    def test_handles_non_dict_memories(self):
        class WeirdTracker:
            def fetch_memories(self):
                return "not a dict"

        assert _fetch_recent_overrides(WeirdTracker()) == []


class TestSelectFocusAsyncWithOverrideHistory:
    def test_passes_override_history_to_llm(self, monkeypatch):
        """When tracker is supplied, the LLM call receives the
        override_history kwarg with parsed events."""
        import json as _json
        issue = _issue(title="ci speed work", labels=["ci-fix"])
        foci = [_focus("feature", keywords=["feature"]),
                _focus("ci_fix", keywords=["ci-fix"], labels=["ci-fix"])]
        captured = {}

        async def fake_llm(issue, foci, provider, override_history=None):
            captured["override_history"] = override_history
            return "ci_fix", "matches recent operator corrections"

        monkeypatch.setattr("oompah.focus._select_focus_llm", fake_llm)
        memories = {
            "focus-override-x-1": _json.dumps(_override_event()),
        }
        tracker = _FakeTracker(memories)
        result = asyncio.run(select_focus_async(
            issue, foci=foci, provider=_FakeProvider(),
            tracker=tracker, project_id="proj-3e4e9214",
        ))
        assert result.name == "ci_fix"
        assert captured["override_history"] is not None
        assert len(captured["override_history"]) == 1
        assert captured["override_history"][0]["override_focus"] == "ci_fix"

    def test_no_tracker_passes_empty_history(self, monkeypatch):
        issue = _issue(title="feature work", description="feature")
        foci = [_focus("feature", keywords=["feature"])]
        captured = {}

        async def fake_llm(issue, foci, provider, override_history=None):
            captured["override_history"] = override_history
            return "feature", "ok"

        monkeypatch.setattr("oompah.focus._select_focus_llm", fake_llm)
        result = asyncio.run(select_focus_async(
            issue, foci=foci, provider=_FakeProvider(),
        ))
        assert result.name == "feature"
        # Empty list (not None) — the helper always passes a list when LLM is consulted
        assert captured["override_history"] == []

    def test_project_filter_is_respected(self, monkeypatch):
        """Events for a different project must NOT leak into the prompt."""
        import json as _json
        issue = _issue(title="some feature work")
        foci = [_focus("feature", keywords=["feature"])]
        captured = {}

        async def fake_llm(issue, foci, provider, override_history=None):
            captured["override_history"] = override_history
            return "feature", "ok"

        monkeypatch.setattr("oompah.focus._select_focus_llm", fake_llm)
        memories = {
            "focus-override-other-1": _json.dumps(_override_event(project_id="proj-OTHER")),
            "focus-override-mine-1": _json.dumps(_override_event(project_id="proj-MINE")),
        }
        asyncio.run(select_focus_async(
            issue, foci=foci, provider=_FakeProvider(),
            tracker=_FakeTracker(memories), project_id="proj-MINE",
        ))
        assert len(captured["override_history"]) == 1
        assert captured["override_history"][0]["project_id"] == "proj-MINE"

    def test_history_change_invalidates_cache(self, monkeypatch):
        """The cache key incorporates the override-history fingerprint
        so a new operator correction triggers a fresh LLM call."""
        import json as _json
        issue = _issue(title="some feature work")
        foci = [_focus("feature", keywords=["feature"])]
        call_count = {"n": 0}

        async def fake_llm(issue, foci, provider, override_history=None):
            call_count["n"] += 1
            return "feature", f"call {call_count['n']}"

        monkeypatch.setattr("oompah.focus._select_focus_llm", fake_llm)

        memories_v1 = {
            "focus-override-x-1": _json.dumps(_override_event(timestamp="2026-05-01T00:00:00Z")),
        }
        asyncio.run(select_focus_async(
            issue, foci=foci, provider=_FakeProvider(),
            tracker=_FakeTracker(memories_v1), project_id="proj-3e4e9214",
        ))
        # Same memories — should hit cache.
        asyncio.run(select_focus_async(
            issue, foci=foci, provider=_FakeProvider(),
            tracker=_FakeTracker(memories_v1), project_id="proj-3e4e9214",
        ))
        assert call_count["n"] == 1

        # New override event lands → cache key changes → fresh LLM call.
        memories_v2 = dict(memories_v1)
        memories_v2["focus-override-x-2"] = _json.dumps(_override_event(
            timestamp="2026-05-08T00:00:00Z",
        ))
        asyncio.run(select_focus_async(
            issue, foci=foci, provider=_FakeProvider(),
            tracker=_FakeTracker(memories_v2), project_id="proj-3e4e9214",
        ))
        assert call_count["n"] == 2

    def test_needs_label_short_circuit_skips_fetch(self, monkeypatch):
        """When a `needs:<focus>` label is present, the LLM is not
        consulted, so we should not waste a tracker fetch either."""
        issue = _issue(labels=["needs:test"])
        foci = [_focus("feature"), _focus("test")]
        tracker = _FakeTracker({})

        async def fake_llm(*a, **kw):  # pragma: no cover - should not run
            raise AssertionError("LLM should not be consulted")

        monkeypatch.setattr("oompah.focus._select_focus_llm", fake_llm)
        result = asyncio.run(select_focus_async(
            issue, foci=foci, provider=_FakeProvider(),
            tracker=tracker, project_id="proj-X",
        ))
        assert result.name == "test"
        assert tracker.fetch_calls == 0
