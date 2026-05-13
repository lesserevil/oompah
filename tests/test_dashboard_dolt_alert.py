"""Tests for the Dolt-sync alert click-to-expand modal (oompah-zlz_2-g8uk).

Two layers:

* Static template assertions on ``oompah/templates/dashboard.html``:
  the modal markup exists, the dolt_sync alert is wired to be clickable,
  the JS helper functions exist (openDoltSyncAlertModal, copyDoltSyncCommand,
  buildDoltSyncRecoveryCommand), and the three command branches are
  literally present.

* Backend assertion: ``_dolt_summarize_for_alerts`` includes
  ``project_id`` in every alert dict so the dashboard can map a clicked
  alert back to ``/api/v1/orchestrator/dolt-sync``.

The frontend logic is exercised via lightweight regex / substring checks
to avoid a hard dependency on a JS runtime; this mirrors the approach in
tests/test_dashboard_hide_merged.py.
"""

from __future__ import annotations

import os
import re

import pytest

from oompah.dolt_sync import DoltSyncState, summarize_for_alerts
from oompah.models import Project


# ---------------------------------------------------------------------------
# Helpers — load dashboard.html
# ---------------------------------------------------------------------------


def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "oompah",
        "templates",
        "dashboard.html",
    )
    with open(template_path, "r") as fh:
        return fh.read()


def _make_project(name: str = "trickle", pid: str = "proj-1") -> Project:
    return Project(
        id=pid,
        name=name,
        repo_url="https://example.com/trickle.git",
        repo_path="/tmp/" + name,
        branch="main",
        paused=False,
    )


@pytest.fixture(scope="module")
def html() -> str:
    return _load_dashboard_html()


# ===========================================================================
# 1. Backend: alert dict includes project_id
# ===========================================================================


class TestAlertProjectId:
    """`_dolt_summarize_for_alerts` (re-exported as summarize_for_alerts)
    must include ``project_id`` in each alert dict so the dashboard can
    map clicks back to the dolt-sync snapshot."""

    def test_divergent_alert_includes_project_id(self):
        proj = _make_project(name="trickle", pid="proj-trickle")
        st = DoltSyncState(project_id=proj.id, divergent=True)
        alerts = summarize_for_alerts({proj.id: st}, {proj.id: proj})
        assert len(alerts) == 1
        assert alerts[0]["project_id"] == "proj-trickle"
        assert alerts[0]["source"] == "dolt_sync"

    def test_consecutive_errors_alert_includes_project_id(self):
        proj = _make_project(name="trickle", pid="proj-trickle")
        st = DoltSyncState(
            project_id=proj.id,
            consecutive_errors=4,
            last_error="rate limited",
        )
        alerts = summarize_for_alerts({proj.id: st}, {proj.id: proj})
        assert len(alerts) == 1
        assert alerts[0]["project_id"] == "proj-trickle"
        assert alerts[0]["source"] == "dolt_sync"

    def test_missing_project_still_carries_id(self):
        """Even when the project lookup misses, the alert still routes
        back via the state-dict key."""
        st = DoltSyncState(project_id="proj-orphan", divergent=True)
        alerts = summarize_for_alerts({"proj-orphan": st}, {})
        assert len(alerts) == 1
        assert alerts[0]["project_id"] == "proj-orphan"

    def test_multiple_problematic_projects(self):
        p1 = _make_project(name="a", pid="proj-a")
        p2 = _make_project(name="b", pid="proj-b")
        states = {
            p1.id: DoltSyncState(project_id=p1.id, divergent=True),
            p2.id: DoltSyncState(
                project_id=p2.id, consecutive_errors=3, last_error="oops",
            ),
        }
        alerts = summarize_for_alerts(states, {p1.id: p1, p2.id: p2})
        assert {a["project_id"] for a in alerts} == {"proj-a", "proj-b"}


# ===========================================================================
# 2. Frontend: alerts are rendered with a clickable dolt-sync handler
# ===========================================================================


class TestAlertRenderingClickable:
    """The agent-bar alert renderer must distinguish dolt_sync alerts
    and wire them to ``openDoltSyncAlertModal(project_id)``."""

    def test_renderer_branches_on_dolt_sync_source(self, html: str):
        # Look for the JS that decides clickable vs plain. The renderer
        # explicitly checks the 'dolt_sync' source AND requires project_id.
        assert "source === 'dolt_sync'" in html, (
            "Alert renderer must check a.source === 'dolt_sync' to make "
            "dolt-sync entries clickable"
        )
        assert "openDoltSyncAlertModal" in html, (
            "Clickable dolt_sync alerts must invoke openDoltSyncAlertModal"
        )

    def test_renderer_uses_cursor_pointer(self, html: str):
        # The chevron / pointer cursor are user-discoverability cues.
        # Look in the renderer for a cursor:pointer or pointer style on
        # the dolt-sync alert span.
        assert "dolt-sync-alert" in html, (
            "Clickable alert span must carry the dolt-sync-alert class"
        )
        # Pointer cursor must be applied somewhere on the dolt-sync alert.
        m = re.search(
            r"dolt-sync-alert[^<]*cursor:pointer", html, re.DOTALL,
        )
        assert m, "dolt-sync-alert span must include cursor:pointer styling"

    def test_renderer_includes_chevron(self, html: str):
        """A right-chevron (›) is the visual affordance for click-to-expand."""
        # The renderer should append a › glyph (HTML entity &#8250;) to
        # signal clickability.
        assert "&#8250;" in html, (
            "Clickable dolt_sync alert must include a › chevron glyph"
        )


# ===========================================================================
# 3. Frontend: modal markup exists
# ===========================================================================


class TestModalMarkup:
    """The modal markup exists at the bottom of the dashboard and
    follows the dialog-overlay pattern used by create-dialog."""

    def test_modal_overlay_present(self, html: str):
        assert 'id="dolt-sync-dialog"' in html, (
            "Dashboard must contain a <div id='dolt-sync-dialog'> modal"
        )

    def test_modal_uses_dialog_overlay_class(self, html: str):
        m = re.search(
            r'class="dialog-overlay"[^>]*id="dolt-sync-dialog"', html,
        )
        assert m, (
            "Modal must reuse the .dialog-overlay class for backdrop and "
            "centring (consistent with create-dialog)"
        )

    def test_modal_body_container_present(self, html: str):
        assert 'id="dolt-sync-dialog-body"' in html, (
            "Modal must contain a body container the JS can populate"
        )

    def test_modal_closes_on_backdrop_click(self, html: str):
        # The overlay-click-to-close pattern is `onclick=if(event.target===this)...`
        m = re.search(
            r'id="dolt-sync-dialog"[^>]*onclick="[^"]*closeDoltSyncAlertModal',
            html,
        )
        assert m, "Modal backdrop must close on click via closeDoltSyncAlertModal"

    def test_modal_has_close_button(self, html: str):
        # There should be at least one explicit Close action.
        assert 'closeDoltSyncAlertModal' in html, (
            "Modal must wire a closeDoltSyncAlertModal() handler"
        )


# ===========================================================================
# 4. Frontend: JS helpers wired up
# ===========================================================================


class TestJSHelpers:
    """The dashboard must define the three helpers the modal depends on."""

    def test_open_modal_function_defined(self, html: str):
        assert re.search(
            r"async\s+function\s+openDoltSyncAlertModal\s*\(", html,
        ), "openDoltSyncAlertModal() must be defined"

    def test_close_modal_function_defined(self, html: str):
        assert re.search(
            r"function\s+closeDoltSyncAlertModal\s*\(", html,
        ), "closeDoltSyncAlertModal() must be defined"

    def test_copy_function_defined(self, html: str):
        assert re.search(
            r"function\s+copyDoltSyncCommand\s*\(", html,
        ), "copyDoltSyncCommand() must be defined"

    def test_build_command_function_defined(self, html: str):
        assert re.search(
            r"function\s+buildDoltSyncRecoveryCommand\s*\(", html,
        ), "buildDoltSyncRecoveryCommand() must be defined"

    def test_humanize_helper_defined(self, html: str):
        assert re.search(
            r"function\s+humanizeTimestamp\s*\(", html,
        ), "humanizeTimestamp() must be defined for relative-time rendering"

    def test_modal_fetches_dolt_sync_endpoint(self, html: str):
        assert "/api/v1/orchestrator/dolt-sync" in html, (
            "Modal must fetch from /api/v1/orchestrator/dolt-sync"
        )

    def test_copy_uses_clipboard_api(self, html: str):
        assert "navigator.clipboard" in html, (
            "copyDoltSyncCommand should prefer navigator.clipboard.writeText"
        )


# ===========================================================================
# 5. Recovery command branches (the three flavours from the issue)
# ===========================================================================


class TestRecoveryCommandBranches:
    """``buildDoltSyncRecoveryCommand`` must produce exactly the three
    command flavours specified by the acceptance criteria."""

    def test_divergent_branch_uses_pull_then_push_force(self, html: str):
        # divergent=true → cd <repo_path> && bd dolt pull && bd dolt push --force
        assert "bd dolt pull && bd dolt push --force" in html, (
            "divergent branch must render 'bd dolt pull && bd dolt push --force'"
        )

    def test_high_error_count_branch_uses_status(self, html: str):
        # consecutive_errors >= 5 and not divergent → cd <repo_path> && bd dolt status
        assert "bd dolt status" in html, (
            "high-error-count branch must render 'bd dolt status'"
        )
        # The function body should contain a >= 5 threshold check.
        m = re.search(
            r"consecutive_errors\s*>=\s*5", html,
        )
        assert m, (
            "buildDoltSyncRecoveryCommand must use a >= 5 threshold for "
            "the bd dolt status branch"
        )

    def test_default_branch_uses_pull_then_push(self, html: str):
        # Otherwise → cd <repo_path> && bd dolt pull && bd dolt push
        # (no --force)
        assert "bd dolt pull && bd dolt push'" in html or (
            'bd dolt pull && bd dolt push"' in html
        ), "default branch must render 'bd dolt pull && bd dolt push' (no --force)"

    def test_command_prefixes_cd_repo_path(self, html: str):
        # All three branches should prefix `cd <repo_path>` so the
        # operator can paste them directly.
        m = re.search(
            r"function\s+buildDoltSyncRecoveryCommand\s*\([^)]*\)\s*\{(.*?)^\}",
            html,
            re.DOTALL | re.MULTILINE,
        )
        assert m, "buildDoltSyncRecoveryCommand body must be findable"
        body = m.group(1)
        # All three flavours start with `cd `.
        cd_count = body.count("'cd ")
        assert cd_count >= 3, (
            f"buildDoltSyncRecoveryCommand should prefix each branch with "
            f"'cd <repo>'; found {cd_count} occurrences"
        )


# ===========================================================================
# 6. End-to-end shape: snapshot includes project_name + repo_path
# ===========================================================================


class TestSnapshotEnrichment:
    """`Orchestrator.dolt_sync_snapshot` must include project_name and
    repo_path so the modal can render them without a second round-trip."""

    def test_snapshot_includes_project_name_and_repo_path(self):
        # The orchestrator's snapshot logic is verified via the public
        # dolt_sync_snapshot method. We exercise the dict-shape contract
        # directly here.
        from oompah.orchestrator import Orchestrator

        orch = Orchestrator.__new__(Orchestrator)
        orch._dolt_sync_state = {
            "proj-trickle": DoltSyncState(
                project_id="proj-trickle",
                last_error="boom",
                consecutive_errors=2,
            )
        }

        class _Store:
            def list_all(self):
                return [_make_project(name="trickle", pid="proj-trickle")]

        orch.project_store = _Store()
        snap = orch.dolt_sync_snapshot()
        assert "proj-trickle" in snap
        entry = snap["proj-trickle"]
        assert entry["project_name"] == "trickle"
        assert entry["repo_path"] == "/tmp/trickle"
        # Existing fields still present
        assert entry["project_id"] == "proj-trickle"
        assert entry["last_error"] == "boom"
        assert entry["consecutive_errors"] == 2

    def test_snapshot_handles_missing_project_gracefully(self):
        from oompah.orchestrator import Orchestrator

        orch = Orchestrator.__new__(Orchestrator)
        orch._dolt_sync_state = {
            "proj-orphan": DoltSyncState(
                project_id="proj-orphan", divergent=True,
            )
        }

        class _Store:
            def list_all(self):
                return []

        orch.project_store = _Store()
        snap = orch.dolt_sync_snapshot()
        entry = snap["proj-orphan"]
        # Fall back to id for name when project missing
        assert entry["project_name"] == "proj-orphan"
        # repo_path should be None, not crash
        assert entry["repo_path"] is None
