"""Tests for the managed-project issue template refresh workflow.

Covers:
- Template drift detection (all current, some drifted, all absent)
- Preview output (unified diff string)
- Apply behavior (writes files, commits, pushes)
- Dirty-worktree conflict handling (refuses when files have uncommitted changes)
- Server API endpoints (status, preview, apply) via TestClient
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.issue_template_refresh import (
    CANONICAL_TEMPLATES,
    TEMPLATE_SUBDIR,
    TemplateDrift,
    TemplateApplyResult,
    TemplateRefreshStatus,
    apply_template_updates,
    check_template_drift,
    ensure_issue_templates,
    preview_template_updates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_managed_repo(tmp_path: Path, *, write_templates: bool = True) -> Path:
    """Initialise a bare git repo at *tmp_path* and optionally plant canonical templates."""
    repo = tmp_path / "managed-repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )

    # Write an initial commit so HEAD exists.
    readme = repo / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )

    if write_templates:
        _write_canonical_templates(repo)

    return repo


def _write_canonical_templates(repo: Path) -> None:
    """Write all canonical templates into the repo (and commit them)."""
    template_dir = repo / TEMPLATE_SUBDIR
    template_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in CANONICAL_TEMPLATES.items():
        (template_dir / filename).write_text(content)
    subprocess.run(
        ["git", "add", TEMPLATE_SUBDIR],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "add canonical templates"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


class TestCheckTemplateDrift:
    def test_all_current_when_templates_match(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        status = check_template_drift(repo)
        assert status.all_current is True
        assert len(status.drifted) == 0
        assert len(status.current) == len(CANONICAL_TEMPLATES)

    def test_all_drifted_when_no_templates(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        status = check_template_drift(repo)
        assert status.all_current is False
        assert len(status.drifted) == len(CANONICAL_TEMPLATES)
        assert len(status.current) == 0
        for drift in status.drifted:
            assert drift.current is None
            assert drift.is_current is False
            assert drift.diff != ""

    def test_partial_drift_one_file_changed(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        # Corrupt one template.
        bug = repo / TEMPLATE_SUBDIR / "bug_report.yml"
        bug.write_text("name: Old Bug\n")

        status = check_template_drift(repo)
        assert status.all_current is False
        drifted_names = {d.filename for d in status.drifted}
        assert "bug_report.yml" in drifted_names
        assert "feature_request.yml" not in drifted_names
        assert "question.yml" not in drifted_names

    def test_drift_contains_unified_diff(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        status = check_template_drift(repo)
        # Every drifted entry should have a diff starting with "---".
        for drift in status.drifted:
            assert "---" in drift.diff
            assert "+++" in drift.diff

    def test_is_current_true_for_matching_file(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        status = check_template_drift(repo)
        for drift in status.current:
            assert drift.is_current is True
            assert drift.diff == ""
            assert drift.current == CANONICAL_TEMPLATES[drift.filename]


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


class TestPreviewTemplateUpdates:
    def test_returns_empty_when_current(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        diff = preview_template_updates(repo)
        assert diff == ""

    def test_returns_diff_when_drifted(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        diff = preview_template_updates(repo)
        assert diff != ""
        assert "+++" in diff

    def test_diff_covers_all_drifted_templates(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        diff = preview_template_updates(repo)
        for filename in CANONICAL_TEMPLATES:
            assert filename in diff


# ---------------------------------------------------------------------------
# Dirty-worktree detection
# ---------------------------------------------------------------------------


class TestDirtyWorktreeHandling:
    def test_refuses_when_template_file_is_dirty(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        # Corrupt and don't commit — makes the file dirty.
        bug = repo / TEMPLATE_SUBDIR / "bug_report.yml"
        bug.write_text("dirty content\n")

        result = apply_template_updates(repo, push=False)

        assert result.error != ""
        assert "Refused" in result.error
        assert "uncommitted changes" in result.error
        assert "bug_report.yml" in result.error or TEMPLATE_SUBDIR in result.error

    def test_allows_apply_when_only_unrelated_files_are_dirty(self, tmp_path: Path) -> None:
        """Unrelated uncommitted changes must not block a template-only update."""
        repo = _make_managed_repo(tmp_path, write_templates=False)
        # Write an unrelated uncommitted file.
        (repo / "unrelated.txt").write_text("untracked\n")

        result = apply_template_updates(repo, push=False)

        # Dirty worktree check only covers the template paths — unrelated
        # files should not block the apply.
        assert result.error == "" or "unrelated" not in result.error
        assert len(result.applied) > 0

    def test_no_conflict_when_all_templates_current(self, tmp_path: Path) -> None:
        """When all templates match canonical, dirty-worktree check is irrelevant."""
        repo = _make_managed_repo(tmp_path, write_templates=True)
        # Dirty an unrelated file.
        (repo / "unrelated.txt").write_text("untracked\n")

        result = apply_template_updates(repo, push=False)

        # Nothing to apply — no error.
        assert result.error == ""
        assert result.applied == []


# ---------------------------------------------------------------------------
# Apply behavior
# ---------------------------------------------------------------------------


class TestApplyTemplateUpdates:
    def test_writes_canonical_templates_to_repo(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        result = apply_template_updates(repo, push=False)

        assert result.error == ""
        assert len(result.applied) == len(CANONICAL_TEMPLATES)
        for filename, canonical in CANONICAL_TEMPLATES.items():
            actual = (repo / TEMPLATE_SUBDIR / filename).read_text(encoding="utf-8")
            assert actual == canonical

    def test_commits_with_expected_message(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        apply_template_updates(repo, push=False)

        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert "canonical issue templates" in log.stdout

    def test_commit_sha_is_populated(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        result = apply_template_updates(repo, push=False)

        assert result.commit_sha != ""
        assert len(result.commit_sha) == 40

    def test_skipped_when_all_current(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        result = apply_template_updates(repo, push=False)

        assert result.error == ""
        assert result.applied == []
        assert len(result.skipped) == len(CANONICAL_TEMPLATES)
        assert result.commit_sha == ""

    def test_skips_already_current_files(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        # Only corrupt one template.
        bug = repo / TEMPLATE_SUBDIR / "bug_report.yml"
        old_content = "name: Outdated Bug\n"
        bug.write_text(old_content)
        subprocess.run(
            ["git", "add", str(bug)],
            cwd=str(repo),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "corrupt bug template"],
            cwd=str(repo),
            check=True,
            capture_output=True,
        )

        result = apply_template_updates(repo, push=False)

        assert result.error == ""
        assert len(result.applied) == 1
        assert any("bug_report.yml" in p for p in result.applied)
        # Other two should be skipped.
        assert len(result.skipped) == 2

    def test_dry_run_does_not_write_or_commit(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)

        result = apply_template_updates(repo, push=False, dry_run=True)

        assert result.error == ""
        assert len(result.applied) > 0
        # Files must NOT have been written.
        for filename in CANONICAL_TEMPLATES:
            path = repo / TEMPLATE_SUBDIR / filename
            assert not path.exists(), f"{filename} should not exist after dry_run"
        # No new commit.
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert "canonical issue templates" not in log.stdout

    def test_uses_project_git_identity(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        apply_template_updates(
            repo,
            git_user_name="oompah-bot",
            git_user_email="bot@example.com",
            push=False,
        )

        log = subprocess.run(
            ["git", "log", "-1", "--format=%an <%ae>"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert "oompah-bot" in log.stdout
        assert "bot@example.com" in log.stdout

    def test_push_is_called_when_enabled(self, tmp_path: Path) -> None:
        """push=True should trigger git push; we mock subprocess to verify."""
        repo = _make_managed_repo(tmp_path, write_templates=False)

        push_calls = []
        original_run = subprocess.run

        def _mock_run(cmd, **kwargs):
            if cmd[:3] == ["git", "push", "origin"]:
                push_calls.append(cmd)
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        with patch("oompah.issue_template_refresh.subprocess.run", side_effect=_mock_run):
            result = apply_template_updates(repo, push=True, branch="main")

        # push=True → push was attempted.
        assert len(push_calls) >= 1

    def test_push_false_does_not_call_git_push(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)

        push_calls = []
        original_run = subprocess.run

        def _mock_run(cmd, **kwargs):
            if isinstance(cmd, list) and len(cmd) >= 3 and cmd[1] == "push":
                push_calls.append(cmd)
                return MagicMock(returncode=0, stdout="", stderr="")
            return original_run(cmd, **kwargs)

        with patch("oompah.issue_template_refresh.subprocess.run", side_effect=_mock_run):
            apply_template_updates(repo, push=False)

        assert push_calls == [], "git push must not be called when push=False"


# ---------------------------------------------------------------------------
# ensure_issue_templates helper
# ---------------------------------------------------------------------------


class TestEnsureIssueTemplates:
    def test_returns_true_when_change_made(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        changed = ensure_issue_templates(repo, branch="main", push=False)
        assert changed is True

    def test_returns_false_when_already_current(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        changed = ensure_issue_templates(repo, branch="main", push=False)
        assert changed is False

    def test_raises_on_error(self, tmp_path: Path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        # Make a template file dirty to trigger the refused error.
        bug = repo / TEMPLATE_SUBDIR / "bug_report.yml"
        bug.write_text("dirty\n")

        with pytest.raises(RuntimeError, match="Refused"):
            ensure_issue_templates(repo, branch="main", push=False)


# ---------------------------------------------------------------------------
# Server API endpoints
# ---------------------------------------------------------------------------


def _make_orch(project: object) -> MagicMock:
    orch = MagicMock()
    orch.project_store.get.return_value = project
    return orch


def _github_project(repo_path: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="proj-1",
        tracker_kind="github_issues",
        repo_path=repo_path,
        git_user_name="bot",
        git_user_email="bot@example.com",
        default_branch="main",
    )


def _native_project(repo_path: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="proj-2",
        tracker_kind="oompah_md",
        repo_path=repo_path,
        git_user_name=None,
        git_user_email=None,
        default_branch="main",
    )


@pytest.fixture
def client(tmp_path):
    """Return a FastAPI TestClient with a mocked orchestrator."""
    from fastapi.testclient import TestClient
    from oompah.server import app

    return TestClient(app, raise_server_exceptions=False)


class TestIssueTemplatesStatusEndpoint:
    def test_404_for_unknown_project(self, client) -> None:
        with patch("oompah.server._get_orchestrator") as mock_orch:
            store = MagicMock()
            store.get.return_value = None
            mock_orch.return_value.project_store = store
            res = client.get("/api/v1/projects/unknown/issue-templates/status")
        assert res.status_code == 404

    def test_400_for_non_github_issues_project(self, client, tmp_path) -> None:
        project = _native_project(str(tmp_path))
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = project
            res = client.get(f"/api/v1/projects/{project.id}/issue-templates/status")
        assert res.status_code == 400
        assert "not_applicable" in res.text

    def test_all_current_when_templates_match(self, client, tmp_path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        project = _github_project(str(repo))
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = project
            res = client.get(f"/api/v1/projects/{project.id}/issue-templates/status")
        assert res.status_code == 200
        data = res.json()
        assert data["all_current"] is True
        assert data["drifted"] == []
        assert len(data["current"]) == len(CANONICAL_TEMPLATES)

    def test_drifted_when_templates_absent(self, client, tmp_path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        project = _github_project(str(repo))
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = project
            res = client.get(f"/api/v1/projects/{project.id}/issue-templates/status")
        assert res.status_code == 200
        data = res.json()
        assert data["all_current"] is False
        assert len(data["drifted"]) == len(CANONICAL_TEMPLATES)
        for entry in data["drifted"]:
            assert "diff" in entry
            assert entry["diff"] != ""


class TestIssueTemplatesPreviewEndpoint:
    def test_empty_diff_when_current(self, client, tmp_path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        project = _github_project(str(repo))
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = project
            res = client.get(f"/api/v1/projects/{project.id}/issue-templates/preview")
        assert res.status_code == 200
        assert res.json()["diff"] == ""

    def test_returns_diff_when_drifted(self, client, tmp_path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        project = _github_project(str(repo))
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = project
            res = client.get(f"/api/v1/projects/{project.id}/issue-templates/preview")
        assert res.status_code == 200
        diff = res.json()["diff"]
        assert "+++" in diff

    def test_400_for_non_github_issues_project(self, client, tmp_path) -> None:
        project = _native_project(str(tmp_path))
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = project
            res = client.get(f"/api/v1/projects/{project.id}/issue-templates/preview")
        assert res.status_code == 400


class TestIssueTemplatesApplyEndpoint:
    def test_applies_templates_and_returns_applied_list(self, client, tmp_path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=False)
        project = _github_project(str(repo))
        fake_result = TemplateApplyResult(
            applied=[
                f"{TEMPLATE_SUBDIR}/bug_report.yml",
                f"{TEMPLATE_SUBDIR}/feature_request.yml",
                f"{TEMPLATE_SUBDIR}/question.yml",
            ],
            skipped=[],
            commit_sha="a" * 40,
            pushed=True,
        )
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = project
            with patch(
                "oompah.issue_template_refresh.apply_template_updates",
                return_value=fake_result,
            ):
                res = client.post(
                    f"/api/v1/projects/{project.id}/issue-templates/apply"
                )
        assert res.status_code == 200
        data = res.json()
        assert len(data["applied"]) == len(CANONICAL_TEMPLATES)
        assert data["commit_sha"] == "a" * 40
        assert data["pushed"] is True

    def test_returns_skipped_when_already_current(self, client, tmp_path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        project = _github_project(str(repo))
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = project
            res = client.post(
                f"/api/v1/projects/{project.id}/issue-templates/apply"
            )
        assert res.status_code == 200
        data = res.json()
        assert data["applied"] == []
        assert len(data["skipped"]) == len(CANONICAL_TEMPLATES)
        assert data["commit_sha"] == ""

    def test_409_on_dirty_worktree_conflict(self, client, tmp_path) -> None:
        repo = _make_managed_repo(tmp_path, write_templates=True)
        # Dirty a template file without committing.
        bug = repo / TEMPLATE_SUBDIR / "bug_report.yml"
        bug.write_text("dirty content\n")
        project = _github_project(str(repo))
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = project
            res = client.post(
                f"/api/v1/projects/{project.id}/issue-templates/apply"
            )
        assert res.status_code == 409
        data = res.json()
        assert data["error"]["code"] == "dirty_worktree"
        assert "uncommitted changes" in data["error"]["message"]

    def test_400_for_non_github_issues_project(self, client, tmp_path) -> None:
        project = _native_project(str(tmp_path))
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = project
            res = client.post(
                f"/api/v1/projects/{project.id}/issue-templates/apply"
            )
        assert res.status_code == 400

    def test_404_for_unknown_project(self, client) -> None:
        with patch("oompah.server._get_orchestrator") as mock_orch:
            mock_orch.return_value.project_store.get.return_value = None
            res = client.post("/api/v1/projects/ghost/issue-templates/apply")
        assert res.status_code == 404
