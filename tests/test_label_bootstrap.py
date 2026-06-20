"""Tests for GitHub label bootstrap on managed projects."""

from __future__ import annotations

from oompah.label_bootstrap import (
    INTAKE_REQUIRED_LABELS,
    REQUIRED_LABEL_NAMES,
    bootstrap_project_labels,
    build_label_bootstrap_alerts,
    ensure_github_labels,
    validate_project_config,
    validate_project_config_warnings,
)
from oompah.models import Project
from oompah.tracker import TrackerError


_TEST_LABELS = (
    ("oompah:status:proposed", "fbca04", "Proposed"),
    ("oompah:status:backlog", "ededed", "Backlog"),
)


class FakeGitHubClient:
    def __init__(
        self,
        *,
        existing: list[str] | None = None,
        list_error: Exception | None = None,
        post_errors: dict[str, Exception] | None = None,
    ) -> None:
        self.existing = list(existing or [])
        self.list_error = list_error
        self.post_errors = dict(post_errors or {})
        self.request_calls: list[tuple[str, dict | None]] = []
        self.post_calls: list[tuple[str, dict]] = []

    def request_paginated(self, path: str, *, params: dict | None = None) -> list[dict]:
        self.request_calls.append((path, params))
        if self.list_error is not None:
            raise self.list_error
        return [{"name": name} for name in self.existing]

    def post(self, path: str, *, json: dict) -> dict:
        self.post_calls.append((path, json))
        label_name = str(json["name"])
        if label_name in self.post_errors:
            raise self.post_errors[label_name]
        self.existing.append(label_name)
        return {}


def _project(**overrides) -> Project:
    values = {
        "id": "proj-gh",
        "name": "trickle",
        "repo_url": "https://github.com/NVIDIA-Omniverse/trickle.git",
        "repo_path": "/tmp/trickle",
        "tracker_kind": "github_issues",
        "tracker_owner": "NVIDIA-Omniverse",
        "tracker_repo": "trickle",
    }
    values.update(overrides)
    return Project(**values)


def test_required_labels_include_proposed_and_all_status_labels() -> None:
    assert "oompah:status:proposed" in REQUIRED_LABEL_NAMES
    assert "oompah:status:decomposed" in REQUIRED_LABEL_NAMES
    assert "oompah:status:duplicate-candidate" in REQUIRED_LABEL_NAMES
    assert INTAKE_REQUIRED_LABELS <= set(REQUIRED_LABEL_NAMES)


def test_bootstrap_project_labels_creates_missing_labels() -> None:
    client = FakeGitHubClient(existing=["oompah:status:backlog"])

    result = bootstrap_project_labels(
        owner="example-org",
        repo="oompah",
        client=client,
        labels=_TEST_LABELS,
        project_id="proj-oompah",
        project_name="oompah",
    )

    assert result.success is True
    assert result.created == ["oompah:status:proposed"]
    assert result.already_exists == ["oompah:status:backlog"]
    assert client.request_calls == [
        ("/repos/example-org/oompah/labels", {"per_page": 100})
    ]
    assert client.post_calls == [
        (
            "/repos/example-org/oompah/labels",
            {
                "name": "oompah:status:proposed",
                "color": "fbca04",
                "description": "Proposed",
            },
        )
    ]


def test_bootstrap_project_labels_is_idempotent() -> None:
    client = FakeGitHubClient(existing=[name for name, _, _ in _TEST_LABELS])

    result = bootstrap_project_labels(
        owner="example-org",
        repo="oompah",
        client=client,
        labels=_TEST_LABELS,
    )

    assert result.success is True
    assert result.created == []
    assert result.already_exists == [name for name, _, _ in _TEST_LABELS]
    assert client.post_calls == []


def test_permission_failure_produces_actionable_alert_with_repo_and_label() -> None:
    client = FakeGitHubClient(
        post_errors={
            "oompah:status:proposed": TrackerError(
                "GitHub API error 403 (POST /repos/example-org/oompah/labels)"
            )
        }
    )

    result = bootstrap_project_labels(
        owner="example-org",
        repo="oompah",
        client=client,
        labels=(("oompah:status:proposed", "fbca04", "Proposed"),),
        project_id="proj-oompah",
        project_name="oompah",
    )
    alerts = build_label_bootstrap_alerts({"proj-oompah": result})

    assert result.success is False
    assert result.has_permission_error is True
    assert alerts[0]["level"] == "error"
    assert alerts[0]["repo"] == "example-org/oompah"
    assert alerts[0]["labels"] == ["oompah:status:proposed"]
    assert "example-org/oompah" in alerts[0]["message"]
    assert "oompah:status:proposed" in alerts[0]["message"]
    assert "write access" in alerts[0]["message"]


def test_label_list_permission_failure_mentions_required_labels() -> None:
    client = FakeGitHubClient(
        list_error=TrackerError(
            "GitHub API error 403 (GET /repos/example-org/oompah/labels)"
        )
    )

    result = bootstrap_project_labels(
        owner="example-org",
        repo="oompah",
        client=client,
        labels=_TEST_LABELS,
    )

    assert result.success is False
    assert [name for name, _ in result.failed] == [
        "oompah:status:proposed",
        "oompah:status:backlog",
    ]
    assert "oompah:status:proposed" in result.alert_message()
    assert "oompah:status:backlog" in result.alert_message()


def test_validate_project_config_accepts_complete_github_project() -> None:
    assert validate_project_config(_project()) == []
    assert validate_project_config_warnings(_project()) == []


def test_validate_project_config_reports_actor_errors() -> None:
    project = _project()
    project.status_label_authorized_logins = ["alice", "Alice", ""]

    errors = validate_project_config(project)

    assert any("duplicate login" in error for error in errors)
    assert any("non-empty string" in error for error in errors)


def test_github_project_without_optional_warnings() -> None:
    project = _project()
    client = FakeGitHubClient(existing=[name for name, _, _ in _TEST_LABELS])

    results = ensure_github_labels(
        [project],
        labels=_TEST_LABELS,
        client_factory=lambda _project: client,
    )

    result = results["proj-gh"]
    assert result.success is True
    assert result.config_warnings == []
    assert build_label_bootstrap_alerts(results) == []


def test_ensure_github_labels_skips_non_github_projects() -> None:
    native = _project(
        id="proj-native",
        tracker_kind="oompah_md",
        tracker_owner=None,
        tracker_repo=None,
    )
    github = _project()
    client = FakeGitHubClient(existing=[name for name, _, _ in _TEST_LABELS])

    results = ensure_github_labels(
        [native, github],
        labels=_TEST_LABELS,
        client_factory=lambda _project: client,
    )

    assert set(results) == {"proj-gh"}
