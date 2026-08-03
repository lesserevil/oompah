"""API serialization/redaction tests for terminal-audit state exposure.

Covers: queued, running, passed, failed, overridden, grandfathered, malformed
metadata, and ACP unknown-model records.

Acceptance criteria (from OOMPAH-484):
- list/detail/activity agree on field names and shape
- sensitive content (credentials, prompts, full diffs, model output) is absent
- existing API consumers see no change when terminal_audit_summary is absent
- grandfathered / never-audited tasks return None (summary omitted)
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from oompah import server as server_module
from oompah.models import Issue, Project
from oompah.server import app
from oompah.terminal_audit import (
    AuditAttempt,
    ContributorIdentity,
    EvidenceFingerprint,
    FailureClassification,
    OverrideRecord,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    MetadataQuarantine,
    TerminalAuditMetadata,
)
from oompah.terminal_transition_coordinator import (
    OverrideRejection,
    OverrideResult,
    TransitionResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FINGERPRINT = EvidenceFingerprint("a" * 64)
_FINGERPRINT2 = EvidenceFingerprint("b" * 64)


def _issue(identifier: str, state: str = "In Validation") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="Task description",
        state=state,
    )


def _attempt(
    attempt_id: str = "attempt-1",
    *,
    request_state: RequestState = RequestState.PENDING,
    verdict: Verdict | None = None,
    failure_classification: FailureClassification | None = None,
) -> AuditAttempt:
    return AuditAttempt(
        attempt_id=attempt_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=_FINGERPRINT,
        request_state=request_state,
        verdict=verdict,
        failure_classification=failure_classification,
        requested_by=ContributorIdentity("alice", "github"),
        created_at="2026-07-28T00:00:00Z",
        completed_at="2026-07-28T00:01:00Z" if verdict is not None else None,
    )


def _record(
    audit_id: str = "audit-1",
    *,
    request_state: RequestState = RequestState.PENDING,
    attempts: list[AuditAttempt] | None = None,
) -> TerminalAuditRecord:
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id="proj-1",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=_FINGERPRINT,
        request_state=request_state,
        attempts=attempts or [],
        requested_by=ContributorIdentity("alice", "github"),
        previous_state="Done",
        created_at="2026-07-28T00:00:00Z",
        updated_at="2026-07-28T00:02:00Z",
    )


def _metadata_dict(
    record: TerminalAuditRecord | None = None,
    *,
    attempt_history: list[AuditAttempt] | None = None,
    quarantine: MetadataQuarantine | None = None,
    unknown_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = TerminalAuditMetadata(
        pending_chain=[record] if record is not None else [],
        attempt_history=attempt_history or [],
        quarantine=quarantine,
        unknown_fields=unknown_fields or {},
    )
    return doc.to_dict()


def _tracker_with_metadata(metadata: dict[str, Any]) -> MagicMock:
    """Return a mock tracker whose get_metadata() returns the given metadata."""
    tracker = MagicMock()
    tracker.get_metadata.return_value = {METADATA_KEY: metadata}
    return tracker


# ---------------------------------------------------------------------------
# _issue_terminal_audit_summary — unit tests
# ---------------------------------------------------------------------------


class TestIssueTerminalAuditSummaryUnit:
    def test_returns_none_for_issue_without_terminal_audit_and_no_tracker(self):
        issue = _issue("TASK-1")
        result = server_module._issue_terminal_audit_summary(issue)
        assert result is None

    def test_returns_none_for_grandfathered_empty_document(self):
        """Empty document (no pending chain, no history) = grandfathered."""
        issue = _issue("TASK-1")
        issue.terminal_audit = _metadata_dict()  # type: ignore[attr-defined]
        result = server_module._issue_terminal_audit_summary(issue)
        assert result is None

    def test_queued_phase_for_pending_record(self):
        record = _record(request_state=RequestState.PENDING)
        issue = _issue("TASK-1")
        issue.terminal_audit = _metadata_dict(record)  # type: ignore[attr-defined]

        result = server_module._issue_terminal_audit_summary(issue)

        assert result is not None
        assert result["phase"] == "queued"
        assert result["target_state"] == "Done"
        assert result["request_state"] == "pending"
        assert result["attempt_count"] == 0
        assert result["fingerprint_prefix"] == "a" * 12
        assert result["verdict"] is None
        assert result["failure_classification"] is None
        assert result["is_overridden"] is False
        assert result["quarantined"] is False

    def test_running_phase_for_in_progress_record(self):
        record = _record(request_state=RequestState.IN_PROGRESS, attempts=[_attempt()])
        issue = _issue("TASK-1")
        issue.terminal_audit = _metadata_dict(record)  # type: ignore[attr-defined]

        result = server_module._issue_terminal_audit_summary(issue)

        assert result is not None
        assert result["phase"] == "running"
        assert result["attempt_count"] == 1

    def test_passed_phase_for_completed_pass(self):
        attempt = _attempt(
            request_state=RequestState.COMPLETED,
            verdict=Verdict.PASS,
        )
        record = _record(
            request_state=RequestState.COMPLETED,
            attempts=[attempt],
        )
        issue = _issue("TASK-1", state="Done")
        issue.terminal_audit = _metadata_dict(record)  # type: ignore[attr-defined]

        result = server_module._issue_terminal_audit_summary(issue)

        assert result is not None
        assert result["phase"] == "passed"
        assert result["verdict"] == "pass"
        assert result["failure_classification"] is None

    def test_failed_phase_for_completed_fail(self):
        attempt = _attempt(
            request_state=RequestState.COMPLETED,
            verdict=Verdict.FAIL,
            failure_classification=FailureClassification.INCOMPLETE,
        )
        record = _record(
            request_state=RequestState.COMPLETED,
            attempts=[attempt],
        )
        issue = _issue("TASK-1", state="In Validation")
        issue.terminal_audit = _metadata_dict(record)  # type: ignore[attr-defined]

        result = server_module._issue_terminal_audit_summary(issue)

        assert result is not None
        assert result["phase"] == "failed"
        assert result["verdict"] == "fail"
        assert result["failure_classification"] == "incomplete"

    def test_overridden_is_detected_from_unknown_fields(self):
        override = OverrideRecord(
            override_id="override-1",
            project_id="proj-1",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=_FINGERPRINT,
            authorized_by=ContributorIdentity("owner", "github"),
            reason="emergency",
            created_at="2026-07-29T00:00:00Z",
        )
        record = _record(request_state=RequestState.COMPLETED, attempts=[
            _attempt(request_state=RequestState.COMPLETED, verdict=Verdict.PASS)
        ])
        issue = _issue("TASK-1", state="Done")
        issue.terminal_audit = _metadata_dict(  # type: ignore[attr-defined]
            record,
            unknown_fields={
                "oompah.terminal_override_records": [override.to_dict()]
            },
        )

        result = server_module._issue_terminal_audit_summary(issue)

        assert result is not None
        assert result["is_overridden"] is True
        assert "override" in result
        override_info = result["override"]
        assert override_info["authorized_by"]["identity"] == "owner"
        assert override_info["authorized_by"]["source"] == "github"
        assert override_info["target_state"] == "Done"

    def test_malformed_metadata_returns_error_phase(self):
        issue = _issue("TASK-1")
        issue.terminal_audit = {"version": 999, "corrupt": True}  # type: ignore[attr-defined]

        result = server_module._issue_terminal_audit_summary(issue)

        assert result is not None
        assert result["phase"] == "error"
        assert result["quarantined"] is True

    def test_quarantined_document_returns_error_phase(self):
        quarantine = MetadataQuarantine(
            fingerprint="c" * 64,
            reason="malformed terminal-audit metadata",
        )
        issue = _issue("TASK-1")
        issue.terminal_audit = _metadata_dict(quarantine=quarantine)  # type: ignore[attr-defined]

        result = server_module._issue_terminal_audit_summary(issue)

        assert result is not None
        assert result["phase"] == "error"
        assert result["quarantined"] is True

    def test_tracker_fallback_when_issue_has_no_terminal_audit(self):
        record = _record(request_state=RequestState.PENDING)
        meta = _metadata_dict(record)
        tracker = _tracker_with_metadata(meta)

        issue = _issue("TASK-1")
        # issue.terminal_audit is NOT set — simulate tracker adapter not loading it

        result = server_module._issue_terminal_audit_summary(issue, tracker=tracker)

        assert result is not None
        assert result["phase"] == "queued"
        tracker.get_metadata.assert_called_once_with("TASK-1")

    def test_tracker_read_failure_returns_none(self):
        tracker = MagicMock()
        tracker.get_metadata.side_effect = RuntimeError("connection lost")
        issue = _issue("TASK-1")

        result = server_module._issue_terminal_audit_summary(issue, tracker=tracker)

        assert result is None

    def test_acp_unknown_model_recorded_as_provider_identity(self):
        """Provider-model identity is not exposed in the summary (safe by design)."""
        record = _record(request_state=RequestState.IN_PROGRESS, attempts=[
            _attempt("attempt-1", request_state=RequestState.IN_PROGRESS)
        ])
        issue = _issue("TASK-1")
        issue.terminal_audit = _metadata_dict(record)  # type: ignore[attr-defined]

        result = server_module._issue_terminal_audit_summary(issue)

        # The summary deliberately omits provider/model identity (can be unknown).
        assert result is not None
        assert "provider_name" not in result
        assert "model_name" not in result
        assert "provider_id" not in result

    def test_requested_by_identity_is_exposed_safely(self):
        record = _record(request_state=RequestState.PENDING)
        issue = _issue("TASK-1")
        issue.terminal_audit = _metadata_dict(record)  # type: ignore[attr-defined]

        result = server_module._issue_terminal_audit_summary(issue)

        assert result is not None
        assert result["requested_by"] == {"identity": "alice", "source": "github"}

    def test_no_credentials_or_secrets_in_summary(self):
        """Summary must not contain credential-like keys."""
        record = _record(request_state=RequestState.PENDING)
        issue = _issue("TASK-1")
        issue.terminal_audit = _metadata_dict(record)  # type: ignore[attr-defined]

        result = server_module._issue_terminal_audit_summary(issue)

        serialized = json.dumps(result)
        assert "token" not in serialized.lower()
        assert "secret" not in serialized.lower()
        assert "password" not in serialized.lower()
        assert "credential" not in serialized.lower()
        assert "diff" not in serialized.lower()

    def test_summary_omits_prompt_and_model_output(self):
        """Model output and prompts must not appear in the summary."""
        record = _record(request_state=RequestState.PENDING)
        issue = _issue("TASK-1")
        issue.terminal_audit = _metadata_dict(record)  # type: ignore[attr-defined]

        result = server_module._issue_terminal_audit_summary(issue)

        serialized = json.dumps(result)
        assert "prompt" not in serialized.lower()
        assert "completion" not in serialized.lower()


# ---------------------------------------------------------------------------
# _terminal_audit_phase — unit tests
# ---------------------------------------------------------------------------


class TestTerminalAuditPhase:
    def test_queued_when_no_record(self):
        doc = TerminalAuditMetadata()
        assert server_module._terminal_audit_phase(doc, None, None) == "queued"

    def test_queued_when_pending_state(self):
        doc = TerminalAuditMetadata()
        record = _record(request_state=RequestState.PENDING)
        assert server_module._terminal_audit_phase(doc, record, None) == "queued"

    def test_running_when_in_progress(self):
        doc = TerminalAuditMetadata()
        record = _record(request_state=RequestState.IN_PROGRESS)
        assert server_module._terminal_audit_phase(doc, record, None) == "running"

    def test_passed_when_completed_with_pass_verdict(self):
        doc = TerminalAuditMetadata()
        record = _record(request_state=RequestState.COMPLETED)
        attempt = _attempt(
            request_state=RequestState.COMPLETED, verdict=Verdict.PASS
        )
        assert server_module._terminal_audit_phase(doc, record, attempt) == "passed"

    def test_failed_when_completed_with_fail_verdict(self):
        doc = TerminalAuditMetadata()
        record = _record(request_state=RequestState.COMPLETED)
        attempt = _attempt(
            request_state=RequestState.COMPLETED, verdict=Verdict.FAIL
        )
        assert server_module._terminal_audit_phase(doc, record, attempt) == "failed"

    def test_failed_when_needs_human(self):
        doc = TerminalAuditMetadata()
        record = _record(request_state=RequestState.COMPLETED)
        attempt = _attempt(
            request_state=RequestState.COMPLETED, verdict=Verdict.NEEDS_HUMAN
        )
        assert server_module._terminal_audit_phase(doc, record, attempt) == "failed"

    def test_cancelled_when_superseded(self):
        doc = TerminalAuditMetadata()
        record = _record(request_state=RequestState.SUPERSEDED)
        assert server_module._terminal_audit_phase(doc, record, None) == "cancelled"

    def test_error_when_quarantined(self):
        quarantine = MetadataQuarantine(fingerprint="c" * 64)
        doc = TerminalAuditMetadata(quarantine=quarantine)
        assert server_module._terminal_audit_phase(doc, None, None) == "error"


# ---------------------------------------------------------------------------
# Integration: _fetch_and_serialize_issues includes terminal_audit_summary
# ---------------------------------------------------------------------------


def _orch_with_issues(issues: list[Issue]) -> MagicMock:
    project = SimpleNamespace(id="proj-1", name="project-1")
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = list(issues)
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    orch._project_epic_strategy.return_value = "flat"
    return orch


class TestListApiIncludesTerminalAuditSummary:
    def test_terminal_audit_summary_included_when_issue_has_terminal_audit(self):
        record = _record(request_state=RequestState.PENDING)
        issue = _issue("TASK-1", state="In Validation")
        issue.terminal_audit = _metadata_dict(record)  # type: ignore[attr-defined]
        orch = _orch_with_issues([issue])

        board = server_module._fetch_and_serialize_issues(orch)

        rows = {row["identifier"]: row for rows in board.values() for row in rows}
        entry = rows.get("TASK-1")
        assert entry is not None
        assert "terminal_audit_summary" in entry
        assert entry["terminal_audit_summary"]["phase"] == "queued"
        assert entry["terminal_audit_summary"]["target_state"] == "Done"

    def test_terminal_audit_summary_omitted_when_not_available(self):
        issue = _issue("TASK-2", state="Open")
        orch = _orch_with_issues([issue])

        board = server_module._fetch_and_serialize_issues(orch)

        rows = {row["identifier"]: row for rows in board.values() for row in rows}
        entry = rows.get("TASK-2")
        assert entry is not None
        assert "terminal_audit_summary" not in entry

    def test_terminal_audit_summary_omitted_for_grandfathered_empty_document(self):
        issue = _issue("TASK-3", state="Done")
        issue.terminal_audit = _metadata_dict()  # type: ignore[attr-defined]
        orch = _orch_with_issues([issue])

        board = server_module._fetch_and_serialize_issues(orch)

        rows = {row["identifier"]: row for rows in board.values() for row in rows}
        entry = rows.get("TASK-3")
        assert entry is not None
        assert "terminal_audit_summary" not in entry

    def test_list_and_detail_have_same_summary_fields(self):
        """Both list and detail endpoints must use identical field names."""
        record = _record(
            request_state=RequestState.COMPLETED,
            attempts=[_attempt(
                request_state=RequestState.COMPLETED, verdict=Verdict.PASS
            )],
        )
        meta = _metadata_dict(record)
        issue = _issue("TASK-4", state="Done")
        issue.terminal_audit = meta  # type: ignore[attr-defined]
        tracker = _tracker_with_metadata(meta)

        # List endpoint reads from issue.terminal_audit
        list_summary = server_module._issue_terminal_audit_summary(issue)
        # Detail endpoint reads from tracker metadata
        detail_summary = server_module._issue_terminal_audit_summary(
            _issue("TASK-4", state="Done"), tracker=tracker
        )

        assert list_summary is not None
        assert detail_summary is not None
        # Both summaries must expose the same field names
        assert set(list_summary.keys()) == set(detail_summary.keys())
        # Core fields must agree
        assert list_summary["phase"] == detail_summary["phase"]
        assert list_summary["verdict"] == detail_summary["verdict"]
        assert list_summary["target_state"] == detail_summary["target_state"]
        assert list_summary["attempt_count"] == detail_summary["attempt_count"]

    def test_existing_issue_fields_unchanged_by_audit_summary(self):
        """Legacy consumers must see all existing fields without alteration."""
        record = _record(request_state=RequestState.PENDING)
        issue = _issue("TASK-5", state="In Validation")
        issue.terminal_audit = _metadata_dict(record)  # type: ignore[attr-defined]
        orch = _orch_with_issues([issue])

        board = server_module._fetch_and_serialize_issues(orch)

        rows = {row["identifier"]: row for rows in board.values() for row in rows}
        entry = rows.get("TASK-5")
        assert entry is not None
        # Existing fields that must remain present
        for field in (
            "id",
            "identifier",
            "title",
            "state",
            "priority",
            "labels",
            "issue_type",
            "project_id",
        ):
            assert field in entry, f"Missing legacy field: {field}"


# ---------------------------------------------------------------------------
# Dashboard HTML static contract
# ---------------------------------------------------------------------------


def _dashboard() -> str:
    from pathlib import Path
    return (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")


class TestDashboardTerminalAuditRendering:
    def test_render_function_exists(self):
        html = _dashboard()
        assert "function renderTerminalAuditSummary(summary)" in html

    def test_render_detail_function_exists(self):
        html = _dashboard()
        assert "function renderTerminalAuditDetail(summary)" in html

    def test_card_includes_audit_summary_render(self):
        html = _dashboard()
        assert "renderTerminalAuditSummary(issue.terminal_audit_summary)" in html

    def test_detail_panel_includes_audit_summary_render(self):
        html = _dashboard()
        assert "renderTerminalAuditDetail(detail.terminal_audit_summary)" in html

    def test_all_audit_phases_have_labels(self):
        html = _dashboard()
        # All phase labels must be defined in the JS
        for phase_label in (
            "Audit queued",
            "Audit running",
            "Audit passed",
            "Audit failed",
            "Owner overridden",
            "Audit cancelled",
            "Audit error",
        ):
            assert phase_label in html, f"Missing phase label: {phase_label}"

    def test_css_classes_for_all_phases_exist(self):
        html = _dashboard()
        for phase in ("queued", "running", "passed", "failed", "overridden", "error"):
            assert f"terminal-audit-phase-{phase}" in html, f"Missing CSS for phase: {phase}"

    def test_audit_pill_css_exists(self):
        html = _dashboard()
        assert ".terminal-audit-pill" in html
        assert ".terminal-audit-summary" in html

    def test_accessibility_attributes_present(self):
        html = _dashboard()
        assert 'role="status"' in html
        # aria-label on terminal audit div (check it's in the right context)
        assert "aria-label" in html

    def test_terminal_audit_summary_in_card_fingerprint(self):
        html = _dashboard()
        assert "terminal_audit_summary: issue.terminal_audit_summary" in html

    def test_detail_renders_key_fields(self):
        html = _dashboard()
        # Detail rendering must expose safe fields
        for field_label in ("Phase", "Target state", "Attempts", "Verdict", "Classification", "Fingerprint", "Owner override"):
            assert field_label in html, f"Missing field label: {field_label}"


# ---------------------------------------------------------------------------
# Cross-surface terminal-status staging (OOMPAH-476)
# ---------------------------------------------------------------------------


class _Tracker:
    def __init__(self, issue: Issue) -> None:
        self.issue = issue
        self.status_updates: list[tuple[str, str]] = []
        self.comments: list[tuple[str, str]] = []

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issue if identifier == self.issue.identifier else None

    def update_issue(self, identifier: str, **fields: str) -> None:
        if "status" in fields:
            self.status_updates.append((identifier, fields["status"]))

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> None:
        self.comments.append((identifier, text))


class _Coordinator:
    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.overrides: list[dict] = []
        self.retries: list[dict] = []
        self.override_result: OverrideResult | None = None
        self.retry_result: TransitionResult | None = None

    async def request_transition(self, **kwargs):
        self.requests.append(kwargs)
        return TransitionResult(
            success=True,
            audit_id="audit-request-1",
            queued_targets=[kwargs["requested_target"]],
            status_staged=True,
        )

    async def override_transition(self, **kwargs):
        self.overrides.append(kwargs)
        if self.override_result is not None:
            return self.override_result
        return OverrideResult(
            success=True,
            override_id="audit-override-1",
            applied_status=kwargs["requested_target"].value,
        )

    async def retry_failed_audit(self, **kwargs):
        self.retries.append(kwargs)
        if self.retry_result is not None:
            return self.retry_result
        return TransitionResult(
            success=True,
            audit_id="audit-retry-1",
            queued_targets=[kwargs["requested_target"]],
            status_staged=True,
        )


def _orchestrator(issue: Issue):
    tracker = _Tracker(issue)
    coordinator = _Coordinator()
    project = Project(
        id="proj-1",
        name="Project",
        repo_url="https://github.com/example/repo",
        repo_path=".",
        tracker_kind="oompah_md",
        tracker_owner="owner",
        tracker_repo="repo",
        status_label_authorized_logins=["owner"],
    )
    store = MagicMock()
    store.list_all.return_value = [project]
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store = store
    orch.terminal_transition_coordinator = coordinator
    orch.config.tracker_terminal_states = ["Done"]
    orch.state.running = {}
    orch.state.retry_attempts = {}
    orch.state.claimed = set()
    orch.state.completed = set()
    orch.request_refresh = MagicMock()
    return orch, tracker, coordinator


@pytest.mark.asyncio
async def test_terminal_stage_refreshes_issue_inside_task_ownership_lock():
    """API staging passes authoritative detail, not its stale caller snapshot."""

    stale = Issue(
        "task-refresh",
        "task-refresh",
        "Task",
        description="work",
        state="In Validation",
    )
    authoritative = Issue(
        "task-refresh",
        "task-refresh",
        "Task",
        description="work",
        state="In Validation",
    )
    authoritative.integration = SimpleNamespace(
        task_branch="feature/task-refresh",
        head_sha="head-sha",
        base_branch="main",
        base_sha="base-sha",
        integrated_sha="integrated-sha",
    )
    orch, tracker, coordinator = _orchestrator(stale)
    tracker.fetch_issue_detail = lambda identifier: authoritative
    orch.issue_transition_lock = lambda _issue_id: asyncio.Lock()

    payload, error = await server_module._stage_terminal_transition(
        orch=orch,
        tracker=tracker,
        project_id="proj-1",
        issue=stale,
        target=TargetState.DONE,
        body={
            "audit_override": True,
            "override_reason": "Recover unchanged integrated task",
            "actor_login": "owner",
        },
    )

    assert error is None
    assert payload is not None
    assert coordinator.overrides[0]["current_issue"] is authoritative
    expected_fingerprint = server_module._terminal_evidence_fingerprint(
        authoritative, "proj-1"
    )
    assert coordinator.overrides[0]["evidence_fingerprint"] == expected_fingerprint


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_patch_terminal_status_stages_and_does_not_write_terminal(client):
    issue = Issue("task-1", "task-1", "Task", description="work", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-1",
            json={"project_id": "proj-1", "status": "closed"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "In Validation"
    assert response.json()["requested_target"] == "Done"
    assert response.json()["audit_id"] == "audit-request-1"
    assert tracker.status_updates == []
    assert coordinator.requests[0]["requested_target"] is TargetState.DONE
    assert issue.id in orch.state.completed
    orch.request_refresh.assert_called_once_with()


def test_patch_terminal_status_rolls_back_dispatch_fence_when_staging_fails(client):
    issue = Issue("task-stage-fails", "task-stage-fails", "Task", description="work", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    coordinator.request_transition = AsyncMock(
        return_value=TransitionResult(success=False, reason="metadata unavailable")
    )
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-stage-fails",
            json={"project_id": "proj-1", "status": "Done"},
        )

    assert response.status_code == 503
    assert tracker.status_updates == []
    assert issue.id not in orch.state.completed
    orch.request_refresh.assert_called_once_with()


def test_patch_terminal_status_reports_unrepaired_current_state(client):
    issue = Issue(
        "task-stage-pending",
        "task-stage-pending",
        "Task",
        description="work",
        state="Needs Human",
    )
    orch, tracker, coordinator = _orchestrator(issue)
    coordinator.request_transition = AsyncMock(
        return_value=TransitionResult(
            success=True,
            audit_id="audit-pending-1",
            queued_targets=[TargetState.DONE],
            coalesced=True,
            status_staged=False,
        )
    )
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-stage-pending",
            json={"project_id": "proj-1", "status": "Done"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "Needs Human"
    assert response.json()["status_staged"] is False
    assert response.json()["status_repaired"] is False
    assert response.json()["audit_id"] == "audit-pending-1"
    assert tracker.status_updates == []


def test_patch_nonterminal_status_keeps_direct_behavior(client):
    issue = Issue("task-2", "task-2", "Task", description="work", state="Backlog")
    orch, tracker, _ = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-2",
            json={"project_id": "proj-1", "status": "open", "actor_login": "owner"},
        )

    assert response.status_code == 200
    assert tracker.status_updates == [("task-2", "open")]


def test_patch_owner_override_requires_reason_and_uses_coordinator(client):
    issue = Issue("task-3", "task-3", "Task", description="work", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        missing_reason = client.patch(
            "/api/v1/issues/task-3",
            json={"project_id": "proj-1", "status": "Done", "audit_override": True, "actor_login": "owner"},
        )
        applied = client.patch(
            "/api/v1/issues/task-3",
            json={
                "project_id": "proj-1",
                "status": "Done",
                "audit_override": True,
                "override_reason": "Emergency release approval",
                "actor_login": "owner",
            },
        )

    assert missing_reason.status_code == 400
    assert applied.status_code == 200
    assert applied.json()["status"] == "Done"
    assert applied.json()["audit_id"] == "audit-override-1"
    assert coordinator.overrides[0]["reason"] == "Emergency release approval"
    assert tracker.status_updates == []


def test_patch_owner_audit_retry_rearms_without_direct_terminal_write(client):
    issue = Issue(
        "task-retry",
        "task-retry",
        "Task",
        description="work",
        state="Needs Human",
    )
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-retry",
            json={
                "project_id": "proj-1",
                "status": "Archived",
                "audit_retry": True,
                "audit_retry_reason": "Detached audit checkout is deployed",
                "actor_login": "owner",
            },
        )

    assert response.status_code == 200
    assert response.json()["audit_retry"] is True
    assert response.json()["status"] == "In Validation"
    assert response.json()["audit_id"] == "audit-retry-1"
    assert coordinator.retries[0]["requested_target"] is TargetState.ARCHIVED
    assert coordinator.retries[0]["reason"] == "Detached audit checkout is deployed"
    assert tracker.status_updates == []


def test_patch_audit_retry_requires_reason(client):
    issue = Issue("task-retry", "task-retry", "Task", state="Needs Human")
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-retry",
            json={
                "project_id": "proj-1",
                "status": "Archived",
                "audit_retry": True,
                "actor_login": "owner",
            },
        )

    assert response.status_code == 400
    assert coordinator.retries == []
    assert tracker.status_updates == []


def test_patch_owner_override_accepts_project_name_alias(client):
    """Project-name aliases must use the managed project's canonical ID."""
    issue = Issue("task-alias", "task-alias", "Task", description="work", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-alias",
            json={
                "project_id": "Project",
                "status": "Done",
                "audit_override": True,
                "override_reason": "Emergency release approval",
                "actor_login": "owner",
            },
        )

    assert response.status_code == 200
    assert response.json()["audit_override"] is True
    assert coordinator.overrides[0]["project_id"] == "proj-1"
    assert coordinator.overrides[0]["project"].id == "proj-1"
    orch._tracker_for_project.assert_called_with("proj-1")
    assert tracker.status_updates == []


def test_patch_terminal_alias_stages_with_canonical_project_id(client):
    """Ordinary terminal staging must also carry the canonical project ID."""
    issue = Issue(
        "task-staged-alias",
        "task-staged-alias",
        "Task",
        description="work",
        state="Open",
    )
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-staged-alias",
            json={"project_id": "Project", "status": "Done"},
        )

    assert response.status_code == 200
    assert coordinator.requests[0]["project_id"] == "proj-1"
    assert tracker.status_updates == []


def test_patch_owner_override_rejects_non_owner_without_metadata_details(client):
    issue = Issue("task-unauthorized", "task-unauthorized", "Task", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    coordinator.override_result = OverrideResult(
        success=False,
        error_code=OverrideRejection.UNAUTHORIZED_ACTOR,
    )
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-unauthorized",
            json={
                "project_id": "proj-1",
                "status": "Done",
                "audit_override": True,
                "override_reason": "Emergency release approval",
                "actor_login": "not-owner",
            },
        )

    assert response.status_code == 403
    assert "owner" in response.json()["error"]["message"].lower()
    assert "metadata" not in response.text.lower()
    assert tracker.status_updates == []


def test_patch_owner_override_rejects_incompatible_shared_epic_merged(client):
    issue = Issue("task-shared", "task-shared", "Task", state="Done")
    issue.parent_id = "epic-1"
    orch, tracker, coordinator = _orchestrator(issue)
    coordinator.override_result = OverrideResult(
        success=False,
        reason=(
            "Cannot transition shared-epic child task-shared to Merged: parent "
            "review must land on configured target branch main first."
        ),
        error_code=OverrideRejection.LIFECYCLE_INCOMPATIBLE,
    )
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-shared",
            json={
                "project_id": "proj-1",
                "status": "Merged",
                "audit_override": True,
                "override_reason": "Emergency release approval",
                "actor_login": "owner",
            },
        )

    assert response.status_code == 409
    assert "parent review must land" in response.json()["error"]["message"]
    assert tracker.status_updates == []


def test_patch_owner_override_alias_rejects_unauthorized_actor(client):
    """Canonicalization must not weaken owner authorization."""
    issue = Issue("task-unauthorized-alias", "task-unauthorized-alias", "Task", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    coordinator.override_result = OverrideResult(
        success=False,
        error_code=OverrideRejection.UNAUTHORIZED_ACTOR,
    )
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-unauthorized-alias",
            json={
                "project_id": "Project",
                "status": "Done",
                "audit_override": True,
                "override_reason": "Emergency release approval",
                "actor_login": "not-owner",
            },
        )

    assert response.status_code == 403
    assert "owner" in response.json()["error"]["message"].lower()
    assert "Project" not in response.text
    assert coordinator.overrides[0]["project_id"] == "proj-1"
    assert tracker.status_updates == []


def test_patch_unknown_project_alias_fails_closed_without_configuration_details(client):
    """Unknown project aliases must not reach terminal authorization."""
    issue = Issue("task-unknown-alias", "task-unknown-alias", "Task", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-unknown-alias",
            json={
                "project_id": "not-a-project",
                "status": "Done",
                "audit_override": True,
                "override_reason": "Emergency release approval",
                "actor_login": "owner",
            },
        )

    assert response.status_code >= 400
    assert "not-a-project" not in response.text
    assert coordinator.overrides == []
    assert tracker.status_updates == []


def test_label_terminal_mutation_is_staged_without_override(client):
    issue = Issue("task-4", "task-4", "Task", description="work", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.post(
            "/api/v1/issues/task-4/labels",
            json={"project_id": "proj-1", "label": "oompah:status:archived"},
        )

    assert response.status_code == 201
    assert response.json()["requested_target"] == "Archived"
    assert response.json()["status"] == "In Validation"
    assert coordinator.requests[0]["requested_target"] is TargetState.ARCHIVED
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_acp_terminal_router_stages_and_supports_override():
    from oompah.acp_tools import _exec_oompah_task_command_async

    issue = Issue("task-5", "task-5", "Task", description="work", state="Open")
    tracker = _Tracker(issue)
    coordinator = _Coordinator()
    project_store = MagicMock()
    project_store.get.return_value = SimpleNamespace(
        id="proj-1", status_label_authorized_logins=["owner"], tracker_owner="owner"
    )

    staged = await _exec_oompah_task_command_async(
        "oompah task set-status task-5 Merged",
        tracker,
        "proj-1",
        project_store=project_store,
        terminal_transition_coordinator=coordinator,
    )
    overridden = await _exec_oompah_task_command_async(
        "oompah task set-status task-5 Archived --audit-override "
        "--override-reason 'retire task' --actor owner",
        tracker,
        "proj-1",
        project_store=project_store,
        terminal_transition_coordinator=coordinator,
    )

    assert "In Validation" in staged
    assert "audit-request-1" in staged
    assert "owner override" in overridden
    assert coordinator.requests[0]["requested_target"] is TargetState.MERGED
    assert coordinator.overrides[0]["requested_target"] is TargetState.ARCHIVED
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_acp_terminal_router_reports_shared_epic_override_conflict():
    from oompah.acp_tools import _exec_oompah_task_command_async

    issue = Issue("task-acp-shared", "task-acp-shared", "Task", state="Done")
    issue.parent_id = "epic-1"
    tracker = _Tracker(issue)
    coordinator = _Coordinator()
    coordinator.override_result = OverrideResult(
        success=False,
        reason=(
            "Cannot transition shared-epic child task-acp-shared to Merged: "
            "parent review must land on configured target branch main first."
        ),
        error_code=OverrideRejection.LIFECYCLE_INCOMPATIBLE,
    )
    project_store = MagicMock()
    project_store.get.return_value = SimpleNamespace(
        id="proj-1", status_label_authorized_logins=["owner"], tracker_owner="owner"
    )

    result = await _exec_oompah_task_command_async(
        "oompah task set-status task-acp-shared Merged --audit-override "
        "--override-reason 'Emergency release approval' --actor owner",
        tracker,
        "proj-1",
        project_store=project_store,
        terminal_transition_coordinator=coordinator,
    )

    assert "parent review must land" in result
    assert coordinator.overrides[0]["requested_target"] is TargetState.MERGED
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_acp_terminal_router_reports_unrepaired_current_state():
    from oompah.acp_tools import _exec_oompah_task_command_async

    issue = Issue("task-acp-pending", "task-acp-pending", "Task", description="work", state="Needs Human")
    tracker = _Tracker(issue)
    coordinator = _Coordinator()
    coordinator.request_transition = AsyncMock(
        return_value=TransitionResult(
            success=True,
            audit_id="audit-acp-pending",
            queued_targets=[TargetState.DONE],
            coalesced=True,
            status_staged=False,
        )
    )

    result = await _exec_oompah_task_command_async(
        "oompah task set-status task-acp-pending Done",
        tracker,
        "proj-1",
        project_store=MagicMock(),
        terminal_transition_coordinator=coordinator,
    )

    assert "Terminal transition recorded: Done" in result
    assert "status remains: Needs Human" in result
    assert "audit-acp-pending" in result


@pytest.mark.asyncio
async def test_acp_terminal_router_hides_tracker_error_details():
    from oompah.acp_tools import _exec_oompah_task_command_async

    class FailingCoordinator:
        async def request_transition(self, **kwargs):
            raise RuntimeError("terminal-audit metadata internals")

    issue = Issue("task-6", "task-6", "Task", description="work", state="Open")
    tracker = _Tracker(issue)
    result = await _exec_oompah_task_command_async(
        "oompah task set-status task-6 Done",
        tracker,
        "proj-1",
        project_store=MagicMock(),
        terminal_transition_coordinator=FailingCoordinator(),
    )

    assert result == "Error: terminal transition request failed"
    assert "metadata" not in result.lower()
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_acp_terminal_router_hides_tracker_fetch_errors():
    from oompah.acp_tools import _exec_oompah_task_command_async

    class FailingTracker:
        def fetch_issue_detail(self, identifier):
            raise RuntimeError("terminal-audit metadata internals")

    result = await _exec_oompah_task_command_async(
        "oompah task set-status task-7 Done",
        FailingTracker(),
        "proj-1",
        terminal_transition_coordinator=MagicMock(),
    )

    assert result == "Error: terminal transition request failed"
    assert "metadata" not in result.lower()


def test_task_handoff_terminal_label_rejects_override_fields(client):
    from oompah.task_handoff import issue_task_handoff_token

    issue = Issue("task-label-override", "task-label-override", "Task", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    token = issue_task_handoff_token(
        project_id="proj-1",
        task_identifier="task-label-override",
        allowed_actions={"add-label"},
    )
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.post(
            "/api/v1/task-handoff",
            headers={"x-oompah-task-capability": token},
            json={
                "action": "add-label",
                "project_id": "proj-1",
                "identifier": "task-label-override",
                "label": "oompah:status:done",
                "audit_override": True,
                "override_reason": "not supported on labels",
            },
        )

    assert response.status_code == 400
    assert "override" in response.json()["error"]["message"].lower()
    assert coordinator.overrides == []
    assert tracker.status_updates == []


def test_task_handoff_set_status_with_project_alias_succeeds_for_authorized_owner(client):
    """Project aliases must be canonicalized for task handoff terminal authorization."""
    from oompah.task_handoff import issue_task_handoff_token

    issue = Issue("task-alias-override", "task-alias-override", "Task", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    # Handoff token created with canonical project ID
    token = issue_task_handoff_token(
        project_id="proj-1",
        task_identifier="task-alias-override",
        allowed_actions={"set-status"},
    )
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        # Request uses project name alias "Project" instead of canonical "proj-1"
        response = client.post(
            "/api/v1/task-handoff",
            headers={"x-oompah-task-capability": token},
            json={
                "action": "set-status",
                "project_id": "Project",  # Using project name alias
                "identifier": "task-alias-override",
                "status": "Done",
                "audit_override": True,
                "override_reason": "Emergency release approval",
                "actor_login": "owner",
            },
        )

    # Should succeed because the alias is canonicalized before validation
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["status"] == "Done"  # applied_status
    assert response.json()["audit_override"] is True
    assert response.json()["audit_id"] == "audit-override-1"
    assert len(coordinator.overrides) == 1
    # Verify coordinator received canonical project ID
    assert coordinator.overrides[0]["project_id"] == "proj-1"
    assert tracker.status_updates == []


def test_task_handoff_set_status_with_unknown_project_alias_fails_closed(client):
    """Unknown project aliases must not reach terminal authorization."""
    from oompah.task_handoff import issue_task_handoff_token

    issue = Issue("task-unknown-alias", "task-unknown-alias", "Task", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    # Handoff token created with canonical project ID
    token = issue_task_handoff_token(
        project_id="proj-1",
        task_identifier="task-unknown-alias",
        allowed_actions={"set-status"},
    )
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        # Request uses unknown project alias
        response = client.post(
            "/api/v1/task-handoff",
            headers={"x-oompah-task-capability": token},
            json={
                "action": "set-status",
                "project_id": "unknown-project",
                "identifier": "task-unknown-alias",
                "status": "Done",
                "audit_override": True,
                "override_reason": "Emergency release approval",
                "actor_login": "owner",
            },
        )

    # Preserve capability-scope rejection precedence without revealing
    # whether the caller supplied an unknown alias or another project.
    assert response.status_code == 403
    assert "another project" in response.json()["error"]["message"].lower()
    assert "unknown-project" not in response.text
    assert coordinator.overrides == []
    assert tracker.status_updates == []
