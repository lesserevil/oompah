from datetime import datetime, timedelta, timezone
import json
import threading
from types import SimpleNamespace

import pytest

from oompah.implementation_prerequisite import (
    METADATA_KEY,
    RESOLUTION_METADATA_KEY,
    ImplementationPrerequisiteRecord,
    ImplementationPrerequisiteResolution,
    MalformedPrerequisiteRecordError,
    MalformedPrerequisiteResolutionError,
    PrerequisiteAdmissionKind,
    PrerequisiteContinuation,
    PrerequisiteConflictError,
    PrerequisiteKind,
    PrerequisiteReadbackError,
    PrerequisiteResolutionConflictError,
    PrerequisiteSourceChangedError,
    RecoveryTriggerKind,
    freeze_execution_profile_snapshot,
    new_record,
    new_resolution,
    parse_prerequisite_declaration,
    project_prerequisite_admission,
    save_record,
    save_resolution,
    select_execution_profile_name,
    select_profile_name,
)


NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)


def _comment(*lines: str) -> str:
    return "\n".join(("Focus handoff: developer", *lines))


def _declaration(
    kind: str = "platform",
    subject: str = "physical-macos-verification",
    trigger: str = "profile-capability:macos",
):
    return parse_prerequisite_declaration(
        _comment(
            f"External prerequisite: {kind}: {subject}",
            f"Recovery trigger: {trigger}",
        )
    )


def _record(*, declaration=None, now: datetime = NOW, run_id: str = "run-1"):
    declaration = declaration or _declaration()
    assert declaration is not None
    return new_record(
        declaration,
        project_id="trickle",
        task_id="143",
        task_identifier="TRICKLE-143",
        source_run_id=run_id,
        source_assignment_id="assignment-1",
        source_generation="generation-1",
        source_focus="developer",
        source_task_authority="a" * 64,
        source_head_sha="b" * 40,
        source_profile_revision="c" * 64,
        now=now,
    )


def _resolution(
    record=None,
    *,
    generation: str = "resolution-generation-1",
    task_authority: str = "d" * 64,
    now: datetime = NOW,
):
    record = record or _record()
    return new_resolution(
        record,
        expected_task_authority=task_authority,
        workflow_generation=generation,
        actor="project-owner",
        reason="The named prerequisite is now satisfied.",
        trigger_evidence={
            "kind": "profile-capability",
            "capability": "macos",
            "profile_name": "mac-runner",
            "profile_revision": "e" * 64,
        },
        continuation=PrerequisiteContinuation(
            resume_status="In Review",
            work_branch="TRICKLE-143",
            head_sha="b" * 40,
            review_id="20",
            review_head_sha="b" * 40,
            pipeline_id="62564237",
            pipeline_head_sha="b" * 40,
        ),
        now=now,
    )


def test_parser_accepts_exact_named_profile_capability_trigger():
    declaration = _declaration("hardware", "apple-silicon-host", "profile-capability:macos-arm64")

    assert declaration is not None
    assert declaration.kind is PrerequisiteKind.HARDWARE
    assert declaration.subject == "apple-silicon-host"
    assert declaration.recovery_trigger.kind is RecoveryTriggerKind.PROFILE_CAPABILITY
    assert declaration.recovery_trigger.value == "macos-arm64"


def test_parser_accepts_project_task_and_operator_trigger_pairs():
    task = _declaration("dependency", "forge-neutral-intake", "task:oompah/OOMPAH-1250")
    operator = _declaration("credentials", "production-signing-key", "operator:signing-key-installed")

    assert task is not None
    assert task.recovery_trigger.to_dict() == {
        "kind": "task",
        "value": "OOMPAH-1250",
        "project_id": "oompah",
    }
    assert operator is not None
    assert operator.recovery_trigger.to_dict() == {
        "kind": "operator",
        "value": "signing-key-installed",
    }


@pytest.mark.parametrize(
    ("kind", "trigger"),
    [
        ("dependency", "profile-capability:macos"),
        ("dependency", "operator:review"),
        ("hardware", "task:trickle/TRICKLE-142"),
        ("hardware", "operator:review"),
        ("platform", "task:trickle/TRICKLE-142"),
        ("credentials", "profile-capability:hsm"),
        ("credentials", "task:ops/OPS-1"),
        ("operator-evidence", "profile-capability:macos"),
        ("operator-evidence", "task:ops/OPS-1"),
    ],
)
def test_parser_rejects_prerequisite_trigger_bypass_pairs(kind, trigger):
    assert _declaration(kind, "named-prerequisite", trigger) is None


@pytest.mark.parametrize(
    "text",
    [
        _comment("Remaining work probably requires a Mac."),
        _comment("External prerequisite: platform: macos"),
        _comment("Recovery trigger: profile-capability:macos"),
        _comment(
            "External prerequisite: platform: macos",
            "Recovery trigger: profile-capability:macos",
            "Recovery trigger: profile-capability:linux",
        ),
        _comment(
            " external prerequisite: platform: macos",
            "Recovery trigger: profile-capability:macos",
        ),
        _comment(
            "EXTERNAL PREREQUISITE: platform: macos",
            "Recovery trigger: profile-capability:macos",
        ),
        _comment(
            "External prerequisite: platform: macos",
            "recovery trigger: profile-capability:macos",
        ),
        _comment(
            "External prerequisite: platform: macos",
            "Recovery trigger: profile-capability:MacOS",
        ),
        _comment(
            "External prerequisite: credentials: sk-proj-secretvalue",
            "Recovery trigger: operator:credential-installed",
        ),
        _comment(
            "External prerequisite: credentials: github_pat_secretvalue",
            "Recovery trigger: operator:credential-installed",
        ),
        _comment(
            "External prerequisite: platform: macos,linux",
            "Recovery trigger: profile-capability:macos",
        ),
        _comment(
            "External prerequisite: platform: macos",
            "Recovery trigger: profile-capability:macos",
            " External prerequisite: platform: linux",
        ),
        _comment(
            "External prerequisite: platform: macos",
            "Recovery trigger: profile-capability:macos",
            "\tRecovery trigger: profile-capability:linux",
        ),
        _comment(
            "External prerequisite: platform: macos",
            "Recovery trigger: profile-capability:macos",
            "**Recovery trigger: profile-capability:linux",
        ),
    ],
)
def test_parser_rejects_prose_aliases_lists_secrets_and_reserved_abuse(text):
    assert parse_prerequisite_declaration(text) is None


def test_record_round_trip_and_id_excludes_display_timestamp():
    record = _record()
    restored = ImplementationPrerequisiteRecord.from_raw(record.to_dict())
    replay = _record(now=NOW + timedelta(hours=1))

    assert restored == record
    assert replay.record_id == record.record_id
    assert replay.created_at != record.created_at


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", True),
        ("schema_version", "1"),
        ("record_id", 1),
        ("source_run_id", False),
        ("source_head_sha", "b" * 41),
        ("source_head_sha", "B" * 40),
        ("source_task_authority", "a" * 63),
        ("source_profile_revision", "c" * 65),
        ("source_focus", "Developer"),
        ("created_at", True),
    ],
)
def test_record_rejects_noncanonical_types_and_authority(field, value):
    raw = _record().to_dict()
    raw[field] = value
    assert ImplementationPrerequisiteRecord.from_raw(raw) is None


def test_record_rejects_tamper_future_schema_unknown_keys_and_noncanonical_time():
    raw = _record().to_dict()
    cases = []
    tampered = dict(raw)
    tampered["source_run_id"] = "replacement"
    cases.append(tampered)
    future = dict(raw)
    future["schema_version"] = 2
    cases.append(future)
    unknown = dict(raw)
    unknown["future_field"] = "value"
    cases.append(unknown)
    noncanonical_time = dict(raw)
    noncanonical_time["created_at"] = "2026-08-14T00:00:00Z"
    cases.append(noncanonical_time)

    assert all(ImplementationPrerequisiteRecord.from_raw(case) is None for case in cases)


def test_resolution_round_trip_preserves_trickle_review_and_pipeline_identity():
    resolution = _resolution()

    restored = ImplementationPrerequisiteResolution.from_raw(resolution.to_dict())

    assert restored == resolution
    assert restored.continuation.resume_status == "In Review"
    assert restored.continuation.review_id == "20"
    assert restored.continuation.pipeline_id == "62564237"
    assert restored.continuation.head_sha == "b" * 40


def test_resolution_rejects_tamper_unknown_fields_and_split_heads():
    raw = _resolution().to_dict()
    tampered = dict(raw)
    tampered["source_run_id"] = "replacement-run"
    unknown = dict(raw)
    unknown["future"] = True
    split_heads = json.loads(json.dumps(raw))
    split_heads["continuation"]["pipeline_head_sha"] = "f" * 40

    assert ImplementationPrerequisiteResolution.from_raw(tampered) is None
    assert ImplementationPrerequisiteResolution.from_raw(unknown) is None
    assert ImplementationPrerequisiteResolution.from_raw(split_heads) is None


class _Tracker:
    def __init__(self, raw=None):
        self.metadata = {} if raw is None else {METADATA_KEY: raw}
        self.writes = []
        self.readback_override = None
        self.raise_after_write = False

    def get_metadata(self, identifier):
        if self.readback_override is not None and self.writes:
            return {METADATA_KEY: self.readback_override}
        return dict(self.metadata)

    def set_metadata_field(self, identifier, key, value):
        self.writes.append((identifier, key, value))
        self.metadata[key] = value
        if self.raise_after_write:
            raise RuntimeError("lost response")


def _issue():
    return SimpleNamespace(
        identifier="TRICKLE-143",
        implementation_prerequisite=None,
        implementation_prerequisite_resolution=None,
    )


def test_store_absent_write_exact_readback_and_lost_response_recovery():
    for lost_response in (False, True):
        tracker = _Tracker()
        tracker.raise_after_write = lost_response
        issue = _issue()
        record = _record()

        saved = save_record(tracker, issue, record, lock=threading.Lock())

        assert saved == record
        assert issue.implementation_prerequisite == record.to_dict()
        assert len(tracker.writes) == 2
        assert tracker.writes[0][2]["state"] == "staged"
        assert tracker.writes[1][2] == record.to_dict()


def test_store_same_id_replay_is_idempotent_and_keeps_first_timestamp():
    first = _record()
    replay = _record(now=NOW + timedelta(days=1))
    tracker = _Tracker(first.to_dict())

    saved = save_record(tracker, _issue(), replay, lock=threading.Lock())

    assert saved == first
    assert tracker.writes == []


def test_store_rejects_different_record_without_resolution_cas():
    tracker = _Tracker(_record().to_dict())
    with pytest.raises(PrerequisiteConflictError):
        save_record(
            tracker,
            _issue(),
            _record(run_id="replacement"),
            lock=threading.Lock(),
        )
    assert tracker.writes == []


def test_store_quarantines_malformed_existing_and_readback_mismatch():
    malformed = _Tracker({"schema_version": 1})
    with pytest.raises(MalformedPrerequisiteRecordError):
        save_record(malformed, _issue(), _record(), lock=threading.Lock())
    assert malformed.writes == []

    mismatched = _Tracker()
    mismatched.readback_override = _record(run_id="other").to_dict()
    with pytest.raises(PrerequisiteReadbackError):
        save_record(mismatched, _issue(), _record(), lock=threading.Lock())


def test_store_rolls_back_exact_staged_record_when_live_source_changes():
    tracker = _Tracker()
    issue = _issue()

    with pytest.raises(PrerequisiteSourceChangedError):
        save_record(
            tracker,
            issue,
            _record(),
            lock=threading.Lock(),
            accept_staged=lambda: False,
        )

    assert tracker.metadata[METADATA_KEY] is None
    assert issue.implementation_prerequisite is None


def test_store_staged_value_is_never_visible_as_authoritative_record():
    tracker = _Tracker()
    seen = []

    def accept():
        raw = tracker.metadata[METADATA_KEY]
        seen.append(raw)
        assert ImplementationPrerequisiteRecord.from_raw(raw) is None
        return True

    saved = save_record(
        tracker,
        _issue(),
        _record(),
        lock=threading.Lock(),
        accept_staged=accept,
    )

    assert saved == _record()
    assert seen[0]["state"] == "staged"


def test_crash_before_finalize_leaves_only_non_authoritative_staging():
    tracker = _Tracker()

    class CrashFence:
        def __enter__(self):
            raise RuntimeError("process interrupted before final authority")

        def __exit__(self, *exc_info):
            return None

    with pytest.raises(RuntimeError, match="interrupted"):
        save_record(
            tracker,
            _issue(),
            _record(),
            lock=threading.Lock(),
            finalize_fence=CrashFence(),
        )

    raw = tracker.metadata[METADATA_KEY]
    assert raw["state"] == "staged"
    assert ImplementationPrerequisiteRecord.from_raw(raw) is None


def test_resolution_store_exact_cas_is_idempotent_and_recovers_lost_response():
    record = _record()
    resolution = _resolution(record)
    tracker = _Tracker(record.to_dict())
    tracker.raise_after_write = True
    issue = _issue()

    saved = save_resolution(
        tracker,
        issue,
        record,
        resolution,
        lock=threading.Lock(),
        accept_current=lambda: True,
    )
    replay = save_resolution(
        tracker,
        issue,
        record,
        resolution,
        lock=threading.Lock(),
        accept_current=lambda: False,
    )

    assert saved == resolution
    assert replay == resolution
    assert issue.implementation_prerequisite_resolution == resolution.to_dict()
    assert [write[1] for write in tracker.writes] == [RESOLUTION_METADATA_KEY]


def test_resolution_store_rejects_stale_task_and_blocker_authority():
    record = _record()
    resolution = _resolution(record)
    stale_task = _Tracker(record.to_dict())
    with pytest.raises(PrerequisiteSourceChangedError, match="task authority"):
        save_resolution(
            stale_task,
            _issue(),
            record,
            resolution,
            lock=threading.Lock(),
            accept_current=lambda: False,
        )
    assert stale_task.writes == []

    replacement = _record(run_id="replacement")
    stale_record = _Tracker(replacement.to_dict())
    with pytest.raises(PrerequisiteSourceChangedError, match="changed"):
        save_resolution(
            stale_record,
            _issue(),
            record,
            resolution,
            lock=threading.Lock(),
            accept_current=lambda: True,
        )
    assert stale_record.writes == []


def test_resolution_store_rejects_concurrent_replacement_and_malformed_history():
    record = _record()
    first = _resolution(record)
    tracker = _Tracker(record.to_dict())
    tracker.metadata[RESOLUTION_METADATA_KEY] = first.to_dict()

    with pytest.raises(PrerequisiteResolutionConflictError):
        save_resolution(
            tracker,
            _issue(),
            record,
            _resolution(record, generation="replacement-generation"),
            lock=threading.Lock(),
            accept_current=lambda: True,
        )

    tracker.metadata[RESOLUTION_METADATA_KEY] = {"state": "staged"}
    with pytest.raises(MalformedPrerequisiteResolutionError):
        save_resolution(
            tracker,
            _issue(),
            record,
            first,
            lock=threading.Lock(),
            accept_current=lambda: True,
        )


def _profile(name, capabilities, **constraints):
    return SimpleNamespace(
        name=name,
        execution_capabilities=list(capabilities),
        issue_types=list(constraints.get("issue_types", [])),
        keywords=list(constraints.get("keywords", [])),
        min_priority=constraints.get("min_priority"),
        max_priority=constraints.get("max_priority"),
    )


def test_profile_snapshot_is_immutable_and_configured_order_is_authority():
    first = _profile("first", ["macos", "arm64", "macos"])
    second = _profile("second", ["macos"])
    snapshot = freeze_execution_profile_snapshot([first, second])
    first.execution_capabilities.append("linux")

    assert snapshot.profiles[0].execution_capabilities == ("arm64", "macos")
    assert [profile.name for profile in snapshot.profiles] == ["first", "second"]
    reordered = freeze_execution_profile_snapshot([second, first])
    assert reordered.revision != snapshot.revision


def test_capability_selection_requires_applicability_and_keeps_first_equal_match():
    snapshot = freeze_execution_profile_snapshot(
        [
            _profile("incapable-applicable", [], issue_types=["task"]),
            _profile("capable-wrong-type", ["macos"], issue_types=["bug"]),
            _profile("capable-first", ["macos"], issue_types=["task"]),
            _profile("capable-equal", ["macos"], issue_types=["task"]),
        ]
    )
    issue = SimpleNamespace(
        issue_type="task",
        title="Physical runner validation",
        description="",
        priority=1,
    )

    assert select_execution_profile_name(snapshot, issue, "macos") == "capable-first"
    assert select_execution_profile_name(snapshot, issue, "linux") is None


def test_capability_selection_has_exact_ordinary_matcher_case_semantics():
    snapshot = freeze_execution_profile_snapshot(
        [_profile("upper", ["macos"], issue_types=["BUG"])]
    )
    issue = SimpleNamespace(
        issue_type="bug", title="Bug", description="", priority="not-an-int"
    )

    assert select_profile_name(snapshot, issue) is None
    assert select_execution_profile_name(snapshot, issue, "macos") is None


@pytest.mark.parametrize(
    ("kind", "trigger", "expected"),
    (
        ("dependency", "task:oompah/OOMPAH-7", PrerequisiteAdmissionKind.BLOCKED_DEPENDENCY),
        ("credentials", "operator:credential-installed", PrerequisiteAdmissionKind.BLOCKED_OPERATOR),
        ("platform", "profile-capability:macos", PrerequisiteAdmissionKind.BLOCKED_CAPABILITY),
    ),
)
def test_durable_record_projects_non_transient_blocked_admission(
    kind, trigger, expected
):
    record = _record(declaration=_declaration(kind, "external-resource", trigger))
    issue = SimpleNamespace(
        id="143",
        identifier="TRICKLE-143",
        project_id="trickle",
        issue_type="task",
        title="Task",
        description="",
        priority=2,
        implementation_prerequisite=record.to_dict(),
    )
    snapshot = freeze_execution_profile_snapshot([_profile("default", [])])

    disposition = project_prerequisite_admission(issue, snapshot)

    assert disposition is not None
    assert disposition.kind is expected
    assert disposition.dispatchable is False


def test_durable_capability_record_projects_exact_capable_profile():
    record = _record()
    issue = SimpleNamespace(
        id="143",
        identifier="TRICKLE-143",
        project_id="trickle",
        issue_type="task",
        title="Task",
        description="",
        priority=2,
        implementation_prerequisite=record.to_dict(),
    )
    snapshot = freeze_execution_profile_snapshot(
        [_profile("default", []), _profile("mac-runner", ["macos"])]
    )

    disposition = project_prerequisite_admission(issue, snapshot)

    assert disposition is not None
    assert disposition.kind is PrerequisiteAdmissionKind.CAPABLE_PROFILE
    assert disposition.profile_name == "mac-runner"
    assert disposition.profile_revision == snapshot.revision
    assert disposition.dispatchable is True


def test_only_exact_committed_resolution_ends_prerequisite_admission():
    record = _record()
    resolution = _resolution(record)
    issue = SimpleNamespace(
        id="143",
        identifier="TRICKLE-143",
        project_id="trickle",
        issue_type="task",
        title="Task",
        description="",
        priority=2,
        implementation_prerequisite=record.to_dict(),
        implementation_prerequisite_resolution=resolution.to_dict(),
    )
    snapshot = freeze_execution_profile_snapshot([])

    assert project_prerequisite_admission(issue, snapshot) is None

    issue.implementation_prerequisite_resolution = {"state": "staged"}
    assert project_prerequisite_admission(issue, snapshot).dispatchable is False

    issue.implementation_prerequisite_resolution = _resolution(
        record, generation="stale-job"
    ).to_dict()
    # A different job-bound resolution is still exact for this record; the
    # first committed receipt wins at the store CAS, while admission consumes
    # whichever exact committed receipt the tracker projects.
    assert project_prerequisite_admission(issue, snapshot) is None


def test_staged_or_cross_task_record_projects_malformed_jobless_admission():
    record = _record()
    issue = SimpleNamespace(
        id="other-task",
        identifier="TRICKLE-143",
        project_id="trickle",
        implementation_prerequisite=record.to_dict(),
    )
    disposition = project_prerequisite_admission(
        issue, freeze_execution_profile_snapshot([])
    )
    assert disposition is not None
    assert disposition.kind is PrerequisiteAdmissionKind.MALFORMED
    assert disposition.dispatchable is False


@pytest.mark.parametrize("malformed", ["scalar", ["list"]])
def test_github_projection_preserves_malformed_prerequisite(malformed):
    from oompah.github_tracker import _gh_issue_to_issue

    body = "<!-- oompah:metadata\n" + json.dumps(
        {
            "implementation_prerequisite": malformed,
            "implementation_prerequisite_resolution": malformed,
        }
    ) + "\n-->"
    issue = _gh_issue_to_issue(
        {
            "number": 7,
            "title": "Task",
            "body": body,
            "state": "open",
            "labels": [],
        },
        "owner",
        "repo",
    )
    assert issue.implementation_prerequisite == malformed
    assert issue.implementation_prerequisite_resolution == malformed


@pytest.mark.parametrize("malformed", ["scalar", ["list"]])
def test_gitlab_projection_preserves_malformed_prerequisite(malformed):
    from oompah.gitlab_tracker import GitLabIssueTracker

    tracker = GitLabIssueTracker.__new__(GitLabIssueTracker)
    tracker.project = "group/sub/project"
    description = "<!-- oompah:metadata\n" + json.dumps(
        {
            "implementation_prerequisite": malformed,
            "implementation_prerequisite_resolution": malformed,
        }
    ) + "\n-->"
    issue = tracker._issue(
        {
            "iid": 7,
            "title": "Task",
            "description": description,
            "state": "opened",
            "labels": [],
            "web_url": "https://gitlab/group/sub/project/-/issues/7",
        }
    )
    assert issue.implementation_prerequisite == malformed
    assert issue.implementation_prerequisite_resolution == malformed


@pytest.mark.parametrize("malformed", ["scalar", ["list"]])
def test_native_projection_preserves_malformed_prerequisite(malformed):
    from oompah.oompah_md_tracker import OompahMarkdownTracker

    tracker = OompahMarkdownTracker.__new__(OompahMarkdownTracker)
    tracker.terminal_states = ["Done", "Merged", "Archived"]
    issue = tracker._normalize_record(
        {
            "path": "Open/TASK-7.md",
            "meta": {
                "id": "TASK-7",
                "title": "Task",
                "status": "Open",
                "oompah.implementation_prerequisite": malformed,
                "oompah.implementation_prerequisite_resolution": malformed,
            },
            "body": "## Summary\nTask body\n",
        }
    )
    assert issue.implementation_prerequisite == malformed
    assert issue.implementation_prerequisite_resolution == malformed
