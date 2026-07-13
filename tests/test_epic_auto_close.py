"""Tests for the epic auto-close hook (oompah-zlz_2-lvcd).

Covers the four-condition gate enforced by ``_epic_auto_close_check``:

1. Every child is in a terminal state.
2. Every child branch with a PR was merged into the project's default
   branch.
3. Children without a PR (research/triage closures) pass the merge
   check trivially.
4. Manually-closed epics are never reanimated.

Plus the cascading-close behaviour of the per-tick scan and the
reactive ``_maybe_auto_close_parent_epic`` worker-exit hook.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import fnmatch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest


# --------------------------------------------------------------------- helpers


_DEFAULT_BRANCH = object()  # sentinel: derive from identifier


def _make_issue(
    identifier: str,
    *,
    state: str = "closed",
    issue_type: str = "task",
    parent_id: str | None = None,
    project_id: str = "proj-1",
    branch_name=_DEFAULT_BRANCH,
) -> Issue:
    if branch_name is _DEFAULT_BRANCH:
        resolved_branch: str | None = identifier
    else:
        resolved_branch = branch_name
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id=project_id,
        branch_name=resolved_branch,
    )


def _make_review(
    *,
    number: int,
    state: str,
    source_branch: str,
    target_branch: str = "main",
) -> ReviewRequest:
    return ReviewRequest(
        id=str(number),
        title=f"PR #{number}",
        url=f"https://example.com/pulls/{number}",
        author="someone",
        state=state,
        source_branch=source_branch,
        target_branch=target_branch,
        created_at="",
        updated_at="",
    )


def _make_project(project_id: str = "proj-1", branch: str = "main") -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.name = "test-project"
    p.repo_url = "https://github.com/org/repo"
    p.repo_path = "/tmp/repo"
    p.branch = branch
    p.default_branch = branch
    p.branches = [branch]
    p.matches_branch = lambda b: fnmatch.fnmatch(b, branch)
    p.paused = False
    p.epic_strategy = "shared"
    p.max_in_flight_prs = 1
    p.access_token = None
    return p


def _epic_branch_name(identifier: str) -> str:
    """Return the expected epic branch name for a given epic identifier."""
    return f"epic-{identifier}"


def _make_orch(
    tmp_path,
    *,
    project=None,
    tracker=None,
    provider=None,
):
    """Build an Orchestrator with mock store/tracker/provider plumbed in."""
    if project is None:
        project = _make_project()

    project_store = MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.side_effect = lambda pid: project if pid == project.id else None
    project_store.epic_branch_name.side_effect = _epic_branch_name

    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    if tracker is not None:
        orch._project_trackers[project.id] = tracker
    # Save the provider on the orch so tests can swap it via the
    # detect_provider monkeypatch helper.
    orch._test_provider = provider  # type: ignore[attr-defined]
    return orch


# ---------------------------------------------------------- Condition 1: all-terminal


class TestAllChildrenTerminal:
    def test_all_children_closed_and_merged_closes_epic(self, tmp_path):
        """Synthetic epic with 3 children, all closed, all merged → close.

        In shared mode, children commit to the epic branch (``epic-epic-1``),
        and the epic branch PR merges that work to main.  Auto-close fires only
        after the epic branch itself is merged.
        """
        project = _make_project()
        epic = _make_issue(
            "epic-1",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("child-1", state="closed", branch_name="child-1"),
            _make_issue("child-2", state="closed", branch_name="child-2"),
            _make_issue("child-3", state="closed", branch_name="child-3"),
        ]

        tracker = MagicMock()
        tracker.fetch_children.return_value = children

        provider = MagicMock()
        _reviews = {
            "child-1": _make_review(number=11, state="merged", source_branch="child-1", target_branch="epic-epic-1"),
            "child-2": _make_review(number=22, state="merged", source_branch="child-2", target_branch="epic-epic-1"),
            "child-3": _make_review(number=33, state="merged", source_branch="child-3", target_branch="epic-epic-1"),
            # The epic branch itself is merged to main.
            "epic-epic-1": _make_review(number=99, state="merged", source_branch="epic-epic-1", target_branch="main"),
        }
        provider.find_pr_for_branch.side_effect = lambda repo, branch: _reviews.get(branch)

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is True
        tracker.close_issue.assert_called_once()
        call_args = tracker.close_issue.call_args
        assert call_args.args[0] == "epic-1"
        reason = call_args.kwargs.get("reason", "")
        assert "all 3 children closed and merged to epic-epic-1" in reason
        assert "child-1 (merged via PR #11)" in reason
        assert "child-2 (merged via PR #22)" in reason
        assert "child-3 (merged via PR #33)" in reason
        # No stuck_epic alert was raised.
        assert all(
            a.get("source") != f"stuck_epic:{epic.identifier}" for a in orch._alerts
        )

    def test_non_terminal_child_blocks_close(self, tmp_path):
        """Epic stays open while any child is still in_progress / open."""
        project = _make_project()
        epic = _make_issue(
            "epic-2",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("child-a", state="closed", branch_name="child-a"),
            _make_issue("child-b", state="in_progress", branch_name="child-b"),
        ]

        tracker = MagicMock()
        tracker.fetch_children.return_value = children
        provider = MagicMock()

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is False
        tracker.close_issue.assert_not_called()
        # find_pr_for_branch should not even be called when the
        # terminal-state gate already fails.
        provider.find_pr_for_branch.assert_not_called()


# ----------------------------------------------------- Condition 2: merge check


class TestMergeCheck:
    def test_one_child_unmerged_does_not_close(self, tmp_path):
        """One child's branch has no merged PR → stay open + stuck_epic alert."""
        project = _make_project()
        epic = _make_issue(
            "epic-3",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("child-1", state="closed", branch_name="child-1"),
            _make_issue("child-2", state="closed", branch_name="child-2"),
            _make_issue("child-3", state="closed", branch_name="child-3"),
        ]

        tracker = MagicMock()
        tracker.fetch_children.return_value = children

        def _fake_find(repo, branch):
            if branch in {"child-1", "child-3"}:
                return _make_review(
                    number={"child-1": 11, "child-3": 33}[branch],
                    state="merged",
                    source_branch=branch,
                )
            # child-2 has an OPEN PR — unmerged → stuck.
            return _make_review(
                number=22,
                state="open",
                source_branch=branch,
            )

        provider = MagicMock()
        provider.find_pr_for_branch.side_effect = _fake_find

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is False
        tracker.close_issue.assert_not_called()
        # stuck_epic alert raised, keyed to this epic.
        alerts_for_epic = [
            a
            for a in orch._alerts
            if a.get("source") == f"stuck_epic:{epic.identifier}"
        ]
        assert len(alerts_for_epic) == 1
        msg = alerts_for_epic[0]["message"]
        assert "child-2" in msg
        assert "PR #22" in msg

    def test_pr_merged_to_wrong_branch_is_unmerged(self, tmp_path):
        """A PR merged into something other than project.branch is stuck."""
        project = _make_project(branch="main")
        epic = _make_issue(
            "epic-4",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("child-x", state="closed", branch_name="child-x"),
        ]

        tracker = MagicMock()
        tracker.fetch_children.return_value = children
        provider = MagicMock()
        provider.find_pr_for_branch.return_value = _make_review(
            number=99,
            state="merged",
            source_branch="child-x",
            # Merged to a different branch → not main → stuck.
            target_branch="some-stale-feature-branch",
        )

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is False
        tracker.close_issue.assert_not_called()
        alerts_for_epic = [
            a
            for a in orch._alerts
            if a.get("source") == f"stuck_epic:{epic.identifier}"
        ]
        assert len(alerts_for_epic) == 1

    def test_custom_project_default_branch(self, tmp_path):
        """``project.branch`` (not hardcoded 'main') is what we check.

        In shared mode the child PR targets the epic branch, and the epic
        branch PR targets the project's configured default branch (here
        "master").  Auto-close requires the epic branch to reach master.
        """
        project = _make_project(branch="master")
        epic = _make_issue(
            "epic-5",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("child-1", state="closed", branch_name="child-1"),
        ]
        tracker = MagicMock()
        tracker.fetch_children.return_value = children
        provider = MagicMock()
        # Child merges to epic branch; epic branch merges to master.
        _reviews = {
            "child-1": _make_review(number=42, state="merged", source_branch="child-1", target_branch="epic-epic-5"),
            "epic-epic-5": _make_review(number=43, state="merged", source_branch="epic-epic-5", target_branch="master"),
        }
        provider.find_pr_for_branch.side_effect = lambda repo, branch: _reviews.get(branch)

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is True
        reason = tracker.close_issue.call_args.kwargs.get("reason", "")
        # Children merged to the epic branch; the auto-close message names that.
        assert "merged to epic-epic-5" in reason


# -------------------------------------------------- Condition 3: no-branch children


class TestChildWithoutBranch:
    def test_child_without_branch_is_no_op_for_merge_check(self, tmp_path):
        """Children with no PR (research/triage closures) pass condition 3.

        The children themselves don't trigger any PR lookup (empty branch names),
        but the epic branch gate still fires — requiring the epic's own PR to be
        merged before auto-close.
        """
        project = _make_project()
        epic = _make_issue(
            "epic-6",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("research-1", state="closed", branch_name=""),
            _make_issue("triage-2", state="closed", branch_name=None),
        ]

        tracker = MagicMock()
        tracker.fetch_children.return_value = children
        provider = MagicMock()
        # No PR for child branches (they have none); the epic branch itself
        # must be merged to main for auto-close to fire.
        def _find(repo, branch):
            if branch == "epic-epic-6":
                return _make_review(number=99, state="merged", source_branch="epic-epic-6", target_branch="main")
            return None
        provider.find_pr_for_branch.side_effect = _find

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is True
        reason = tracker.close_issue.call_args.kwargs.get("reason", "")
        assert "research-1 (closed without PR)" in reason
        assert "triage-2 (closed without PR)" in reason
        # Provider was called only for the epic branch gate (not for empty child branches).
        provider.find_pr_for_branch.assert_called_once_with(
            provider.find_pr_for_branch.call_args.args[0], "epic-epic-6"
        )

    def test_child_branch_with_no_pr_record_is_eligible(self, tmp_path):
        """A child with a branch name but no PR record is treated as closed-without-PR.

        The child passes the merge-check (no PR → eligible), and the epic
        branch gate still requires the epic's own PR to be merged to main.
        """
        project = _make_project()
        epic = _make_issue(
            "epic-7",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("ghost", state="closed", branch_name="ghost"),
        ]
        tracker = MagicMock()
        tracker.fetch_children.return_value = children
        provider = MagicMock()
        # No PR for the child branch; the epic branch must be merged.
        def _find(repo, branch):
            if branch == "ghost":
                return None  # no PR ever opened
            if branch == "epic-epic-7":
                return _make_review(number=99, state="merged", source_branch="epic-epic-7", target_branch="main")
            return None
        provider.find_pr_for_branch.side_effect = _find

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is True
        reason = tracker.close_issue.call_args.kwargs.get("reason", "")
        assert "ghost (closed without PR)" in reason


# ---------------------------------------------------- Condition 4: don't reanimate


class TestManuallyClosedEpic:
    def test_manually_closed_epic_not_reanimated(self, tmp_path):
        """Epic state = closed; gate fires; no-op."""
        project = _make_project()
        epic = _make_issue(
            "epic-8",
            state="closed",
            issue_type="epic",
            branch_name=None,
        )
        tracker = MagicMock()
        # If children were even fetched, they'd report closed/merged —
        # but the gate should bail out before then.
        tracker.fetch_children.return_value = []
        provider = MagicMock()

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is False
        tracker.close_issue.assert_not_called()
        # No PR lookups should happen — we exit before fetching children.
        provider.find_pr_for_branch.assert_not_called()


# ---------------------------------------------------------- Empty-epic edge case


class TestEpicWithNoChildren:
    def test_epic_with_no_children_skipped(self, tmp_path):
        """Don't auto-close an empty epic (might still be in planning)."""
        project = _make_project()
        epic = _make_issue(
            "epic-empty",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        tracker = MagicMock()
        tracker.fetch_children.return_value = []
        provider = MagicMock()

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is False
        tracker.close_issue.assert_not_called()


# ----------------------------------------------------------- Cascading auto-close


class TestCascadingAutoClose:
    def test_cascading_auto_close(self, tmp_path):
        """Three-level chain: leaves close → mid closes → top closes.

        v1 doesn't recurse explicitly: it relies on the per-child trigger
        firing on every close. We model that here by running the gate
        twice across two ticks:

        * Tick 1: leaves are closed. The mid-tier epic auto-closes when
          its children (the leaves) are all merged.
        * Tick 2: the top-tier epic auto-closes when its only child
          (the now-closed mid-tier) is terminal.
        """
        project = _make_project()
        top = _make_issue(
            "epic-top",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        mid = _make_issue(
            "epic-mid",
            state="open",
            issue_type="epic",
            parent_id="epic-top",
            branch_name=None,
        )
        leaves = [
            _make_issue(
                "leaf-1",
                state="closed",
                parent_id="epic-mid",
                branch_name="leaf-1",
            ),
            _make_issue(
                "leaf-2",
                state="closed",
                parent_id="epic-mid",
                branch_name="leaf-2",
            ),
        ]

        tracker = MagicMock()

        def _fetch_children(parent_id):
            if parent_id == "epic-top":
                return [mid]
            if parent_id == "epic-mid":
                return leaves
            return []

        tracker.fetch_children.side_effect = _fetch_children

        # Track which epic was closed so we can simulate mid closing
        # between ticks.
        closed_epics: set[str] = set()

        def _fake_close(identifier, **kw):
            closed_epics.add(identifier)
            if identifier == "epic-mid":
                mid.state = "closed"
            if identifier == "epic-top":
                top.state = "closed"

        tracker.close_issue.side_effect = _fake_close

        provider = MagicMock()
        # In shared mode, leaves commit to the mid epic's branch; the mid
        # epic branch then merges to main.  Similarly for the top tier.
        _reviews = {
            "leaf-1": _make_review(number=1, state="merged", source_branch="leaf-1", target_branch="epic-epic-mid"),
            "leaf-2": _make_review(number=2, state="merged", source_branch="leaf-2", target_branch="epic-epic-mid"),
            "epic-epic-mid": _make_review(number=3, state="merged", source_branch="epic-epic-mid", target_branch="main"),
            "epic-epic-top": _make_review(number=4, state="merged", source_branch="epic-epic-top", target_branch="main"),
        }
        provider.find_pr_for_branch.side_effect = lambda repo, branch: _reviews.get(branch)

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            # Tick 1 — check the mid-tier (leaves already closed/merged).
            assert orch._epic_auto_close_check(mid) is True
            assert "epic-mid" in closed_epics
            # Tick 2 — check the top-tier; its only child is now mid
            # which just closed. The mid epic doesn't have a branch
            # of its own, so condition 3 (no PR) applies and it's
            # eligible.
            assert orch._epic_auto_close_check(top) is True
            assert "epic-top" in closed_epics


# --------------------------------------------- Sweep helper preserves invariants


class TestAutoCloseCompletedEpicsSweep:
    def test_sweep_delegates_to_check(self, tmp_path):
        """The full-sync ``_auto_close_completed_epics`` calls the new helper."""
        project = _make_project()
        orch = _make_orch(tmp_path, project=project)
        # Patch the per-epic check so we only verify delegation here.
        orch._epic_auto_close_check = MagicMock(return_value=True)

        candidates = [
            _make_issue("epic-x", state="open", issue_type="epic"),
            _make_issue("epic-y", state="closed", issue_type="epic"),
            _make_issue("task-z", state="open"),
        ]
        orch._auto_close_completed_epics(candidates)

        # Only the open epic should be passed to the check; the closed
        # epic and the non-epic task are skipped.
        called_with = [
            c.args[0].identifier for c in orch._epic_auto_close_check.call_args_list
        ]
        assert called_with == ["epic-x"]

    def test_sweep_clears_stale_alert_for_terminal_epic(self, tmp_path):
        """A terminal epic should not leave an obsolete stuck_epic alert visible."""
        project = _make_project()
        orch = _make_orch(tmp_path, project=project)
        orch._epic_auto_close_check = MagicMock(return_value=True)
        orch._alerts = [
            {
                "level": "warning",
                "source": "stuck_epic:epic-y",
                "message": "old stale alert",
            },
            {
                "level": "warning",
                "source": "other",
                "message": "unrelated alert",
            },
        ]

        orch._auto_close_completed_epics(
            [_make_issue("epic-y", state="Merged", issue_type="epic")]
        )

        orch._epic_auto_close_check.assert_not_called()
        assert [a.get("source") for a in orch._alerts] == ["other"]


# ----------------------------------- Stuck-epic alert lifecycle (idempotent re-arm)


class TestStuckEpicAlertLifecycle:
    def test_rearming_does_not_duplicate(self, tmp_path):
        """Two calls to the gate with the same stuck state → one alert."""
        project = _make_project()
        epic = _make_issue(
            "epic-9",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("child-x", state="closed", branch_name="child-x"),
        ]
        tracker = MagicMock()
        tracker.fetch_children.return_value = children
        provider = MagicMock()
        provider.find_pr_for_branch.return_value = _make_review(
            number=1,
            state="open",
            source_branch="child-x",
        )

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            orch._epic_auto_close_check(epic)
            orch._epic_auto_close_check(epic)

        alerts_for_epic = [
            a
            for a in orch._alerts
            if a.get("source") == f"stuck_epic:{epic.identifier}"
        ]
        assert len(alerts_for_epic) == 1

    def test_alert_cleared_when_child_reopens(self, tmp_path):
        """A previously-stuck alert clears once children are non-terminal again."""
        project = _make_project()
        epic = _make_issue(
            "epic-10",
            state="open",
            issue_type="epic",
            branch_name=None,
        )

        children_stuck = [
            _make_issue("child-y", state="closed", branch_name="child-y"),
        ]
        tracker = MagicMock()
        tracker.fetch_children.return_value = children_stuck
        provider = MagicMock()
        provider.find_pr_for_branch.return_value = _make_review(
            number=1,
            state="open",
            source_branch="child-y",
        )
        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            orch._epic_auto_close_check(epic)
        assert any(
            a.get("source") == f"stuck_epic:{epic.identifier}" for a in orch._alerts
        )

        # Now the child is reopened (back to in_progress) → re-running
        # the gate should clear the stuck alert.
        children_reopened = [
            _make_issue("child-y", state="in_progress", branch_name="child-y"),
        ]
        tracker.fetch_children.return_value = children_reopened
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            orch._epic_auto_close_check(epic)
        assert not any(
            a.get("source") == f"stuck_epic:{epic.identifier}" for a in orch._alerts
        )

    def test_mark_epic_merged_clears_stale_alert(self, tmp_path):
        """Landing an epic should clear any earlier stuck_epic warning."""
        project = _make_project()
        epic = _make_issue("epic-11", state="Done", issue_type="epic")
        tracker = MagicMock()
        tracker.fetch_children.return_value = []
        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        orch.project_store.epic_branch_name.return_value = "epic-epic-11"
        orch._alerts = [
            {
                "level": "warning",
                "source": "stuck_epic:epic-11",
                "message": "old stale alert",
            },
            {
                "level": "warning",
                "source": "other",
                "message": "unrelated alert",
            },
        ]

        orch._mark_epic_merged(epic)

        tracker.update_issue.assert_called_once_with("epic-11", status="Merged")
        assert [a.get("source") for a in orch._alerts] == ["other"]


# ----------------------------------------- Reactive hook from _on_worker_exit


class TestMaybeAutoCloseParentEpic:
    def test_calls_check_for_parent_epic(self, tmp_path):
        """When a child closes, the parent epic is evaluated for auto-close."""
        project = _make_project()
        parent_epic = _make_issue(
            "epic-r",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        child = _make_issue(
            "child-r",
            state="closed",
            parent_id="epic-r",
            branch_name="child-r",
        )

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent_epic
        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        orch._epic_auto_close_check = MagicMock(return_value=True)

        orch._maybe_auto_close_parent_epic(child)

        tracker.fetch_issue_detail.assert_called_once_with("epic-r")
        orch._epic_auto_close_check.assert_called_once_with(parent_epic)

    def test_skips_when_no_parent(self, tmp_path):
        """A child with no parent_id is a no-op."""
        project = _make_project()
        orch = _make_orch(tmp_path, project=project)
        orch._epic_auto_close_check = MagicMock()
        child = _make_issue("orphan", state="closed", parent_id=None)

        orch._maybe_auto_close_parent_epic(child)
        orch._epic_auto_close_check.assert_not_called()

    def test_skips_when_parent_not_epic(self, tmp_path):
        """If parent isn't an epic, don't trigger the gate."""
        project = _make_project()
        parent_task = _make_issue(
            "task-parent",
            state="open",
            issue_type="task",
        )
        child = _make_issue(
            "child-r",
            state="closed",
            parent_id="task-parent",
            branch_name="child-r",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent_task

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        orch._epic_auto_close_check = MagicMock()
        orch._maybe_auto_close_parent_epic(child)

        orch._epic_auto_close_check.assert_not_called()

    def test_swallow_failure(self, tmp_path):
        """Errors from _epic_auto_close_check are logged, not raised."""
        project = _make_project()
        parent_epic = _make_issue(
            "epic-boom",
            state="open",
            issue_type="epic",
        )
        child = _make_issue(
            "child",
            state="closed",
            parent_id="epic-boom",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = parent_epic

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        orch._epic_auto_close_check = MagicMock(side_effect=RuntimeError("boom"))
        # Should not propagate the exception.
        orch._maybe_auto_close_parent_epic(child)


# ---------------------------------------------- Provider error / no-provider paths


class TestEpicBranchGate:
    """Shared-mode epics: children target the epic branch and the epic's
    own branch must merge to the project default branch before auto-close fires.
    """

    def test_children_merged_to_epic_branch_then_epic_merged_to_main(
        self,
        tmp_path,
    ):
        project = _make_project()
        epic = _make_issue(
            "epic-st",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("ch-1", state="closed", branch_name="ch-1"),
            _make_issue("ch-2", state="closed", branch_name="ch-2"),
        ]

        tracker = MagicMock()
        tracker.fetch_children.return_value = children

        def _find(repo, branch):
            if branch in ("ch-1", "ch-2"):
                return _make_review(
                    number={"ch-1": 11, "ch-2": 22}[branch],
                    state="merged",
                    source_branch=branch,
                    target_branch="epic-epic-st",
                )
            if branch == "epic-epic-st":
                return _make_review(
                    number=99,
                    state="merged",
                    source_branch="epic-epic-st",
                    target_branch="main",
                )
            return None

        provider = MagicMock()
        provider.find_pr_for_branch.side_effect = _find

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        orch.project_store.epic_branch_name = MagicMock(
            return_value="epic-epic-st",
        )
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is True
        tracker.close_issue.assert_called_once()
        reason = tracker.close_issue.call_args.kwargs.get("reason", "")
        # The summary describes the per-child merge into the epic branch.
        assert "merged to epic-epic-st" in reason

    def test_epic_pending_when_epic_branch_not_yet_merged(
        self,
        tmp_path,
    ):
        project = _make_project()
        epic = _make_issue(
            "epic-pn",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("c1", state="closed", branch_name="c1"),
        ]
        tracker = MagicMock()
        tracker.fetch_children.return_value = children

        def _find(repo, branch):
            if branch == "c1":
                return _make_review(
                    number=1,
                    state="merged",
                    source_branch="c1",
                    target_branch="epic-epic-pn",
                )
            if branch == "epic-epic-pn":
                # Epic branch PR exists but is still open (pending merge).
                return _make_review(
                    number=2,
                    state="open",
                    source_branch="epic-epic-pn",
                    target_branch="main",
                )
            return None

        provider = MagicMock()
        provider.find_pr_for_branch.side_effect = _find

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        orch.project_store.epic_branch_name = MagicMock(
            return_value="epic-epic-pn",
        )
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        # Don't close — epic merge is pending — and don't alarm.
        assert closed is False
        tracker.close_issue.assert_not_called()
        assert not any(
            a.get("source") == f"stuck_epic:{epic.identifier}" for a in orch._alerts
        )

    def test_child_merged_directly_to_main_is_landed_bypass(self, tmp_path):
        """A child already merged to the final target is treated as a bypass landing.

        This is not the intended merge-train shape, but the code is already
        downstream of the epic branch.  Keep the epic pending for its own rollup
        instead of arming an unmerged-child alert that cannot be repaired by
        merging the child again.
        """
        project = _make_project()
        epic = _make_issue(
            "epic-mt",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("c1", state="closed", branch_name="c1"),
        ]
        tracker = MagicMock()
        tracker.fetch_children.return_value = children

        def _find(repo, branch):
            if branch == "c1":
                return _make_review(
                    number=1,
                    state="merged",
                    source_branch="c1",
                    target_branch="main",
                )
            return None

        provider = MagicMock()
        provider.find_pr_for_branch.side_effect = _find

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        orch.project_store.epic_branch_name = MagicMock(
            return_value="epic-epic-mt",
        )
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is False
        tracker.close_issue.assert_not_called()
        assert not any(
            a.get("source") == f"stuck_epic:{epic.identifier}" for a in orch._alerts
        )

    def test_child_merged_to_unrelated_branch_is_stuck(self, tmp_path):
        """A child merged to an unrelated branch (neither epic branch nor final target) is stuck."""
        project = _make_project()
        epic = _make_issue(
            "epic-mt",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("c1", state="closed", branch_name="c1"),
        ]
        tracker = MagicMock()
        tracker.fetch_children.return_value = children
        provider = MagicMock()
        provider.find_pr_for_branch.return_value = _make_review(
            number=1,
            state="merged",
            source_branch="c1",
            target_branch="release/oops",  # Should have been epic-epic-mt or main
        )

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        orch.project_store.epic_branch_name = MagicMock(
            return_value="epic-epic-mt",
        )
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        assert closed is False
        alerts_for_epic = [
            a
            for a in orch._alerts
            if a.get("source") == f"stuck_epic:{epic.identifier}"
        ]
        assert len(alerts_for_epic) == 1


class TestProviderErrorHandling:
    def test_no_provider_blocks_auto_close(self, tmp_path):
        """Without an SCM provider the epic branch gate cannot be verified → stay open."""
        # Simulate a project with no repo_url → no provider.
        project = _make_project()
        project.repo_url = ""

        epic = _make_issue(
            "epic-np",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("child-np", state="closed", branch_name="child-np"),
        ]
        tracker = MagicMock()
        tracker.fetch_children.return_value = children

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=None):
            closed = orch._epic_auto_close_check(epic)

        # Without a provider we can't verify the epic branch merge — the
        # epic branch gate requires a confirmed merged PR, so auto-close
        # is blocked.  This prevents premature closure when SCM credentials
        # are temporarily missing.
        assert closed is False

    def test_find_pr_raises_blocks_epic_branch_gate(self, tmp_path):
        """A throwing provider call at the epic branch gate returns False."""
        project = _make_project()
        epic = _make_issue(
            "epic-bp",
            state="open",
            issue_type="epic",
            branch_name=None,
        )
        children = [
            _make_issue("child-bp", state="closed", branch_name="child-bp"),
        ]
        tracker = MagicMock()
        tracker.fetch_children.return_value = children
        provider = MagicMock()
        # Errors during child branch lookups are swallowed (child treated as no-PR).
        # Errors during the epic branch gate are also swallowed, but the gate
        # fails closed (returns False) so the epic is not prematurely closed.
        provider.find_pr_for_branch.side_effect = RuntimeError("nope")

        orch = _make_orch(tmp_path, project=project, tracker=tracker)
        with patch("oompah.orchestrator.detect_provider", return_value=provider):
            closed = orch._epic_auto_close_check(epic)

        # Child lookup raised (treated as no-PR → eligible), but then the
        # epic branch gate also raised → gate returns False → not closed.
        assert closed is False
