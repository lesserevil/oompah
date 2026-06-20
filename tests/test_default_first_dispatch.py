"""Tests for the default_first_dispatch feature (oompah-zlz_2-17u).

The feature inverts the initial dispatch path when enabled:
- First dispatch → catch-all "default" profile + provider.default_model
- First retry after failure → the profile _match_agent_profile() would
  have originally chosen (the "natural" match)
- Subsequent retries → continue escalating up _PROFILE_HIERARCHY

needs:<focus> labels bypass the flag at both dispatch and retry.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import AgentProfile, Issue, RunningEntry
from oompah.orchestrator import Orchestrator

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_profiles() -> list[AgentProfile]:
    """Create a standard set of agent profiles used by multiple tests."""
    return [
        AgentProfile(
            name="default",
            command="cli",
            model_role="fast",
        ),
        AgentProfile(
            name="quick",
            command="cli",
            model_role="fast",
            issue_types=["chore"],
            keywords=["typo", "cleanup"],
            max_priority=4,
        ),
        AgentProfile(
            name="standard",
            command="cli",
            model_role="standard",
            issue_types=["task", "feature"],
        ),
        AgentProfile(
            name="deep",
            command="cli",
            model_role="deep",
            issue_types=["bug", "epic"],
            keywords=["security", "critical"],
        ),
    ]


def _make_config(default_first_dispatch: bool = False) -> ServiceConfig:
    cfg = ServiceConfig(default_first_dispatch=default_first_dispatch)
    cfg.agent_profiles = _make_profiles()
    return cfg


def _make_issue(
    identifier: str = "test-1",
    state: str = "open",
    issue_type: str = "bug",
    priority: int = 2,
    labels: list | None = None,
    description: str = "This is a well-described bug issue.",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description=description,
        state=state,
        issue_type=issue_type,
        priority=priority,
        labels=labels or [],
    )


def _make_running_entry(
    issue: Issue,
    profile_name: str = "default",
    natural_profile_name: str | None = None,
    retry_attempt: int = 0,
) -> RunningEntry:
    from datetime import datetime, timezone
    return RunningEntry(
        worker_task=MagicMock(),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=retry_attempt,
        started_at=datetime.now(timezone.utc),
        agent_profile_name=profile_name,
        natural_profile_name=natural_profile_name,
    )


def _make_orchestrator(
    tmp_path,
    default_first_dispatch: bool = False,
) -> Orchestrator:
    """Create a minimal Orchestrator with mocked project store."""
    project_store = MagicMock()
    project_store.list_all.return_value = []
    return Orchestrator(
        config=_make_config(default_first_dispatch=default_first_dispatch),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


# ---------------------------------------------------------------------------
# ServiceConfig.from_workflow — flag parsing
# ---------------------------------------------------------------------------

class TestDefaultFirstDispatchConfig:
    """Tests for config loading of the default_first_dispatch flag."""

    def setup_method(self):
        import os
        for key in list(os.environ):
            if key.startswith("OOMPAH_"):
                os.environ.pop(key, None)

    def teardown_method(self):
        import os
        for key in list(os.environ):
            if key.startswith("OOMPAH_"):
                os.environ.pop(key, None)

    def test_default_is_false(self):
        """Flag defaults to False (current behaviour preserved)."""
        from oompah.models import WorkflowDefinition
        wf = WorkflowDefinition(config={}, prompt_template="t")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.default_first_dispatch is False

    def test_flag_enabled_via_yaml(self):
        """Flag can be enabled via WORKFLOW.md agent.default_first_dispatch: true."""
        from oompah.models import WorkflowDefinition
        wf = WorkflowDefinition(
            config={"agent": {"default_first_dispatch": True}},
            prompt_template="t",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.default_first_dispatch is True

    def test_flag_enabled_via_yaml_string(self):
        """Flag accepts string 'true' in YAML."""
        from oompah.models import WorkflowDefinition
        wf = WorkflowDefinition(
            config={"agent": {"default_first_dispatch": "true"}},
            prompt_template="t",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.default_first_dispatch is True

    def test_flag_disabled_via_yaml(self):
        """Flag can be explicitly disabled via WORKFLOW.md."""
        from oompah.models import WorkflowDefinition
        wf = WorkflowDefinition(
            config={"agent": {"default_first_dispatch": False}},
            prompt_template="t",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.default_first_dispatch is False

    def test_env_var_enables_flag(self, monkeypatch):
        """OOMPAH_DEFAULT_FIRST_DISPATCH=1 enables the flag."""
        monkeypatch.setenv("OOMPAH_DEFAULT_FIRST_DISPATCH", "1")
        from oompah.models import WorkflowDefinition
        wf = WorkflowDefinition(config={}, prompt_template="t")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.default_first_dispatch is True

    def test_env_var_true_string(self, monkeypatch):
        """OOMPAH_DEFAULT_FIRST_DISPATCH=true enables the flag."""
        monkeypatch.setenv("OOMPAH_DEFAULT_FIRST_DISPATCH", "true")
        from oompah.models import WorkflowDefinition
        wf = WorkflowDefinition(config={}, prompt_template="t")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.default_first_dispatch is True

    def test_env_var_yes_string(self, monkeypatch):
        """OOMPAH_DEFAULT_FIRST_DISPATCH=yes enables the flag."""
        monkeypatch.setenv("OOMPAH_DEFAULT_FIRST_DISPATCH", "yes")
        from oompah.models import WorkflowDefinition
        wf = WorkflowDefinition(config={}, prompt_template="t")
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.default_first_dispatch is True

    def test_env_var_zero_disables_flag(self, monkeypatch):
        """OOMPAH_DEFAULT_FIRST_DISPATCH=0 disables the flag."""
        monkeypatch.setenv("OOMPAH_DEFAULT_FIRST_DISPATCH", "0")
        from oompah.models import WorkflowDefinition
        wf = WorkflowDefinition(
            config={"agent": {"default_first_dispatch": True}},
            prompt_template="t",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.default_first_dispatch is False

    def test_env_var_overrides_yaml(self, monkeypatch):
        """Env var wins over YAML value."""
        monkeypatch.setenv("OOMPAH_DEFAULT_FIRST_DISPATCH", "1")
        from oompah.models import WorkflowDefinition
        wf = WorkflowDefinition(
            config={"agent": {"default_first_dispatch": False}},
            prompt_template="t",
        )
        cfg = ServiceConfig.from_workflow(wf)
        assert cfg.default_first_dispatch is True


# ---------------------------------------------------------------------------
# _is_first_dispatch / _has_explicit_handoff_label / _get_default_catch_all_profile
# ---------------------------------------------------------------------------

class TestHelperMethods:
    def test_is_first_dispatch_true_when_no_attempt_no_override(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        assert orch._is_first_dispatch(issue, attempt=None, override_profile=None) is True

    def test_is_first_dispatch_false_when_attempt_set(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        assert orch._is_first_dispatch(issue, attempt=1, override_profile=None) is False

    def test_is_first_dispatch_false_when_override_set(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        assert orch._is_first_dispatch(issue, attempt=None, override_profile="deep") is False

    def test_has_explicit_handoff_label_true(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(labels=["needs:test"])
        assert orch._has_explicit_handoff_label(issue) is True

    def test_has_explicit_handoff_label_false(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(labels=["bug", "priority:high"])
        assert orch._has_explicit_handoff_label(issue) is False

    def test_has_explicit_handoff_label_empty_labels(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(labels=[])
        assert orch._has_explicit_handoff_label(issue) is False

    def test_get_default_catch_all_profile_returns_named_default(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        result = orch._get_default_catch_all_profile()
        assert result is not None
        assert result.name == "default"

    def test_get_default_catch_all_profile_fallback_to_first_unconstrained(self, tmp_path):
        """If no profile is named 'default', returns first profile with no constraints."""
        orch = _make_orchestrator(tmp_path)
        # Replace profiles with ones that have no "default" name
        orch.config.agent_profiles = [
            AgentProfile(name="any", command="cli"),  # no constraints
            AgentProfile(name="specialized", command="cli", issue_types=["bug"]),
        ]
        result = orch._get_default_catch_all_profile()
        assert result is not None
        assert result.name == "any"

    def test_get_default_catch_all_profile_none_when_all_constrained(self, tmp_path):
        """Returns None when all profiles have constraints and none is named 'default'."""
        orch = _make_orchestrator(tmp_path)
        orch.config.agent_profiles = [
            AgentProfile(name="bugs", command="cli", issue_types=["bug"]),
            AgentProfile(name="tasks", command="cli", issue_types=["task"]),
        ]
        result = orch._get_default_catch_all_profile()
        assert result is None


# ---------------------------------------------------------------------------
# _match_agent_profile — verify profile matching works as expected
# ---------------------------------------------------------------------------

class TestMatchAgentProfile:
    def test_bug_matches_deep_profile(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(issue_type="bug")
        profile = orch._match_agent_profile(issue)
        assert profile is not None
        assert profile.name == "deep"

    def test_task_matches_standard_profile(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(issue_type="task")
        profile = orch._match_agent_profile(issue)
        assert profile is not None
        assert profile.name == "standard"

    def test_chore_matches_quick_profile(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(issue_type="chore", description="cleanup typo in docs")
        profile = orch._match_agent_profile(issue)
        assert profile is not None
        assert profile.name == "quick"

    def test_unknown_type_falls_back_to_default(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(issue_type="something_unknown")
        profile = orch._match_agent_profile(issue)
        assert profile is not None
        assert profile.name == "default"


# ---------------------------------------------------------------------------
# _next_profile_for_retry — escalation logic
# ---------------------------------------------------------------------------

class TestNextProfileForRetry:
    """Tests for the _next_profile_for_retry helper."""

    def test_flag_off_escalates_normally(self, tmp_path):
        """Without flag, escalates one step up the hierarchy."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=False)
        issue = _make_issue(issue_type="bug")
        entry = _make_running_entry(issue, profile_name="standard")
        escalated, name = orch._next_profile_for_retry(entry)
        assert escalated is not None
        assert escalated.name == "deep"
        assert name == "deep"

    def test_flag_on_with_natural_profile_jumps_to_it(self, tmp_path):
        """With flag=True and natural_profile_name set, jumps to natural profile."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug")
        # Was dispatched on "default" but natural profile is "deep"
        entry = _make_running_entry(
            issue, profile_name="default", natural_profile_name="deep"
        )
        escalated, name = orch._next_profile_for_retry(entry)
        assert escalated is not None
        assert escalated.name == "deep"
        assert name == "deep"

    def test_flag_on_without_natural_profile_escalates_normally(self, tmp_path):
        """With flag=True but no natural_profile_name, falls back to normal escalation."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug")
        # No natural_profile_name — this is already a normal retry
        entry = _make_running_entry(
            issue, profile_name="standard", natural_profile_name=None
        )
        escalated, name = orch._next_profile_for_retry(entry)
        assert escalated is not None
        assert escalated.name == "deep"
        assert name == "deep"

    def test_flag_on_already_at_top_profile(self, tmp_path):
        """When already on the highest profile, returns no escalation."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug")
        entry = _make_running_entry(
            issue, profile_name="deep", natural_profile_name=None
        )
        escalated, name = orch._next_profile_for_retry(entry)
        assert escalated is None
        assert name == ""

    def test_flag_on_natural_profile_not_found_falls_back(self, tmp_path):
        """If natural_profile_name no longer exists, falls back to normal escalation."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="task")
        # natural_profile_name references a non-existent profile
        entry = _make_running_entry(
            issue, profile_name="default", natural_profile_name="nonexistent_profile"
        )
        # Should fall through to normal escalation from "default"
        escalated, name = orch._next_profile_for_retry(entry)
        # "default" escalates to "quick" in the hierarchy
        assert escalated is not None
        assert escalated.name == "quick"

    def test_flag_off_no_escalation_when_at_top(self, tmp_path):
        """Without flag, no escalation when at top of hierarchy."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=False)
        issue = _make_issue(issue_type="bug")
        entry = _make_running_entry(issue, profile_name="deep")
        escalated, name = orch._next_profile_for_retry(entry)
        assert escalated is None
        assert name == ""


# ---------------------------------------------------------------------------
# _dispatch() — profile selection with default_first_dispatch
# ---------------------------------------------------------------------------

class TestDispatchWithDefaultFirstDispatch:
    """Tests for the dispatch path when default_first_dispatch is True."""

    def _make_orch_with_mocks(self, tmp_path, default_first_dispatch: bool = True):
        """Create an orchestrator with tracker/workspace mocked out."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=default_first_dispatch)
        # Mock everything needed to make _dispatch succeed without real infrastructure
        orch.tracker = MagicMock()
        orch.tracker.update_issue = MagicMock()
        orch.tracker.add_comment = MagicMock()
        orch.tracker.fetch_issue_states_by_ids = MagicMock(return_value=[])
        orch._tracker_for_issue = MagicMock(return_value=orch.tracker)
        orch._post_comment = MagicMock()
        orch._run_worker = AsyncMock()
        return orch

    def test_flag_off_bug_dispatches_deep_profile(self, tmp_path):
        """Without flag, bug issue dispatches on the deep profile immediately."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=False)
        issue = _make_issue(issue_type="bug")
        dispatched_profile = []

        async def capture(issue, attempt, profile):
            dispatched_profile.append(profile.name if profile else "none")

        orch._run_worker = capture

        asyncio.run(orch._dispatch(issue, attempt=None))

        # Worker should have been called with the "deep" profile
        assert "deep" in dispatched_profile

    def test_flag_on_bug_dispatches_default_profile_first(self, tmp_path):
        """With flag=True, bug issue dispatches on default profile first."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug")
        dispatched_profile = []

        async def capture(issue, attempt, profile):
            dispatched_profile.append(profile.name if profile else "none")

        orch._run_worker = capture

        asyncio.run(orch._dispatch(issue, attempt=None))

        # First dispatch should use the default (catch-all) profile
        assert "default" in dispatched_profile

    def test_flag_on_bug_stores_natural_profile_name(self, tmp_path):
        """With flag=True, running entry stores the natural profile name (deep for bug)."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug")

        # Run dispatch and let the worker complete immediately
        asyncio.run(orch._dispatch(issue, attempt=None))

        # natural_profile_name should be "deep" (what _match_agent_profile returns for bug)
        entry = orch.state.running.get(issue.id)
        assert entry is not None
        assert entry.natural_profile_name == "deep"
        assert entry.agent_profile_name == "default"

    def test_flag_on_task_stores_natural_profile_name(self, tmp_path):
        """With flag=True, running entry stores standard as natural profile for task."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="task")

        asyncio.run(orch._dispatch(issue, attempt=None))

        entry = orch.state.running.get(issue.id)
        assert entry is not None
        assert entry.natural_profile_name == "standard"
        assert entry.agent_profile_name == "default"

    def test_flag_on_override_profile_bypasses_default_first(self, tmp_path):
        """An explicit override_profile bypasses the default_first_dispatch logic."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug")
        dispatched_profile = []

        async def capture(issue, attempt, profile):
            dispatched_profile.append(profile.name if profile else "none")

        orch._run_worker = capture

        asyncio.run(orch._dispatch(issue, attempt=1, override_profile="standard"))

        # Should use the override, not default
        assert "standard" in dispatched_profile
        assert "default" not in dispatched_profile

    def test_flag_on_needs_label_bypasses_default_first(self, tmp_path):
        """needs:* label bypasses default_first_dispatch — user intent wins."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        # Issue has a needs:test label — explicit user routing
        issue = _make_issue(issue_type="bug", labels=["needs:test"])
        dispatched_profile = []

        async def capture(issue, attempt, profile):
            dispatched_profile.append(profile.name if profile else "none")

        orch._run_worker = capture

        asyncio.run(orch._dispatch(issue, attempt=None))

        # Should NOT use default profile when needs:* label is present
        assert "default" not in dispatched_profile
        # Should use the natural match for a bug (deep)
        assert "deep" in dispatched_profile

    def test_flag_on_retry_does_not_override_profile(self, tmp_path):
        """With flag=True, a retry (attempt > 0) uses the override_profile, not default."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug")
        dispatched_profile = []

        async def capture(issue, attempt, profile):
            dispatched_profile.append(profile.name if profile else "none")

        orch._run_worker = capture

        # Retry with explicit override
        asyncio.run(orch._dispatch(issue, attempt=1, override_profile="deep"))

        assert "deep" in dispatched_profile
        assert "default" not in dispatched_profile

    def test_flag_on_no_natural_match_uses_default(self, tmp_path):
        """When natural match IS default, no natural_profile_name is stored."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        # Issue type that matches the default (catch-all) profile
        issue = _make_issue(issue_type="unknown_type_xyz")

        asyncio.run(orch._dispatch(issue, attempt=None))

        entry = orch.state.running.get(issue.id)
        assert entry is not None
        # natural_profile_name should be None when natural match == default
        assert entry.natural_profile_name is None

    def test_flag_on_no_profiles_configured(self, tmp_path):
        """With flag=True but no profiles configured, dispatch doesn't crash."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        orch.config.agent_profiles = []  # No profiles
        issue = _make_issue(issue_type="bug")

        # Should not raise
        asyncio.run(orch._dispatch(issue, attempt=None))

    def test_flag_on_paused_skips_dispatch(self, tmp_path):
        """Paused state still prevents dispatch even with the flag on."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        orch._paused = True
        issue = _make_issue(issue_type="bug")
        issue_id = issue.id
        orch.state.claimed.add(issue_id)

        asyncio.run(orch._dispatch(issue, attempt=None))

        # Claim should be released, worker not started
        assert issue_id not in orch.state.claimed
        assert issue_id not in orch.state.running

    def test_flag_on_epic_keeps_natural_routing(self, tmp_path):
        """With flag=True, epics are NOT routed to default — they keep existing routing."""
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="epic")
        dispatched_profile = []

        async def capture(issue, attempt, profile):
            dispatched_profile.append(profile.name if profile else "none")

        orch._run_worker = capture

        asyncio.run(orch._dispatch(issue, attempt=None))

        # Epic should NOT use default profile — epics keep existing routing
        assert "default" not in dispatched_profile
        # Epic should route to "deep" (which includes epic in issue_types)
        assert "deep" in dispatched_profile

    def test_flag_on_merge_conflict_label_bypasses_default_first(self, tmp_path):
        """With flag=True, tasks carrying the 'merge-conflict' label bypass the
        cost optimization (oompah-zlz_2-2sd). The merge_conflict Focus has strict
        must_not_do rails (no squash, no blind ours/theirs, no force-push to main)
        that the default profile cannot enforce on its own — so we want the
        natural specialist on the FIRST dispatch, not after a bounce.
        """
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        # Bug-typed task with the merge-conflict label — like the trickle-dhr
        # task from the issue's live evidence.
        issue = _make_issue(
            issue_type="bug",
            labels=["merge-conflict"],
            description="Resolve merge conflicts on PR #16",
        )
        dispatched_profile = []

        async def capture(issue, attempt, profile):
            dispatched_profile.append(profile.name if profile else "none")

        orch._run_worker = capture

        asyncio.run(orch._dispatch(issue, attempt=None))

        # Carve-out: merge-conflict tasks must NOT be routed to default first.
        assert "default" not in dispatched_profile, (
            "merge-conflict task was dispatched on default profile — "
            "default_first_dispatch carve-out failed"
        )
        # They get the natural match (deep for type=bug in our test profile set).
        assert "deep" in dispatched_profile

    def test_flag_on_merge_conflict_label_does_not_store_natural_profile(self, tmp_path):
        """When the merge-conflict carve-out fires, natural_profile_name stays None
        because we dispatched on the natural profile directly — there is no
        escalation jump pending.
        """
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug", labels=["merge-conflict"])

        asyncio.run(orch._dispatch(issue, attempt=None))

        entry = orch.state.running.get(issue.id)
        assert entry is not None
        assert entry.agent_profile_name == "deep"
        # No escalation pending — we already dispatched on the natural profile
        assert entry.natural_profile_name is None

    def test_flag_on_merge_conflict_keyword_bypasses_default_first(self, tmp_path):
        """A task without the label but whose title/description matches the
        merge_conflict Focus keywords also bypasses the cost optimization.
        Detection mirrors the Focus's keyword set so users describing the work
        in plain English still get the safety rails.
        """
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        issue = _make_issue(
            issue_type="bug",
            labels=[],  # no label — only the keyword should trigger
            description="Need to rebase conflict on the feature branch.",
        )
        dispatched_profile = []

        async def capture(issue, attempt, profile):
            dispatched_profile.append(profile.name if profile else "none")

        orch._run_worker = capture

        asyncio.run(orch._dispatch(issue, attempt=None))

        assert "default" not in dispatched_profile
        assert "deep" in dispatched_profile

    def test_flag_on_ci_fix_label_bypasses_default_first(self, tmp_path):
        """With flag=True, tasks carrying the 'ci-fix' label bypass the
        cost optimization (oompah-zlz_2-0pr). The ci_fix Focus has strict
        must_not_do rails (no new branch, no new PR) that the default
        profile cannot enforce on its own — so we want the natural
        specialist on the FIRST dispatch, not after a bounce.
        """
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        # Bug-typed task with the ci-fix label — like the trickle-icl
        # task from the issue's live evidence.
        issue = _make_issue(
            issue_type="bug",
            labels=["ci-fix"],
            description="Fix CI failures on PR #23 (branch trickle-rl5)",
        )
        dispatched_profile = []

        async def capture(issue, attempt, profile):
            dispatched_profile.append(profile.name if profile else "none")

        orch._run_worker = capture

        asyncio.run(orch._dispatch(issue, attempt=None))

        assert "default" not in dispatched_profile, (
            "ci-fix task was dispatched on default profile — "
            "default_first_dispatch carve-out failed"
        )
        # They get the natural match (deep for type=bug in our test profile set).
        assert "deep" in dispatched_profile

    def test_flag_on_ci_fix_label_does_not_store_natural_profile(self, tmp_path):
        """Mirror of the merge-conflict test: when the ci-fix carve-out
        fires, natural_profile_name stays None because we dispatched on
        the natural profile directly — there is no escalation jump pending.
        """
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug", labels=["ci-fix"])

        asyncio.run(orch._dispatch(issue, attempt=None))

        entry = orch.state.running.get(issue.id)
        assert entry is not None
        assert entry.agent_profile_name == "deep"
        assert entry.natural_profile_name is None

    def test_flag_on_unrelated_bug_is_unaffected(self, tmp_path):
        """Sanity check: the carve-out is narrow. A normal bug without
        merge-conflict label/keywords still uses default_first_dispatch.
        """
        orch = self._make_orch_with_mocks(tmp_path, default_first_dispatch=True)
        issue = _make_issue(
            issue_type="bug",
            labels=["needs-investigation"],
            description="Login fails when password contains a unicode char.",
        )
        dispatched_profile = []

        async def capture(issue, attempt, profile):
            dispatched_profile.append(profile.name if profile else "none")

        orch._run_worker = capture

        asyncio.run(orch._dispatch(issue, attempt=None))

        # Normal bug still uses default first
        assert "default" in dispatched_profile
        assert "deep" not in dispatched_profile


# ---------------------------------------------------------------------------
# _is_safety_critical_issue helper — direct unit tests
# ---------------------------------------------------------------------------

class TestIsSafetyCriticalIssue:
    """Unit tests for _is_safety_critical_issue (oompah-zlz_2-2sd)."""

    def test_label_match(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(labels=["merge-conflict"])
        assert orch._is_safety_critical_issue(issue) is True

    def test_label_match_case_insensitive(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(labels=["Merge-Conflict"])
        assert orch._is_safety_critical_issue(issue) is True

    def test_keyword_match_in_title(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(description="")
        issue.title = "Resolve merge conflict on PR #16"
        assert orch._is_safety_critical_issue(issue) is True

    def test_keyword_match_in_description(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(description="Need to rebase conflict on this branch")
        assert orch._is_safety_critical_issue(issue) is True

    def test_no_match_for_unrelated_bug(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            issue_type="bug",
            description="Login fails for unicode passwords",
        )
        assert orch._is_safety_critical_issue(issue) is False

    def test_no_match_for_substring_only(self, tmp_path):
        """Whole-word matching: 'merging' or 'preconflict' should not match."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            description="Investigate preconflict detection in merging policy.",
        )
        assert orch._is_safety_critical_issue(issue) is False

    def test_no_match_for_empty_issue(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(description="")
        issue.title = ""
        issue.labels = []
        assert orch._is_safety_critical_issue(issue) is False

    def test_no_match_for_none_labels(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(description="")
        issue.title = ""
        issue.labels = None
        assert orch._is_safety_critical_issue(issue) is False

    def test_ci_fix_label_match(self, tmp_path):
        """oompah-zlz_2-0pr: ci-fix tasks should be safety-critical too."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(labels=["ci-fix"])
        assert orch._is_safety_critical_issue(issue) is True

    def test_ci_fix_label_match_case_insensitive(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(labels=["CI-Fix"])
        assert orch._is_safety_critical_issue(issue) is True

    def test_ci_fix_keyword_match_in_description(self, tmp_path):
        """A task describing CI failure work without the label still matches."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            description="The tier-c-windows-nvidia job is failing on PR #23.",
        )
        assert orch._is_safety_critical_issue(issue) is True

    def test_ci_fix_keyword_match_failing_tests(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            description="The PR has failing tests in matrix-verify on Windows.",
        )
        assert orch._is_safety_critical_issue(issue) is True


# ---------------------------------------------------------------------------
# get_snapshot() — exposes flag in state
# ---------------------------------------------------------------------------

class TestGetSnapshotExposeFlag:
    def test_snapshot_includes_default_first_dispatch_false(self, tmp_path):
        orch = _make_orchestrator(tmp_path, default_first_dispatch=False)
        snapshot = orch.get_snapshot()
        assert "config" in snapshot
        assert snapshot["config"]["default_first_dispatch"] is False

    def test_snapshot_includes_default_first_dispatch_true(self, tmp_path):
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        snapshot = orch.get_snapshot()
        assert "config" in snapshot
        assert snapshot["config"]["default_first_dispatch"] is True


# ---------------------------------------------------------------------------
# Escalation after default_first_dispatch: end-to-end retry profile selection
# ---------------------------------------------------------------------------

class TestEscalationAfterDefaultFirstDispatch:
    """Verify the retry escalation path with default_first_dispatch semantics."""

    def test_retry_after_default_jumps_to_natural_profile(self, tmp_path):
        """When first dispatch was on default, first retry escalates to natural profile."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug")
        # Simulate a running entry that was dispatched on "default" with natural="deep"
        entry = _make_running_entry(
            issue, profile_name="default", natural_profile_name="deep"
        )
        escalated, name = orch._next_profile_for_retry(entry)
        assert escalated is not None
        assert escalated.name == "deep"

    def test_subsequent_retry_continues_up_hierarchy(self, tmp_path):
        """After jumping to natural profile, subsequent retries continue up the hierarchy."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="task")
        # First retry already jumped to "standard" — simulate that state
        # (natural_profile_name is now None since we're past the first retry)
        entry_on_standard = _make_running_entry(
            issue, profile_name="standard", natural_profile_name=None
        )
        escalated, name = orch._next_profile_for_retry(entry_on_standard)
        assert escalated is not None
        assert escalated.name == "deep"

    def test_flag_off_starts_at_matched_profile_not_default(self, tmp_path):
        """Without flag, retry escalates from the naturally-matched profile."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=False)
        issue = _make_issue(issue_type="task")
        # Without the flag, first dispatch would have been on "standard"
        entry = _make_running_entry(
            issue, profile_name="standard", natural_profile_name=None
        )
        escalated, name = orch._next_profile_for_retry(entry)
        assert escalated is not None
        assert escalated.name == "deep"

    def test_bug_full_escalation_path_with_flag(self, tmp_path):
        """Full escalation path for a bug with default_first_dispatch=True:
        default → (jump) deep → None (already at top).
        """
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="bug")

        # Step 1: First dispatch on "default" (natural="deep")
        entry_step1 = _make_running_entry(
            issue, profile_name="default", natural_profile_name="deep"
        )
        step1_escalated, step1_name = orch._next_profile_for_retry(entry_step1)
        assert step1_escalated is not None
        assert step1_escalated.name == "deep"

        # Step 2: Second dispatch on "deep" (no natural_profile_name)
        entry_step2 = _make_running_entry(
            issue, profile_name="deep", natural_profile_name=None
        )
        step2_escalated, step2_name = orch._next_profile_for_retry(entry_step2)
        assert step2_escalated is None  # already at the top

    def test_task_full_escalation_path_with_flag(self, tmp_path):
        """Full escalation path for a task with default_first_dispatch=True:
        default → (jump) standard → deep → None.
        """
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="task")

        # Step 1: First dispatch on "default" (natural="standard")
        entry_step1 = _make_running_entry(
            issue, profile_name="default", natural_profile_name="standard"
        )
        step1_escalated, _ = orch._next_profile_for_retry(entry_step1)
        assert step1_escalated is not None
        assert step1_escalated.name == "standard"

        # Step 2: On "standard", escalates to "deep"
        entry_step2 = _make_running_entry(
            issue, profile_name="standard", natural_profile_name=None
        )
        step2_escalated, _ = orch._next_profile_for_retry(entry_step2)
        assert step2_escalated is not None
        assert step2_escalated.name == "deep"

        # Step 3: Already at top
        entry_step3 = _make_running_entry(
            issue, profile_name="deep", natural_profile_name=None
        )
        step3_escalated, _ = orch._next_profile_for_retry(entry_step3)
        assert step3_escalated is None


# ---------------------------------------------------------------------------
# needs:<focus> label does not affect profile selection
# ---------------------------------------------------------------------------

class TestNeedsLabelDoesNotAffectProfile:
    """needs:* labels bypass default_first_dispatch but don't change profile matching."""

    def test_needs_label_does_not_store_natural_profile(self, tmp_path):
        """When needs:* label bypasses the flag, natural_profile_name is None."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        # Mock the worker so dispatch doesn't actually run
        orch.tracker = MagicMock()
        orch.tracker.update_issue = MagicMock()
        orch.tracker.add_comment = MagicMock()
        orch.tracker.fetch_issue_states_by_ids = MagicMock(return_value=[])
        orch._tracker_for_issue = MagicMock(return_value=orch.tracker)
        orch._post_comment = MagicMock()
        orch._run_worker = AsyncMock()

        # Issue with needs:test label
        issue = _make_issue(issue_type="bug", labels=["needs:test"])
        asyncio.run(orch._dispatch(issue, attempt=None))

        entry = orch.state.running.get(issue.id)
        assert entry is not None
        # No natural_profile_name since we didn't use the default_first_dispatch path
        assert entry.natural_profile_name is None

    def test_multiple_needs_labels_still_bypasses(self, tmp_path):
        """Multiple needs:* labels still bypass the flag."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        issue = _make_issue(labels=["needs:frontend", "priority:high"])
        assert orch._has_explicit_handoff_label(issue) is True

    def test_non_needs_labels_dont_bypass(self, tmp_path):
        """Labels not starting with 'needs:' don't bypass the flag."""
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        issue = _make_issue(labels=["bug", "priority:high", "ci-fix"])
        assert orch._has_explicit_handoff_label(issue) is False


# ---------------------------------------------------------------------------
# Safety-critical ACP routing (oompah-zlz_2-lfy)
# ---------------------------------------------------------------------------

def _make_profiles_with_acp_default() -> list[AgentProfile]:
    """Profile set where ONLY the 'default' profile has mode='acp'.

    Mirrors the trickle WORKFLOW.md setup that produced the live
    incident on 2026-05-07: the safety-critical carve-out skipped
    default_first_dispatch and routed trickle-6zi through the
    api-mode 'standard' profile, which then hit token-rate-limit
    cascades. With the lfy fix, carved-out tasks should land on
    the ACP-enabled 'default' profile instead.
    """
    return [
        AgentProfile(
            name="quick",
            command="cli",
            model_role="fast",
            issue_types=["chore"],
            keywords=["typo", "cleanup"],
            max_priority=4,
        ),
        AgentProfile(
            name="standard",
            command="cli",
            model_role="standard",
            issue_types=["task", "feature"],
        ),
        AgentProfile(
            name="deep",
            command="cli",
            model_role="deep",
            issue_types=["bug", "epic"],
            keywords=["security", "architecture", "refactor", "critical"],
        ),
        AgentProfile(
            name="default",
            command="cli",
            model_role="fast",
            mode="acp",
        ),
    ]


def _make_profiles_all_acp() -> list[AgentProfile]:
    """Profile set where every profile has mode='acp'.

    Used to verify the carve-out is a no-op when the natural-resolved
    profile already has mode=acp — the issue's "carve-out + ACP
    natural → unchanged" regression case.
    """
    return [
        AgentProfile(
            name="default",
            command="cli",
            model_role="fast",
            mode="acp",
        ),
        AgentProfile(
            name="standard",
            command="cli",
            model_role="standard",
            issue_types=["task", "feature"],
            mode="acp",
        ),
        AgentProfile(
            name="deep",
            command="cli",
            model_role="deep",
            issue_types=["bug", "epic"],
            keywords=["security", "critical"],
            mode="acp",
        ),
    ]


def _make_profiles_no_acp() -> list[AgentProfile]:
    """Profile set with NO ACP profile at all.

    The carve-out must fall through unchanged: no swap, no log line,
    natural profile dispatches as before.
    """
    return [
        AgentProfile(name="default", command="cli", model_role="fast"),
        AgentProfile(
            name="standard", command="cli", model_role="standard",
            issue_types=["task", "feature"],
        ),
        AgentProfile(
            name="deep", command="cli", model_role="deep",
            issue_types=["bug", "epic"], keywords=["critical"],
        ),
    ]


class TestFindAcpProfile:
    """Unit tests for the _find_acp_profile() helper."""

    def test_returns_default_when_default_is_acp(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch.config.agent_profiles = _make_profiles_with_acp_default()
        result = orch._find_acp_profile()
        assert result is not None
        assert result.name == "default"

    def test_returns_first_acp_when_default_is_not_acp(self, tmp_path):
        """When 'default' isn't ACP but another profile is, return that one."""
        orch = _make_orchestrator(tmp_path)
        orch.config.agent_profiles = [
            AgentProfile(name="default", command="cli"),
            AgentProfile(name="alt", command="cli", mode="acp"),
            AgentProfile(name="other", command="cli", mode="acp"),
        ]
        result = orch._find_acp_profile()
        assert result is not None
        assert result.name == "alt"  # first ACP profile in declaration order

    def test_returns_none_when_no_acp_profile(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch.config.agent_profiles = _make_profiles_no_acp()
        result = orch._find_acp_profile()
        assert result is None

    def test_returns_none_when_no_profiles(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch.config.agent_profiles = []
        result = orch._find_acp_profile()
        assert result is None

    def test_profile_is_acp_helper(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert Orchestrator._profile_is_acp(
            AgentProfile(name="x", command="c", mode="acp")
        ) is True
        assert Orchestrator._profile_is_acp(
            AgentProfile(name="x", command="c", mode="api")
        ) is False
        # Default value 'auto' is not ACP
        assert Orchestrator._profile_is_acp(
            AgentProfile(name="x", command="c")
        ) is False
        assert Orchestrator._profile_is_acp(None) is False
        # Case insensitive (mode is normalized at config-load, but be
        # defensive).
        assert Orchestrator._profile_is_acp(
            AgentProfile(name="x", command="c", mode="ACP")
        ) is True


class TestSafetyCriticalAcpRouting:
    """Tests for the safety-critical ACP-routing carve-out (oompah-zlz_2-lfy).

    Acceptance criteria:
    - merge-conflict / ci-fix task with non-ACP natural → ACP profile
    - merge-conflict / ci-fix task with ACP natural → unchanged
    - non-carved-out task → default_first_dispatch behavior preserved
    - Telemetry: log line includes both ACP profile name AND natural profile name
    """

    def _make_orch_with_mocks(
        self, tmp_path, default_first_dispatch: bool = True,
        profiles: list[AgentProfile] | None = None,
    ):
        orch = _make_orchestrator(
            tmp_path, default_first_dispatch=default_first_dispatch
        )
        if profiles is not None:
            orch.config.agent_profiles = profiles
        orch.tracker = MagicMock()
        orch.tracker.update_issue = MagicMock()
        orch.tracker.add_comment = MagicMock()
        orch.tracker.fetch_issue_states_by_ids = MagicMock(return_value=[])
        orch._tracker_for_issue = MagicMock(return_value=orch.tracker)
        orch._post_comment = MagicMock()
        orch._run_worker = AsyncMock()
        return orch

    def test_carve_out_with_non_acp_natural_swaps_to_acp(self, tmp_path):
        """Live evidence case: trickle-6zi with label=ci-fix on a profile
        set where only 'default' has mode=acp. Natural match for type=bug
        is 'deep' (api mode); the lfy fix swaps to 'default' (acp).
        """
        orch = self._make_orch_with_mocks(
            tmp_path, profiles=_make_profiles_with_acp_default(),
        )
        issue = _make_issue(
            issue_type="bug",
            labels=["ci-fix"],
            description="Fix CI failures on PR #23",
        )
        dispatched = []

        async def capture(issue, attempt, profile):
            dispatched.append(profile.name if profile else None)

        orch._run_worker = capture
        asyncio.run(orch._dispatch(issue, attempt=None))

        assert "default" in dispatched, (
            "safety-critical task with non-ACP natural profile was NOT "
            "routed to the ACP profile — lfy fix didn't fire"
        )
        assert "deep" not in dispatched

        # natural_profile_name preserved for telemetry / first-retry escalation
        entry = orch.state.running.get(issue.id)
        assert entry is not None
        assert entry.agent_profile_name == "default"
        assert entry.natural_profile_name == "deep"

    def test_carve_out_with_merge_conflict_label(self, tmp_path):
        """Same routing for the other carve-out trigger."""
        orch = self._make_orch_with_mocks(
            tmp_path, profiles=_make_profiles_with_acp_default(),
        )
        issue = _make_issue(
            issue_type="bug",
            labels=["merge-conflict"],
            description="Resolve merge conflicts on PR #16",
        )
        dispatched = []

        async def capture(issue, attempt, profile):
            dispatched.append(profile.name if profile else None)

        orch._run_worker = capture
        asyncio.run(orch._dispatch(issue, attempt=None))

        assert "default" in dispatched
        entry = orch.state.running.get(issue.id)
        assert entry.natural_profile_name == "deep"

    def test_carve_out_with_acp_natural_unchanged(self, tmp_path):
        """Regression: when the natural-resolved profile is already ACP
        (e.g. all profiles have mode=acp), the carve-out must NOT swap
        to a different ACP profile. Otherwise we'd silently re-route
        every safety-critical dispatch to whichever ACP profile sits
        first — defeating per-issue model selection.
        """
        orch = self._make_orch_with_mocks(
            tmp_path, profiles=_make_profiles_all_acp(),
        )
        # Natural match for type=bug is 'deep' (which already has mode=acp).
        issue = _make_issue(
            issue_type="bug",
            labels=["ci-fix"],
            description="Fix CI on PR #99",
        )
        dispatched = []

        async def capture(issue, attempt, profile):
            dispatched.append(profile.name if profile else None)

        orch._run_worker = capture
        asyncio.run(orch._dispatch(issue, attempt=None))

        # Should dispatch on the natural ACP profile, NOT swap to 'default'
        assert "deep" in dispatched
        assert "default" not in dispatched

        entry = orch.state.running.get(issue.id)
        assert entry is not None
        assert entry.agent_profile_name == "deep"
        # No natural_profile_name pending — we already dispatched on the
        # natural pick, no escalation jump is queued.
        assert entry.natural_profile_name is None

    def test_carve_out_with_no_acp_profile_falls_through(self, tmp_path):
        """When no ACP profile is configured, the carve-out is a no-op:
        the dispatch proceeds on the natural-resolved (non-ACP) profile.
        Legacy / api-only deployments must continue to work.
        """
        orch = self._make_orch_with_mocks(
            tmp_path, profiles=_make_profiles_no_acp(),
        )
        issue = _make_issue(
            issue_type="bug",
            labels=["ci-fix"],
            description="Fix CI on PR #1",
        )
        dispatched = []

        async def capture(issue, attempt, profile):
            dispatched.append(profile.name if profile else None)

        orch._run_worker = capture
        asyncio.run(orch._dispatch(issue, attempt=None))

        # Dispatches on the natural match for type=bug → 'deep'
        assert "deep" in dispatched
        entry = orch.state.running.get(issue.id)
        assert entry.agent_profile_name == "deep"
        # No swap happened, so natural_profile_name stays None
        assert entry.natural_profile_name is None

    def test_non_carved_out_task_is_unaffected(self, tmp_path):
        """A regular bug (no merge-conflict / ci-fix label) still uses
        default_first_dispatch normally — the lfy fix only kicks in
        for safety-critical tasks.
        """
        orch = self._make_orch_with_mocks(
            tmp_path, profiles=_make_profiles_with_acp_default(),
        )
        issue = _make_issue(
            issue_type="bug",
            description="Login fails for unicode passwords",
        )
        dispatched = []

        async def capture(issue, attempt, profile):
            dispatched.append(profile.name if profile else None)

        orch._run_worker = capture
        asyncio.run(orch._dispatch(issue, attempt=None))

        # default_first_dispatch picks 'default' (the catch-all) and
        # records 'deep' as the natural — same as before lfy.
        assert "default" in dispatched
        entry = orch.state.running.get(issue.id)
        assert entry.agent_profile_name == "default"
        assert entry.natural_profile_name == "deep"

    def test_carve_out_logs_both_profile_names(self, tmp_path, caplog):
        """Telemetry: the swap log line must include both the ACP profile
        name AND the natural profile name so escalation history is
        auditable. Mirrors the existing default_first_dispatch log shape.
        """
        import logging
        orch = self._make_orch_with_mocks(
            tmp_path, profiles=_make_profiles_with_acp_default(),
        )
        issue = _make_issue(
            issue_type="bug",
            labels=["ci-fix"],
            description="Fix CI on PR #7",
        )

        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            asyncio.run(orch._dispatch(issue, attempt=None))

        msgs = [r.getMessage() for r in caplog.records]
        swap_lines = [m for m in msgs if "safety_critical_acp_routing" in m]
        assert swap_lines, (
            "expected a 'safety_critical_acp_routing' INFO log when the "
            "carve-out swap fires"
        )
        line = swap_lines[0]
        assert "default" in line, "ACP profile name not in log"
        assert "deep" in line, "natural profile name not in log"
        assert "ci-fix" in line, "labels not in log (telemetry)"

    def test_carve_out_skipped_when_default_first_dispatch_off(self, tmp_path):
        """When default_first_dispatch is OFF entirely, the lfy fix
        should still apply on first dispatch — the carve-out logic is
        about safety-critical tasks, not the default_first_dispatch
        flag. Verify this regression: a flag=False operator should
        still get ACP routing for ci-fix / merge-conflict tasks.
        """
        orch = self._make_orch_with_mocks(
            tmp_path,
            default_first_dispatch=False,
            profiles=_make_profiles_with_acp_default(),
        )
        issue = _make_issue(
            issue_type="bug",
            labels=["ci-fix"],
            description="Fix CI on PR #11",
        )
        dispatched = []

        async def capture(issue, attempt, profile):
            dispatched.append(profile.name if profile else None)

        orch._run_worker = capture
        asyncio.run(orch._dispatch(issue, attempt=None))

        # Even with flag=False, safety-critical tasks route to ACP
        assert "default" in dispatched
        entry = orch.state.running.get(issue.id)
        assert entry.agent_profile_name == "default"
        assert entry.natural_profile_name == "deep"

    def test_retry_does_not_swap_to_acp(self, tmp_path):
        """A retry (attempt > 0 OR override_profile set) must NOT trigger
        the safety-critical ACP swap. The escalation hierarchy decides
        what to dispatch on retry, and we don't want to silently divert
        the operator's escalation choice to the ACP profile.
        """
        orch = self._make_orch_with_mocks(
            tmp_path, profiles=_make_profiles_with_acp_default(),
        )
        issue = _make_issue(
            issue_type="bug",
            labels=["ci-fix"],
            description="Fix CI on PR #11",
        )
        dispatched = []

        async def capture(issue, attempt, profile):
            dispatched.append(profile.name if profile else None)

        orch._run_worker = capture
        # Simulate a retry: override_profile=deep, attempt=1
        asyncio.run(orch._dispatch(issue, attempt=1, override_profile="deep"))

        # Should use the explicit override, not swap to 'default'
        assert "deep" in dispatched
        assert "default" not in dispatched

    def test_explicit_handoff_label_skips_swap(self, tmp_path):
        """needs:* label means explicit user routing — don't override it
        with the ACP swap. The ACP carve-out only fires when no explicit
        handoff is set.
        """
        orch = self._make_orch_with_mocks(
            tmp_path, profiles=_make_profiles_with_acp_default(),
        )
        # needs:test label + ci-fix label
        issue = _make_issue(
            issue_type="bug",
            labels=["ci-fix", "needs:test"],
            description="CI failures",
        )
        dispatched = []

        async def capture(issue, attempt, profile):
            dispatched.append(profile.name if profile else None)

        orch._run_worker = capture
        asyncio.run(orch._dispatch(issue, attempt=None))

        # needs:* wins → the natural deep profile, NOT the default ACP swap
        assert "deep" in dispatched
        assert "default" not in dispatched

    def test_would_dispatch_via_acp_agrees_with_dispatch(self, tmp_path):
        """The budget gate's ``_would_dispatch_via_acp`` must agree with
        what ``_dispatch`` will actually choose. Otherwise an over-
        budget orchestrator would reject a dispatch that would in fact
        go through the subscription-billed ACP path.
        """
        orch = _make_orchestrator(tmp_path, default_first_dispatch=True)
        orch.config.agent_profiles = _make_profiles_with_acp_default()

        # Safety-critical task whose natural profile (deep) is non-ACP.
        # Dispatch will swap to 'default' (mode=acp), so the gate must
        # report True.
        issue = _make_issue(
            issue_type="bug",
            labels=["ci-fix"],
            description="Fix CI on PR #2",
        )
        assert orch._would_dispatch_via_acp(issue) is True

        # Non-safety-critical: no swap → natural is deep (api) → False
        regular = _make_issue(
            issue_type="bug",
            description="Login fails for unicode passwords",
        )
        assert orch._would_dispatch_via_acp(regular) is False

    def test_would_dispatch_via_acp_no_acp_profile(self, tmp_path):
        """Without any ACP profile, even safety-critical tasks return
        False — there's no ACP path to bypass the budget through.
        """
        orch = _make_orchestrator(tmp_path)
        orch.config.agent_profiles = _make_profiles_no_acp()
        issue = _make_issue(
            issue_type="bug",
            labels=["ci-fix"],
            description="Fix CI",
        )
        assert orch._would_dispatch_via_acp(issue) is False
