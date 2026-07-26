"""Regression tests for OOMPAH-449: post-synchronize CI check race.

Timeline reproduced from PR #555 (2026-07-26):

  T+0s  PR #555 receives new head ed815c908 via synchronize webhook.
  T+3s  Oompah queries combined status + check-runs — both APIs return
        empty (workflow not registered yet).
  T+4s  GitHub creates the workflow run.
  T+6s  Workflow jobs start.
  T+7s  YOLO merged the PR.  ← BUG: CI had not finished.
  T+6m  CI matrix completes.

Root cause: GitHubProvider._fetch_ci_status_and_warnings returned "passed"
for empty check sets, and the YOLO gate accepted "passed".

Fix: repos known to use CI (have had non-empty check-runs at any point in
the process lifetime) fail-closed: empty check sets → "pending".  Repos
never seen with checks keep the old "passed" behaviour.

Test matrix
-----------
1. Known-CI repo: old SHA failed → synchronize → new SHA empty → pending
   → checks register (pending) → checks pass — no merge during empty window,
   merge eligible after "passed".
2. No-CI repo: empty checks always → "passed" → YOLO merges immediately.
3. Stale prior-SHA verdict: after synchronize, the new SHA's CI is
   evaluated independently — no old-SHA result is inherited.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from oompah.scm import GitHubProvider, ReviewRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    project_id: str = "proj-1",
    repo_url: str = "https://github.com/org/repo",
    yolo: bool = True,
    merge_queue_enabled: bool = False,
):
    p = MagicMock()
    p.id = project_id
    p.name = "test-project"
    p.repo_url = repo_url
    p.yolo = yolo
    p.default_branch = "main"
    p.merge_queue_enabled = merge_queue_enabled
    p.churn_magnet_gate_enabled = False
    p.access_token = None
    return p


def _make_review(
    review_id: str = "555",
    ci_status: str = "passed",
    source_branch: str = "OOMPAH-447",
    target_branch: str = "main",
    has_conflicts: bool = False,
    needs_rebase: bool = False,
    auto_merge_enabled: bool = False,
    draft: bool = False,
) -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title=f"PR #{review_id}",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="alice",
        state="open",
        source_branch=source_branch,
        target_branch=target_branch,
        created_at="2026-07-26T04:26:36Z",
        updated_at="2026-07-26T04:26:37Z",
        ci_status=ci_status,
        has_conflicts=has_conflicts,
        needs_rebase=needs_rebase,
        auto_merge_enabled=auto_merge_enabled,
        draft=draft,
    )


def _ci_fetch_side_effect(responses: list[tuple[str, list[dict]]]):
    """Build a fake _fetch_ci_status_and_warnings that returns a sequence.

    ``responses`` is a list of (status, warnings) tuples returned in order.
    """
    it = iter(responses)

    def _fake(repo, sha):
        return next(it)

    return _fake


# ---------------------------------------------------------------------------
# Unit tests: _fetch_ci_status_and_warnings race guard (OOMPAH-449)
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class TestCISyncRaceGuard:
    """Direct unit tests for the post-synchronize empty-check guard."""

    def _provider(self, status_payload, checkruns_payload):
        provider = GitHubProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if path.endswith("/status"):
                return FakeResponse(status_payload)
            if path.endswith("/check-runs"):
                return FakeResponse(checkruns_payload)
            raise AssertionError(f"unexpected API call: {path}")

        provider._api = fake_api
        return provider

    def _clean_ci_active(self, repo):
        """Remove repo from _ci_active_repos for test isolation."""
        with GitHubProvider._ci_active_repos_lock:
            GitHubProvider._ci_active_repos.discard(repo)

    def _mark_ci_active(self, repo):
        """Directly mark repo as CI-active (simulates prior check-runs seen)."""
        with GitHubProvider._ci_active_repos_lock:
            GitHubProvider._ci_active_repos.add(repo)

    def _is_ci_active(self, repo) -> bool:
        with GitHubProvider._ci_active_repos_lock:
            return repo in GitHubProvider._ci_active_repos

    # -- No-CI repos must still merge immediately --------------------------

    def test_no_ci_repo_empty_checks_passes(self):
        """Repo never seen with CI → empty checks → 'passed' (no-CI YOLO preserved)."""
        self._clean_ci_active("o/no-ci")
        provider = self._provider(
            {"state": "pending", "total_count": 0},
            {"check_runs": []},
        )
        status, _ = provider._fetch_ci_status_and_warnings("o/no-ci", "abc1")
        assert status == "passed"
        # And the repo was NOT marked CI-active (no checks seen)
        assert not self._is_ci_active("o/no-ci")

    # -- Known-CI repos fail closed ----------------------------------------

    def test_known_ci_repo_empty_checks_returns_pending(self):
        """Repo known to use CI → empty checks on new SHA → 'pending'."""
        repo = "o/known-ci"
        self._mark_ci_active(repo)
        try:
            provider = self._provider(
                {"state": "pending", "total_count": 0},
                {"check_runs": []},
            )
            status, _ = provider._fetch_ci_status_and_warnings(repo, "newsha123")
            assert status == "pending", (
                "fail-closed: known-CI repo must not synthesize 'passed' "
                "before checks register"
            )
        finally:
            self._clean_ci_active(repo)

    # -- Seeing checks marks the repo as CI-active -------------------------

    def test_non_empty_checks_mark_repo_ci_active(self):
        """Observing check-runs for a repo registers it as CI-active."""
        repo = "o/new-ci-repo"
        self._clean_ci_active(repo)
        provider = self._provider(
            {"state": "pending", "total_count": 0},
            {"check_runs": [{"conclusion": "success", "status": "completed"}]},
        )
        try:
            status, _ = provider._fetch_ci_status_and_warnings(repo, "sha-ok")
            assert status == "passed"
            assert self._is_ci_active(repo), (
                "after observing non-empty check-runs, repo must be in _ci_active_repos"
            )
        finally:
            self._clean_ci_active(repo)

    # -- Full PR #555 sequence (old-SHA-failed → synchronize → empty → pending → passed)

    def test_pr555_sequence_empty_window_returns_pending(self):
        """Reproduce the PR #555 race:

        1. Old SHA: CI failed (would normally retry)
        2. Synchronize → new SHA.  Empty check-runs response (race window).
        3. New SHA: checks register as pending.
        4. New SHA: all checks pass.

        Assert: step 2 returns 'pending' (not 'passed') so YOLO cannot merge.
        Assert: step 4 returns 'passed' so YOLO can merge normally.
        """
        repo = "org/repo"
        old_sha = "ed815c900"  # approximate PR #555 timeline
        new_sha = "ed815c908"

        # Make repo CI-active (simulates prior successful CI runs)
        self._mark_ci_active(repo)
        try:
            # Step 2 — empty check-runs immediately after synchronize
            p_empty = self._provider(
                {"state": "pending", "total_count": 0},
                {"check_runs": []},
            )
            status_empty, _ = p_empty._fetch_ci_status_and_warnings(repo, new_sha)
            assert status_empty == "pending", (
                f"Expected 'pending' during empty check window, got {status_empty!r}. "
                "YOLO must not merge during the post-synchronize race."
            )

            # Step 3 — checks have registered but are still running
            p_pending = self._provider(
                {"state": "pending", "total_count": 0},
                {"check_runs": [
                    {"conclusion": None, "status": "in_progress"},
                    {"conclusion": None, "status": "queued"},
                ]},
            )
            status_pending, _ = p_pending._fetch_ci_status_and_warnings(repo, new_sha)
            assert status_pending == "pending"

            # Step 4 — all checks passed
            p_passed = self._provider(
                {"state": "pending", "total_count": 0},
                {"check_runs": [
                    {"conclusion": "success", "status": "completed"},
                    {"conclusion": "success", "status": "completed"},
                ]},
            )
            status_passed, _ = p_passed._fetch_ci_status_and_warnings(repo, new_sha)
            assert status_passed == "passed", (
                "Once checks pass, 'passed' must be returned so YOLO can merge."
            )
        finally:
            self._clean_ci_active(repo)

    def test_stale_prior_sha_verdict_not_inherited(self):
        """New SHA's CI verdict is independent from the old SHA's verdict.

        Scenario: old SHA had 'failed' CI. After synchronize, the new SHA
        gets empty checks (CI not yet registered). The new SHA must NOT
        inherit the old SHA's 'failed' state — it gets 'pending' (fail-closed)
        because the repo is CI-active.
        """
        repo = "org/repo-stale"
        old_sha = "oldsha"
        new_sha = "newsha"
        self._mark_ci_active(repo)
        try:
            # Old SHA: failed
            p_old = self._provider(
                {"state": "pending", "total_count": 0},
                {"check_runs": [{"conclusion": "failure", "status": "completed"}]},
            )
            old_status, _ = p_old._fetch_ci_status_and_warnings(repo, old_sha)
            assert old_status == "failed"

            # New SHA: empty checks (different provider with empty payload)
            p_new = self._provider(
                {"state": "pending", "total_count": 0},
                {"check_runs": []},
            )
            new_status, _ = p_new._fetch_ci_status_and_warnings(repo, new_sha)
            # Must be pending (fail-closed), NOT 'failed' (no inheritance) or
            # 'passed' (no race bypass)
            assert new_status == "pending", (
                f"New SHA must get independent verdict; got {new_status!r}. "
                "Neither inherit old-SHA 'failed' nor bypass to 'passed'."
            )
        finally:
            self._clean_ci_active(repo)

    def test_legacy_failure_plus_empty_checks_still_fails_for_known_ci(self):
        """When there's a legacy failure and empty modern checks, fail wins.

        The legacy_failure path takes precedence over the CI-active guard,
        so repos with stale legacy failures still return 'failed'.
        """
        repo = "org/legacy-fail-repo"
        self._mark_ci_active(repo)
        try:
            provider = self._provider(
                {"state": "failure", "total_count": 1},  # legacy failure
                {"check_runs": []},  # no modern checks
            )
            status, _ = provider._fetch_ci_status_and_warnings(repo, "sha")
            assert status == "failed"
        finally:
            self._clean_ci_active(repo)


# ---------------------------------------------------------------------------
# Integration-level test: YOLO gate respects pending CI
# ---------------------------------------------------------------------------


class TestYoloGateCiSyncRace:
    """YOLO must not merge/enqueue a PR whose CI is 'pending'.

    These tests verify the YOLO gate in _yolo_review_actions_sync correctly
    refuses to merge when ci_status='pending' (the post-synchronize state).
    """

    def _make_orch(self, tmp_path, projects):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator
        from oompah.roles import RoleStore

        project_store = MagicMock()
        project_store.list_all.return_value = list(projects)
        project_store.get.side_effect = lambda pid: next(
            (p for p in projects if p.id == pid), None
        )
        project_store.epic_branch_name = MagicMock(side_effect=lambda i: f"epic-{i}")
        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        return Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            role_store=role_store,
            state_path=str(tmp_path / "state.json"),
        )

    def test_pending_ci_blocks_merge(self, tmp_path):
        """ci_status='pending' must prevent merge/enqueue (the race window)."""
        project = _make_project()
        orch = self._make_orch(tmp_path, [project])

        provider = MagicMock()
        provider.merge_review = MagicMock(return_value=(True, "merged"))
        provider.enable_auto_merge = MagicMock(return_value=(True, "queued"))

        # Simulate post-synchronize state: pending CI (checks registered but running)
        review = _make_review(ci_status="pending", has_conflicts=False, needs_rebase=False)
        orch._reviews_cache = {project.id: [review]}
        orch._yolo_epic_strategy_block_reason = MagicMock(return_value=None)
        orch._tracker_for_project = MagicMock(return_value=MagicMock())

        with (
            MagicMock() as mock_detect,
            MagicMock() as mock_slug,
        ):
            import unittest.mock as mock_module
            with (
                mock_module.patch("oompah.orchestrator.detect_provider", return_value=provider),
                mock_module.patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
            ):
                orch._yolo_review_actions_sync()

        # Neither merge nor enqueue should have been called
        provider.merge_review.assert_not_called()
        provider.enable_auto_merge.assert_not_called()

    def test_no_ci_repo_passes_and_merges(self, tmp_path):
        """Repos not in _ci_active_repos get ci_status='passed' → YOLO merges.

        _fetch_ci_status_and_warnings returns 'passed' for repos never seen
        with CI checks (no-CI repos).  The ReviewRequest stores 'passed' and
        the YOLO gate allows the merge.  This confirms no-CI YOLO behavior is
        preserved end-to-end (OOMPAH-449 acceptance criterion #4).
        """
        project = _make_project()
        orch = self._make_orch(tmp_path, [project])

        provider = MagicMock()
        provider.merge_review = MagicMock(return_value=(True, "merged"))

        # No-CI repos get ci_status='passed' from _fetch_ci_status_and_warnings
        review = _make_review(ci_status="passed", has_conflicts=False, needs_rebase=False)
        orch._reviews_cache = {project.id: [review]}
        orch._yolo_epic_strategy_block_reason = MagicMock(return_value=None)
        orch._tracker_for_project = MagicMock(return_value=MagicMock())

        import unittest.mock as mock_module
        with (
            mock_module.patch("oompah.orchestrator.detect_provider", return_value=provider),
            mock_module.patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._yolo_review_actions_sync()

        # A no-CI repo with 'passed' status should merge immediately
        provider.merge_review.assert_called_once()

    def test_passed_ci_triggers_merge(self, tmp_path):
        """After CI checks pass, YOLO merges normally."""
        project = _make_project()
        orch = self._make_orch(tmp_path, [project])

        provider = MagicMock()
        provider.merge_review = MagicMock(return_value=(True, "merged"))

        review = _make_review(ci_status="passed", has_conflicts=False, needs_rebase=False)
        orch._reviews_cache = {project.id: [review]}
        orch._yolo_epic_strategy_block_reason = MagicMock(return_value=None)
        orch._tracker_for_project = MagicMock(return_value=MagicMock())

        import unittest.mock as mock_module
        with (
            mock_module.patch("oompah.orchestrator.detect_provider", return_value=provider),
            mock_module.patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
        ):
            orch._yolo_review_actions_sync()

        provider.merge_review.assert_called_once()

    def test_full_pr555_sequence_no_premature_merge(self, tmp_path):
        """Full regression sequence for PR #555.

        Phase 1 (old SHA, failed CI): YOLO retries CI, no merge.
        Phase 2 (new SHA, empty checks post-synchronize): no merge.
        Phase 3 (new SHA, checks pending): no merge.
        Phase 4 (new SHA, checks passed): merge fires.
        """
        project = _make_project()
        orch = self._make_orch(tmp_path, [project])

        provider = MagicMock()
        provider.merge_review = MagicMock(return_value=(True, "merged"))
        orch._tracker_for_project = MagicMock(return_value=MagicMock())
        orch._yolo_epic_strategy_block_reason = MagicMock(return_value=None)
        orch._yolo_retry_ci = MagicMock()  # suppress real tracker calls

        import unittest.mock as mock_module

        def _run_yolo(ci_status: str):
            review = _make_review(
                ci_status=ci_status, has_conflicts=False, needs_rebase=False
            )
            orch._reviews_cache = {project.id: [review]}
            with (
                mock_module.patch(
                    "oompah.orchestrator.detect_provider", return_value=provider
                ),
                mock_module.patch(
                    "oompah.orchestrator.extract_repo_slug", return_value="org/repo"
                ),
            ):
                orch._yolo_review_actions_sync()

        # Phase 1: old SHA failed — YOLO should retry CI, not merge
        _run_yolo("failed")
        provider.merge_review.assert_not_called()
        orch._yolo_retry_ci.assert_called_once()

        # Phase 2: new SHA, empty checks (post-synchronize race window)
        # ci_status='pending' (as returned by _fetch_ci_status_and_warnings
        # for a known-CI repo with empty checks after our fix)
        _run_yolo("pending")
        provider.merge_review.assert_not_called()

        # Phase 3: checks registered but still running
        _run_yolo("pending")
        provider.merge_review.assert_not_called()

        # Phase 4: checks passed — merge should fire
        _run_yolo("passed")
        provider.merge_review.assert_called_once()
