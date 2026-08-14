from datetime import datetime, timezone
import threading
from types import SimpleNamespace

import pytest

from oompah.implementation_prerequisite import (
    METADATA_KEY,
    ImplementationPrerequisiteRecord,
    PrerequisiteSourceChangedError,
    parse_prerequisite_declaration,
)
from oompah.models import AgentProfile, Issue, OrchestratorState, RunningEntry
from oompah.orchestrator import Orchestrator


class _Tracker:
    def __init__(self, issue, on_staged=None):
        self.issue = issue
        self.metadata = {}
        self.on_staged = on_staged
        self.final_fence_held = lambda: True

    def fetch_issue_detail(self, _identifier):
        return self.issue

    def get_metadata(self, _identifier):
        return dict(self.metadata)

    def set_metadata_field(self, _identifier, key, value):
        if isinstance(value, dict) and value.get("state") == "staged":
            self.metadata[key] = value
            if self.on_staged is not None:
                self.on_staged()
            return
        if isinstance(value, dict):
            assert self.final_fence_held()
        self.metadata[key] = value


def _orchestrator(issue, tracker):
    orch = Orchestrator.__new__(Orchestrator)
    orch.state = OrchestratorState(max_concurrent_agents=1)
    orch.config = SimpleNamespace(
        agent_profiles=[
            AgentProfile(
                name="mac-runner",
                command="runner",
                mode="cli",
                execution_capabilities=["macos"],
            )
        ]
    )
    orch.project_store = SimpleNamespace(
        project_write_lock=lambda _project_id: threading.RLock()
    )
    orch._retry_authority_lock = threading.RLock()
    orch._pending_profiles_lock = threading.RLock()
    orch._pending_agent_profiles = None
    orch._implementation_prerequisite_locks_guard = threading.Lock()
    orch._implementation_prerequisite_locks = {}
    orch._worktree_head = lambda _path: "b" * 40
    entry = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
        focus_name="developer",
        workspace_path="/worktree",
        run_id="run-1",
        assignment_id="assignment-1",
        authority_generation="generation-1",
    )
    orch.state.running[issue.id] = entry
    return orch, entry


def _issue():
    return Issue(
        id="task-1",
        identifier="TASK-1",
        title="Task",
        description="Implementation",
        state="In Progress",
        issue_type="task",
        project_id="project-1",
        assignment_id="assignment-1",
    )


def _declaration():
    result = parse_prerequisite_declaration(
        "Focus handoff: developer\n"
        "External prerequisite: platform: physical-macos-verification\n"
        "Recovery trigger: profile-capability:macos"
    )
    assert result is not None
    return result


def test_runtime_replacement_during_staging_cannot_finalize_stale_authority():
    issue = _issue()
    tracker = _Tracker(issue)
    orch, entry = _orchestrator(issue, tracker)
    replacement = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        focus_name="developer",
        run_id="run-2",
        assignment_id="assignment-2",
        authority_generation="generation-2",
    )
    tracker.on_staged = lambda: orch.state.running.__setitem__(
        issue.id, replacement
    )

    with pytest.raises(PrerequisiteSourceChangedError):
        orch._persist_handoff_implementation_prerequisite(
            entry=entry,
            declaration=_declaration(),
            tracker=tracker,
            identifier=issue.identifier,
            project_id="project-1",
        )

    assert tracker.metadata[METADATA_KEY] is None


def test_final_canonical_write_occurs_inside_project_and_runtime_fence():
    issue = _issue()
    tracker = _Tracker(issue)
    orch, entry = _orchestrator(issue, tracker)
    project_lock = threading.RLock()
    orch.project_store = SimpleNamespace(
        project_write_lock=lambda _project_id: project_lock
    )

    def fence_held():
        project_owned = getattr(project_lock, "_is_owned", lambda: False)()
        retry_owned = getattr(
            orch._retry_authority_lock, "_is_owned", lambda: False
        )()
        return project_owned and retry_owned

    tracker.final_fence_held = fence_held

    saved = orch._persist_handoff_implementation_prerequisite(
        entry=entry,
        declaration=_declaration(),
        tracker=tracker,
        identifier=issue.identifier,
        project_id="project-1",
    )

    assert isinstance(saved, ImplementationPrerequisiteRecord)
    assert tracker.metadata[METADATA_KEY] == saved.to_dict()
