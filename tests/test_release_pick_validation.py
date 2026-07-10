"""Tests for release-pick target branch validation (TASK-454.3).

Covers:
  - validate_release_pick_target: per-issue target_branch checks
  - validate_backports_list: oompah.backports list validation
  - _is_release_pick_issue: backport-task detection heuristic
  - Orchestrator._should_dispatch integration: invalid target_branch rejected
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from oompah.models import Issue, Project
from oompah.release_pick_validation import (
    ALLOW_SOURCE_LABEL,
    ReleaseBranchValidationResult,
    _is_release_pick_issue,
    _label_set,
    validate_backports_list,
    validate_release_pick_target,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project(
    name: str = "myrepo",
    branches: list[str] | None = None,
    default_branch: str = "main",
) -> Project:
    """Build a minimal Project for testing."""
    b = branches if branches is not None else ["main", "release/*"]
    return Project(
        id="proj-1",
        name=name,
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repo",
        branches=b,
        default_branch=default_branch,
    )


def _issue(
    identifier: str = "TASK-1",
    target_branch: str | None = None,
    labels: list[str] | None = None,
    project_id: str = "proj-1",
    parent_id: str | None = None,
    state: str = "open",
) -> Issue:
    """Build a minimal Issue for testing."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Test issue",
        description="A test issue",
        state=state,
        target_branch=target_branch,
        labels=labels or [],
        project_id=project_id,
        parent_id=parent_id,
    )


# ---------------------------------------------------------------------------
# validate_release_pick_target — no target set
# ---------------------------------------------------------------------------


def test_no_target_branch_is_valid():
    """Issues without a target_branch always pass — not a release-pick context."""
    issue = _issue(target_branch=None)
    proj = _project()
    result = validate_release_pick_target(issue, proj)
    assert result.valid is True
    assert result.target_branch is None
    assert result.error == ""
    assert result.reason == ""


def test_empty_string_target_branch_is_valid():
    """Whitespace-only target_branch is treated the same as None."""
    issue = _issue(target_branch="   ")
    proj = _project()
    result = validate_release_pick_target(issue, proj)
    assert result.valid is True
    assert result.target_branch is None


# ---------------------------------------------------------------------------
# validate_release_pick_target — untracked branch patterns
# ---------------------------------------------------------------------------


def test_target_matches_exact_pattern():
    """A branch that exactly matches a tracked pattern passes."""
    issue = _issue(target_branch="release/1.0")
    proj = _project(branches=["main", "release/*"])
    result = validate_release_pick_target(issue, proj)
    assert result.valid is True
    assert result.target_branch == "release/1.0"


def test_target_matches_wildcard_pattern():
    """A branch matching a glob wildcard passes."""
    issue = _issue(target_branch="hotfix/security-patch")
    proj = _project(branches=["main", "release/*", "hotfix/*"])
    result = validate_release_pick_target(issue, proj)
    assert result.valid is True


def test_target_does_not_match_any_pattern():
    """A branch not matching any configured pattern is rejected."""
    issue = _issue(target_branch="feature/my-work")
    proj = _project(branches=["main", "release/*"])
    result = validate_release_pick_target(issue, proj)
    assert result.valid is False
    assert result.reason == "untracked_branch"
    assert "feature/my-work" in result.error
    assert "release/*" in result.error
    assert "main" in result.error
    assert "Tracked patterns" in result.error


def test_untracked_error_is_actionable():
    """The error message tells the operator exactly how to fix the problem."""
    issue = _issue(target_branch="unknown/branch")
    proj = _project(branches=["main", "release/*"], name="test-repo")
    result = validate_release_pick_target(issue, proj)
    assert "test-repo" in result.error
    # Should mention fixing the branch list or the frontmatter field
    assert "oompah.target_branch" in result.error or "branches" in result.error


def test_untracked_branch_target_is_preserved():
    """ReleaseBranchValidationResult.target_branch holds the original name."""
    issue = _issue(target_branch="invalid/branch")
    proj = _project()
    result = validate_release_pick_target(issue, proj)
    assert result.target_branch == "invalid/branch"


def test_generated_epic_target_branch_bypasses_branch_patterns():
    """Oompah-owned epic branches do not need to be listed in project.branches."""
    issue = _issue(
        identifier="COROOT-21",
        target_branch="epic-COROOT-5",
        parent_id="COROOT-5",
        labels=["ci-fix"],
    )
    proj = _project(branches=["main"], default_branch="main")
    result = validate_release_pick_target(issue, proj)
    assert result.valid is True
    assert result.target_branch == "epic-COROOT-5"
    assert result.reason == ""


def test_epic_like_target_branch_must_match_parent_id():
    """Only the generated branch for this issue's parent bypasses validation."""
    issue = _issue(
        identifier="COROOT-21",
        target_branch="epic-COROOT-5",
        parent_id="COROOT-6",
        labels=["ci-fix"],
    )
    proj = _project(branches=["main"], default_branch="main")
    result = validate_release_pick_target(issue, proj)
    assert result.valid is False
    assert result.reason == "untracked_branch"


def test_generated_epic_target_branch_uses_sanitized_parent_id():
    """The bypass mirrors ProjectStore.epic_branch_name sanitization."""
    issue = _issue(
        identifier="TASK-2",
        target_branch="epic-parent_2",
        parent_id="parent/2",
    )
    proj = _project(branches=["main"], default_branch="main")
    result = validate_release_pick_target(issue, proj)
    assert result.valid is True
    assert result.target_branch == "epic-parent_2"


# ---------------------------------------------------------------------------
# validate_release_pick_target — source-only branch protection
# ---------------------------------------------------------------------------


def test_normal_issue_targeting_default_branch_is_valid():
    """A non-backport issue may target the default branch (normal task scenario)."""
    issue = _issue(target_branch="main", labels=[])
    proj = _project(branches=["main", "release/*"], default_branch="main")
    result = validate_release_pick_target(issue, proj)
    assert result.valid is True


def test_backport_issue_targeting_default_branch_is_rejected():
    """A backport-labeled issue must not target the source branch."""
    issue = _issue(target_branch="main", labels=["backport"])
    proj = _project(branches=["main", "release/*"], default_branch="main")
    result = validate_release_pick_target(issue, proj)
    assert result.valid is False
    assert result.reason == "source_only_branch"
    assert "main" in result.error
    assert ALLOW_SOURCE_LABEL in result.error


def test_backport_prefixed_label_triggers_source_protection():
    """Any label starting with 'backport:' marks it as a release-pick."""
    issue = _issue(target_branch="main", labels=["backport:1.0"])
    proj = _project(default_branch="main")
    result = validate_release_pick_target(issue, proj)
    assert result.valid is False
    assert result.reason == "source_only_branch"


def test_allow_source_label_bypasses_protection():
    """backport:allow-source opts the issue out of source-only protection."""
    issue = _issue(
        target_branch="main",
        labels=["backport", ALLOW_SOURCE_LABEL],
    )
    proj = _project(default_branch="main")
    result = validate_release_pick_target(issue, proj)
    assert result.valid is True


def test_allow_source_label_with_backport_prefix_label():
    """allow-source label bypasses protection even with backport:* labels."""
    issue = _issue(
        target_branch="main",
        labels=["backport:allow-source", "backport:v1"],
    )
    proj = _project(default_branch="main")
    result = validate_release_pick_target(issue, proj)
    assert result.valid is True


def test_backport_issue_targeting_release_branch_is_valid():
    """A backport-labeled issue correctly targeting a release branch passes."""
    issue = _issue(target_branch="release/1.0", labels=["backport"])
    proj = _project(branches=["main", "release/*"], default_branch="main")
    result = validate_release_pick_target(issue, proj)
    assert result.valid is True


def test_source_only_check_skipped_when_default_branch_unset():
    """When project.default_branch is empty, source-only check is skipped."""
    proj = _project(default_branch="")
    # Manually clear it to simulate empty
    proj.default_branch = ""
    issue = _issue(target_branch="main", labels=["backport"])
    result = validate_release_pick_target(issue, proj)
    # "main" must still pass the pattern check
    proj2 = _project(branches=["main"], default_branch="")
    proj2.default_branch = ""
    result2 = validate_release_pick_target(issue, proj2)
    assert result2.valid is True  # no source-only protection without default_branch


# ---------------------------------------------------------------------------
# validate_release_pick_target — tracker metadata path
# ---------------------------------------------------------------------------


def test_tracker_backport_of_metadata_triggers_protection():
    """oompah.backport_of in tracker metadata marks the issue as a backport."""
    issue = _issue(target_branch="main", labels=[])  # no label
    proj = _project(default_branch="main")
    tracker = MagicMock()
    tracker.get_metadata.return_value = {"oompah.backport_of": "TASK-100"}
    result = validate_release_pick_target(issue, proj, tracker=tracker)
    assert result.valid is False
    assert result.reason == "source_only_branch"


def test_tracker_backports_metadata_triggers_protection():
    """oompah.backports in tracker metadata also marks it as a backport source."""
    issue = _issue(target_branch="main", labels=[])
    proj = _project(default_branch="main")
    tracker = MagicMock()
    tracker.get_metadata.return_value = {"oompah.backports": ["release/1.0"]}
    result = validate_release_pick_target(issue, proj, tracker=tracker)
    assert result.valid is False
    assert result.reason == "source_only_branch"


def test_tracker_no_backport_metadata_skips_protection():
    """Without backport metadata, the issue is not treated as a release-pick."""
    issue = _issue(target_branch="main", labels=[])
    proj = _project(default_branch="main")
    tracker = MagicMock()
    tracker.get_metadata.return_value = {}  # no backport fields
    result = validate_release_pick_target(issue, proj, tracker=tracker)
    assert result.valid is True


def test_tracker_error_is_tolerated():
    """When tracker.get_metadata raises, validation fails open (does not crash)."""
    issue = _issue(target_branch="main", labels=["backport"])
    proj = _project(default_branch="main")
    tracker = MagicMock()
    tracker.get_metadata.side_effect = RuntimeError("tracker exploded")
    # Should still detect via labels and reject
    result = validate_release_pick_target(issue, proj, tracker=tracker)
    assert result.valid is False
    assert result.reason == "source_only_branch"


# ---------------------------------------------------------------------------
# validate_backports_list
# ---------------------------------------------------------------------------


def test_backports_list_empty_returns_empty():
    """None and empty list both return []."""
    proj = _project()
    assert validate_backports_list(None, proj) == []
    assert validate_backports_list([], proj) == []


def test_backports_list_valid_entries():
    """All entries matching project patterns return valid results."""
    proj = _project(branches=["main", "release/*"], default_branch="main")
    results = validate_backports_list(["release/1.0", "release/2.0"], proj)
    assert len(results) == 2
    assert all(r.valid for r in results)
    assert results[0].target_branch == "release/1.0"
    assert results[1].target_branch == "release/2.0"


def test_backports_list_untracked_entry():
    """An untracked branch in the list produces valid=False."""
    proj = _project(branches=["main", "release/*"])
    results = validate_backports_list(["release/1.0", "unknown/branch"], proj)
    assert results[0].valid is True
    assert results[1].valid is False
    assert results[1].reason == "untracked_branch"
    assert "unknown/branch" in results[1].error


def test_backports_list_source_branch_rejected():
    """The default branch in a backports list is always rejected."""
    proj = _project(branches=["main", "release/*"], default_branch="main")
    results = validate_backports_list(["main"], proj)
    assert len(results) == 1
    assert results[0].valid is False
    assert results[0].reason == "source_only_branch"
    assert "main" in results[0].error


def test_backports_list_mixed_valid_and_invalid():
    """Mixed list returns one result per entry with correct validity."""
    proj = _project(branches=["main", "release/*"], default_branch="main")
    results = validate_backports_list(
        ["release/1.0", "main", "feature/nope"], proj
    )
    assert len(results) == 3
    assert results[0].valid is True
    assert results[1].valid is False
    assert results[1].reason == "source_only_branch"
    assert results[2].valid is False
    assert results[2].reason == "untracked_branch"


def test_backports_list_scalar_string():
    """A bare string (not a list) is treated as a single-entry list."""
    proj = _project(branches=["main", "release/*"])
    results = validate_backports_list("release/1.0", proj)
    assert len(results) == 1
    assert results[0].valid is True
    assert results[0].target_branch == "release/1.0"


def test_backports_list_scalar_string_invalid():
    """A bare untracked string produces a single invalid result."""
    proj = _project(branches=["main", "release/*"])
    results = validate_backports_list("feature/oops", proj)
    assert len(results) == 1
    assert results[0].valid is False
    assert results[0].reason == "untracked_branch"


def test_backports_list_skips_empty_entries():
    """Blank / whitespace entries in the list are silently skipped."""
    proj = _project(branches=["main", "release/*"])
    results = validate_backports_list(["release/1.0", "", "  "], proj)
    assert len(results) == 1
    assert results[0].valid is True


def test_backports_list_error_messages_name_project():
    """Error messages include the project name for context."""
    proj = _project(branches=["main", "release/*"], name="my-project")
    results = validate_backports_list(["nope/branch"], proj)
    assert "my-project" in results[0].error


# ---------------------------------------------------------------------------
# _is_release_pick_issue
# ---------------------------------------------------------------------------


def test_is_release_pick_by_backport_label():
    """Exact 'backport' label → release pick."""
    issue = _issue(labels=["backport"])
    assert _is_release_pick_issue(issue, None) is True


def test_is_release_pick_by_backport_prefix_label():
    """Any label starting with 'backport:' → release pick."""
    issue = _issue(labels=["backport:1.0", "other"])
    assert _is_release_pick_issue(issue, None) is True


def test_is_not_release_pick_without_labels_or_tracker():
    """No labels and no tracker → not a release pick."""
    issue = _issue(labels=[])
    assert _is_release_pick_issue(issue, None) is False


def test_is_release_pick_via_tracker_backport_of():
    """oompah.backport_of metadata (via tracker) → release pick."""
    issue = _issue(labels=[])
    tracker = MagicMock()
    tracker.get_metadata.return_value = {"oompah.backport_of": "TASK-50"}
    assert _is_release_pick_issue(issue, tracker) is True


def test_is_release_pick_via_tracker_backports():
    """oompah.backports metadata (via tracker) → release pick."""
    issue = _issue(labels=[])
    tracker = MagicMock()
    tracker.get_metadata.return_value = {"oompah.backports": ["release/1.0"]}
    assert _is_release_pick_issue(issue, tracker) is True


def test_is_not_release_pick_via_empty_tracker_metadata():
    """Empty tracker metadata and no labels → not a release pick."""
    issue = _issue(labels=[])
    tracker = MagicMock()
    tracker.get_metadata.return_value = {}
    assert _is_release_pick_issue(issue, tracker) is False


# ---------------------------------------------------------------------------
# _label_set helper
# ---------------------------------------------------------------------------


def test_label_set_normalises_case():
    """Labels are lowercased and stripped."""
    issue = _issue(labels=["Backport", " RELEASE "])
    assert "backport" in _label_set(issue)
    assert "release" in _label_set(issue)


def test_label_set_none_labels():
    """Issue with no labels returns an empty frozenset."""
    issue = _issue(labels=[])
    assert _label_set(issue) == frozenset()


# ---------------------------------------------------------------------------
# ReleaseBranchValidationResult dataclass
# ---------------------------------------------------------------------------


def test_result_defaults():
    """A ReleaseBranchValidationResult with defaults is valid and empty."""
    r = ReleaseBranchValidationResult(valid=True)
    assert r.valid is True
    assert r.target_branch is None
    assert r.error == ""
    assert r.reason == ""


def test_result_invalid_fields():
    """All fields of an invalid result are accessible."""
    r = ReleaseBranchValidationResult(
        valid=False,
        target_branch="bad/branch",
        reason="untracked_branch",
        error="Some actionable error",
    )
    assert r.valid is False
    assert r.target_branch == "bad/branch"
    assert r.reason == "untracked_branch"
    assert "actionable" in r.error


# ---------------------------------------------------------------------------
# Orchestrator._should_dispatch integration
# ---------------------------------------------------------------------------


def _make_orchestrator_with_project(project: Project):
    """Create a minimal Orchestrator stub that supports _should_dispatch."""
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator
    from oompah.projects import ProjectStore

    store = MagicMock(spec=ProjectStore)
    store.get.return_value = project
    store.list_all.return_value = [project]

    config = ServiceConfig(
        agent_command="echo",
        tracker_kind="oompah_md",
        tracker_active_states=["open", "Needs CI Fix", "Needs Rebase"],
        tracker_terminal_states=["done"],
    )

    orch = Orchestrator.__new__(Orchestrator)
    # Minimal state bootstrap (avoid __init__ I/O)
    from oompah.models import OrchestratorState
    orch.state = OrchestratorState()
    orch.config = config
    orch.project_store = store
    orch._paused = False
    orch._project_trackers = {}
    return orch


def test_should_dispatch_rejects_untracked_target_branch():
    """_should_dispatch returns False when target_branch is untracked."""
    proj = _project(branches=["main", "release/*"], default_branch="main")
    orch = _make_orchestrator_with_project(proj)
    issue = _issue(
        identifier="TASK-10",
        target_branch="unknown/branch",
        project_id="proj-1",
    )
    result = orch._should_dispatch(issue)
    assert result is False
    reason, _ = orch.state.reject_streak.get("TASK-10", ("", 0))
    assert "invalid_target_branch" in reason
    assert "untracked_branch" in reason


def test_should_dispatch_rejects_source_only_for_backport():
    """_should_dispatch rejects a backport issue targeting the source branch."""
    proj = _project(branches=["main", "release/*"], default_branch="main")
    orch = _make_orchestrator_with_project(proj)
    issue = _issue(
        identifier="TASK-11",
        target_branch="main",
        labels=["backport"],
        project_id="proj-1",
    )
    result = orch._should_dispatch(issue)
    assert result is False
    reason, _ = orch.state.reject_streak.get("TASK-11", ("", 0))
    assert "invalid_target_branch" in reason
    assert "source_only_branch" in reason


def test_should_dispatch_allows_valid_release_branch():
    """_should_dispatch does NOT reject a valid release branch target."""
    proj = _project(branches=["main", "release/*"], default_branch="main")
    orch = _make_orchestrator_with_project(proj)
    issue = _issue(
        identifier="TASK-12",
        target_branch="release/1.0",
        labels=["backport"],
        project_id="proj-1",
    )
    # We only care that the rejection reason is NOT about target_branch
    result = orch._should_dispatch(issue)
    # The issue may fail for other reasons (budget, slots, etc.) but
    # invalid_target_branch should NOT be the reason
    reason, _ = orch.state.reject_streak.get("TASK-12", ("", 0))
    assert "invalid_target_branch" not in reason


@pytest.mark.parametrize("state,label", [
    ("Needs CI Fix", "ci-fix"),
    ("Needs Rebase", "merge-conflict"),
])
def test_should_dispatch_allows_repair_task_on_generated_epic_branch(state, label):
    """P0 repair tasks can run on oompah-generated stacked epic branches."""
    proj = _project(branches=["main"], default_branch="main")
    proj.epic_strategy = "stacked"
    orch = _make_orchestrator_with_project(proj)
    issue = _issue(
        identifier="COROOT-21",
        target_branch="epic-COROOT-5",
        parent_id="COROOT-5",
        labels=[label],
        project_id="proj-1",
        state=state,
    )
    issue.priority = 0
    orch._should_dispatch(issue)
    reason, _ = orch.state.reject_streak.get("COROOT-21", ("", 0))
    assert "invalid_target_branch" not in reason


def test_should_dispatch_skips_validation_without_project():
    """When no project is found, target_branch validation is skipped gracefully."""
    proj = _project()
    orch = _make_orchestrator_with_project(proj)
    orch.project_store.get.return_value = None  # project not found
    issue = _issue(
        identifier="TASK-13",
        target_branch="completely/unknown/branch",
        project_id="proj-1",
    )
    # Should not raise; validation is skipped
    result = orch._should_dispatch(issue)
    reason, _ = orch.state.reject_streak.get("TASK-13", ("", 0))
    assert "invalid_target_branch" not in reason


def test_should_dispatch_skips_validation_without_project_id():
    """When issue has no project_id, target_branch validation is skipped."""
    proj = _project()
    orch = _make_orchestrator_with_project(proj)
    issue = _issue(
        identifier="TASK-14",
        target_branch="nope/branch",
        project_id="",
    )
    issue.project_id = None
    result = orch._should_dispatch(issue)
    reason, _ = orch.state.reject_streak.get("TASK-14", ("", 0))
    assert "invalid_target_branch" not in reason


def test_should_dispatch_allows_no_target_branch():
    """Issues with no target_branch skip validation entirely."""
    proj = _project()
    orch = _make_orchestrator_with_project(proj)
    issue = _issue(
        identifier="TASK-15",
        target_branch=None,
        project_id="proj-1",
    )
    result = orch._should_dispatch(issue)
    reason, _ = orch.state.reject_streak.get("TASK-15", ("", 0))
    assert "invalid_target_branch" not in reason


def test_should_dispatch_allow_source_label_bypasses_protection():
    """backport:allow-source label lets backport tasks target the default branch."""
    proj = _project(branches=["main"], default_branch="main")
    orch = _make_orchestrator_with_project(proj)
    issue = _issue(
        identifier="TASK-16",
        target_branch="main",
        labels=["backport", ALLOW_SOURCE_LABEL],
        project_id="proj-1",
    )
    result = orch._should_dispatch(issue)
    reason, _ = orch.state.reject_streak.get("TASK-16", ("", 0))
    assert "invalid_target_branch" not in reason
