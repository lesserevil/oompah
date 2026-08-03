"""OOMPAH-735: reconcile integration_retry alerts against live recovery.

Covers the pure classifier ``Orchestrator._classify_integration_retry_recovery``
and the reconciliation pass ``_reconcile_integration_retry_alerts`` used by
``get_snapshot``.  Tests exercise every severity/actionability transition
without spinning up a live orchestrator: worker dispatch/exit, scheduled
retry, staleness, authority revocation, retry exhaustion, and successful
integration.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from oompah.integration_queue import IntegrationQueueItem
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.integration_executor import IntegrationExecutionResult
from tests.test_epic_strategy import _make_orch, _make_project_record


PROJECT_ID = "proj-1"
TASK_ID = "TASK-1"
EPIC_ID = "EPIC-1"


def _queue_item(
    *,
    state: str = "ready",
    attempts: int = 1,
    next_retry_at: float | None = None,
) -> IntegrationQueueItem:
    return IntegrationQueueItem(
        project_id=PROJECT_ID,
        epic_id=EPIC_ID,
        task_id=TASK_ID,
        task_branch=f"epic-{EPIC_ID}--task-{TASK_ID}",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at=datetime.now(timezone.utc).isoformat(),
        state=state,
        attempts=attempts,
        lease_owner=None,
        lease_expires_at=None,
        updated_at=datetime.now(timezone.utc).isoformat(),
        last_error=None,
        retry_forced=False,
        next_retry_at=next_retry_at,
    )


def _alert(
    *,
    recovery_state: str = "awaiting_repair",
    action_required: bool = False,
    attempts: int = 1,
    max_attempts: int = 5,
    recorded_at: str | None = None,
) -> dict:
    return {
        "level": "info" if not action_required else "warning",
        "source": f"integration_retry:{PROJECT_ID}:{TASK_ID}",
        "message": "Integration task TASK-1 failed at rebase: real conflict.",
        "task_id": TASK_ID,
        "project_id": PROJECT_ID,
        "failing_step": "rebase",
        "error": "conflict",
        "next_retry_at": None,
        "repair_action": "resolve conflict manually",
        "attempts": attempts,
        "max_attempts": max_attempts,
        "recovery_state": recovery_state,
        "action_required": action_required,
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------- pure classifier


def test_classifier_active_repair_downgrades_to_info():
    """A fresh repair worker suppresses the global operator warning."""
    now = time.time()
    alert = _alert()
    state, actionable, level = (
        Orchestrator._classify_integration_retry_recovery(
            alert,
            running_focus="merge_conflict",
            running_last_event_at=now - 10.0,
            running_authority_revoked=False,
            queue_item=None,
            integration_state=None,
            integration_updated_at=None,
            now=now,
            freshness_seconds=300,
        )
    )
    assert state == "active_repair"
    assert actionable is False
    assert level == "info"


def test_classifier_scheduled_retry_is_not_actionable():
    """A bounded automatic retry is normal activity."""
    now = time.time()
    alert = _alert(recovery_state="scheduled_retry")
    qi = _queue_item(next_retry_at=now + 60.0, attempts=1)
    state, actionable, level = (
        Orchestrator._classify_integration_retry_recovery(
            alert,
            running_focus=None,
            running_last_event_at=None,
            running_authority_revoked=False,
            queue_item=qi,
            integration_state=None,
            integration_updated_at=None,
            now=now,
            freshness_seconds=300,
        )
    )
    assert state == "scheduled_retry"
    assert actionable is False
    assert level == "info"


def test_classifier_no_owner_no_retry_is_actionable():
    """No repair, no queued retry — the alert warns the operator."""
    now = time.time()
    alert = _alert(recovery_state="awaiting_repair")
    state, actionable, level = (
        Orchestrator._classify_integration_retry_recovery(
            alert,
            running_focus=None,
            running_last_event_at=None,
            running_authority_revoked=False,
            queue_item=None,
            integration_state=None,
            integration_updated_at=None,
            now=now,
            freshness_seconds=300,
        )
    )
    assert state == "no_recovery"
    assert actionable is True
    assert level == "warning"


def test_classifier_stale_repair_rearms_warning():
    """A running worker with no fresh events past the window re-arms."""
    now = time.time()
    alert = _alert(recovery_state="active_repair")
    state, actionable, level = (
        Orchestrator._classify_integration_retry_recovery(
            alert,
            running_focus="merge_conflict",
            running_last_event_at=now - 3600.0,
            running_authority_revoked=False,
            queue_item=None,
            integration_state=None,
            integration_updated_at=None,
            now=now,
            freshness_seconds=300,
        )
    )
    assert state == "stale_repair"
    assert actionable is True
    assert level == "warning"


def test_classifier_authority_revoked_rearms_warning():
    now = time.time()
    alert = _alert(recovery_state="active_repair")
    state, actionable, _ = (
        Orchestrator._classify_integration_retry_recovery(
            alert,
            running_focus="merge_conflict",
            running_last_event_at=now,
            running_authority_revoked=True,
            queue_item=None,
            integration_state=None,
            integration_updated_at=None,
            now=now,
            freshness_seconds=300,
        )
    )
    assert state == "authority_revoked"
    assert actionable is True


def test_classifier_retry_exhausted_is_actionable():
    now = time.time()
    alert = _alert(attempts=5, max_attempts=5, recovery_state="retry_exhausted")
    state, actionable, _ = (
        Orchestrator._classify_integration_retry_recovery(
            alert,
            running_focus=None,
            running_last_event_at=None,
            running_authority_revoked=False,
            queue_item=None,
            integration_state=None,
            integration_updated_at=None,
            now=now,
            freshness_seconds=300,
        )
    )
    assert state == "retry_exhausted"
    assert actionable is True


def test_classifier_successful_integration_clears_alert():
    now = time.time()
    alert = _alert(recovery_state="active_repair")
    state, actionable, level = (
        Orchestrator._classify_integration_retry_recovery(
            alert,
            running_focus="merge_conflict",
            running_last_event_at=now,
            running_authority_revoked=False,
            queue_item=None,
            integration_state="integrated",
            integration_updated_at=None,
            now=now,
            freshness_seconds=300,
        )
    )
    assert state == "resolved"
    assert actionable is False
    assert level == "info"


def test_classifier_freshly_dispatched_worker_no_events_yet_is_info():
    """A worker just dispatched has no session events yet — treat as awaiting."""
    now = time.time()
    alert = _alert(
        recovery_state="awaiting_repair",
        recorded_at=datetime.fromtimestamp(now - 10, tz=timezone.utc).isoformat(),
    )
    state, actionable, _ = (
        Orchestrator._classify_integration_retry_recovery(
            alert,
            running_focus="merge_conflict",
            running_last_event_at=None,
            running_authority_revoked=False,
            queue_item=None,
            integration_state=None,
            integration_updated_at=None,
            now=now,
            freshness_seconds=300,
        )
    )
    assert state == "awaiting_repair"
    assert actionable is False


def test_classifier_unrecoverable_state_stays_error():
    """Integrity/auth/transport/policy failures remain error-level."""
    now = time.time()
    alert = _alert(recovery_state="unrecoverable", action_required=True)
    alert["level"] = "error"
    state, actionable, level = (
        Orchestrator._classify_integration_retry_recovery(
            alert,
            running_focus=None,
            running_last_event_at=None,
            running_authority_revoked=False,
            queue_item=None,
            integration_state=None,
            integration_updated_at=None,
            now=now,
            freshness_seconds=300,
        )
    )
    assert state == "unrecoverable"
    assert actionable is True
    assert level == "error"


def test_classifier_stale_scheduled_retry_rearms_warning():
    """A queued retry that overran its window without firing is stale."""
    now = time.time()
    alert = _alert(recovery_state="scheduled_retry")
    qi = _queue_item(next_retry_at=now - 3600.0, attempts=1)
    state, actionable, _ = (
        Orchestrator._classify_integration_retry_recovery(
            alert,
            running_focus=None,
            running_last_event_at=None,
            running_authority_revoked=False,
            queue_item=qi,
            integration_state=None,
            integration_updated_at=None,
            now=now,
            freshness_seconds=300,
        )
    )
    assert state == "stale_retry"
    assert actionable is True


# --------------------------------------------------- orchestrator integration


def _prime_alert(orch, alert: dict) -> None:
    orch._alerts.append(alert)


def _make_running(orch, project_id, task_id, focus="merge_conflict",
                  last_event_at=None, authority_revoked=False):
    issue = Issue(
        id=task_id,
        identifier=task_id,
        title="Task",
        state="Needs Rebase",
        project_id=project_id,
    )
    entry = RunningEntry(
        worker_task=MagicMock(),
        identifier=task_id,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="default",
        focus_name=focus,
    )
    entry.authority_revoked = authority_revoked
    if last_event_at is not None:
        session = MagicMock()
        session.last_timestamp = datetime.fromtimestamp(
            last_event_at, tz=timezone.utc
        )
        entry.session = session
    orch.state.running[issue.id] = entry


def test_reconcile_suppresses_active_recovery_warning(tmp_path):
    project = _make_project_record(project_id=PROJECT_ID)
    orch = _make_orch(tmp_path, projects=[project])
    _prime_alert(
        orch,
        _alert(recovery_state="awaiting_repair", action_required=False),
    )
    _make_running(
        orch,
        PROJECT_ID,
        TASK_ID,
        focus="merge_conflict",
        last_event_at=time.time() - 5,
    )
    orch._reconcile_integration_retry_alerts()
    reconciled = orch._alerts[-1]
    assert reconciled["recovery_state"] == "active_repair"
    assert reconciled["action_required"] is False
    assert reconciled["level"] == "info"


def test_reconcile_rearms_when_no_owner_or_retry(tmp_path):
    project = _make_project_record(project_id=PROJECT_ID)
    orch = _make_orch(tmp_path, projects=[project])
    _prime_alert(
        orch,
        _alert(recovery_state="awaiting_repair", action_required=False),
    )
    orch._reconcile_integration_retry_alerts()
    reconciled = orch._alerts[-1]
    assert reconciled["action_required"] is True
    assert reconciled["level"] == "warning"
    assert reconciled["recovery_state"] == "no_recovery"


def test_reconcile_downgrades_scheduled_retry(tmp_path):
    project = _make_project_record(project_id=PROJECT_ID)
    orch = _make_orch(tmp_path, projects=[project])
    _prime_alert(orch, _alert(recovery_state="scheduled_retry"))
    orch.integration_queue.enqueue(
        project_id=PROJECT_ID,
        epic_id=EPIC_ID,
        task_id=TASK_ID,
        task_branch=f"epic-{EPIC_ID}--task-{TASK_ID}",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at=datetime.now(timezone.utc).isoformat(),
        retry_at=time.time() + 60,
    )
    orch._reconcile_integration_retry_alerts()
    reconciled = orch._alerts[-1]
    assert reconciled["recovery_state"] == "scheduled_retry"
    assert reconciled["action_required"] is False
    assert reconciled["level"] == "info"


def test_reconcile_rearms_stale_repair(tmp_path):
    project = _make_project_record(project_id=PROJECT_ID)
    orch = _make_orch(tmp_path, projects=[project])
    _prime_alert(orch, _alert(recovery_state="active_repair"))
    _make_running(
        orch,
        PROJECT_ID,
        TASK_ID,
        focus="merge_conflict",
        last_event_at=time.time() - 3600,
    )
    orch._reconcile_integration_retry_alerts()
    reconciled = orch._alerts[-1]
    assert reconciled["recovery_state"] == "stale_repair"
    assert reconciled["action_required"] is True
    assert reconciled["level"] == "warning"


def test_reconcile_rearms_on_authority_revocation(tmp_path):
    project = _make_project_record(project_id=PROJECT_ID)
    orch = _make_orch(tmp_path, projects=[project])
    _prime_alert(orch, _alert(recovery_state="active_repair"))
    _make_running(
        orch,
        PROJECT_ID,
        TASK_ID,
        focus="merge_conflict",
        last_event_at=time.time(),
        authority_revoked=True,
    )
    orch._reconcile_integration_retry_alerts()
    reconciled = orch._alerts[-1]
    assert reconciled["recovery_state"] == "authority_revoked"
    assert reconciled["action_required"] is True


def test_reconcile_preserves_diagnostics(tmp_path):
    """Reconciliation must not lose failure/retry diagnostics."""
    project = _make_project_record(project_id=PROJECT_ID)
    orch = _make_orch(tmp_path, projects=[project])
    original = _alert(recovery_state="awaiting_repair")
    original["failing_step"] = "rebase"
    original["error"] = "merge conflict in file"
    original["attempts"] = 3
    original["max_attempts"] = 5
    _prime_alert(orch, original)
    orch._reconcile_integration_retry_alerts()
    reconciled = orch._alerts[-1]
    assert reconciled["failing_step"] == "rebase"
    assert reconciled["error"] == "merge conflict in file"
    assert reconciled["attempts"] == 3
    assert reconciled["max_attempts"] == 5
    assert reconciled["task_id"] == TASK_ID
    assert reconciled["project_id"] == PROJECT_ID
    # updated_at is refreshed
    assert "updated_at" in reconciled


def test_reconcile_ignores_non_integration_retry_alerts(tmp_path):
    project = _make_project_record(project_id=PROJECT_ID)
    orch = _make_orch(tmp_path, projects=[project])
    other = {
        "level": "error",
        "source": "credential_error:proj-1",
        "message": "auth failure",
    }
    orch._alerts.append(other)
    _prime_alert(orch, _alert(recovery_state="awaiting_repair"))
    orch._reconcile_integration_retry_alerts()
    # The credential-error alert must not be touched.
    assert orch._alerts[0] == other
    assert orch._alerts[0]["level"] == "error"


def test_clear_integration_retry_alert_removes_both_severities(tmp_path):
    """Successful integration clears actionable and informational rows."""
    project = _make_project_record(project_id=PROJECT_ID)
    orch = _make_orch(tmp_path, projects=[project])
    _prime_alert(orch, _alert(recovery_state="active_repair"))
    orch._clear_integration_retry_alert(PROJECT_ID, TASK_ID)
    assert not any(
        str(a.get("source", "")).startswith("integration_retry:")
        for a in orch._alerts
    )


# --------------------------------------------------- record-time defaults


def test_route_integration_failure_marks_retryable_as_info(tmp_path):
    """A scheduled retry starts as informational activity."""
    project = _make_project_record(epic_strategy="shared")
    orch = _make_orch(tmp_path, projects=[project])
    orch.integration_queue.enqueue(
        project_id=project.id,
        epic_id="EPIC-1",
        task_id="TASK-1",
        task_branch="epic-EPIC-1--task-TASK-1",
        head_sha="a" * 40,
        priority=1,
    )
    claimed = orch.integration_queue.claim_next(
        project_id=project.id,
        epic_id="EPIC-1",
        lease_owner="lease-1",
        dependency_map={"TASK-1": ()},
        satisfied=set(),
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        state="Ready to Integrate",
    )
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._route_integration_failure(
        claimed,
        IntegrationExecutionResult(
            status="epic_head_race",
            message="epic advanced",
            expected_epic_sha="b" * 40,
            rebased_task_sha="c" * 40,
        ),
    )
    alert = next(
        a for a in orch._alerts
        if a["source"] == f"integration_retry:{project.id}:TASK-1"
    )
    assert alert["recovery_state"] == "scheduled_retry"
    assert alert["action_required"] is False
    assert alert["level"] == "info"


def test_get_snapshot_publishes_reconciled_alerts(tmp_path):
    """State API/WS snapshots must publish each transition without a refresh.

    Verifies the reconciliation is invoked from get_snapshot so subscribers
    observe the current recovery_state/action_required immediately.
    """
    project = _make_project_record(project_id=PROJECT_ID)
    orch = _make_orch(tmp_path, projects=[project])
    _prime_alert(
        orch,
        _alert(recovery_state="awaiting_repair", action_required=False),
    )
    snap = orch.get_snapshot()
    published = next(
        a for a in snap["alerts"]
        if str(a.get("source", "")).startswith("integration_retry:")
    )
    # No repair worker and no scheduled retry — must be actionable.
    assert published["recovery_state"] == "no_recovery"
    assert published["action_required"] is True
    assert published["level"] == "warning"
    # Now dispatch a fresh repair worker and verify the next snapshot
    # downgrades the alert without any explicit call.
    _make_running(
        orch,
        PROJECT_ID,
        TASK_ID,
        focus="merge_conflict",
        last_event_at=time.time(),
    )
    snap2 = orch.get_snapshot()
    published2 = next(
        a for a in snap2["alerts"]
        if str(a.get("source", "")).startswith("integration_retry:")
    )
    assert published2["recovery_state"] == "active_repair"
    assert published2["action_required"] is False
    assert published2["level"] == "info"


def test_route_integration_failure_conflict_starts_as_awaiting_repair(tmp_path):
    """A real conflict starts non-actionable until repair worker gets stale."""
    project = _make_project_record(epic_strategy="shared")
    orch = _make_orch(tmp_path, projects=[project])
    orch.integration_queue.enqueue(
        project_id=project.id,
        epic_id="EPIC-1",
        task_id="TASK-1",
        task_branch="epic-EPIC-1--task-TASK-1",
        head_sha="a" * 40,
        priority=1,
    )
    claimed = orch.integration_queue.claim_next(
        project_id=project.id,
        epic_id="EPIC-1",
        lease_owner="lease-1",
        dependency_map={"TASK-1": ()},
        satisfied=set(),
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        state="Ready to Integrate",
    )
    orch._tracker_for_project = MagicMock(return_value=tracker)
    transcript = (
        Path(__file__).parent / "fixtures" / "exocomp_147_rebase_conflict.txt"
    ).read_text(encoding="utf-8")
    orch._route_integration_failure(
        claimed,
        IntegrationExecutionResult(
            status="conflict",
            message=transcript,
            expected_epic_sha="b" * 40,
        ),
    )
    alert = next(
        a for a in orch._alerts
        if a["source"] == f"integration_retry:{project.id}:TASK-1"
    )
    assert alert["recovery_state"] == "awaiting_repair"
    assert alert["action_required"] is False
    assert alert["level"] == "info"
    # The producer emits compact presentation fields and keeps the bounded,
    # sanitized transcript separate for the explicit details view.
    assert alert["failing_step"] == "task rebase"
    assert "\n" not in alert["title"]
    assert "\n" not in alert["summary"]
    assert "\n" not in alert["message"]
    assert "CONFLICT" in alert["diagnostic"]
    assert "EXOCOMP-147" in alert["error"]
