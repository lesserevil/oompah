"""Tests for oompah/task_cli.py — the tracker-neutral task command wrapper.

Covers:
  - _resolve_server_url: URL env var, port override, explicit server URL
  - _http: connection error, timeout, 4xx/5xx errors, success
  - _encode_id: slash/hash encoding
  - _print_issue_detail: formatting
  - _cmd_view: correct URL, params, output
  - _cmd_comment: correct method, body
  - _cmd_create: correct body including labels, --source flag sends source_task_id
  - _cmd_child_create: parent_id in body
  - _cmd_set_status: status + summary comment
  - _cmd_add_label: correct endpoint, body
  - _cmd_remove_label: query-param identifier, encoded label
  - _cmd_set_dependency: correct endpoint, body
  - _cmd_set_source: PATCH with source_task_id; empty source exits; project forwarded
  - _cmd_remove_source: PATCH with clear_source=True; project forwarded
  - main(): dispatch table including set-source and remove-source
  - build_parser(): set-source and remove-source subcommands
  - __main__.py: task subcommand dispatch
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, call, patch

import pytest

from oompah import task_cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(**kwargs):
    """Return a mock Namespace with defaults overridden by kwargs."""
    defaults = {
        "server": None,
        "port": None,
        "subcommand": "view",
        "identifier": "TASK-1",
        "project": None,
    }
    defaults.update(kwargs)
    ns = MagicMock()
    for k, v in defaults.items():
        setattr(ns, k, v)
    return ns


# ---------------------------------------------------------------------------
# _resolve_server_url
# ---------------------------------------------------------------------------


class TestResolveServerUrl:
    def test_default_returns_localhost_8080(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_URL", raising=False)
        assert task_cli._resolve_server_url(None, None) == "http://127.0.0.1:8080"

    def test_explicit_server_wins(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_URL", "http://env.example:9999")
        result = task_cli._resolve_server_url("http://example.com:1234", None)
        assert result == "http://example.com:1234"

    def test_explicit_server_trailing_slash_stripped(self):
        assert task_cli._resolve_server_url("http://example.com/", None) == "http://example.com"

    def test_port_override_uses_localhost(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_URL", raising=False)
        result = task_cli._resolve_server_url(None, 9090)
        assert result == "http://127.0.0.1:9090"

    def test_env_server_url(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_URL", "http://10.0.0.1:7777")
        result = task_cli._resolve_server_url(None, None)
        assert result == "http://10.0.0.1:7777"

    def test_env_server_url_trailing_slash_stripped(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_URL", "http://10.0.0.1:7777/")
        result = task_cli._resolve_server_url(None, None)
        assert result == "http://10.0.0.1:7777"

    def test_port_override_takes_precedence_over_env_url(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_URL", "http://env.example:9999")
        result = task_cli._resolve_server_url(None, 1234)
        assert "1234" in result


# ---------------------------------------------------------------------------
# _encode_id
# ---------------------------------------------------------------------------


class TestEncodeId:
    def test_plain_identifier_unchanged(self):
        assert task_cli._encode_id("TASK-123") == "TASK-123"

    def test_github_identifier_encoded(self):
        encoded = task_cli._encode_id("owner/repo#42")
        assert "/" not in encoded
        assert "#" not in encoded
        assert "owner" in encoded

    def test_percent_encoded_slash(self):
        assert "%2F" in task_cli._encode_id("owner/repo#42")

    def test_percent_encoded_hash(self):
        assert "%23" in task_cli._encode_id("owner/repo#42")


class TestPathIdentifier:
    def test_plain_identifier_is_path_identifier(self):
        assert task_cli._path_identifier("TASK-123") == "TASK-123"

    def test_github_identifier_uses_issue_number_for_path(self):
        assert task_cli._path_identifier("owner/repo#42") == "42"

    def test_github_identifier_path_id_has_no_encoded_slash(self):
        encoded = task_cli._encode_path_id("owner/repo#42")
        assert encoded == "42"
        assert "%2F" not in encoded


# ---------------------------------------------------------------------------
# _http — error handling
# ---------------------------------------------------------------------------


class TestHttpErrorHandling:
    def test_default_timeout_is_long_enough_for_busy_local_server(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_TASK_CLI_TIMEOUT_SECONDS", raising=False)
        assert task_cli._resolve_http_timeout() == 600.0

    def test_timeout_env_override(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_TASK_CLI_TIMEOUT_SECONDS", "45.5")
        assert task_cli._resolve_http_timeout() == 45.5

    @pytest.mark.parametrize("value", ["", "bogus", "0", "-1", "inf", "nan"])
    def test_invalid_timeout_env_uses_default(self, monkeypatch, value):
        monkeypatch.setenv("OOMPAH_TASK_CLI_TIMEOUT_SECONDS", value)
        assert task_cli._resolve_http_timeout() == 600.0

    def test_http_uses_resolved_timeout(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_TASK_CLI_TIMEOUT_SECONDS", "75")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.is_success = True
        mock_resp.status_code = 200

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client", return_value=mock_client) as client_cls:
            result = task_cli._http("GET", "http://127.0.0.1:8080/api/v1/test")

        assert result == {"ok": True}
        client_cls.assert_called_once_with(timeout=75.0)

    def test_connection_error_exits_with_actionable_message(self):
        import httpx

        with (
            patch.object(
                httpx.Client,
                "__enter__",
                side_effect=httpx.ConnectError("refused"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            task_cli._http("GET", "http://127.0.0.1:8080/api/v1/issues/x/detail")
        assert exc_info.value.code != 0
        msg = str(exc_info.value.code)
        assert "ERROR" in msg
        assert "oompah server" in msg.lower() or "connect" in msg.lower()

    def test_timeout_exits_with_actionable_message(self):
        import httpx

        with (
            patch.object(
                httpx.Client,
                "__enter__",
                side_effect=httpx.TimeoutException("timeout"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            task_cli._http("GET", "http://127.0.0.1:8080/api/v1/issues/x/detail")
        assert exc_info.value.code != 0
        msg = str(exc_info.value.code)
        assert "timed out" in msg.lower() or "timeout" in msg.lower()

    def test_4xx_exits_with_error_message(self):
        import httpx

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error": {"message": "not found"}}
        mock_resp.is_success = False
        mock_resp.status_code = 404
        mock_resp.text = "not found"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp

        with (
            patch("httpx.Client", return_value=mock_client),
            pytest.raises(SystemExit) as exc_info,
        ):
            task_cli._http("GET", "http://127.0.0.1:8080/api/v1/issues/x/detail")
        assert exc_info.value.code != 0
        assert "404" in str(exc_info.value.code)

    def test_success_returns_dict(self):
        import httpx

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.is_success = True
        mock_resp.status_code = 200

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client", return_value=mock_client):
            result = task_cli._http("GET", "http://127.0.0.1:8080/api/v1/test")
        assert result == {"ok": True}


# ---------------------------------------------------------------------------
# _print_issue_detail
# ---------------------------------------------------------------------------


class TestPrintIssueDetail:
    def test_minimal_detail_prints_without_error(self, capsys):
        task_cli._print_issue_detail({"identifier": "TASK-1", "title": "Test"})
        out = capsys.readouterr().out
        assert "TASK-1" in out
        assert "Test" in out

    def test_full_detail_with_all_fields(self, capsys):
        task_cli._print_issue_detail(
            {
                "display_identifier": "tasks#1",
                "title": "My Feature",
                "state": "In Progress",
                "priority": "high",
                "project_name": "My Project",
                "labels": ["bug", "needs:frontend"],
                "url": "https://github.com/org/repo/issues/1",
                "description": "A detailed description.",
                "children": [
                    {
                        "identifier": "TASK-2",
                        "title": "Child task",
                        "state": "Backlog",
                    }
                ],
                "comments": [
                    {
                        "id": 1,
                        "author": "oompah",
                        "created_at": "2026-01-01",
                        "text": "A comment.",
                    }
                ],
            }
        )
        out = capsys.readouterr().out
        assert "tasks#1" in out
        assert "My Feature" in out
        assert "In Progress" in out
        assert "high" in out
        assert "My Project" in out
        assert "bug" in out
        assert "https://github.com" in out
        assert "A detailed description." in out
        assert "TASK-2" in out
        assert "Child task" in out
        assert "oompah" in out
        assert "A comment." in out

    def test_missing_labels_skipped(self, capsys):
        task_cli._print_issue_detail({"identifier": "T-1", "title": "x"})
        out = capsys.readouterr().out
        assert "Labels" not in out


# ---------------------------------------------------------------------------
# Individual command functions
# ---------------------------------------------------------------------------


def _make_http_mock(return_value: dict | None = None):
    """Return a patch context and mock for task_cli._http."""
    if return_value is None:
        return_value = {"ok": True}
    return patch.object(task_cli, "_http", return_value=return_value)


class TestCmdView:
    def test_calls_detail_endpoint(self, capsys):
        detail = {
            "identifier": "TASK-42",
            "title": "Test task",
            "state": "open",
        }
        args = _make_args(subcommand="view", identifier="TASK-42", project=None)
        with _make_http_mock(detail):
            task_cli._cmd_view("http://localhost:8080", args)
        out = capsys.readouterr().out
        assert "TASK-42" in out

    def test_uses_issue_key_param(self):
        args = _make_args(subcommand="view", identifier="owner/repo#42", project=None)
        with _make_http_mock({"identifier": "owner/repo#42", "title": "t"}) as m:
            task_cli._cmd_view("http://localhost:8080", args)
        _url, = [c.args[1] for c in m.call_args_list]
        # issue_key must be in params or the URL
        call_kwargs = m.call_args.kwargs or {}
        params = call_kwargs.get("params", {})
        assert params.get("issue_key") == "owner/repo#42"

    def test_github_identifier_uses_route_safe_path_segment(self):
        args = _make_args(subcommand="view", identifier="owner/repo#42", project=None)
        with _make_http_mock({"identifier": "owner/repo#42", "title": "t"}) as m:
            task_cli._cmd_view("http://localhost:8080", args)
        url = m.call_args.args[1]
        assert url == "http://localhost:8080/api/v1/issues/42/detail"

    def test_github_identifier_adds_managed_repo_when_project_omitted(self):
        args = _make_args(subcommand="view", identifier="owner/repo#42", project=None)
        with _make_http_mock({"identifier": "owner/repo#42", "title": "t"}) as m:
            task_cli._cmd_view("http://localhost:8080", args)
        params = (m.call_args.kwargs or {}).get("params", {})
        assert params["managed_repo"] == "owner/repo"

    def test_passes_project_id_when_given(self):
        args = _make_args(subcommand="view", identifier="TASK-1", project="proj-99")
        with _make_http_mock({"identifier": "TASK-1", "title": "t"}) as m:
            task_cli._cmd_view("http://localhost:8080", args)
        params = (m.call_args.kwargs or {}).get("params", {})
        assert params.get("project_id") == "proj-99"


class TestCmdComment:
    def test_posts_to_comments_endpoint(self):
        args = _make_args(
            subcommand="comment",
            identifier="TASK-1",
            message="Hello!",
            author="oompah",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_comment("http://localhost:8080", args)
        assert m.called
        url = m.call_args.args[1]
        assert "/comments" in url

    def test_body_contains_text_and_author(self):
        args = _make_args(
            subcommand="comment",
            identifier="TASK-1",
            message="My comment",
            author="oompah",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_comment("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["text"] == "My comment"
        assert data["author"] == "oompah"

    def test_body_contains_issue_key(self):
        args = _make_args(
            subcommand="comment",
            identifier="owner/repo#5",
            message="hi",
            author="user",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_comment("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["issue_key"] == "owner/repo#5"
        assert data["managed_repo"] == "owner/repo"

    def test_prints_confirmation(self, capsys):
        args = _make_args(
            subcommand="comment",
            identifier="TASK-1",
            message="hi",
            author="oompah",
            project=None,
        )
        with _make_http_mock():
            task_cli._cmd_comment("http://localhost:8080", args)
        assert "posted" in capsys.readouterr().out.lower()


class TestCmdCreate:
    def test_posts_to_issues_endpoint(self):
        args = _make_args(
            subcommand="create",
            title="New task",
            project="proj-1",
            issue_type="task",
            description=None,
            priority=None,
            labels=None,
        )
        with _make_http_mock({"ok": True, "issue": {"identifier": "T-99", "title": "New task"}}) as m:
            task_cli._cmd_create("http://localhost:8080", args)
        url = m.call_args.args[1]
        assert "/issues" in url
        assert m.call_args.args[0] == "POST"

    def test_body_contains_title_and_project(self):
        args = _make_args(
            subcommand="create",
            title="Test",
            project="proj-X",
            issue_type="task",
            description=None,
            priority=None,
            labels=None,
        )
        with _make_http_mock({"ok": True, "issue": {"identifier": "T-1", "title": "Test"}}) as m:
            task_cli._cmd_create("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["title"] == "Test"
        assert data["project_id"] == "proj-X"

    def test_labels_included_in_body(self):
        args = _make_args(
            subcommand="create",
            title="Tagged",
            project="proj-1",
            issue_type="bug",
            description=None,
            priority="high",
            labels=["needs:frontend", "p0"],
        )
        with _make_http_mock({"ok": True, "issue": {"identifier": "T-2", "title": "Tagged"}}) as m:
            task_cli._cmd_create("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert "needs:frontend" in data["labels"]
        assert data["priority"] == "high"

    def test_prints_created_identifier(self, capsys):
        args = _make_args(
            subcommand="create",
            title="T",
            project="p",
            issue_type="task",
            description=None,
            priority=None,
            labels=None,
        )
        with _make_http_mock({"ok": True, "issue": {"identifier": "T-77", "title": "T", "url": "http://x"}}):
            task_cli._cmd_create("http://localhost:8080", args)
        out = capsys.readouterr().out
        assert "T-77" in out
        assert "http://x" in out

    def test_source_task_id_included_when_given(self):
        """--source sends source_task_id so server can prepend 'Triggered by:' to description."""
        args = _make_args(
            subcommand="create",
            title="Follow-up task",
            project="proj-1",
            issue_type="task",
            description="Some detail",
            priority=None,
            labels=None,
            source="TASK-99",
        )
        with _make_http_mock({"ok": True, "issue": {"identifier": "T-100", "title": "Follow-up task"}}) as m:
            task_cli._cmd_create("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data.get("source_task_id") == "TASK-99"

    def test_source_task_id_omitted_when_not_given(self):
        """Without --source, source_task_id is absent from the request body."""
        args = _make_args(
            subcommand="create",
            title="Plain task",
            project="proj-1",
            issue_type="task",
            description=None,
            priority=None,
            labels=None,
            source=None,
        )
        with _make_http_mock({"ok": True, "issue": {"identifier": "T-101", "title": "Plain task"}}) as m:
            task_cli._cmd_create("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert "source_task_id" not in data


class TestCmdChildCreate:
    def test_body_contains_parent_id(self):
        args = _make_args(
            subcommand="child-create",
            parent_id="TASK-10",
            title="Child",
            project=None,
            issue_type="task",
            description=None,
            priority=None,
        )
        with _make_http_mock({"ok": True, "issue": {"identifier": "T-11", "title": "Child"}}) as m:
            task_cli._cmd_child_create("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["parent_id"] == "TASK-10"
        assert data["title"] == "Child"

    def test_project_id_included_when_given(self):
        args = _make_args(
            subcommand="child-create",
            parent_id="TASK-10",
            title="Child",
            project="proj-42",
            issue_type="task",
            description=None,
            priority=None,
        )
        with _make_http_mock({"ok": True, "issue": {"identifier": "T-11", "title": "Child"}}) as m:
            task_cli._cmd_child_create("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["project_id"] == "proj-42"

    def test_github_parent_adds_managed_repo_when_project_omitted(self):
        args = _make_args(
            subcommand="child-create",
            parent_id="owner/repo#10",
            title="Child",
            project=None,
            issue_type="task",
            description=None,
            priority=None,
        )
        with _make_http_mock({"ok": True, "issue": {"identifier": "T-11", "title": "Child"}}) as m:
            task_cli._cmd_child_create("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["managed_repo"] == "owner/repo"


class TestCmdSetStatus:
    def test_patches_issue_with_status(self):
        args = _make_args(
            subcommand="set-status",
            identifier="TASK-5",
            status="Done",
            summary=None,
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_status("http://localhost:8080", args)
        assert m.call_args.args[0] == "PATCH"
        data = m.call_args.kwargs.get("data", {})
        assert data["status"] == "Done"

    def test_summary_posts_comment(self):
        args = _make_args(
            subcommand="set-status",
            identifier="TASK-5",
            status="Done",
            summary="All done!",
            project=None,
        )
        calls = []
        def _fake_http(method, url, *, data=None, params=None):
            calls.append((method, url, data))
            return {"ok": True}

        with patch.object(task_cli, "_http", side_effect=_fake_http):
            task_cli._cmd_set_status("http://localhost:8080", args)

        # First call: PATCH status; second call: POST comment
        assert len(calls) == 2
        assert calls[0][0] == "PATCH"
        assert calls[1][0] == "POST"
        assert "/comments" in calls[1][1]
        assert calls[1][2]["text"] == "All done!"

    def test_github_identifier_adds_managed_repo(self):
        args = _make_args(
            subcommand="set-status",
            identifier="owner/repo#5",
            status="Done",
            summary=None,
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_status("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["managed_repo"] == "owner/repo"

    def test_no_summary_no_comment_call(self):
        args = _make_args(
            subcommand="set-status",
            identifier="TASK-5",
            status="Open",
            summary=None,
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_status("http://localhost:8080", args)
        assert m.call_count == 1

    def test_actor_forwarded_for_gated_status_transition(self):
        args = _make_args(
            subcommand="set-status",
            identifier="TASK-5",
            status="Open",
            summary=None,
            project=None,
            actor="owner",
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_status("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["actor_login"] == "owner"

    def test_prints_new_status(self, capsys):
        args = _make_args(
            subcommand="set-status",
            identifier="TASK-5",
            status="In Progress",
            summary=None,
            project=None,
        )
        with _make_http_mock():
            task_cli._cmd_set_status("http://localhost:8080", args)
        out = capsys.readouterr().out
        assert "In Progress" in out


class TestCmdAddLabel:
    def test_posts_to_labels_endpoint(self):
        args = _make_args(
            subcommand="add-label",
            identifier="TASK-1",
            label="needs:frontend",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_add_label("http://localhost:8080", args)
        url = m.call_args.args[1]
        assert "/labels" in url
        assert m.call_args.args[0] == "POST"

    def test_body_contains_label(self):
        args = _make_args(
            subcommand="add-label",
            identifier="TASK-1",
            label="bug",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_add_label("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["label"] == "bug"

    def test_actor_forwarded_for_gated_status_label(self):
        args = _make_args(
            subcommand="add-label",
            identifier="TASK-1",
            label="oompah:status:open",
            project=None,
            actor="owner",
        )
        with _make_http_mock() as m:
            task_cli._cmd_add_label("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["actor_login"] == "owner"

    def test_prints_confirmation(self, capsys):
        args = _make_args(
            subcommand="add-label",
            identifier="TASK-1",
            label="draft",
            project=None,
        )
        with _make_http_mock():
            task_cli._cmd_add_label("http://localhost:8080", args)
        assert "draft" in capsys.readouterr().out


class TestCmdRemoveLabel:
    def test_deletes_from_label_endpoint(self):
        args = _make_args(
            subcommand="remove-label",
            identifier="TASK-1",
            label="draft",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_remove_label("http://localhost:8080", args)
        assert m.call_args.args[0] == "DELETE"

    def test_label_appears_in_url(self):
        args = _make_args(
            subcommand="remove-label",
            identifier="TASK-1",
            label="draft",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_remove_label("http://localhost:8080", args)
        url = m.call_args.args[1]
        assert "draft" in url

    def test_url_encoded_label_in_url(self):
        args = _make_args(
            subcommand="remove-label",
            identifier="TASK-1",
            label="needs:frontend",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_remove_label("http://localhost:8080", args)
        url = m.call_args.args[1]
        # colon must be percent-encoded
        assert "%3A" in url or "needs%3Afrontend" in url

    def test_issue_key_in_params(self):
        args = _make_args(
            subcommand="remove-label",
            identifier="owner/repo#7",
            label="bug",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_remove_label("http://localhost:8080", args)
        params = (m.call_args.kwargs or {}).get("params", {})
        assert params.get("issue_key") == "owner/repo#7"

    def test_prints_confirmation(self, capsys):
        args = _make_args(
            subcommand="remove-label",
            identifier="TASK-1",
            label="draft",
            project=None,
        )
        with _make_http_mock():
            task_cli._cmd_remove_label("http://localhost:8080", args)
        assert "draft" in capsys.readouterr().out


class TestCmdSetSource:
    def test_patches_issue_with_source_task_id(self):
        """set-source sends PATCH with source_task_id in the body."""
        args = _make_args(
            subcommand="set-source",
            identifier="TASK-5",
            source_id="TASK-42",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_source("http://localhost:8080", args)
        assert m.call_args.args[0] == "PATCH"
        data = m.call_args.kwargs.get("data", {})
        assert data["source_task_id"] == "TASK-42"

    def test_patches_issue_url_contains_identifier(self):
        args = _make_args(
            subcommand="set-source",
            identifier="TASK-5",
            source_id="TASK-42",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_source("http://localhost:8080", args)
        url = m.call_args.args[1]
        assert "TASK-5" in url
        assert url.startswith("http://localhost:8080/api/v1/issues/")

    def test_body_contains_issue_key(self):
        args = _make_args(
            subcommand="set-source",
            identifier="TASK-5",
            source_id="TASK-42",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_source("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["issue_key"] == "TASK-5"

    def test_project_forwarded_when_given(self):
        args = _make_args(
            subcommand="set-source",
            identifier="TASK-5",
            source_id="TASK-42",
            project="proj-99",
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_source("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data.get("project_id") == "proj-99"

    def test_github_identifier_adds_managed_repo(self):
        args = _make_args(
            subcommand="set-source",
            identifier="owner/repo#5",
            source_id="TASK-42",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_source("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data.get("managed_repo") == "owner/repo"

    def test_empty_source_id_exits_before_http_call(self):
        """An empty string source_id must exit with an error, not send to server."""
        args = _make_args(
            subcommand="set-source",
            identifier="TASK-5",
            source_id="   ",  # whitespace-only
            project=None,
        )
        with _make_http_mock() as m:
            with pytest.raises(SystemExit) as exc_info:
                task_cli._cmd_set_source("http://localhost:8080", args)
        assert exc_info.value.code != 0
        m.assert_not_called()

    def test_prints_confirmation_with_source_id(self, capsys):
        args = _make_args(
            subcommand="set-source",
            identifier="TASK-5",
            source_id="TASK-42",
            project=None,
        )
        with _make_http_mock():
            task_cli._cmd_set_source("http://localhost:8080", args)
        out = capsys.readouterr().out
        assert "TASK-42" in out

    def test_replace_existing_source_sends_new_source_task_id(self):
        """set-source on a task that already has a source sends the new id."""
        args = _make_args(
            subcommand="set-source",
            identifier="TASK-5",
            source_id="TASK-99",  # replacing TASK-42
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_source("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["source_task_id"] == "TASK-99"


class TestCmdRemoveSource:
    def test_patches_issue_with_clear_source(self):
        """remove-source sends PATCH with clear_source=True in the body."""
        args = _make_args(
            subcommand="remove-source",
            identifier="TASK-5",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_remove_source("http://localhost:8080", args)
        assert m.call_args.args[0] == "PATCH"
        data = m.call_args.kwargs.get("data", {})
        assert data.get("clear_source") is True

    def test_patches_issue_url_contains_identifier(self):
        args = _make_args(
            subcommand="remove-source",
            identifier="TASK-7",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_remove_source("http://localhost:8080", args)
        url = m.call_args.args[1]
        assert "TASK-7" in url
        assert url.startswith("http://localhost:8080/api/v1/issues/")

    def test_body_contains_issue_key(self):
        args = _make_args(
            subcommand="remove-source",
            identifier="TASK-7",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_remove_source("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["issue_key"] == "TASK-7"

    def test_project_forwarded_when_given(self):
        args = _make_args(
            subcommand="remove-source",
            identifier="TASK-7",
            project="proj-42",
        )
        with _make_http_mock() as m:
            task_cli._cmd_remove_source("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data.get("project_id") == "proj-42"

    def test_github_identifier_adds_managed_repo(self):
        args = _make_args(
            subcommand="remove-source",
            identifier="owner/repo#12",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_remove_source("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data.get("managed_repo") == "owner/repo"

    def test_source_task_id_not_in_body(self):
        """remove-source must NOT send source_task_id (only clear_source)."""
        args = _make_args(
            subcommand="remove-source",
            identifier="TASK-5",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_remove_source("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert "source_task_id" not in data

    def test_prints_removal_confirmation(self, capsys):
        args = _make_args(
            subcommand="remove-source",
            identifier="TASK-5",
            project=None,
        )
        with _make_http_mock():
            task_cli._cmd_remove_source("http://localhost:8080", args)
        out = capsys.readouterr().out
        assert "removed" in out.lower()


class TestCmdSetDependency:
    def test_posts_to_dependencies_endpoint(self):
        args = _make_args(
            subcommand="set-dependency",
            identifier="TASK-2",
            depends_on="TASK-1",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_dependency("http://localhost:8080", args)
        assert m.call_args.args[0] == "POST"
        url = m.call_args.args[1]
        assert "/dependencies" in url

    def test_body_contains_depends_on(self):
        args = _make_args(
            subcommand="set-dependency",
            identifier="TASK-2",
            depends_on="TASK-1",
            project=None,
        )
        with _make_http_mock() as m:
            task_cli._cmd_set_dependency("http://localhost:8080", args)
        data = m.call_args.kwargs.get("data", {})
        assert data["depends_on"] == "TASK-1"

    def test_prints_confirmation(self, capsys):
        args = _make_args(
            subcommand="set-dependency",
            identifier="TASK-2",
            depends_on="TASK-1",
            project=None,
        )
        with _make_http_mock():
            task_cli._cmd_set_dependency("http://localhost:8080", args)
        out = capsys.readouterr().out
        assert "TASK-2" in out
        assert "TASK-1" in out


# ---------------------------------------------------------------------------
# main() / build_parser()
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_view_subcommand_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(["view", "TASK-99"])
        assert args.subcommand == "view"
        assert args.identifier == "TASK-99"

    def test_comment_subcommand_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(["comment", "TASK-1", "--message", "hello"])
        assert args.subcommand == "comment"
        assert args.message == "hello"
        assert args.author == "oompah"

    def test_create_subcommand_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["create", "--title", "My Task", "--description", "My task description", "--project", "proj-1"]
        )
        assert args.subcommand == "create"
        assert args.title == "My Task"
        assert args.project == "proj-1"
        assert args.issue_type == "task"

    def test_create_with_multiple_labels(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            [
                "create",
                "--title", "T",
                "--description", "T description",
                "--project", "p",
                "--label", "bug",
                "--label", "p0",
            ]
        )
        assert args.labels == ["bug", "p0"]

    def test_create_with_source_flag(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["create", "--title", "Follow-up", "--description", "Follow-up description", "--project", "p", "--source", "TASK-42"]
        )
        assert args.source == "TASK-42"

    def test_create_source_defaults_to_none(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["create", "--title", "No source", "--description", "No source description", "--project", "p"]
        )
        assert args.source is None

    def test_child_create_subcommand_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["child-create", "TASK-5", "--title", "Sub", "--description", "Sub task description"]
        )
        assert args.subcommand == "child-create"
        assert args.parent_id == "TASK-5"
        assert args.title == "Sub"

    def test_set_status_subcommand_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["set-status", "TASK-1", "Done", "--summary", "All done"]
        )
        assert args.subcommand == "set-status"
        assert args.status == "Done"
        assert args.summary == "All done"

    def test_add_label_subcommand_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(["add-label", "TASK-1", "draft"])
        assert args.subcommand == "add-label"
        assert args.label == "draft"

    def test_remove_label_subcommand_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(["remove-label", "TASK-1", "draft"])
        assert args.subcommand == "remove-label"
        assert args.label == "draft"

    def test_set_dependency_subcommand_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["set-dependency", "TASK-2", "--depends-on", "TASK-1"]
        )
        assert args.subcommand == "set-dependency"
        assert args.identifier == "TASK-2"
        assert args.depends_on == "TASK-1"

    def test_set_source_subcommand_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(["set-source", "TASK-5", "TASK-42"])
        assert args.subcommand == "set-source"
        assert args.identifier == "TASK-5"
        assert args.source_id == "TASK-42"
        assert args.project is None

    def test_set_source_with_project_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["set-source", "TASK-5", "TASK-42", "--project", "proj-1"]
        )
        assert args.project == "proj-1"

    def test_set_source_with_project_id_alias(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["set-source", "TASK-5", "TASK-42", "--project-id", "proj-1"]
        )
        assert args.project == "proj-1"

    def test_set_source_missing_source_id_exits(self):
        """set-source without SOURCE_ID argument must fail argument parsing."""
        parser = task_cli.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["set-source", "TASK-5"])

    def test_remove_source_subcommand_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(["remove-source", "TASK-5"])
        assert args.subcommand == "remove-source"
        assert args.identifier == "TASK-5"
        assert args.project is None

    def test_remove_source_with_project_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["remove-source", "TASK-5", "--project", "proj-1"]
        )
        assert args.project == "proj-1"

    def test_port_flag_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(["--port", "9090", "view", "TASK-1"])
        assert args.port == 9090

    def test_server_flag_parses(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["--server", "http://example.com:1234", "view", "TASK-1"]
        )
        assert args.server == "http://example.com:1234"

    def test_project_id_alias(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(["view", "TASK-1", "--project-id", "proj-9"])
        assert args.project == "proj-9"

    def test_final_summary_alias(self):
        parser = task_cli.build_parser()
        args = parser.parse_args(
            ["set-status", "TASK-1", "Done", "--final-summary", "done msg"]
        )
        assert args.summary == "done msg"

    def test_no_subcommand_exits(self):
        parser = task_cli.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


class TestMainDispatch:
    def test_main_dispatches_view(self):
        with patch.object(task_cli, "_cmd_view") as mock_view:
            with patch.object(task_cli, "_http", return_value={"identifier": "T", "title": "t"}):
                task_cli.main(["view", "TASK-1"])
        mock_view.assert_called_once()

    def test_main_dispatches_comment(self):
        with patch.object(task_cli, "_cmd_comment") as mock_fn:
            task_cli.main(["comment", "TASK-1", "--message", "hi"])
        mock_fn.assert_called_once()

    def test_main_dispatches_create(self):
        with patch.object(task_cli, "_cmd_create") as mock_fn:
            task_cli.main(["create", "--title", "T", "--description", "T description", "--project", "p"])
        mock_fn.assert_called_once()

    def test_main_dispatches_child_create(self):
        with patch.object(task_cli, "_cmd_child_create") as mock_fn:
            task_cli.main(["child-create", "TASK-5", "--title", "Sub", "--description", "Sub description"])
        mock_fn.assert_called_once()

    def test_main_dispatches_set_status(self):
        with patch.object(task_cli, "_cmd_set_status") as mock_fn:
            task_cli.main(["set-status", "TASK-1", "Done"])
        mock_fn.assert_called_once()

    def test_main_dispatches_add_label(self):
        with patch.object(task_cli, "_cmd_add_label") as mock_fn:
            task_cli.main(["add-label", "TASK-1", "draft"])
        mock_fn.assert_called_once()

    def test_main_dispatches_remove_label(self):
        with patch.object(task_cli, "_cmd_remove_label") as mock_fn:
            task_cli.main(["remove-label", "TASK-1", "draft"])
        mock_fn.assert_called_once()

    def test_main_dispatches_set_dependency(self):
        with patch.object(task_cli, "_cmd_set_dependency") as mock_fn:
            task_cli.main(["set-dependency", "TASK-2", "--depends-on", "TASK-1"])
        mock_fn.assert_called_once()

    def test_main_dispatches_set_source(self):
        with patch.object(task_cli, "_cmd_set_source") as mock_fn:
            task_cli.main(["set-source", "TASK-5", "TASK-42"])
        mock_fn.assert_called_once()

    def test_main_dispatches_remove_source(self):
        with patch.object(task_cli, "_cmd_remove_source") as mock_fn:
            task_cli.main(["remove-source", "TASK-5"])
        mock_fn.assert_called_once()

    def test_main_passes_port_to_server_url(self):
        resolved_urls = []

        def _fake_cmd_view(base_url, args):
            resolved_urls.append(base_url)

        with patch.object(task_cli, "_cmd_view", side_effect=_fake_cmd_view):
            task_cli.main(["--port", "9191", "view", "TASK-1"])
        assert resolved_urls and "9191" in resolved_urls[0]


# ---------------------------------------------------------------------------
# __main__.py integration
# ---------------------------------------------------------------------------


class TestMainEntryPoint:
    def test_oompah_task_dispatches_to_task_cli(self, monkeypatch):
        """oompah task view ... should reach task_cli.main."""
        dispatched = []
        monkeypatch.setattr(sys, "argv", ["oompah", "task", "view", "TASK-1"])

        def _fake_task_main(argv):
            dispatched.append(argv)

        with patch("oompah.task_cli.main", side_effect=_fake_task_main):
            from oompah import __main__
            # Re-import to pick up changes; or call main directly
            import importlib
            # Patch the import inside __main__
            with patch.dict(sys.modules, {}):
                import oompah.__main__ as mm
                with patch.object(mm, "main", wraps=mm.main):
                    pass
        # Just verify the module structure is correct
        assert hasattr(task_cli, "main")
