"""Tests for tracker-neutral terminal-audit records and evidence."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from oompah.terminal_audit import (
    AuditAttempt,
    AuditRevisionBinding,
    ContributorIdentity,
    EvidenceFingerprint,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    archive_default_branch_fallback_authorized,
    build_revision_candidate_list,
    compute_evidence_fingerprint,
    compute_issue_evidence_fingerprint,
    _resolve_epic_branch_names,
)
from oompah.models import Issue


def _fingerprint(**overrides: object) -> EvidenceFingerprint:
    values: dict[str, object] = {
        "requirements_text": "Ship the audit state model.",
        "project_id": "proj-1",
        "task_id": "TASK-1",
        "source_branch": "feature/TASK-1",
        "source_sha": "a" * 40,
        "target_branch": "main",
        "target_sha": "b" * 40,
        "review_id": "42",
        "review_state": "open",
        "child_audit_digests": ["child-b", "child-a"],
        "contributors": [
            ContributorIdentity("alice", "github"),
            ContributorIdentity("bob", "git"),
        ],
    }
    values.update(overrides)
    return compute_evidence_fingerprint(**values)  # type: ignore[arg-type]


def _record() -> TerminalAuditRecord:
    fingerprint = _fingerprint()
    attempt = AuditAttempt(
        attempt_id="attempt-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        verdict=Verdict.PASS,
        requested_by=ContributorIdentity("alice", "github"),
        created_at="2026-07-28T00:00:00Z",
        completed_at="2026-07-28T00:01:00Z",
    )
    return TerminalAuditRecord(
        audit_id="audit-1",
        project_id="proj-1",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        attempts=[attempt],
        requested_by=ContributorIdentity("alice", "github"),
        previous_state="In Validation",
        created_at="2026-07-28T00:00:00Z",
    )


class TestSerialization:
    def test_round_trip_is_deterministic(self) -> None:
        original = _record()
        serialized = original.to_dict()
        restored = TerminalAuditRecord.from_dict(serialized)

        assert restored == original
        assert restored.to_dict() == serialized
        assert serialized["version"] == 1
        assert serialized["evidence_fingerprint"]["version"] == 1

    def test_unknown_fields_are_ignored_for_forward_compatibility(self) -> None:
        data = _record().to_dict()
        data["future_field"] = {"new": "value"}
        data["attempts"][0]["future_attempt_field"] = True
        data["evidence_fingerprint"]["future_fingerprint_field"] = 7

        restored = TerminalAuditRecord.from_dict(data)

        assert restored == _record()

    def test_legacy_optional_fields_can_be_missing(self) -> None:
        data = _record().to_dict()
        data.pop("requested_by")
        data.pop("previous_state")
        data.pop("created_at")
        data["attempts"][0].pop("requested_by")
        data["attempts"][0].pop("created_at")
        data["attempts"][0].pop("completed_at")

        restored = TerminalAuditRecord.from_dict(data)

        assert restored.requested_by is None
        assert restored.previous_state is None
        assert restored.created_at is None
        assert restored.attempts[0].requested_by is None

    def test_legacy_record_without_attempts_defaults_to_empty(self) -> None:
        data = _record().to_dict()
        data.pop("attempts")

        restored = TerminalAuditRecord.from_dict(data)

        assert restored.attempts == []

    def test_revision_binding_round_trips_and_legacy_record_remains_readable(
        self,
    ) -> None:
        sha = "c" * 40
        original = replace(
            _record(),
            selected_ref="origin/epic-OOMPAH-768",
            selected_sha=sha,
            attempts=[
                replace(
                    _record().attempts[0],
                    selected_ref="origin/epic-OOMPAH-768",
                    selected_sha=sha,
                )
            ],
        )

        assert TerminalAuditRecord.from_dict(original.to_dict()) == original
        legacy = _record().to_dict()
        assert TerminalAuditRecord.from_dict(legacy).selected_sha is None

    def test_revision_binding_is_all_or_nothing_and_immutable_ref_matches_sha(
        self,
    ) -> None:
        with pytest.raises(ValueError, match="supplied together"):
            replace(_record(), selected_ref="origin/main")
        with pytest.raises(ValueError, match="must equal"):
            AuditRevisionBinding("a" * 40, "b" * 40)

    @pytest.mark.parametrize(
        "record_type, payload, missing",
        [
            (TerminalAuditRecord, _record().to_dict(), "audit_id"),
            (AuditAttempt, _record().attempts[0].to_dict(), "attempt_id"),
            (EvidenceFingerprint, _record().evidence_fingerprint.to_dict(), "digest"),
            (ContributorIdentity, ContributorIdentity("alice").to_dict(), "identity"),
        ],
    )
    def test_required_fields_are_strict(
        self, record_type: type[object], payload: dict[str, object], missing: str
    ) -> None:
        payload.pop(missing)

        with pytest.raises(ValueError, match=missing):
            record_type.from_dict(payload)  # type: ignore[attr-defined]

    @pytest.mark.parametrize("record_type", [TerminalAuditRecord, AuditAttempt, EvidenceFingerprint])
    def test_version_is_required_and_supported(self, record_type: type[object]) -> None:
        payload = (
            _record().to_dict()
            if record_type is TerminalAuditRecord
            else _record().attempts[0].to_dict()
            if record_type is AuditAttempt
            else _record().evidence_fingerprint.to_dict()
        )
        payload.pop("version")
        with pytest.raises(ValueError, match="version"):
            record_type.from_dict(payload)  # type: ignore[attr-defined]

        payload["version"] = 99
        with pytest.raises(ValueError, match="version"):
            record_type.from_dict(payload)  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "enum_type, value",
        [
            (TargetState, "not-terminal"),
            (RequestState, "not-request"),
            (Verdict, "maybe"),
            (FailureClassification, "made-up"),
        ],
    )
    def test_unknown_enum_values_are_rejected(self, enum_type: type[object], value: str) -> None:
        with pytest.raises(ValueError):
            enum_type.from_raw(value)  # type: ignore[attr-defined]


class TestEvidenceFingerprint:
    def test_identical_evidence_has_identical_sha256(self) -> None:
        first = _fingerprint()
        second = _fingerprint(
            contributors=[
                ContributorIdentity("bob", "git"),
                ContributorIdentity("alice", "github"),
            ],
            child_audit_digests=["child-a", "child-b"],
        )

        assert first == second
        assert len(first.digest) == 64
        assert first.algorithm == "sha256"

    @pytest.mark.parametrize(
        "change",
        [
            {"requirements_text": "Ship the changed audit state model."},
            {"source_sha": "c" * 40},
            {"target_sha": "c" * 40},
            {"review_id": "43"},
            {"review_state": "merged"},
            {"child_audit_digests": ["child-a", "child-c"]},
            {"project_id": "proj-2"},
            {"task_id": "TASK-2"},
            {"source_branch": "feature/other"},
            {"target_branch": "release/1.0"},
        ],
    )
    def test_material_evidence_changes_digest(self, change: dict[str, object]) -> None:
        assert _fingerprint() != _fingerprint(**change)

    def test_requirements_whitespace_is_normalized(self) -> None:
        assert _fingerprint(requirements_text="  Ship\n\tthe audit state model. ") == _fingerprint()

    def test_fingerprint_payload_excludes_diff_credentials_and_prose(self) -> None:
        baseline = _fingerprint()
        # The public constructor has no parameters for any of these values;
        # changing unrelated local data cannot alter the digest.
        unrelated = replace(
            _record(),
            previous_state="model response: token=secret full diff follows",
        )

        assert unrelated.evidence_fingerprint == baseline


class TestEpicBranchResolution:
    """Tests for resolving canonical epic branch names (OOMPAH-746)."""

    def test_resolve_epic_branch_for_standalone_epic(self) -> None:
        """A standalone epic should try its own epic branch."""
        branches = _resolve_epic_branch_names("EPIC-42", parent_id=None, issue_type="epic")
        assert branches == ["epic-EPIC-42"]

    def test_resolve_epic_branch_for_nested_epic(self) -> None:
        """A nested epic should try parent's branch first, then its own."""
        branches = _resolve_epic_branch_names(
            "CHILD-1", parent_id="EPIC-42", issue_type="epic"
        )
        assert branches == ["epic-EPIC-42", "epic-CHILD-1"]

    def test_resolve_epic_branch_for_non_epic_issue(self) -> None:
        """Non-epic issues should not produce any epic branch names."""
        branches = _resolve_epic_branch_names("TASK-1", parent_id=None, issue_type="task")
        assert branches == []

        branches = _resolve_epic_branch_names("TASK-1", parent_id=None, issue_type="")
        assert branches == []

    def test_epic_branch_resolution_is_empty_without_identifier(self) -> None:
        """Empty or missing issue identifier should not produce branches."""
        branches = _resolve_epic_branch_names("", parent_id=None, issue_type="epic")
        assert branches == []

    def test_compute_fingerprint_uses_work_branch_when_set(self) -> None:
        """When work_branch is explicitly set, it should be used (not epic branch)."""
        issue = Issue(
            id="EPIC-42",
            identifier="EPIC-42",
            title="Test epic",
            description="Epic description",
            work_branch="epic-custom-name",
            issue_type="epic",
        )
        
        fp = compute_issue_evidence_fingerprint(issue, "proj-1")
        
        # Fingerprint should reflect the explicit work_branch
        fp2 = compute_evidence_fingerprint(
            requirements_text="Epic description",
            project_id="proj-1",
            task_id="EPIC-42",
            source_branch="epic-custom-name",
        )
        assert fp == fp2

    def test_compute_fingerprint_resolves_epic_branch_when_work_branch_absent(self) -> None:
        """When work_branch is absent for an epic, use canonical epic branch."""
        issue = Issue(
            id="EPIC-42",
            identifier="EPIC-42",
            title="Test epic",
            description="Epic description",
            work_branch=None,
            issue_type="epic",
        )
        
        fp = compute_issue_evidence_fingerprint(issue, "proj-1")
        
        # Should use the resolved epic-EPIC-42 branch name
        fp_expected = compute_evidence_fingerprint(
            requirements_text="Epic description",
            project_id="proj-1",
            task_id="EPIC-42",
            source_branch="epic-EPIC-42",
        )
        assert fp == fp_expected

    def test_compute_fingerprint_for_nested_epic_without_work_branch(self) -> None:
        """Nested epic without work_branch should try parent branch first."""
        issue = Issue(
            id="CHILD-1",
            identifier="CHILD-1",
            title="Nested epic",
            description="Child epic description",
            parent_id="EPIC-42",
            work_branch=None,
            issue_type="epic",
        )
        
        fp = compute_issue_evidence_fingerprint(issue, "proj-1")
        
        # Should use the parent's epic branch (first candidate)
        fp_expected = compute_evidence_fingerprint(
            requirements_text="Child epic description",
            project_id="proj-1",
            task_id="CHILD-1",
            source_branch="epic-EPIC-42",
        )
        assert fp == fp_expected

    def test_compute_fingerprint_respects_integration_record(self) -> None:
        """Integrated task evidence takes precedence over epic branch resolution."""
        issue = Issue(
            id="EPIC-42",
            identifier="EPIC-42",
            title="Integrated epic",
            description="Description",
            work_branch=None,
            issue_type="epic",
        )
        
        # Add integration record with explicit task_branch
        issue.integration = Mock(
            task_branch="epic-EPIC-42",
            head_sha="abc123",
            base_branch="main",
            base_sha="def456",
            state="integrated",
            integrated_sha="ghi789",
        )
        
        fp = compute_issue_evidence_fingerprint(issue, "proj-1")
        
        # For integrated state, should use integrated_sha/branch
        fp_expected = compute_evidence_fingerprint(
            requirements_text="Description",
            project_id="proj-1",
            task_id="EPIC-42",
            source_branch="main",
            source_sha="ghi789",
            target_branch="main",
            target_sha="ghi789",
            contributors=[ContributorIdentity("epic-EPIC-42", "git-branch")],
        )
        assert fp == fp_expected

    def test_accepted_generation_overrides_stale_source_projection(self) -> None:
        """Auditor lock and fingerprint use the same exact accepted generation."""

        issue = Issue(
            id="OOMPAH-814",
            identifier="OOMPAH-814",
            title="Accepted task",
            description="Description",
            project_id="proj-1",
            work_branch="epic-OOMPAH-763--task-OOMPAH-814",
            branch_name="epic-OOMPAH-763--task-OOMPAH-814",
            target_branch="main",
        )
        issue.source_branch = "stale-source"
        issue.source_sha = "b" * 40
        issue.integration = Mock(
            state="ready",
            task_branch="OOMPAH-814",
            head_sha="a" * 40,
            base_branch="main",
            base_sha="c" * 40,
            integrated_sha=None,
        )

        fingerprint = compute_issue_evidence_fingerprint(issue, "proj-1")

        expected = compute_evidence_fingerprint(
            requirements_text="Description",
            project_id="proj-1",
            task_id="OOMPAH-814",
            source_branch="OOMPAH-814",
            source_sha="a" * 40,
            target_branch="main",
            target_sha="c" * 40,
        )
        assert fingerprint == expected

    def test_compute_fingerprint_prefers_explicit_work_branch_over_epic_branch(self) -> None:
        """Explicit work_branch takes precedence over epic branch resolution."""
        issue = Issue(
            id="EPIC-42",
            identifier="EPIC-42",
            title="Epic with explicit branch",
            description="Description",
            work_branch="custom-epic-branch",
            issue_type="epic",
        )
        
        fp = compute_issue_evidence_fingerprint(issue, "proj-1")
        
        # Should use explicit work_branch, not epic branch
        fp_expected = compute_evidence_fingerprint(
            requirements_text="Description",
            project_id="proj-1",
            task_id="EPIC-42",
            source_branch="custom-epic-branch",
        )
        assert fp == fp_expected

    def test_ordinary_head_sha_preserves_legacy_branch_and_sha_shape(self) -> None:
        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Task",
            description="Description",
            work_branch="task-work",
            integration=Mock(
                state="ready",
                task_branch="task-work",
                head_sha="a" * 40,
                integrated_sha=None,
                base_branch="main",
                base_sha="b" * 40,
            ),
        )

        actual = compute_issue_evidence_fingerprint(issue, "proj-1")

        assert actual == compute_evidence_fingerprint(
            requirements_text="Description",
            project_id="proj-1",
            task_id="TASK-1",
            source_branch="task-work",
            source_sha="a" * 40,
            target_branch="main",
            target_sha="b" * 40,
        )

    def test_compute_fingerprint_falls_back_through_candidates(self) -> None:
        """Branch resolution tries candidates in order: source_branch, work_branch, integration, branch_name, epic."""
        issue = Issue(
            id="TASK-99",
            identifier="TASK-99",
            title="Task",
            description="Description",
        )
        
        # Only issue_type and identifier set, should not trigger epic resolution
        # for non-epic tasks
        fp = compute_issue_evidence_fingerprint(issue, "proj-1")
        
        fp_expected = compute_evidence_fingerprint(
            requirements_text="Description",
            project_id="proj-1",
            task_id="TASK-99",
            source_branch="",  # Empty, no candidates matched
        )
        assert fp == fp_expected


class TestRevisionCandidateList:
    """Tests for immutable terminal-audit revision authority."""

    def test_standalone_epic_without_work_branch_resolves_epic_branch(self) -> None:
        """Standalone epic with no work_branch should resolve epic-EPIC-42."""
        issue = Issue(
            id="EPIC-42",
            identifier="EPIC-42",
            title="Standalone epic",
            description="Description",
            work_branch=None,
            issue_type="epic",
        )

        candidates = build_revision_candidate_list(issue, "proj-1")

        assert list(candidates.iter_for_workspace()) == ["origin/epic-EPIC-42"]

    def test_nested_epic_tries_parent_branch_first(self) -> None:
        """Nested epic should try parent epic branch first, then own branch."""
        issue = Issue(
            id="CHILD-1",
            identifier="CHILD-1",
            title="Nested epic",
            description="Description",
            parent_id="EPIC-42",
            work_branch=None,
            issue_type="epic",
        )

        candidates = build_revision_candidate_list(issue, "proj-1")

        revisions = list(candidates.iter_for_workspace())
        assert revisions == ["origin/epic-EPIC-42", "origin/epic-CHILD-1"]

    def test_immutable_sha_takes_precedence(self) -> None:
        """When immutable SHA is present, it takes precedence over branches."""
        issue = Issue(
            id="EPIC-42",
            identifier="EPIC-42",
            title="Epic with SHA",
            description="Description",
            work_branch=None,
            issue_type="epic",
        )
        issue.source_sha = "abc123def456abc123def456abc123def456abc1"

        candidates = build_revision_candidate_list(issue, "proj-1")

        assert list(candidates.iter_for_workspace()) == [
            "abc123def456abc123def456abc123def456abc1"
        ]
        assert candidates.immutable_shas_available is True

    def test_immutable_sha_prevents_branch_fallback(self) -> None:
        """When immutable SHA is present, branches are skipped in workspace iteration."""
        issue = Issue(
            id="EPIC-42",
            identifier="EPIC-42",
            title="Epic with SHA and branch",
            description="Description",
            work_branch="custom-branch",
            issue_type="epic",
        )
        issue.source_sha = "abc123def456abc123def456abc123def456abc1"

        candidates = build_revision_candidate_list(issue, "proj-1")

        revisions = list(candidates.iter_for_workspace())
        assert revisions == ["abc123def456abc123def456abc123def456abc1"]

    def test_explicit_work_branch_takes_precedence_over_epic_branch(self) -> None:
        """Explicit work_branch should be tried first, with epic branch as fallback."""
        issue = Issue(
            id="EPIC-42",
            identifier="EPIC-42",
            title="Epic with explicit branch",
            description="Description",
            work_branch="custom-epic-work",
            issue_type="epic",
        )

        candidates = build_revision_candidate_list(issue, "proj-1")

        revisions = list(candidates.iter_for_workspace())
        assert revisions == [
            "origin/custom-epic-work",
            "origin/epic-EPIC-42",
        ]

    def test_non_epic_task_does_not_get_epic_branches(self) -> None:
        """Regular tasks should not try to resolve epic branches."""
        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Regular task",
            description="Description",
            issue_type="task",
        )

        candidates = build_revision_candidate_list(issue, "proj-1")

        revisions = list(candidates.iter_for_workspace())
        assert all(not rev.endswith("epic-TASK-1") for rev in revisions)

    def test_default_branch_not_added_without_permission(self) -> None:
        """Default branch fallback should only be added when allowed by audit policy."""
        issue = Issue(
            id="EPIC-42",
            identifier="EPIC-42",
            title="Epic",
            description="Description",
            issue_type="epic",
            work_branch=None,
        )

        candidates = build_revision_candidate_list(
            issue,
            "proj-1",
            target_state=TargetState.DONE,
            previous_state="Open",
            default_branch="main",
        )

        revisions = list(candidates.iter_for_workspace())
        assert "origin/main" not in revisions

    def test_merged_default_branch_is_last_candidate(self) -> None:
        issue = Issue(
            id="EPIC-42",
            identifier="EPIC-42",
            title="Epic",
            description="Description",
            work_branch="explicit-work",
            issue_type="epic",
        )

        candidates = build_revision_candidate_list(
            issue,
            "proj-1",
            target_state=TargetState.MERGED,
            default_branch="main",
        )

        assert list(candidates.iter_for_workspace())[-1] == "origin/main"

    def test_archived_done_auto_archive_default_branch_is_last_candidate(self) -> None:
        """Aged Done auto-archive retention binds the canonical default branch."""
        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Tracker-only maintenance task",
            description="Description",
            issue_type="task",
        )

        authorized = archive_default_branch_fallback_authorized(
            "Done",
            ContributorIdentity("oompah", "auto_archive"),
        )
        assert authorized is True

        candidates = build_revision_candidate_list(
            issue,
            "proj-1",
            target_state=TargetState.ARCHIVED,
            previous_state="Done",
            default_branch="main",
            archive_default_branch_authorized=authorized,
        )

        assert list(candidates.iter_for_workspace()) == ["origin/main"]

    def test_archived_done_non_auto_archive_does_not_default_to_main(self) -> None:
        """A generic archive request cannot turn Done into landing evidence."""
        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Tracker-only maintenance task",
            description="Description",
            issue_type="task",
        )

        authorized = archive_default_branch_fallback_authorized(
            "Done",
            ContributorIdentity("operator", "api"),
        )
        assert authorized is False

        candidates = build_revision_candidate_list(
            issue,
            "proj-1",
            target_state=TargetState.ARCHIVED,
            previous_state="Done",
            default_branch="main",
            archive_default_branch_authorized=authorized,
        )

        assert list(candidates.iter_for_workspace()) == []

    @pytest.mark.parametrize(
        "source",
        ["github_intake", "release_pick_migration", "stalled_task_watchdog"],
    )
    def test_archived_open_automated_dispositions_do_not_default_to_main(
        self,
        source: str,
    ) -> None:
        """External or supersession archive triggers cannot retire abandoned work."""
        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Unintegrated task",
            description="Description",
            issue_type="task",
        )

        authorized = archive_default_branch_fallback_authorized(
            "Open",
            ContributorIdentity("oompah", source),
        )
        assert authorized is False

        candidates = build_revision_candidate_list(
            issue,
            "proj-1",
            target_state=TargetState.ARCHIVED,
            previous_state="Open",
            default_branch="main",
            archive_default_branch_authorized=authorized,
        )

        assert list(candidates.iter_for_workspace()) == []

    def test_archived_merged_default_branch_remains_last_candidate(self) -> None:
        """Already-merged retention retains the established default fallback."""
        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Merged task",
            description="Description",
            issue_type="task",
        )

        candidates = build_revision_candidate_list(
            issue,
            "proj-1",
            target_state=TargetState.ARCHIVED,
            previous_state="Merged",
            default_branch="main",
        )

        assert list(candidates.iter_for_workspace()) == ["origin/main"]

    def test_invalid_recorded_immutable_revision_fails_closed(self) -> None:
        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Task",
            description="Description",
            work_branch="mutable-fallback",
        )
        issue.source_sha = "abbreviated"

        with pytest.raises(ValueError, match="full Git object ID"):
            build_revision_candidate_list(issue, "proj-1")

    def test_integration_record_provides_immutable_sha(self) -> None:
        """Integration record integrated_sha provides immutable precedence."""
        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Task",
            description="Description",
        )
        issue.integration = Mock(
            integrated_sha="abc1abc1abc1abc1abc1abc1abc1abc1abc1abc1",
            head_sha="def2def2def2def2def2def2def2def2def2def2",
            base_branch="main",
            base_sha="aaa2aaa2aaa2aaa2aaa2aaa2aaa2aaa2aaa2aaa2",
            task_branch="my-task",
            state="integrated",
        )

        candidates = build_revision_candidate_list(issue, "proj-1")

        assert list(candidates.iter_for_workspace()) == [
            "abc1abc1abc1abc1abc1abc1abc1abc1abc1abc1"
        ]

    def test_integrated_record_without_integrated_sha_fails_closed(self) -> None:
        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Task",
            work_branch="mutable-fallback",
            integration=Mock(state="integrated", integrated_sha=None),
        )

        with pytest.raises(ValueError, match="missing its immutable revision"):
            build_revision_candidate_list(issue, "proj-1")
