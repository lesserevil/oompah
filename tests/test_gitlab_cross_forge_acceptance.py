"""Offline cross-forge acceptance coverage for the GitLab parity rollout.

This module deliberately replaces every provider transport with a local fixture.
It is the final regression boundary: the same SCM-facing expectations must hold
for a GitHub project and a GitLab project without a token or network access.
Live smoke checks are intentionally opt-in at the bottom of this file.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from oompah.projects import ProjectStore
from oompah.scm import CIStatus, GitHubProvider, GitLabProvider, SCMProvider


class _Response:
    """Small httpx-compatible response fixture; it never opens a socket."""

    def __init__(self, payload: Any = None, status_code: int = 200):
        self._payload = {} if payload is None else payload
        self.status_code = status_code
        self.text = json.dumps(self._payload)

    def json(self) -> Any:
        return self._payload


@dataclass(frozen=True)
class _ForgeFixture:
    name: str
    repo: str
    provider: SCMProvider

    def install(self) -> list[tuple[str, str, dict[str, Any]]]:
        calls: list[tuple[str, str, dict[str, Any]]] = []

        def api(method: str, path: str, **kwargs: Any) -> _Response:
            calls.append((method, path, kwargs))
            if self.name == "github":
                if path.endswith("/pulls"):
                    return _Response([{
                        "number": 7, "title": "Ship widget", "html_url": "https://github.test/acme/widgets/pull/7",
                        "user": {"login": "octo"}, "head": {"ref": "feature/widget"},
                        "base": {"ref": "main"}, "created_at": "2026-01-01", "updated_at": "2026-01-02",
                        "labels": [{"name": "ready"}], "draft": False,
                    }])
                if path.endswith("/pulls/7"):
                    return _Response({"node_id": "PR_fixture_7"})
                if path.endswith("/files"):
                    return _Response([{"filename": "src/widget.py"}])
                if path.endswith("/commits"):
                    return _Response([{"sha": "a" * 40}, {"sha": "b" * 40}])
                if path.endswith("/merge"):
                    return _Response({}, 200)
                if "/issues/7/labels" in path:
                    return _Response([], 200)
                return _Response({}, 200)

            if path.endswith("/merge_requests"):
                return _Response([{
                    "iid": 7, "title": "Ship widget", "web_url": "https://gitlab.test/acme/widgets/-/merge_requests/7",
                    "author": {"username": "gitlab-user"}, "source_branch": "feature/widget",
                    "target_branch": "main", "created_at": "2026-01-01", "updated_at": "2026-01-02",
                    "labels": ["ready"], "head_pipeline": {"status": "success"},
                }])
            if path.endswith("/changes"):
                return _Response({"changes": [{"new_path": "src/widget.py"}]})
            if path.endswith("/commits"):
                # GitLab delivers newest-first; the contract requires oldest-first.
                return _Response([{"id": "b" * 40}, {"id": "a" * 40}])
            if path.endswith("/merge"):
                return _Response({}, 200)
            if path.endswith("/merge_requests/7"):
                return _Response({"labels": ["ready"], "source_branch": "feature/widget"})
            return _Response({}, 200)

        # The concrete providers use this private seam for their HTTP APIs;
        # replacing it gives a strict no-network fixture without mocking httpx.
        self.provider._api = api  # type: ignore[attr-defined]
        if self.name == "github":
            self.provider._graphql = lambda *args, **kwargs: _Response({  # type: ignore[attr-defined]
                "data": {"enablePullRequestAutoMerge": {"pullRequest": {"autoMergeRequest": {"enabledAt": "2026-01-02"}}}}
            })
        return calls


def _github_fixture() -> _ForgeFixture:
    return _ForgeFixture("github", "acme/widgets", GitHubProvider(access_token="fixture-token"))


def _gitlab_fixture() -> _ForgeFixture:
    return _ForgeFixture("gitlab", "acme/widgets", GitLabProvider(access_token="fixture-token"))


@pytest.fixture(params=[_github_fixture, _gitlab_fixture], ids=["github", "gitlab"])
def forge(request: pytest.FixtureRequest) -> _ForgeFixture:
    fixture = request.param()
    fixture.install()
    return fixture


class TestSharedProviderAcceptanceContract:
    """The normalized SCM contract is exercised identically for both forges."""

    def test_open_review_lifecycle_exposes_normalized_fields(self, forge: _ForgeFixture) -> None:
        reviews = forge.provider.list_open_reviews(forge.repo)

        assert len(reviews) == 1
        review = reviews[0]
        assert (review.id, review.title, review.state) == ("7", "Ship widget", "open")
        assert (review.source_branch, review.target_branch) == ("feature/widget", "main")
        assert review.labels == ["ready"]
        assert review.ci_status in {CIStatus.PASSED, CIStatus.UNKNOWN}

    def test_changed_files_and_commits_are_contract_normalized(self, forge: _ForgeFixture) -> None:
        assert forge.provider.get_review_files(forge.repo, "7") == ["src/widget.py"]
        assert forge.provider.get_review_commits(forge.repo, "7") == ["a" * 40, "b" * 40]

    def test_labels_and_auto_merge_do_not_leak_forge_errors(self, forge: _ForgeFixture) -> None:
        forge.provider.add_review_label(forge.repo, "7", "oompah:ready")
        forge.provider.remove_review_label(forge.repo, "7", "oompah:ready")

        ok, message = forge.provider.enable_auto_merge(forge.repo, "7")
        assert ok is True
        assert message

    def test_auth_failure_degrades_to_safe_empty_results(self, forge: _ForgeFixture) -> None:
        forge.provider._api = lambda *args, **kwargs: _Response({}, 401)  # type: ignore[attr-defined]

        assert forge.provider.list_open_reviews(forge.repo) == []
        assert forge.provider.get_review_files(forge.repo, "7") == []
        assert forge.provider.get_review_commits(forge.repo, "7") == []


class TestGitLabFixtureSpecificAcceptance:
    def test_nested_self_managed_project_paths_are_encoded_offline(self) -> None:
        fixture = _ForgeFixture(
            "gitlab", "group/subgroup/widgets",
            GitLabProvider(hostname="gitlab.internal.test", access_token="fixture-token"),
        )
        calls = fixture.install()

        fixture.provider.get_review_files(fixture.repo, "7")

        assert calls[0][1] == "/projects/group%2Fsubgroup%2Fwidgets/merge_requests/7/changes"
        assert fixture.provider._api_url() == "https://gitlab.internal.test/api/v4"  # type: ignore[attr-defined]


class TestPreForgeGitHubProjectMigration:
    def test_persisted_pre_forge_github_record_loads_unchanged_then_round_trips(self, tmp_path: Path) -> None:
        path = tmp_path / "projects.json"
        legacy = {
            "id": "proj-legacy", "name": "legacy", "repo_url": "https://github.com/acme/widgets.git",
            "repo_path": "/work/widgets", "branch": "main", "tracker_kind": "github_issues",
            "tracker_owner": "acme", "tracker_repo": "widgets", "github_issue_intake_enabled": True,
        }
        path.write_text(json.dumps([legacy]))

        store = ProjectStore(path=str(path))
        project = store.get("proj-legacy")

        assert project is not None
        assert project.forge_kind == "github"
        assert project.forge_base_url == "https://github.com"
        assert project.tracker_kind == "github_issues"
        assert project.tracker_owner == "acme"
        assert project.github_issue_intake_enabled is True

        store._save()  # Persist the transparent migration and verify reload safety.
        reloaded = ProjectStore(path=str(path)).get("proj-legacy")
        assert reloaded is not None
        assert reloaded.to_dict()["forge_kind"] == "github"
        assert reloaded.to_dict()["repo_url"] == legacy["repo_url"]


_GITLAB_COM_ENV = ("GITLAB_TOKEN", "OOMPAH_GITLAB_SMOKE_PROJECT")
_GITLAB_SELF_MANAGED_ENV = (
    "OOMPAH_GITLAB_SELF_MANAGED_URL", "OOMPAH_GITLAB_SELF_MANAGED_TOKEN", "OOMPAH_GITLAB_SELF_MANAGED_PROJECT",
)


@pytest.mark.skipif(
    not all(os.environ.get(name) for name in _GITLAB_COM_ENV),
    reason="GitLab.com smoke test requires GITLAB_TOKEN and OOMPAH_GITLAB_SMOKE_PROJECT",
)
def test_gitlab_com_smoke_is_explicitly_opt_in() -> None:
    provider = GitLabProvider(access_token=os.environ["GITLAB_TOKEN"])
    assert provider.is_available()
    assert isinstance(provider.list_open_reviews(os.environ["OOMPAH_GITLAB_SMOKE_PROJECT"]), list)


@pytest.mark.skipif(
    not all(os.environ.get(name) for name in _GITLAB_SELF_MANAGED_ENV),
    reason="Self-managed GitLab smoke test requires URL, token, and project environment variables",
)
def test_gitlab_self_managed_smoke_is_explicitly_opt_in() -> None:
    hostname = os.environ["OOMPAH_GITLAB_SELF_MANAGED_URL"].removeprefix("https://").rstrip("/")
    provider = GitLabProvider(hostname=hostname, access_token=os.environ["OOMPAH_GITLAB_SELF_MANAGED_TOKEN"])
    assert provider.is_available()
    assert isinstance(provider.list_open_reviews(os.environ["OOMPAH_GITLAB_SELF_MANAGED_PROJECT"]), list)
