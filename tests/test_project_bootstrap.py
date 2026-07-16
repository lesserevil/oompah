"""Tests for oompah managed-project bootstrap scaffolding."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from oompah.project_bootstrap import (
    ProjectBootstrapApplyResult,
    apply_project_bootstrap_updates,
    check_project_bootstrap_drift,
    preview_project_bootstrap_updates,
)
from oompah.project_bootstrap.templates import CANONICAL_FILES, HTML_BEGIN_MARKER


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
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
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(repo), check=True)
    return repo


def test_missing_bootstrap_files_are_drifted(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    status = check_project_bootstrap_drift(repo)

    assert status.all_current is False
    assert {d.path for d in status.drifted} == set(CANONICAL_FILES)
    assert status.protected == []
    assert "AGENTS.md" in preview_project_bootstrap_updates(repo)


def test_apply_writes_missing_files_without_commit(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    result = apply_project_bootstrap_updates(repo, commit=False, push=False)

    assert result.error == ""
    assert set(result.applied) == set(CANONICAL_FILES)
    agents = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "BEGIN OOMPAH TASK INTEGRATION" in agents
    assert "GitHub Issues are customer-facing intake" in agents
    hook = repo / "scripts/githooks/pre-commit"
    assert hook.exists()
    assert hook.stat().st_mode & stat.S_IXUSR
    assert (repo / "docs/README.md").exists()
    assert (repo / "plans/README.md").exists()
    workflow = (repo / ".github/workflows/filtered-release-notes.yml").read_text(
        encoding="utf-8"
    )
    assert "Generate filtered commit notes" in workflow
    assert "grep -qv '^\\.oompah/'" in workflow


def test_bootstrap_distinguishes_plans_from_tracked_tasks(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    result = apply_project_bootstrap_updates(repo, commit=False, push=False)

    assert result.error == ""
    agents = (repo / "AGENTS.md").read_text(encoding="utf-8")
    plans = (repo / "plans/README.md").read_text(encoding="utf-8")
    assert "Planning Does Not Require a Task" in agents
    assert "does not prohibit design documents in `plans/`" in agents
    assert "Plans Are Not Tasks" in plans
    assert "does not require a corresponding\noompah task" in plans
    assert "when implementation begins" in plans
    assert "not a substitute task\ntracker" in plans


def test_existing_project_owned_files_are_protected(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    makefile = repo / "Makefile"
    makefile.write_text("test:\n\tcargo test\n", encoding="utf-8")
    subprocess.run(["git", "add", "Makefile"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "custom makefile"], cwd=str(repo), check=True)

    status = check_project_bootstrap_drift(repo)

    protected = {d.path: d for d in status.protected}
    assert "Makefile" in protected
    assert "project-owned" in protected["Makefile"].reason

    result = apply_project_bootstrap_updates(repo, commit=False, push=False)

    assert "Makefile" in result.protected
    assert makefile.read_text(encoding="utf-8") == "test:\n\tcargo test\n"


def test_managed_bootstrap_file_is_updated(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    docs = repo / "docs"
    docs.mkdir()
    readme = docs / "README.md"
    readme.write_text(f"{HTML_BEGIN_MARKER}\nold\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/README.md"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "old docs"], cwd=str(repo), check=True)

    result = apply_project_bootstrap_updates(repo, commit=False, push=False)

    assert result.error == ""
    assert "docs/README.md" in result.applied
    assert "Keeping Docs In Sync" in readme.read_text(encoding="utf-8")


def test_legacy_bootstrap_agents_github_section_is_replaced(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    agents = repo / "AGENTS.md"
    agents.write_text(
        """# Agent Instructions

## Issue Tracking with GitHub Issues

This project uses **GitHub Issues** for ALL task tracking.

## Documentation must match code

Keep docs current.
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "AGENTS.md"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "legacy agents"], cwd=str(repo), check=True)

    result = apply_project_bootstrap_updates(repo, commit=False, push=False)

    assert "AGENTS.md" in result.applied
    text = agents.read_text(encoding="utf-8")
    assert "BEGIN OOMPAH TASK INTEGRATION" in text
    assert "This project uses **GitHub Issues** for ALL task tracking" not in text
    assert "## Documentation must match code" in text


def test_dirty_bootstrap_file_is_refused(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    agents = repo / "AGENTS.md"
    agents.write_text("# Agent Instructions\n", encoding="utf-8")
    subprocess.run(["git", "add", "AGENTS.md"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "agents"], cwd=str(repo), check=True)
    agents.write_text("# Agent Instructions\n\nlocal dirty edit\n", encoding="utf-8")

    result = apply_project_bootstrap_updates(repo, commit=False, push=False)

    assert "Refused" in result.error
    assert "AGENTS.md" in result.error


def test_apply_can_commit_without_push(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    result = apply_project_bootstrap_updates(
        repo,
        git_user_name="Bootstrap Bot",
        git_user_email="bootstrap@example.com",
        commit=True,
        push=False,
    )

    assert result.error == ""
    assert result.commit_sha
    assert result.pushed is False
    log = subprocess.run(
        ["git", "log", "-1", "--format=%an <%ae> %s"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Bootstrap Bot <bootstrap@example.com>" in log.stdout
    assert "refresh oompah project bootstrap files" in log.stdout


def _project(repo_path: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="proj-bootstrap",
        repo_path=repo_path,
        git_user_name="bot",
        git_user_email="bot@example.com",
        default_branch="main",
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from oompah.server import app

    return TestClient(app, raise_server_exceptions=False)


def test_project_bootstrap_status_endpoint(client, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    project = _project(str(repo))

    with patch("oompah.server._get_orchestrator") as mock_orch:
        mock_orch.return_value.project_store.get.return_value = project
        res = client.get(f"/api/v1/projects/{project.id}/bootstrap/status")

    assert res.status_code == 200
    data = res.json()
    assert data["all_current"] is False
    assert any(entry["path"] == "AGENTS.md" for entry in data["drifted"])


def test_project_bootstrap_preview_endpoint(client, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    project = _project(str(repo))

    with patch("oompah.server._get_orchestrator") as mock_orch:
        mock_orch.return_value.project_store.get.return_value = project
        res = client.get(f"/api/v1/projects/{project.id}/bootstrap/preview")

    assert res.status_code == 200
    assert "AGENTS.md" in res.json()["diff"]


def test_project_bootstrap_apply_endpoint(client, tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    project = _project(str(repo))
    fake_result = ProjectBootstrapApplyResult(
        applied=["AGENTS.md"],
        protected=["Makefile"],
        commit_sha="a" * 40,
        pushed=True,
    )

    with patch("oompah.server._get_orchestrator") as mock_orch:
        mock_orch.return_value.project_store.get.return_value = project
        with patch(
            "oompah.project_bootstrap.apply_project_bootstrap_updates",
            return_value=fake_result,
        ):
            res = client.post(f"/api/v1/projects/{project.id}/bootstrap/apply")

    assert res.status_code == 200
    data = res.json()
    assert data["applied"] == ["AGENTS.md"]
    assert data["protected"] == ["Makefile"]
    assert data["commit_sha"] == "a" * 40
    assert data["pushed"] is True


def test_project_bootstrap_apply_endpoint_returns_dirty_conflict(
    client,
    tmp_path: Path,
) -> None:
    project = _project(str(tmp_path))
    fake_result = ProjectBootstrapApplyResult(
        error="Refused: bootstrap files have uncommitted changes"
    )

    with patch("oompah.server._get_orchestrator") as mock_orch:
        mock_orch.return_value.project_store.get.return_value = project
        with patch(
            "oompah.project_bootstrap.apply_project_bootstrap_updates",
            return_value=fake_result,
        ):
            res = client.post(f"/api/v1/projects/{project.id}/bootstrap/apply")

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "dirty_worktree"


def test_project_bootstrap_status_endpoint_404(client) -> None:
    store = MagicMock()
    store.get.return_value = None
    with patch("oompah.server._get_orchestrator") as mock_orch:
        mock_orch.return_value.project_store = store
        res = client.get("/api/v1/projects/missing/bootstrap/status")

    assert res.status_code == 404


def test_project_bootstrap_cli_status_outputs_drift(capsys, tmp_path: Path) -> None:
    from oompah.project_bootstrap_cli import main

    repo = _make_repo(tmp_path)

    main(["status", str(repo)])

    out = capsys.readouterr().out
    assert "All current: no" in out
    assert "AGENTS.md (missing)" in out


def test_project_bootstrap_cli_apply_dry_run_does_not_write(
    capsys,
    tmp_path: Path,
) -> None:
    from oompah.project_bootstrap_cli import main

    repo = _make_repo(tmp_path)

    main(["apply", str(repo), "--dry-run"])

    out = capsys.readouterr().out
    assert "Dry run: no files written." in out
    assert "AGENTS.md" in out
    assert not (repo / "AGENTS.md").exists()


def test_main_dispatches_project_bootstrap_without_server_dependencies(monkeypatch):
    import sys
    from oompah import __main__ as main_mod

    called = {}

    def fake_main(argv):
        called["argv"] = argv

    monkeypatch.setattr(sys, "argv", ["oompah", "project-bootstrap", "status", "."])
    monkeypatch.setattr("oompah.project_bootstrap_cli.main", fake_main)

    main_mod.main()

    assert called["argv"] == ["status", "."]


def test_agents_md_template_uses_1_0_native_tracker_workflow() -> None:
    """AGENTS.md bootstrap template must use the 1.0 native oompah task workflow.

    This validates the HOW TO VERIFY criterion for OOMPAH-31: the generated
    AGENTS.md instructions must match the 1.0 native tracker workflow
    (OOMPAH TASK INTEGRATION v:2), NOT the GitHub Issues workflow.
    """
    from oompah.project_bootstrap.templates import AGENTS_MD

    # Must carry the 1.0 native tracker integration marker (v:2)
    assert "BEGIN OOMPAH TASK INTEGRATION v:2" in AGENTS_MD, (
        "AGENTS.md template must use the 1.0 native tracker workflow marker "
        "'BEGIN OOMPAH TASK INTEGRATION v:2'"
    )

    # Must mention native .oompah/tasks storage — the 1.0 canonical tracker
    assert ".oompah/tasks" in AGENTS_MD, (
        "AGENTS.md template must reference .oompah/tasks as the canonical tracker"
    )

    # Must describe GitHub Issues as intake, not as the primary tracker
    assert "GitHub Issues are customer-facing intake" in AGENTS_MD, (
        "AGENTS.md template must describe GitHub Issues as customer-facing intake, "
        "not as the primary task tracker"
    )

    # Must NOT use the GitHub Issues integration marker (wrong tracker)
    assert "BEGIN OOMPAH GITHUB ISSUES INTEGRATION" not in AGENTS_MD, (
        "AGENTS.md template must not embed the GitHub Issues tracker block — "
        "the 1.0 native workflow uses 'BEGIN OOMPAH TASK INTEGRATION v:2'"
    )


def test_apply_agents_md_template_is_current_after_apply(tmp_path: Path) -> None:
    """After apply, AGENTS.md must contain the 1.0 native tracker marker.

    Validates the end-to-end bootstrap apply path generates instructions that
    match the 1.0 native tracker workflow as required by OOMPAH-31.
    """
    repo = _make_repo(tmp_path)

    result = apply_project_bootstrap_updates(repo, commit=False, push=False)

    assert result.error == ""
    assert "AGENTS.md" in result.applied

    agents_text = (repo / "AGENTS.md").read_text(encoding="utf-8")

    # Confirm 1.0 native tracker workflow is present
    assert "BEGIN OOMPAH TASK INTEGRATION v:2" in agents_text
    assert ".oompah/tasks" in agents_text
    assert "GitHub Issues are customer-facing intake" in agents_text

    # Confirm the bootstrap status reports AGENTS.md as current after apply
    status = check_project_bootstrap_drift(repo)
    agents_drift = {d.path: d for d in (status.drifted + status.current + status.protected)}
    assert "AGENTS.md" in agents_drift
    agents_entry = agents_drift["AGENTS.md"]
    assert agents_entry.is_current, (
        "AGENTS.md should be current immediately after bootstrap apply"
    )
