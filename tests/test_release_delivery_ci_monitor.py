"""Tests for release delivery CI monitoring (OOMPAH-314).

Covers:
- _monitor_merged_delivery_ci: skips projects without repo_url.
- _monitor_merged_delivery_ci: skips deliveries already with ci_remediation_task_id.
- _monitor_merged_delivery_ci: skips non-merged deliveries (open, in_review, blocked).
- _monitor_merged_delivery_ci: skips merged deliveries without result_commits.
- _monitor_merged_delivery_ci: no remediation on passing CI.
- _monitor_merged_delivery_ci: no remediation on pending CI.
- _monitor_merged_delivery_ci: creates remediation task on failed release branch CI.
- _check_and_remediate_delivery_ci: dispatches remediation on CI failure.
- _dispatch_release_ci_fix_task: stamps ci_remediation_task_id before creating task.
- _dispatch_release_ci_fix_task: idempotency — already-stamped delivery skipped.
- Queue integration: orchestrator calls cherry_pick_delivery with sync_source_branch=False.
- get_branch_head_sha (GitHub): returns SHA for known branch, None for missing branch.
- get_ci_status_for_sha (GitHub): delegates to _fetch_ci_status.
- get_branch_ci_status (base): combines head SHA lookup and CI check.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from oompah.release_addendum_schema import AddendumStatus
from oompah.release_delivery_store import (
    ReleaseDelivery,
    SourceKind,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
PROJECT_ID = "proj-ci-monitor"
_SHA_A = "a" * 40
_SHA_B = "b" * 40
_RESULT_SHA = "e" * 40


def _delivery(
    *,
    delivery_id: str = "rd_ci_001",
    status: AddendumStatus = AddendumStatus.MERGED,
    ci_remediation_task_id: str | None = None,
    result_commits: list[str] | None = None,
    work_branch: str | None = "oompah/release/FOO-10/release-0.11",
    pr_url: str | None = "https://github.com/org/trickle/pull/303",
    target_branch: str = "release/0.11",
    source_identifier: str | None = "FOO-10",
) -> ReleaseDelivery:
    return ReleaseDelivery(
        id=delivery_id,
        project_id=PROJECT_ID,
        source_branch="main",
        source_kind=SourceKind.TASK,
        source_identifier=source_identifier,
        source_commits=[_SHA_A, _SHA_B],
        target_branch=target_branch,
        status=status,
        queued_at=NOW.isoformat(),
        work_branch=work_branch,
        pr_url=pr_url,
        result_commits=result_commits if result_commits is not None else [_RESULT_SHA],
        ci_remediation_task_id=ci_remediation_task_id,
    )


class _FakeStore:
    """In-memory store for CI monitor tests."""

    def __init__(self, deliveries: list[ReleaseDelivery]) -> None:
        self._deliveries = list(deliveries)
        self.update_calls: list[dict[str, Any]] = []

    def read_ledger(self) -> Any:
        from oompah.release_delivery_store import ReleaseDeliveryLedger
        return ReleaseDeliveryLedger(version=1, deliveries=list(self._deliveries))

    def lookup_by_id(self, delivery_id: str) -> ReleaseDelivery | None:
        return next((d for d in self._deliveries if d.id == delivery_id), None)

    def update(self, delivery_id: str, **fields: Any) -> ReleaseDelivery:
        from oompah.release_addendum_schema import AddendumStatus as AS, is_valid_transition
        from oompah.release_delivery_store import DeliveryNotFoundError

        self.update_calls.append({"delivery_id": delivery_id, **fields})
        idx = next(
            (i for i, d in enumerate(self._deliveries) if d.id == delivery_id),
            None,
        )
        if idx is None:
            raise DeliveryNotFoundError(delivery_id)
        current = self._deliveries[idx]
        new_status = current.status
        if "status" in fields:
            raw = fields["status"]
            new_status = raw if isinstance(raw, AS) else AS.from_raw(raw)
        updated = dataclasses.replace(
            current,
            status=new_status,
            work_branch=fields.get("work_branch", current.work_branch),
            pr_url=fields.get("pr_url", current.pr_url),
            pr_number=fields.get("pr_number", current.pr_number),
            result_commits=fields.get("result_commits", list(current.result_commits)),
            error=fields.get("error", current.error),
            claimed_by=fields.get("claimed_by", current.claimed_by),
            lease_expires_at=fields.get("lease_expires_at", current.lease_expires_at),
            started_at=fields.get("started_at", current.started_at),
            completed_at=fields.get("completed_at", current.completed_at),
            ci_remediation_task_id=fields.get(
                "ci_remediation_task_id", current.ci_remediation_task_id
            ),
        )
        self._deliveries[idx] = updated
        return updated


def _make_orchestrator(
    deliveries: list[ReleaseDelivery],
    *,
    ci_status: str = "failed",
    repo_url: str = "https://github.com/org/trickle",
    raise_on_create: bool = False,
    existing_remediation_task_ids: set[str] | None = None,
) -> tuple[Any, list[dict], _FakeStore]:
    """Build a minimal fake orchestrator for CI monitor tests.

    Returns:
        (orch, created_issues, store)
    """
    created_issues: list[dict] = []
    store = _FakeStore(deliveries)

    if existing_remediation_task_ids is None:
        existing_remediation_task_ids = {
            d.ci_remediation_task_id
            for d in deliveries
            if d.ci_remediation_task_id
        }

    class _FakeTracker:
        def fetch_issue_detail(self, identifier: str):
            if identifier in existing_remediation_task_ids:
                return SimpleNamespace(identifier=identifier)
            return None

        def create_issue(self, **kwargs):
            if raise_on_create:
                raise RuntimeError("simulated issue creation failure")
            iss = SimpleNamespace(identifier=f"OOMPAH-{len(created_issues) + 1}")
            created_issues.append(kwargs)
            return iss

    project_tracker = _FakeTracker()
    global_tracker = MagicMock()
    global_tracker.create_issue.side_effect = AssertionError(
        "release CI remediation must use the affected project's tracker"
    )
    project = SimpleNamespace(
        id=PROJECT_ID,
        name="trickle",
        repo_url=repo_url,
        repo_path="/tmp/trickle",
        access_token=None,
    )

    def _make_store(proj, git_writer=None):
        return store

    mock_scm = MagicMock()
    mock_scm.get_branch_ci_status.return_value = ci_status

    from oompah.orchestrator import Orchestrator

    class _FakeOrchestrator:
        tracker = global_tracker
        project_store = SimpleNamespace(list_all=lambda: [project])

        def _tracker_for_project(self, pid):
            assert pid == PROJECT_ID
            return project_tracker

        def _job_deadline_exceeded(self, _label):
            return False

        _check_and_remediate_delivery_ci = Orchestrator._check_and_remediate_delivery_ci
        _dispatch_release_ci_fix_task = Orchestrator._dispatch_release_ci_fix_task
        _monitor_merged_delivery_ci = Orchestrator._monitor_merged_delivery_ci
        _has_live_release_ci_remediation = staticmethod(
            Orchestrator._has_live_release_ci_remediation
        )

    orch = _FakeOrchestrator()

    with (
        patch("oompah.orchestrator.make_delivery_store", side_effect=_make_store),
        patch(
            "oompah.orchestrator.detect_provider",
            return_value=mock_scm,
        ),
        patch(
            "oompah.orchestrator.extract_repo_slug",
            return_value="org/trickle",
        ),
    ):
        Orchestrator._monitor_merged_delivery_ci(orch)

    return orch, created_issues, store


# ---------------------------------------------------------------------------
# Release CI failure fixture: creates/surfaces remediation
# ---------------------------------------------------------------------------


class TestMonitorMergedDeliveryCi:
    """Fixture-driven tests for release-branch CI monitoring after delivery merge."""

    def test_ci_failure_creates_remediation_task(self):
        """CI failed on release branch → remediation task is created and stamped."""
        d = _delivery(ci_remediation_task_id=None, result_commits=[_RESULT_SHA])
        _orch, created, store = _make_orchestrator([d], ci_status="failed")

        assert len(created) == 1, (
            "Expected exactly one remediation task to be created; "
            f"got {len(created)}"
        )
        task_kwargs = created[0]
        assert "release" in task_kwargs["title"].lower() or "ci" in task_kwargs["title"].lower()
        assert "release/0.11" in task_kwargs["description"]
        assert "Acceptance Criteria" in task_kwargs["description"]
        assert task_kwargs["labels"] == ["release-ci-failure", "ci-fix"]
        # Verify idempotency stamp was set
        assert store._deliveries[0].ci_remediation_task_id == "OOMPAH-1"

    def test_ci_passed_no_remediation(self):
        """Passed CI → no remediation task."""
        d = _delivery(ci_remediation_task_id=None, result_commits=[_RESULT_SHA])
        _orch, created, _store = _make_orchestrator([d], ci_status="passed")
        assert len(created) == 0

    def test_ci_pending_no_remediation(self):
        """Pending CI → no remediation task (not yet actionable)."""
        d = _delivery(ci_remediation_task_id=None, result_commits=[_RESULT_SHA])
        _orch, created, _store = _make_orchestrator([d], ci_status="pending")
        assert len(created) == 0

    def test_ci_unknown_no_remediation(self):
        """Unknown CI status ('') → no remediation task."""
        d = _delivery(ci_remediation_task_id=None, result_commits=[_RESULT_SHA])
        _orch, created, _store = _make_orchestrator([d], ci_status="")
        assert len(created) == 0

    def test_already_remediated_delivery_skipped(self):
        """Delivery with ci_remediation_task_id already set → no new task."""
        d = _delivery(ci_remediation_task_id="OOMPAH-50", result_commits=[_RESULT_SHA])
        _orch, created, _store = _make_orchestrator([d], ci_status="failed")
        assert len(created) == 0, (
            "Already-remediated delivery should be skipped (idempotency)"
        )

    def test_stale_global_remediation_reference_is_replaced(self):
        """A legacy global issue ID must not block a project-local task."""
        d = _delivery(ci_remediation_task_id="OOMPAH-481", result_commits=[_RESULT_SHA])
        _orch, created, store = _make_orchestrator(
            [d],
            ci_status="failed",
            existing_remediation_task_ids=set(),
        )

        assert len(created) == 1
        assert store._deliveries[0].ci_remediation_task_id == "OOMPAH-1"

    def test_non_merged_delivery_skipped(self):
        """open/in_review/blocked deliveries are not monitored."""
        deliveries = [
            _delivery(
                delivery_id=f"rd_{s}",
                status=s,
                ci_remediation_task_id=None,
                result_commits=[_RESULT_SHA],
            )
            for s in (
                AddendumStatus.OPEN,
                AddendumStatus.IN_PROGRESS,
                AddendumStatus.IN_REVIEW,
                AddendumStatus.BLOCKED,
            )
        ]
        _orch, created, _store = _make_orchestrator(deliveries, ci_status="failed")
        assert len(created) == 0, (
            "Non-merged deliveries should never trigger CI remediation"
        )

    def test_merged_delivery_without_result_commits_skipped(self):
        """Merged deliveries with empty result_commits are not monitored."""
        d = _delivery(
            ci_remediation_task_id=None,
            result_commits=[],  # no evidence of what landed
        )
        _orch, created, _store = _make_orchestrator([d], ci_status="failed")
        assert len(created) == 0, (
            "Merged delivery without result_commits must be skipped "
            "(no evidence of what actually landed on the release branch)"
        )

    def test_project_without_repo_url_skipped(self):
        """Projects without repo_url are never monitored."""
        d = _delivery(ci_remediation_task_id=None, result_commits=[_RESULT_SHA])
        # Pass an empty repo_url — orchestrator should skip entirely
        _orch, created, _store = _make_orchestrator([d], ci_status="failed", repo_url="")
        assert len(created) == 0

    def test_remediation_task_content_is_actionable(self):
        """Remediation task description contains actionable CI fix information."""
        d = _delivery(
            ci_remediation_task_id=None,
            result_commits=[_RESULT_SHA],
            target_branch="release/0.11",
            pr_url="https://github.com/org/trickle/pull/303",
        )
        _orch, created, _store = _make_orchestrator([d], ci_status="failed")

        assert len(created) == 1
        desc = created[0]["description"]
        # Must reference the target branch clearly
        assert "release/0.11" in desc
        # Must contain the delivery ID for traceability
        assert "rd_ci_001" in desc
        # Must have actionable guidance
        assert "CI" in desc or "ci" in desc.lower()

    def test_create_issue_failure_does_not_propagate(self):
        """A create_issue failure is caught and does not crash the monitor."""
        d = _delivery(ci_remediation_task_id=None, result_commits=[_RESULT_SHA])
        # Should not raise even though create_issue raises internally
        _orch, created, _store = _make_orchestrator(
            [d], ci_status="failed", raise_on_create=True
        )
        # No task created, but no exception either
        assert len(created) == 0

    def test_multiple_merged_deliveries_all_remediated(self):
        """Each merged delivery with CI failure gets its own remediation task."""
        d1 = _delivery(delivery_id="rd_1", ci_remediation_task_id=None, result_commits=[_SHA_A])
        d2 = _delivery(delivery_id="rd_2", ci_remediation_task_id=None, result_commits=[_SHA_B])
        _orch, created, store = _make_orchestrator([d1, d2], ci_status="failed")

        assert len(created) == 2
        # Both deliveries should be stamped
        stamped = [d.ci_remediation_task_id for d in store._deliveries]
        assert all(t is not None for t in stamped)

    def test_idempotency_across_ticks(self):
        """Second call with ci_remediation_task_id already set → no second task."""
        d = _delivery(ci_remediation_task_id=None, result_commits=[_RESULT_SHA])
        _orch1, created1, store = _make_orchestrator([d], ci_status="failed")
        assert len(created1) == 1

        # Simulate second tick — the delivery now has ci_remediation_task_id
        # (as written by the first tick)
        d_after = store._deliveries[0]
        _orch2, created2, _store2 = _make_orchestrator([d_after], ci_status="failed")
        assert len(created2) == 0, "Second tick must not create a duplicate remediation task"


# ---------------------------------------------------------------------------
# Queue integration: sync_source_branch=False in orchestrator
# ---------------------------------------------------------------------------


class TestQueueIntegrationSyncSourceBranchFalse:
    """Verify that the orchestrator calls cherry_pick_delivery with sync_source_branch=False.

    This is the regression guard for PR #303 where sync_source_branch=True
    caused all of main to be merged into release/0.11 despite an explicit
    selected-commit delivery.
    """

    def test_orchestrator_passes_sync_source_branch_false(self):
        """_process_release_delivery_queue must pass sync_source_branch=False."""
        from oompah.release_delivery_queue import ReleaseDeliveryQueue
        from oompah.orchestrator import Orchestrator
        from oompah.release_addendum_schema import AddendumStatus

        delivery = _delivery(
            status=AddendumStatus.OPEN,
            ci_remediation_task_id=None,
            result_commits=[],
        )

        # Patch ReleaseDeliveryQueue.claim_one to return our delivery as a queue item
        mock_item = SimpleNamespace(
            delivery_id=delivery.id,
            project_id=PROJECT_ID,
            delivery=delivery,
        )

        project = SimpleNamespace(
            id=PROJECT_ID,
            name="trickle",
            repo_url="https://github.com/org/trickle",
            access_token=None,
        )

        captured_kwargs: list[dict] = []

        def _fake_cherry_pick(store, delivery, **kwargs):
            captured_kwargs.append(kwargs)
            return dataclasses.replace(delivery, status=AddendumStatus.IN_REVIEW)

        mock_queue = MagicMock()
        mock_queue.claim_one.return_value = mock_item
        mock_store = MagicMock()
        mock_scm = MagicMock()

        class _FakeOrchestrator:
            project_store = SimpleNamespace(list_all=lambda: [project])

            def _tracker_for_project(self, pid):
                return MagicMock()

            def _job_deadline_exceeded(self, _label):
                return False

            _process_release_delivery_queue = Orchestrator._process_release_delivery_queue

        orch = _FakeOrchestrator()

        with (
            patch("oompah.orchestrator.make_delivery_store", return_value=mock_store),
            patch(
                "oompah.orchestrator.ReleaseDeliveryQueue",
                return_value=mock_queue,
            ),
            patch("oompah.orchestrator.detect_provider", return_value=mock_scm),
            patch("oompah.orchestrator.extract_repo_slug", return_value="org/trickle"),
            patch("oompah.orchestrator.cherry_pick_delivery", side_effect=_fake_cherry_pick),
        ):
            Orchestrator._process_release_delivery_queue(orch)

        assert len(captured_kwargs) == 1, (
            "cherry_pick_delivery should have been called once"
        )
        kwargs = captured_kwargs[0]
        assert "sync_source_branch" in kwargs, (
            "cherry_pick_delivery must be called with explicit sync_source_branch"
        )
        assert kwargs["sync_source_branch"] is False, (
            f"sync_source_branch must be False (got {kwargs['sync_source_branch']!r}); "
            "passing True was the root cause of PR #303 merging all of main into "
            "release/0.11 despite a selected-commit delivery"
        )

    def test_selected_commits_only_no_source_branch_in_release(self):
        """E2E invariant: source_commits are applied; source branch is not merged.

        This is the core regression guard: a selected delivery (source_commits=[A, B])
        must NEVER write any commit to the release branch other than those two commits
        (plus the required delivery metadata commit from the git writer).
        """
        from oompah.release_delivery_executor import cherry_pick_delivery
        from oompah.release_addendum_schema import AddendumStatus

        selected_sha_1 = "1" * 40
        selected_sha_2 = "2" * 40

        d = dataclasses.replace(
            _delivery(result_commits=[]),
            status=AddendumStatus.IN_PROGRESS,
            source_commits=[selected_sha_1, selected_sha_2],
        )
        store = _FakeStore([d])
        ps = MagicMock()
        ps.create_worktree.return_value = "/fake/release/wt"

        merge_calls: list[tuple[str, str]] = []
        apply_calls: list[list[str]] = []

        def _capture_merge(wt: str, branch: str) -> None:
            merge_calls.append((wt, branch))

        def _capture_apply(wt: str, commits: list[str]) -> None:
            apply_calls.append(list(commits))

        scm = MagicMock()
        scm.find_pr_for_branch.return_value = None
        scm.create_review.return_value = SimpleNamespace(
            url="https://github.com/org/trickle/pull/999",
            id=999,
            number=999,
            state="open",
        )

        with (
            patch("oompah.release_delivery_executor._merge_source_branch", side_effect=_capture_merge),
            patch("oompah.release_delivery_executor._has_new_commits", return_value=False),
            patch("oompah.release_delivery_executor.apply_cherry_pick", side_effect=_capture_apply),
            patch("oompah.release_delivery_executor.push_branch"),
            patch(
                "oompah.release_delivery_executor._get_result_commits",
                return_value=[selected_sha_1, selected_sha_2],
            ),
        ):
            result = cherry_pick_delivery(
                store,
                d,
                project_store=ps,
                project_id=PROJECT_ID,
                scm=scm,
                repo="org/trickle",
                sync_source_branch=False,
            )

        # The source branch must never be merged
        assert merge_calls == [], (
            f"Source branch was merged {len(merge_calls)} time(s); "
            "a selected delivery must ONLY apply its source_commits"
        )

        # Exactly the selected commits were applied
        assert len(apply_calls) == 1
        assert apply_calls[0] == [selected_sha_1, selected_sha_2]

        assert result.status is AddendumStatus.IN_REVIEW


# ---------------------------------------------------------------------------
# SCM: get_branch_head_sha and get_ci_status_for_sha
# ---------------------------------------------------------------------------


class TestGetBranchHeadSha:
    """Unit tests for GitHubProvider.get_branch_head_sha."""

    def _make_github(self):
        from oompah.scm import GitHubProvider
        gh = object.__new__(GitHubProvider)
        return gh

    def test_returns_sha_for_known_branch(self):
        from oompah.scm import GitHubProvider
        gh = self._make_github()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "ref": "refs/heads/release/0.11",
                "object": {"sha": "a" * 40, "type": "commit"},
            }
        ]
        with patch.object(gh, "_api", return_value=mock_resp):
            sha = GitHubProvider.get_branch_head_sha(gh, "org/repo", "release/0.11")
        assert sha == "a" * 40

    def test_returns_none_for_missing_branch(self):
        from oompah.scm import GitHubProvider
        gh = self._make_github()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"message": "Not Found"}
        with patch.object(gh, "_api", return_value=mock_resp):
            sha = GitHubProvider.get_branch_head_sha(gh, "org/repo", "release/9.9")
        assert sha is None

    def test_returns_none_on_api_error(self):
        import httpx
        from oompah.scm import GitHubProvider
        gh = self._make_github()
        with patch.object(gh, "_api", side_effect=httpx.HTTPError("timeout")):
            sha = GitHubProvider.get_branch_head_sha(gh, "org/repo", "release/0.11")
        assert sha is None

    def test_single_dict_response_normalised(self):
        """GitHub may return a single dict (exact ref match) instead of a list."""
        from oompah.scm import GitHubProvider
        gh = self._make_github()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ref": "refs/heads/main",
            "object": {"sha": "b" * 40},
        }
        with patch.object(gh, "_api", return_value=mock_resp):
            sha = GitHubProvider.get_branch_head_sha(gh, "org/repo", "main")
        assert sha == "b" * 40


class TestGetCiStatusForSha:
    """Unit tests for GitHubProvider.get_ci_status_for_sha."""

    def _make_github(self):
        from oompah.scm import GitHubProvider
        gh = object.__new__(GitHubProvider)
        return gh

    def test_delegates_to_fetch_ci_status(self):
        from oompah.scm import GitHubProvider
        gh = self._make_github()
        with patch.object(gh, "_fetch_ci_status", return_value="passed") as mock_fetch:
            status = GitHubProvider.get_ci_status_for_sha(gh, "org/repo", "a" * 40)
        mock_fetch.assert_called_once_with("org/repo", "a" * 40)
        assert status == "passed"

    def test_returns_empty_on_exception(self):
        from oompah.scm import GitHubProvider
        gh = self._make_github()
        with patch.object(gh, "_fetch_ci_status", side_effect=RuntimeError("network")):
            status = GitHubProvider.get_ci_status_for_sha(gh, "org/repo", "a" * 40)
        from oompah.scm import CIStatus
        assert status is CIStatus.UNKNOWN


class TestGetBranchCiStatus:
    """Unit tests for the default SCMProvider.get_branch_ci_status."""

    def test_chains_head_sha_and_ci_status(self):
        from oompah.scm import SCMProvider

        class _FakeSCM(SCMProvider):
            # Minimal implementations to satisfy ABC
            def list_open_reviews(self, repo): return []
            def list_merged_branches(self, repo): return set()
            def list_merged_reviews(self, repo): return []
            def find_pr_for_branch(self, repo, branch): return None
            def get_review(self, repo, review_id): return None
            def create_review(self, repo, title, source_branch, target_branch="main", description=""): return None
            def rebase_review(self, repo, review_id): return False, ""
            def needs_rebase(self, repo, review_id): return False
            def merge_review(self, repo, review_id): return False, ""
            def close_review(self, repo, review_id, comment=""): return False, ""
            def enable_auto_merge(self, repo, review_id): return False, ""
            def is_available(self): return True
            def provider_name(self): return "fake"
            def get_review_files(self, repo, review_id): return []
            def add_review_label(self, repo, review_id, label): pass
            def remove_review_label(self, repo, review_id, label): pass

            def get_branch_head_sha(self, repo, branch):
                return "c" * 40

            def get_ci_status_for_sha(self, repo, sha):
                assert sha == "c" * 40
                return "failed"

        scm = _FakeSCM()
        result = scm.get_branch_ci_status("org/repo", "release/0.11")
        assert result == "failed"

    def test_returns_empty_when_no_head_sha(self):
        from oompah.scm import SCMProvider

        class _FakeSCM(SCMProvider):
            def list_open_reviews(self, repo): return []
            def list_merged_branches(self, repo): return set()
            def list_merged_reviews(self, repo): return []
            def find_pr_for_branch(self, repo, branch): return None
            def get_review(self, repo, review_id): return None
            def create_review(self, repo, title, source_branch, target_branch="main", description=""): return None
            def rebase_review(self, repo, review_id): return False, ""
            def needs_rebase(self, repo, review_id): return False
            def merge_review(self, repo, review_id): return False, ""
            def close_review(self, repo, review_id, comment=""): return False, ""
            def enable_auto_merge(self, repo, review_id): return False, ""
            def is_available(self): return True
            def provider_name(self): return "fake"
            def get_review_files(self, repo, review_id): return []
            def add_review_label(self, repo, review_id, label): pass
            def remove_review_label(self, repo, review_id, label): pass

            def get_branch_head_sha(self, repo, branch):
                return None  # branch not found

        scm = _FakeSCM()
        result = scm.get_branch_ci_status("org/repo", "release/0.11")
        from oompah.scm import CIStatus
        assert result is CIStatus.UNKNOWN
