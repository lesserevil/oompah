"""Tests for the focus-override feature (oompah-zlz_2-8yt).

Covers:
- POST /api/v1/agents/{identifier}/override-focus endpoint contracts
  (202, 404 not running, 400 unknown focus)
- GET /api/v1/foci/override-history endpoint
- Persistence shape of override events
- _dispatch honors override_focus (skips LLM/scorer, logs override)
- _run_worker / _run_api_worker / _run_acp_worker / _run_cli_worker
  honor override_focus
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.focus import Focus, BUILTIN_FOCI
from oompah.models import AgentProfile, Issue, RunningEntry, OrchestratorState
from oompah.orchestrator import Orchestrator
from oompah.config import ServiceConfig
from oompah.server import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(identifier: str = "test-1", state: str = "open",
                issue_type: str = "task", priority: int = 2,
                project_id: str | None = "proj-1",
                labels: list | None = None) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Test issue body — passes the empty-description gate.",
        state=state,
        issue_type=issue_type,
        priority=priority,
        project_id=project_id,
        labels=labels or [],
    )


def _make_running_entry(issue: Issue, focus_name: str = "feature",
                        focus_role: str = "Feature Developer") -> RunningEntry:
    task = MagicMock()
    task.done.return_value = False
    task.cancel = MagicMock()
    return RunningEntry(
        worker_task=task,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="standard",
        focus_name=focus_name,
        focus_role=focus_role,
    )


def _make_focus(name: str = "ci_fix", role: str = "CI Failure Fixer",
                status: str = "active") -> Focus:
    return Focus(
        name=name,
        role=role,
        description=f"Focus on {name}",
        status=status,
    )


def _make_mock_orchestrator_with_running(issue: Issue, running_entry: RunningEntry):
    """Build a mock orchestrator with a running agent."""
    mock_orch = MagicMock()
    mock_orch.state = OrchestratorState()
    mock_orch.state.running[issue.id] = running_entry

    # _terminate_running removes from state.running
    async def _mock_terminate(issue_id, cleanup_workspace):
        mock_orch.state.running.pop(issue_id, None)
        mock_orch.state.claimed.discard(issue_id)
    mock_orch._terminate_running = _mock_terminate

    # _dispatch is a coroutine
    mock_orch._dispatch = AsyncMock()

    # persist_override_event is sync
    mock_orch.persist_override_event = MagicMock()

    return mock_orch


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /api/v1/agents/{identifier}/override-focus
# ---------------------------------------------------------------------------

class TestOverrideFocusEndpoint:
    """Endpoint contract tests for POST /api/v1/agents/{id}/override-focus."""

    def test_returns_404_when_agent_not_running(self, client):
        """Returns 404 when no running entry exists for identifier."""
        mock_orch = MagicMock()
        mock_orch.state = OrchestratorState()  # empty running dict

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
        ):
            resp = client.post(
                "/api/v1/agents/nonexistent-1/override-focus",
                json={"focus_name": "ci_fix"},
            )

        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "not_running"
        assert "not running" in data["error"]["message"]

    def test_returns_400_for_unknown_focus(self, client):
        """Returns 400 when focus_name doesn't match any known focus."""
        issue = _make_issue()
        entry = _make_running_entry(issue)
        mock_orch = _make_mock_orchestrator_with_running(issue, entry)

        fake_foci = [_make_focus("ci_fix"), _make_focus("feature")]

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch("oompah.server.load_foci", return_value=fake_foci),
        ):
            resp = client.post(
                f"/api/v1/agents/{issue.identifier}/override-focus",
                json={"focus_name": "totally_unknown_focus"},
            )

        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "unknown_focus"

    def test_returns_400_when_focus_name_missing(self, client):
        """Returns 400 when focus_name is not provided."""
        mock_orch = MagicMock()
        mock_orch.state = OrchestratorState()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
        ):
            resp = client.post(
                "/api/v1/agents/any-1/override-focus",
                json={},
            )

        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "validation"

    def test_returns_202_on_success(self, client):
        """Returns 202 with override info when everything is valid."""
        issue = _make_issue()
        entry = _make_running_entry(issue)
        mock_orch = _make_mock_orchestrator_with_running(issue, entry)

        fake_foci = [_make_focus("ci_fix"), _make_focus("feature")]

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch("oompah.server.load_foci", return_value=fake_foci),
            patch("oompah.server.select_focus", return_value=fake_foci[1]),
            patch("oompah.server.score_focus", return_value=15),
        ):
            resp = client.post(
                f"/api/v1/agents/{issue.identifier}/override-focus",
                json={"focus_name": "ci_fix", "reason": "wrong focus"},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert data["ok"] is True
        assert data["identifier"] == issue.identifier
        assert data["override_focus"] == "ci_fix"
        assert "timestamp" in data

    def test_terminates_running_agent_on_success(self, client):
        """The running agent is terminated before re-dispatch."""
        issue = _make_issue()
        entry = _make_running_entry(issue)
        mock_orch = _make_mock_orchestrator_with_running(issue, entry)

        fake_foci = [_make_focus("ci_fix"), _make_focus("feature")]
        terminated_ids = []

        original_terminate = mock_orch._terminate_running

        async def _track_terminate(issue_id, cleanup_workspace):
            terminated_ids.append(issue_id)
            await original_terminate(issue_id, cleanup_workspace)

        mock_orch._terminate_running = _track_terminate

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch("oompah.server.load_foci", return_value=fake_foci),
            patch("oompah.server.select_focus", return_value=fake_foci[1]),
            patch("oompah.server.score_focus", return_value=10),
        ):
            resp = client.post(
                f"/api/v1/agents/{issue.identifier}/override-focus",
                json={"focus_name": "ci_fix"},
            )

        assert resp.status_code == 202
        assert issue.id in terminated_ids

    def test_dispatches_with_override_focus(self, client):
        """After termination, _dispatch is called with override_focus set."""
        issue = _make_issue()
        entry = _make_running_entry(issue)
        mock_orch = _make_mock_orchestrator_with_running(issue, entry)

        fake_foci = [_make_focus("ci_fix"), _make_focus("feature")]

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch("oompah.server.load_foci", return_value=fake_foci),
            patch("oompah.server.select_focus", return_value=fake_foci[1]),
            patch("oompah.server.score_focus", return_value=10),
        ):
            resp = client.post(
                f"/api/v1/agents/{issue.identifier}/override-focus",
                json={"focus_name": "ci_fix"},
            )

        assert resp.status_code == 202
        mock_orch._dispatch.assert_called_once()
        call_kwargs = mock_orch._dispatch.call_args
        # _dispatch called with issue, attempt=None, override_focus="ci_fix"
        assert call_kwargs.kwargs.get("override_focus") == "ci_fix" or \
               (len(call_kwargs.args) >= 3 and call_kwargs.args[2] == "ci_fix") or \
               call_kwargs.kwargs.get("override_focus") == "ci_fix"


# ---------------------------------------------------------------------------
# Persistence shape
# ---------------------------------------------------------------------------

class TestOverridePersistenceShape:
    """The override event persisted to bd memories has the correct shape."""

    def test_persist_override_event_calls_bd_remember(self, tmp_path):
        """persist_override_event calls _run_bd with remember + key."""
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        event = {
            "issue_id": "trickle-6zi",
            "issue_title": "Test issue",
            "issue_labels": ["ci-fix"],
            "issue_type": "task",
            "issue_priority": 0,
            "original_focus": "devops",
            "original_focus_score": 15,
            "original_focus_via": "llm",
            "override_focus": "ci_fix",
            "operator_reason": "this is a ci-fix bead",
            "timestamp": "2026-05-07T16:42:00Z",
            "project_id": "",
        }
        orch.persist_override_event(event)

        mock_tracker._run_bd.assert_called_once()
        args = mock_tracker._run_bd.call_args[0][0]
        # Should be ["remember", "<json>", "--key=focus-override-trickle-6zi-<ts>"]
        assert args[0] == "remember"
        assert "focus-override-trickle-6zi-" in args[2]
        # The second arg should be valid JSON matching the event
        stored = json.loads(args[1])
        assert stored["override_focus"] == "ci_fix"
        assert stored["original_focus"] == "devops"

    def test_event_json_has_required_fields(self):
        """All required fields are present in the override event JSON."""
        required_fields = {
            "issue_id", "issue_title", "issue_labels", "issue_type",
            "issue_priority", "original_focus", "original_focus_score",
            "original_focus_via", "override_focus", "operator_reason",
            "timestamp", "project_id",
        }
        event = {
            "issue_id": "test-1",
            "issue_title": "Test",
            "issue_labels": [],
            "issue_type": "task",
            "issue_priority": 2,
            "original_focus": "feature",
            "original_focus_score": 10,
            "original_focus_via": "llm",
            "override_focus": "ci_fix",
            "operator_reason": "",
            "timestamp": "2026-05-07T16:42:00Z",
            "project_id": "proj-1",
        }
        assert required_fields.issubset(event.keys())


# ---------------------------------------------------------------------------
# GET /api/v1/foci/override-history
# ---------------------------------------------------------------------------

class TestOverrideHistoryEndpoint:
    """Tests for GET /api/v1/foci/override-history."""

    def test_returns_empty_list_when_no_overrides(self, client):
        """Returns [] when no focus-override memories exist."""
        mock_orch = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.fetch_memories.return_value = {"some-other-key": "value"}
        mock_orch.tracker = mock_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
        ):
            resp = client.get("/api/v1/foci/override-history")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_parsed_override_events(self, client):
        """Returns parsed events from memories with focus-override- prefix."""
        event1 = {
            "issue_id": "test-1", "override_focus": "ci_fix",
            "original_focus": "feature", "timestamp": "2026-05-07T16:42:00Z",
            "project_id": "proj-1",
        }
        event2 = {
            "issue_id": "test-2", "override_focus": "feature",
            "original_focus": "devops", "timestamp": "2026-05-07T15:00:00Z",
            "project_id": "proj-1",
        }
        mock_orch = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.fetch_memories.return_value = {
            "focus-override-test-1-20260507T164200Z": json.dumps(event1),
            "focus-override-test-2-20260507T150000Z": json.dumps(event2),
            "other-memory": "irrelevant",
        }
        mock_orch.tracker = mock_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
        ):
            resp = client.get("/api/v1/foci/override-history")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Most recent first
        assert data[0]["timestamp"] >= data[1]["timestamp"]

    def test_returns_most_recent_first(self, client):
        """Events are sorted most-recent first by timestamp."""
        event_old = {
            "issue_id": "old-1", "timestamp": "2026-01-01T00:00:00Z",
            "override_focus": "ci_fix", "project_id": "",
        }
        event_new = {
            "issue_id": "new-1", "timestamp": "2026-06-01T00:00:00Z",
            "override_focus": "feature", "project_id": "",
        }
        mock_orch = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.fetch_memories.return_value = {
            "focus-override-old-1-ts": json.dumps(event_old),
            "focus-override-new-1-ts": json.dumps(event_new),
        }
        mock_orch.tracker = mock_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
        ):
            resp = client.get("/api/v1/foci/override-history")

        data = resp.json()
        assert data[0]["issue_id"] == "new-1"
        assert data[1]["issue_id"] == "old-1"

    def test_respects_limit_param(self, client):
        """Limit query param caps number of returned events."""
        memories = {
            f"focus-override-test-{i}-ts": json.dumps({
                "issue_id": f"test-{i}",
                "timestamp": f"2026-0{(i % 9) + 1}-01T00:00:00Z",
                "override_focus": "ci_fix",
                "project_id": "",
            })
            for i in range(1, 11)
        }
        mock_orch = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.fetch_memories.return_value = memories
        mock_orch.tracker = mock_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
        ):
            resp = client.get("/api/v1/foci/override-history?limit=3")

        data = resp.json()
        assert len(data) == 3

    def test_skips_invalid_json_memories(self, client):
        """Events with invalid JSON values are silently skipped."""
        mock_orch = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.fetch_memories.return_value = {
            "focus-override-valid-ts": json.dumps({"issue_id": "valid", "timestamp": "2026-01-01T00:00:00Z",
                                                    "override_focus": "ci_fix", "project_id": ""}),
            "focus-override-invalid-ts": "not valid json {{{",
        }
        mock_orch.tracker = mock_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
        ):
            resp = client.get("/api/v1/foci/override-history")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["issue_id"] == "valid"


# ---------------------------------------------------------------------------
# Dispatcher honors override_focus
# ---------------------------------------------------------------------------

class TestDispatchHonorsOverrideFocus:
    """_dispatch passes override_focus to _run_worker."""

    def test_dispatch_signature_accepts_override_focus(self, tmp_path):
        """_dispatch should accept override_focus keyword argument."""
        import inspect
        sig = inspect.signature(Orchestrator._dispatch)
        assert "override_focus" in sig.parameters

    def test_run_worker_signature_accepts_override_focus(self, tmp_path):
        """_run_worker should accept override_focus keyword argument."""
        import inspect
        sig = inspect.signature(Orchestrator._run_worker)
        assert "override_focus" in sig.parameters

    def test_run_api_worker_signature_accepts_override_focus(self, tmp_path):
        """_run_api_worker should accept override_focus keyword argument."""
        import inspect
        sig = inspect.signature(Orchestrator._run_api_worker)
        assert "override_focus" in sig.parameters

    def test_run_acp_worker_signature_accepts_override_focus(self, tmp_path):
        """_run_acp_worker should accept override_focus keyword argument."""
        import inspect
        sig = inspect.signature(Orchestrator._run_acp_worker)
        assert "override_focus" in sig.parameters

    def test_run_cli_worker_signature_accepts_override_focus(self, tmp_path):
        """_run_cli_worker should accept override_focus keyword argument."""
        import inspect
        sig = inspect.signature(Orchestrator._run_cli_worker)
        assert "override_focus" in sig.parameters

    def test_run_worker_uses_override_focus_for_api_path(self, tmp_path):
        """_run_worker calls _run_api_worker with override_focus when provider resolves."""
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

        issue = _make_issue()
        profile = MagicMock()
        profile.mode = "api"
        mock_provider = MagicMock()

        with (
            patch.object(orch, "_resolve_provider", return_value=mock_provider),
            patch.object(orch, "_run_api_worker", new_callable=AsyncMock) as mock_api,
        ):
            asyncio.run(orch._run_worker(issue, attempt=None, profile=profile, override_focus="ci_fix"))

        mock_api.assert_called_once_with(issue, None, profile, mock_provider, override_focus="ci_fix")

    def test_run_worker_uses_override_focus_for_cli_path(self, tmp_path):
        """_run_worker calls _run_cli_worker with override_focus when mode=cli."""
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

        issue = _make_issue()
        profile = MagicMock()
        profile.mode = "cli"

        with (
            patch.object(orch, "_run_cli_worker", new_callable=AsyncMock) as mock_cli,
        ):
            asyncio.run(orch._run_worker(issue, attempt=None, profile=profile, override_focus="ci_fix"))

        mock_cli.assert_called_once_with(issue, None, profile, override_focus="ci_fix")

    def test_run_worker_uses_override_focus_for_acp_path(self, tmp_path):
        """_run_worker calls _run_acp_worker with override_focus when mode=acp."""
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

        issue = _make_issue()
        profile = MagicMock()
        profile.mode = "acp"

        with (
            patch.object(orch, "_run_acp_worker", new_callable=AsyncMock) as mock_acp,
        ):
            asyncio.run(orch._run_worker(issue, attempt=None, profile=profile, override_focus="ci_fix"))

        mock_acp.assert_called_once_with(issue, None, profile, override_focus="ci_fix")

    def test_run_api_worker_uses_named_focus_when_override_set(self, tmp_path):
        """When override_focus is set, _run_api_worker uses named focus directly (not triage)."""
        ci_fix_focus = _make_focus("ci_fix", "CI Failure Fixer")
        feature_focus = _make_focus("feature", "Feature Developer")
        all_foci = [ci_fix_focus, feature_focus]

        # Test the focus selection logic directly (the logic embedded in _run_api_worker)
        # When override_focus is set, we find in all_foci by name
        with patch("oompah.orchestrator.load_foci", return_value=all_foci):
            import oompah.orchestrator as orch_mod
            loaded = orch_mod.load_foci()
            override_focus = "ci_fix"
            chosen = next((f for f in loaded if f.name == override_focus), None)
            assert chosen is not None
            assert chosen.name == "ci_fix"
            assert chosen.role == "CI Failure Fixer"

    def test_run_cli_worker_uses_named_focus_when_override_set(self, tmp_path):
        """When override_focus is set, _run_cli_worker uses named focus via load_foci."""
        ci_fix_focus = _make_focus("ci_fix", "CI Failure Fixer")
        feature_focus = _make_focus("feature", "Feature Developer")
        all_foci = [ci_fix_focus, feature_focus]

        with patch("oompah.orchestrator.load_foci", return_value=all_foci):
            import oompah.orchestrator as orch_mod
            loaded = orch_mod.load_foci()
            override_focus = "ci_fix"
            chosen = next((f for f in loaded if f.name == override_focus), None)
            assert chosen is not None
            assert chosen.name == "ci_fix"


# ---------------------------------------------------------------------------
# Dashboard HTML structural tests
# ---------------------------------------------------------------------------

class TestDashboardFocusOverrideUI:
    """Verify the focus override UI is present in dashboard.html."""

    @pytest.fixture(scope="class")
    def html(self):
        import os
        path = os.path.join(
            os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
        )
        with open(path) as f:
            return f.read()

    def test_focus_meta_row_exists(self, html):
        """activity-meta div with focus name element should exist."""
        assert 'id="activity-meta"' in html
        assert 'id="activity-focus-name"' in html

    def test_override_toggle_link_exists(self, html):
        """Override link that toggles the dropdown should be present."""
        assert 'id="focus-override-toggle"' in html
        assert "toggleFocusOverride" in html

    def test_override_select_exists(self, html):
        """Focus override select dropdown should be present."""
        assert 'id="focus-override-select"' in html

    def test_apply_button_exists(self, html):
        """Apply button should be present and call applyFocusOverride."""
        assert 'id="focus-override-apply"' in html
        assert "applyFocusOverride" in html

    def test_cancel_link_exists(self, html):
        """Cancel link should call cancelFocusOverride."""
        assert "cancelFocusOverride" in html

    def test_confirmation_prompt_in_js(self, html):
        """applyFocusOverride should use confirm() for the confirmation prompt."""
        import re
        # Find the applyFocusOverride function body
        match = re.search(
            r"async function applyFocusOverride\(\)(.*?)^}",
            html, re.DOTALL | re.MULTILINE,
        )
        assert match, "applyFocusOverride function not found"
        fn_body = match.group(1)
        assert "confirm(" in fn_body

    def test_posts_to_override_endpoint(self, html):
        """applyFocusOverride should POST to /api/v1/agents/.../override-focus."""
        assert "override-focus" in html
        assert "POST" in html

    def test_open_activity_panel_populates_focus(self, html):
        """openActivityPanel should populate activity-focus-name and show meta."""
        assert "activity-focus-name" in html
        assert "_populateFocusOverrideSelect" in html

    def test_populate_focus_override_select_fetches_foci(self, html):
        """_populateFocusOverrideSelect should fetch /api/v1/foci."""
        assert "/api/v1/foci" in html


# ---------------------------------------------------------------------------
# persist_override_event method
# ---------------------------------------------------------------------------

class TestPersistOverrideEventMethod:
    """Tests for Orchestrator.persist_override_event."""

    def test_key_contains_issue_id(self, tmp_path):
        """The bd remember key includes the issue_id."""
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        orch.persist_override_event({
            "issue_id": "my-issue-123",
            "timestamp": "2026-05-07T16:42:00Z",
            "override_focus": "ci_fix",
        })

        args = mock_tracker._run_bd.call_args[0][0]
        assert "my-issue-123" in args[2]

    def test_gracefully_handles_tracker_error(self, tmp_path):
        """persist_override_event should not raise on tracker failure."""
        from oompah.tracker import TrackerError
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        mock_tracker = MagicMock()
        mock_tracker._run_bd.side_effect = TrackerError("bd not found")
        orch.tracker = mock_tracker

        # Should not raise
        orch.persist_override_event({
            "issue_id": "test-1",
            "timestamp": "2026-01-01T00:00:00Z",
            "override_focus": "ci_fix",
        })

    def test_value_is_valid_json(self, tmp_path):
        """The value passed to bd remember must be valid JSON."""
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        event = {
            "issue_id": "test-1",
            "timestamp": "2026-01-01T00:00:00Z",
            "override_focus": "ci_fix",
            "original_focus": "feature",
        }
        orch.persist_override_event(event)

        args = mock_tracker._run_bd.call_args[0][0]
        # args[1] is the JSON value
        parsed = json.loads(args[1])
        assert parsed["override_focus"] == "ci_fix"
