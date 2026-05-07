"""Tests for P0 dispatch bypass policy (oompah-zlz_2-dyi).

P0 beads bypass the blocker-chain check (a blocker in non-terminal
state OR closed-with-unmerged-PR no longer blocks dispatch). Other
gates — pauses, structural sanity, dedup, label gates that signal
human interaction — still apply to P0.
"""

from unittest.mock import MagicMock

from oompah.config import ServiceConfig
from oompah.models import BlockerRef, Issue
from oompah.orchestrator import Orchestrator


def _make_issue(
    identifier: str = "test-1",
    state: str = "open",
    priority: int | None = None,
    labels: list | None = None,
    blocked_by: list | None = None,
    description: str = "Body so the empty-description gate passes.",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description=description,
        state=state,
        priority=priority,
        labels=labels or [],
        blocked_by=blocked_by or [],
    )


def _make_orchestrator(tmp_path) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.return_value = None
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    # Default: nothing paused, no merged-branch data.
    orch._paused = False
    orch._unmerged_review_branches = set()
    orch._merged_branches = set()
    return orch


class TestP0BypassesBlockerChain:
    """P0 dispatch must succeed even when a blocker is non-terminal
    or closed-with-unmerged-PR."""

    def test_p1_with_open_blocker_is_rejected(self, tmp_path):
        # Regression: ensure non-P0 still blocked.
        orch = _make_orchestrator(tmp_path)
        blocker = BlockerRef(id="upstream", identifier="upstream", state="open")
        issue = _make_issue(priority=1, blocked_by=[blocker])
        assert orch._should_dispatch(issue) is False

    def test_p0_with_open_blocker_dispatches(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        blocker = BlockerRef(id="upstream", identifier="upstream", state="open")
        issue = _make_issue(priority=0, blocked_by=[blocker])
        assert orch._should_dispatch(issue) is True

    def test_p1_with_closed_unmerged_blocker_is_rejected(self, tmp_path):
        # Regression: closed-with-unmerged-PR still blocks non-P0.
        orch = _make_orchestrator(tmp_path)
        orch._unmerged_review_branches = {"upstream"}
        blocker = BlockerRef(id="upstream", identifier="upstream", state="closed")
        issue = _make_issue(priority=1, blocked_by=[blocker])
        assert orch._should_dispatch(issue) is False

    def test_p0_with_closed_unmerged_blocker_dispatches(self, tmp_path):
        # The dyi case: trickle-6zi (P0) was held by trickle-0vv whose
        # PR was sitting in the merge queue. P0 must run anyway.
        orch = _make_orchestrator(tmp_path)
        orch._unmerged_review_branches = {"upstream"}
        blocker = BlockerRef(id="upstream", identifier="upstream", state="closed")
        issue = _make_issue(priority=0, blocked_by=[blocker])
        assert orch._should_dispatch(issue) is True

    def test_p0_with_multiple_blockers_dispatches(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._unmerged_review_branches = {"upstream-2"}
        blockers = [
            BlockerRef(id="upstream-1", identifier="upstream-1", state="open"),
            BlockerRef(id="upstream-2", identifier="upstream-2", state="closed"),
        ]
        issue = _make_issue(priority=0, blocked_by=blockers)
        assert orch._should_dispatch(issue) is True


class TestP0StillRespectsHumanGates:
    """Even at P0, gates that signal 'a human must intervene first'
    (asking_question, human-only) and structural gates (decomposed)
    keep the dispatcher out."""

    def test_p0_with_asking_question_label_is_rejected(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(priority=0, labels=["asking_question"])
        assert orch._should_dispatch(issue) is False

    def test_p0_with_human_only_label_is_rejected(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(priority=0, labels=["human-only"])
        assert orch._should_dispatch(issue) is False

    def test_p0_with_decomposed_label_is_rejected(self, tmp_path):
        # Structural gate: parent's work is now in children. Dispatching
        # would duplicate. Applies regardless of priority.
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(priority=0, labels=["decomposed"])
        assert orch._should_dispatch(issue) is False


class TestP0StillRespectsPauses:
    """Server / project pauses always halt P0 dispatch."""

    def test_p0_blocked_by_global_pause(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._paused = True
        issue = _make_issue(priority=0)
        assert orch._should_dispatch(issue) is False

    def test_p0_blocked_by_project_pause(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        # Make _is_project_paused return True for any project_id.
        orch._is_project_paused = lambda pid: True
        issue = _make_issue(priority=0)
        assert orch._should_dispatch(issue) is False
