"""Tests for operator reports around legacy Backlog files."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from oompah.models import Project
from oompah.server import app


def _git(repo, *args, env=None):
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _commit_file(repo, rel_path: str, content: str, when: str):
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", rel_path)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "oompah",
        "GIT_AUTHOR_EMAIL": "example-org@users.noreply.github.com",
        "GIT_COMMITTER_NAME": "oompah",
        "GIT_COMMITTER_EMAIL": "example-org@users.noreply.github.com",
        "GIT_AUTHOR_DATE": when,
        "GIT_COMMITTER_DATE": when,
    }
    _git(repo, "commit", "-m", f"add {rel_path}", env=env)


def test_backlog_files_post_cutover_report_lists_new_backlog_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "oompah")
    _git(repo, "config", "user.email", "example-org@users.noreply.github.com")

    _commit_file(
        repo,
        "backlog/tasks/task-1 - old.md",
        "---\nid: task-1\n---\n",
        "2026-06-10T15:00:00+0000",
    )
    _commit_file(
        repo,
        "backlog/tasks/task-2 - new.md",
        "---\nid: task-2\n---\n",
        "2026-06-10T16:05:00+0000",
    )

    project = Project(
        id="proj-gh",
        name="github-backed",
        repo_url="https://github.com/example-org/oompah",
        repo_path=str(repo),
        tracker_kind="github_issues",
        tracker_owner="example-org",
        tracker_repo="oompah",
        tracker_cutover_at=datetime(2026, 6, 10, 16, 0, tzinfo=timezone.utc),
    )
    legacy_project = Project(
        id="proj-legacy",
        name="legacy",
        repo_url="https://github.com/example/legacy",
        repo_path=str(repo),
        tracker_kind="backlog_md",
        tracker_cutover_at=datetime(2026, 6, 10, 16, 0, tzinfo=timezone.utc),
    )
    orch = SimpleNamespace(project_store=MagicMock())
    orch.project_store.list_all.return_value = [project, legacy_project]

    with patch("oompah.server._get_orchestrator", return_value=orch):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/reports/backlog-files-post-cutover")

    assert response.status_code == 200
    body = response.json()
    assert body["total_projects"] == 1
    assert body["total_files"] == 1
    assert body["projects"][0]["project_id"] == "proj-gh"
    assert body["projects"][0]["files"] == [
        {
            "path": "backlog/tasks/task-2 - new.md",
            "added_at": "2026-06-10T16:05:00+00:00",
            "source": "git",
        }
    ]
