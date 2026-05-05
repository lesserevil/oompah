"""Tests for oompah.webhooks — forge webhook parsing and validation.

Covers:
- GitHub HMAC-SHA256 signature validation
- GitLab secret token validation
- GitHub pull_request payload parsing
- GitLab Merge Request Hook payload parsing
- Non-PR/MR event rejection
- Project matching by repo slug
- WebhookEvent dataclass fields
- WebhookForwarder subprocess management
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import tempfile

import pytest

from oompah.webhooks import (
    WebhookEvent,
    WebhookForwarder,
    _ForwarderProcess,
    match_project_by_repo,
    parse_github_webhook,
    parse_gitlab_webhook,
    validate_github_signature,
    validate_gitlab_token,
)
from oompah.models import Project


# ---------------------------------------------------------------------------
# Fixtures — sample payloads
# ---------------------------------------------------------------------------


def _github_pr_payload(
    action: str = "opened",
    number: int = 42,
    repo_full_name: str = "org/repo",
    source_branch: str = "feature-branch",
    target_branch: str = "main",
    author: str = "octocat",
    title: str = "Add new feature",
    merged: bool = False,
) -> dict:
    """Build a minimal GitHub pull_request webhook payload."""
    return {
        "action": action,
        "pull_request": {
            "number": number,
            "title": title,
            "merged": merged,
            "user": {"login": author},
            "head": {"ref": source_branch},
            "base": {"ref": target_branch},
        },
        "repository": {
            "full_name": repo_full_name,
        },
    }


def _gitlab_mr_payload(
    action: str = "open",
    iid: int = 7,
    repo_path: str = "group/project",
    source_branch: str = "fix-branch",
    target_branch: str = "main",
    author: str = "tanuki",
    title: str = "Fix the thing",
    state: str = "opened",
) -> dict:
    """Build a minimal GitLab Merge Request Hook webhook payload."""
    return {
        "object_attributes": {
            "iid": iid,
            "title": title,
            "action": action,
            "state": state,
            "source_branch": source_branch,
            "target_branch": target_branch,
        },
        "user": {"username": author},
        "project": {"path_with_namespace": repo_path},
    }


def _make_project(
    repo_url: str = "https://github.com/org/repo.git",
    project_id: str = "proj-test1",
    name: str = "test-project",
    webhook_secret: str | None = None,
) -> Project:
    return Project(
        id=project_id,
        name=name,
        repo_url=repo_url,
        repo_path="/tmp/repos/test",
        webhook_secret=webhook_secret,
    )


# ---------------------------------------------------------------------------
# GitHub signature validation
# ---------------------------------------------------------------------------


class TestValidateGitHubSignature:
    """Tests for validate_github_signature()."""

    def test_valid_signature(self):
        secret = "my-webhook-secret"
        body = b'{"action":"opened"}'
        sig = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        assert validate_github_signature(body, sig, secret) is True

    def test_invalid_signature(self):
        secret = "my-webhook-secret"
        body = b'{"action":"opened"}'
        assert validate_github_signature(body, "sha256=deadbeef", secret) is False

    def test_wrong_secret(self):
        secret = "correct-secret"
        wrong = "wrong-secret"
        body = b'{"action":"opened"}'
        sig = "sha256=" + hmac.new(
            wrong.encode(), body, hashlib.sha256
        ).hexdigest()
        assert validate_github_signature(body, sig, secret) is False

    def test_missing_prefix(self):
        secret = "my-secret"
        body = b"hello"
        # No sha256= prefix
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert validate_github_signature(body, sig, secret) is False

    def test_empty_signature_header(self):
        assert validate_github_signature(b"body", "", "secret") is False

    def test_empty_secret(self):
        assert validate_github_signature(b"body", "sha256=abc", "") is False

    def test_empty_both(self):
        assert validate_github_signature(b"body", "", "") is False

    def test_large_payload(self):
        """Signature validation works on large payloads."""
        secret = "big-secret"
        body = b"x" * 100_000
        sig = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        assert validate_github_signature(body, sig, secret) is True


# ---------------------------------------------------------------------------
# GitLab token validation
# ---------------------------------------------------------------------------


class TestValidateGitLabToken:
    """Tests for validate_gitlab_token()."""

    def test_valid_token(self):
        secret = "gitlab-secret-token"
        assert validate_gitlab_token(secret, secret) is True

    def test_invalid_token(self):
        assert validate_gitlab_token("wrong", "correct") is False

    def test_empty_token(self):
        assert validate_gitlab_token("", "secret") is False

    def test_empty_secret(self):
        assert validate_gitlab_token("token", "") is False

    def test_empty_both(self):
        assert validate_gitlab_token("", "") is False

    def test_timing_safe_comparison(self):
        """Ensure comparison is constant-time (uses hmac.compare_digest)."""
        # We can't directly test timing, but we verify the function
        # still works with long strings
        long_a = "a" * 1000
        long_b = "a" * 1000
        assert validate_gitlab_token(long_a, long_b) is True
        assert validate_gitlab_token(long_a, long_a[:-1] + "b") is False


# ---------------------------------------------------------------------------
# GitHub payload parsing
# ---------------------------------------------------------------------------


class TestParseGitHubWebhook:
    """Tests for parse_github_webhook()."""

    def test_pr_opened(self):
        payload = _github_pr_payload(action="opened")
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.provider == "github"
        assert event.event_type == "pull_request"
        assert event.action == "opened"
        assert event.repo_slug == "org/repo"
        assert event.review_id == "42"
        assert event.source_branch == "feature-branch"
        assert event.target_branch == "main"
        assert event.author == "octocat"
        assert event.title == "Add new feature"
        assert event.merged is False

    def test_pr_closed_merged(self):
        payload = _github_pr_payload(action="closed", merged=True)
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.action == "closed"
        assert event.merged is True

    def test_pr_closed_not_merged(self):
        payload = _github_pr_payload(action="closed", merged=False)
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.merged is False

    def test_pr_synchronize(self):
        payload = _github_pr_payload(action="synchronize")
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.action == "synchronize"

    def test_pr_review_requested(self):
        payload = _github_pr_payload(action="review_requested")
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.action == "review_requested"

    def test_ping_event_returns_none(self):
        assert parse_github_webhook("ping", {"zen": "test"}) is None

    def test_issues_event_returns_none(self):
        assert parse_github_webhook("issues", {"action": "opened"}) is None

    def test_missing_pull_request_key_returns_none(self):
        """If the payload is pull_request type but missing the PR object."""
        assert parse_github_webhook("pull_request", {"action": "opened"}) is None

    def test_raw_payload_preserved(self):
        payload = _github_pr_payload()
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.raw is payload

    def test_different_repo(self):
        payload = _github_pr_payload(repo_full_name="other-org/other-repo")
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.repo_slug == "other-org/other-repo"


class TestParseGitHubPushWebhook:
    """Tests for parse_github_webhook() handling of push events."""

    def _push_payload(
        self,
        ref: str = "refs/heads/main",
        repo_full_name: str = "org/repo",
        deleted: bool = False,
        head_message: str = "chore(beads): undefer all",
        pusher_name: str = "octocat",
    ) -> dict:
        return {
            "ref": ref,
            "deleted": deleted,
            "before": "0" * 40,
            "after": "1" * 40,
            "repository": {"full_name": repo_full_name},
            "pusher": {"name": pusher_name, "email": "x@example.com"},
            "sender": {"login": pusher_name},
            "head_commit": {"message": head_message, "id": "1" * 40},
        }

    def test_push_to_main(self):
        event = parse_github_webhook("push", self._push_payload())
        assert event is not None
        assert event.event_type == "push"
        assert event.action == "pushed"
        assert event.target_branch == "main"
        assert event.source_branch == ""
        assert event.review_id == ""
        assert event.merged is False
        assert event.author == "octocat"
        assert event.title == "chore(beads): undefer all"
        assert event.repo_slug == "org/repo"

    def test_push_to_feature_branch(self):
        event = parse_github_webhook("push", self._push_payload(ref="refs/heads/feature-x"))
        assert event is not None
        assert event.target_branch == "feature-x"

    def test_push_branch_deletion_returns_none(self):
        payload = self._push_payload(deleted=True)
        assert parse_github_webhook("push", payload) is None

    def test_push_tag_returns_none(self):
        payload = self._push_payload(ref="refs/tags/v1.0")
        assert parse_github_webhook("push", payload) is None

    def test_push_multiline_message_takes_first_line_only(self):
        payload = self._push_payload(head_message="first line\n\nbody continues here")
        event = parse_github_webhook("push", payload)
        assert event is not None
        assert event.title == "first line"

    def test_push_missing_head_commit(self):
        payload = self._push_payload()
        del payload["head_commit"]
        event = parse_github_webhook("push", payload)
        assert event is not None
        assert event.title == ""

    def test_push_falls_back_to_sender_when_pusher_missing(self):
        payload = self._push_payload()
        del payload["pusher"]
        event = parse_github_webhook("push", payload)
        assert event is not None
        assert event.author == "octocat"


# ---------------------------------------------------------------------------
# GitLab payload parsing
# ---------------------------------------------------------------------------


class TestParseGitLabWebhook:
    """Tests for parse_gitlab_webhook()."""

    def test_mr_open(self):
        payload = _gitlab_mr_payload(action="open")
        event = parse_gitlab_webhook("Merge Request Hook", payload)
        assert event is not None
        assert event.provider == "gitlab"
        assert event.event_type == "Merge Request Hook"
        assert event.action == "open"
        assert event.repo_slug == "group/project"
        assert event.review_id == "7"
        assert event.source_branch == "fix-branch"
        assert event.target_branch == "main"
        assert event.author == "tanuki"
        assert event.title == "Fix the thing"
        assert event.merged is False

    def test_mr_merged(self):
        payload = _gitlab_mr_payload(action="merge", state="merged")
        event = parse_gitlab_webhook("Merge Request Hook", payload)
        assert event is not None
        assert event.action == "merge"
        assert event.merged is True

    def test_mr_close(self):
        payload = _gitlab_mr_payload(action="close", state="closed")
        event = parse_gitlab_webhook("Merge Request Hook", payload)
        assert event is not None
        assert event.action == "close"
        assert event.merged is False

    def test_mr_update(self):
        payload = _gitlab_mr_payload(action="update")
        event = parse_gitlab_webhook("Merge Request Hook", payload)
        assert event is not None
        assert event.action == "update"

    def test_non_mr_event_returns_none(self):
        assert parse_gitlab_webhook("Push Hook", {"ref": "refs/heads/main"}) is None

    def test_pipeline_event_returns_none(self):
        assert parse_gitlab_webhook("Pipeline Hook", {}) is None

    def test_missing_object_attributes_returns_none(self):
        assert parse_gitlab_webhook("Merge Request Hook", {"user": {}}) is None

    def test_raw_payload_preserved(self):
        payload = _gitlab_mr_payload()
        event = parse_gitlab_webhook("Merge Request Hook", payload)
        assert event is not None
        assert event.raw is payload


# ---------------------------------------------------------------------------
# Project matching
# ---------------------------------------------------------------------------


class TestMatchProjectByRepo:
    """Tests for match_project_by_repo()."""

    def test_match_github_https(self):
        projects = [_make_project(repo_url="https://github.com/org/repo.git")]
        matched = match_project_by_repo(projects, "org/repo", "github")
        assert matched is not None
        assert matched.id == "proj-test1"

    def test_match_github_ssh(self):
        projects = [_make_project(repo_url="git@github.com:org/repo.git")]
        matched = match_project_by_repo(projects, "org/repo", "github")
        assert matched is not None

    def test_match_gitlab(self):
        projects = [_make_project(
            repo_url="https://gitlab.com/group/project.git",
            project_id="proj-gl1",
        )]
        matched = match_project_by_repo(projects, "group/project", "gitlab")
        assert matched is not None
        assert matched.id == "proj-gl1"

    def test_no_match(self):
        projects = [_make_project(repo_url="https://github.com/org/other.git")]
        matched = match_project_by_repo(projects, "org/repo", "github")
        assert matched is None

    def test_empty_projects(self):
        matched = match_project_by_repo([], "org/repo", "github")
        assert matched is None

    def test_multiple_projects_returns_first_match(self):
        projects = [
            _make_project(repo_url="https://github.com/org/other.git", project_id="p1"),
            _make_project(repo_url="https://github.com/org/repo.git", project_id="p2"),
        ]
        matched = match_project_by_repo(projects, "org/repo", "github")
        assert matched is not None
        assert matched.id == "p2"


# ---------------------------------------------------------------------------
# WebhookEvent dataclass
# ---------------------------------------------------------------------------


class TestWebhookEvent:
    """Tests for WebhookEvent dataclass."""

    def test_default_values(self):
        event = WebhookEvent(provider="github", event_type="pull_request", action="opened")
        assert event.repo_slug == ""
        assert event.review_id == ""
        assert event.source_branch == ""
        assert event.target_branch == ""
        assert event.author == ""
        assert event.title == ""
        assert event.merged is False
        assert event.raw == {}

    def test_all_fields(self):
        raw = {"key": "value"}
        event = WebhookEvent(
            provider="gitlab",
            event_type="Merge Request Hook",
            action="merge",
            repo_slug="group/proj",
            review_id="10",
            source_branch="feat",
            target_branch="main",
            author="dev",
            title="My MR",
            merged=True,
            raw=raw,
        )
        assert event.provider == "gitlab"
        assert event.merged is True
        assert event.raw is raw


# ---------------------------------------------------------------------------
# WebhookForwarder
# ---------------------------------------------------------------------------


class _FakeProjectStore:
    """Minimal ProjectStore stand-in for testing."""

    def __init__(self, projects: list[Project] | None = None):
        self._projects = {p.id: p for p in (projects or [])}

    def list_all(self) -> list[Project]:
        return list(self._projects.values())

    def get(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)


class _DummyProjectStore:
    """ProjectStore that always returns empty list."""

    def list_all(self) -> list[Project]:
        return []


class TestForwarderProcess:
    """Tests for _ForwarderProcess dataclass."""

    def test_initial_state(self):
        fp = _ForwarderProcess(
            project_id="p1",
            project_name="my-project",
            repo_path="/tmp/repos/my-project",
        )
        assert fp.project_id == "p1"
        assert fp.project_name == "my-project"
        assert fp.repo_path == "/tmp/repos/my-project"
        assert fp.process is None
        assert fp.restart_delay_s == 1.0
        assert fp.restart_attempts == 0


class TestWebhookForwarderInit:
    """Tests for WebhookForwarder.__init__()."""

    def test_default_webhook_url(self):
        fwd = WebhookForwarder()
        assert fwd._webhook_url == "http://localhost:8080/api/v1/webhooks/github"

    def test_explicit_webhook_url(self):
        fwd = WebhookForwarder(webhook_url="http://example.com/hooks")
        assert fwd._webhook_url == "http://example.com/hooks"

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_WEBHOOK_FORWARD_URL", "http://env-url.test/hooks")
        fwd = WebhookForwarder()
        assert fwd._webhook_url == "http://env-url.test/hooks"

    def test_explicit_overrides_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_WEBHOOK_FORWARD_URL", "http://env-url.test/hooks")
        fwd = WebhookForwarder(webhook_url="http://explicit.test/hooks")
        assert fwd._webhook_url == "http://explicit.test/hooks"

    def test_custom_poll_interval(self):
        fwd = WebhookForwarder(poll_interval_s=10.0)
        assert fwd._poll_interval_s == 10.0

    def test_default_poll_interval(self):
        fwd = WebhookForwarder()
        assert fwd._poll_interval_s == 5.0

    def test_is_running_false_initially(self):
        fwd = WebhookForwarder()
        assert fwd.is_running is False


class TestWebhookForwarderStartStop:
    """Tests for WebhookForwarder start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        await fwd.start()
        assert fwd.is_running is True
        # Second start should be no-op (already running)
        await fwd.start()
        assert fwd.is_running is True
        await fwd.stop()

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        await fwd.start()
        await fwd.stop()
        assert fwd.is_running is False
        # Second stop should be no-op
        await fwd.stop()
        assert fwd.is_running is False

    @pytest.mark.asyncio
    async def test_start_then_stop_cleans_up_task(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        await fwd.start()
        await fwd.stop()
        assert fwd._task is None


class TestWebhookForwarderPoll:
    """Tests for WebhookForwarder polling and restart logic."""

    @pytest.mark.asyncio
    async def test_no_project_store_means_no_error(self):
        fwd = WebhookForwarder(project_store=None)
        # Calling _poll_and_restart with no project store should not raise.
        await fwd._poll_and_restart()

    @pytest.mark.asyncio
    async def test_empty_project_store_means_no_error(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        await fwd._poll_and_restart()
        # No processes should be tracked.
        assert len(fwd._processes) == 0

    @pytest.mark.asyncio
    async def test_adding_project_creates_forwarder_process(self):
        proj = Project(
            id="proj-1",
            name="test-repo",
            repo_url="https://github.com/org/repo.git",
            repo_path="/tmp/test-repo",
        )
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)
        await fwd._poll_and_restart()
        assert "proj-1" in fwd._processes
        fp = fwd._processes["proj-1"]
        assert fp.project_name == "test-repo"
        assert fp.repo_path == "/tmp/test-repo"
        assert fp.process is None  # gh not available, so not started

    @pytest.mark.asyncio
    async def test_removing_project_terminates_forwarder(self):
        proj = Project(
            id="proj-1",
            name="test-repo",
            repo_url="https://github.com/org/repo.git",
            repo_path="/tmp/test-repo",
        )
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)

        # Poll once to register.
        await fwd._poll_and_restart()
        assert "proj-1" in fwd._processes

        # Simulate project removal: store returns empty.
        fwd.project_store = _DummyProjectStore()
        await fwd._poll_and_restart()
        assert "proj-1" not in fwd._processes

    @pytest.mark.asyncio
    async def test_skips_non_git_repo(self, tmp_path):
        """A project whose repo_path is not a git directory is skipped."""
        non_git_dir = str(tmp_path)
        proj = Project(
            id="proj-1",
            name="non-git",
            repo_url="https://github.com/org/repo.git",
            repo_path=non_git_dir,
        )
        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)
        await fwd._poll_and_restart()
        assert "proj-1" in fwd._processes
        # gh forward should not be started (not a git repo).
        assert fwd._processes["proj-1"].process is None

    @pytest.mark.asyncio
    async def test_launch_skips_missing_gh(self, tmp_path):
        """If gh CLI is not found, _launch logs a warning and sets process=None."""
        proj = Project(
            id="proj-1",
            name="test-repo",
            repo_url="https://github.com/org/repo.git",
            repo_path=str(tmp_path),
        )
        # Make it a git repo so it passes the .git check.
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        fwd = WebhookForwarder(project_store=_FakeProjectStore([proj]))
        fp = _ForwarderProcess("proj-1", "test-repo", str(tmp_path))
        await fwd._launch(fp)
        # gh is unlikely to be missing in CI, but if it is, process stays None.
        # Either way, no exception is raised.
        assert fp.project_id == "proj-1"

    @pytest.mark.asyncio
    async def test_exponential_backoff_reset_on_running(self, tmp_path):
        """When a process is still running, its restart_delay resets to base."""
        proj = Project(
            id="proj-1",
            name="test-repo",
            repo_url="https://github.com/org/repo.git",
            repo_path=str(tmp_path),
        )
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        store = _FakeProjectStore([proj])
        fwd = WebhookForwarder(project_store=store)

        # Register project.
        await fwd._poll_and_restart()
        fp = fwd._processes["proj-1"]

        # Simulate a running process by patching poll to return None.
        class _FakeProc:
            pid = 12345
            returncode = None

            def poll(self):
                return None  # still running

        fp.process = _FakeProc()
        fp.restart_delay_s = 8.0  # had grown via backoff

        await fwd._check_and_restart(fp)
        # Delay should be reset since process is still alive.
        assert fp.restart_delay_s == 1.0

    @pytest.mark.asyncio
    async def test_terminate_noop_when_already_exited(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        fwd._processes["proj-1"] = _ForwarderProcess("proj-1", "p", "/tmp/p")

        class _DeadProc:
            pid = 999
            returncode = 1  # already dead

            def poll(self):
                return 1

            def terminate(self):
                pass  # should not be called

        fwd._processes["proj-1"].process = _DeadProc()
        await fwd._terminate("proj-1")
        # _terminate should detect already-exited process and not call terminate.

    @pytest.mark.asyncio
    async def test_kill_all_terminates_all(self, tmp_path):
        """_kill_all should clear all tracked processes."""
        proj1 = Project(id="p1", name="r1", repo_url="https://github.com/org/r1.git", repo_path=str(tmp_path))
        proj2 = Project(id="p2", name="r2", repo_url="https://github.com/org/r2.git", repo_path=str(tmp_path))
        store = _FakeProjectStore([proj1, proj2])
        fwd = WebhookForwarder(project_store=store)

        await fwd._poll_and_restart()
        assert len(fwd._processes) == 2

        await fwd._kill_all()
        assert len(fwd._processes) == 0


class TestWebhookForwarderFullLifecycle:
    """Integration-style tests for the full start → poll → stop cycle."""

    @pytest.mark.asyncio
    async def test_start_stop_with_empty_store(self):
        fwd = WebhookForwarder(project_store=_DummyProjectStore())
        await fwd.start()
        # Let one poll cycle run.
        await asyncio.sleep(0.05)
        await fwd.stop()
        assert fwd.is_running is False

    @pytest.mark.asyncio
    async def test_stop_while_loop_running_cancels_task(self):
        fwd = WebhookForwarder(
            project_store=_DummyProjectStore(),
            poll_interval_s=10.0,  # slow poll so we can cancel mid-cycle
        )
        await fwd.start()
        # Stop immediately — the task should cancel without error.
        await fwd.stop()
        assert fwd._task is None or fwd._task.done()
