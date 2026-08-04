"""Tests for ArchivedEvidenceCollector."""

import pytest

from oompah.archived_evidence_collector import (
    ArchivedEvidenceCollector,
    ArchivedEvidenceSnapshot,
    DispositionReason,
    DispositionType,
    EvidenceInvalid,
    EvidenceUnavailable,
    RestorationGuidance,
    SafetyFailureMode,
    TaskStateSnapshot,
    AuditReferenceEvidence,
    metadata_archive_disposition,
    revisionless_metadata_archive_candidate,
)
from oompah.models import Issue
from oompah.terminal_audit import EvidenceFingerprint, TargetState


class TestDispositionType:
    """Tests for DispositionType enum."""

    def test_disposition_from_raw_string(self) -> None:
        assert DispositionType.from_raw("retention") == DispositionType.RETENTION
        assert DispositionType.from_raw("duplicate") == DispositionType.DUPLICATE
        assert DispositionType.from_raw("obsolete") == DispositionType.OBSOLETE

    def test_disposition_from_raw_enum(self) -> None:
        dt = DispositionType.RETENTION
        assert DispositionType.from_raw(dt) == dt

    def test_disposition_case_insensitive(self) -> None:
        assert DispositionType.from_raw("RETENTION") == DispositionType.RETENTION
        assert DispositionType.from_raw("Duplicate") == DispositionType.DUPLICATE

    def test_disposition_underscore_and_dash(self) -> None:
        assert DispositionType.from_raw("retention") == DispositionType.RETENTION
        # Also test with spaces converted to underscores
        dt = DispositionType.from_raw("retention")
        assert dt.value == "retention"

    def test_disposition_invalid(self) -> None:
        with pytest.raises(ValueError):
            DispositionType.from_raw("invalid_type")

    def test_disposition_empty_string(self) -> None:
        with pytest.raises(ValueError):
            DispositionType.from_raw("")


class TestRevisionlessMetadataArchiveClassification:
    """Regression coverage for the OOMPAH-803 metadata-only retirement."""

    def test_backlog_duplicate_ignores_derived_identifier_branch(self) -> None:
        issue = Issue(
            id="OOMPAH-803",
            identifier="OOMPAH-803",
            title="Duplicate",
            state="In Validation",
            branch_name="OOMPAH-803",
        )

        assert revisionless_metadata_archive_candidate(
            issue,
            target_state=TargetState.ARCHIVED,
            previous_state="Backlog",
        )

    def test_code_bearing_archive_keeps_immutable_revision_path(self) -> None:
        issue = Issue(
            id="OOMPAH-803",
            identifier="OOMPAH-803",
            title="Implemented",
            work_branch="OOMPAH-803",
        )

        assert not revisionless_metadata_archive_candidate(
            issue,
            target_state=TargetState.ARCHIVED,
            previous_state="Backlog",
        )

    def test_oompah_803_reason_and_replacement_are_extracted(self) -> None:
        disposition, explanation, source = metadata_archive_disposition(
            "Triggered by: OOMPAH-775\n\nMigrate all transition writers.",
            [
                {
                    "text": (
                        "Archiving as an exact duplicate of the earlier, more "
                        "actionable OOMPAH-775."
                    )
                }
            ],
        )

        assert disposition is DispositionType.DUPLICATE
        assert "exact duplicate" in explanation
        assert source == "OOMPAH-775"

    def test_source_without_disposition_reason_remains_actionably_missing(self) -> None:
        disposition, explanation, source = metadata_archive_disposition(
            "Triggered by: OOMPAH-775\n\nDuplicate requirements.",
            [],
        )

        assert disposition is None
        assert explanation == ""
        assert source == "OOMPAH-775"


class TestDispositionReason:
    """Tests for DispositionReason data structure."""

    def test_valid_retention_reason(self) -> None:
        reason = DispositionReason(
            type=DispositionType.RETENTION,
            explanation="Completed and archived per retention policy",
        )
        assert reason.type == DispositionType.RETENTION
        assert reason.requires_source_link() is False

    def test_duplicate_without_source_link(self) -> None:
        reason = DispositionReason(
            type=DispositionType.DUPLICATE,
            explanation="Duplicate of existing task",
        )
        assert reason.requires_source_link() is True
        assert reason.source_link is None

    def test_duplicate_with_source_link(self) -> None:
        reason = DispositionReason(
            type=DispositionType.DUPLICATE,
            explanation="Duplicate of existing task",
            source_link="https://github.com/repo/issues/123",
        )
        assert reason.requires_source_link() is True
        assert reason.source_link == "https://github.com/repo/issues/123"

    def test_obsolete_requires_source(self) -> None:
        reason = DispositionReason(
            type=DispositionType.OBSOLETE,
            explanation="No longer needed",
            source_link="https://github.com/repo/issues/456",
        )
        assert reason.requires_source_link() is True

    def test_superseded_requires_source(self) -> None:
        reason = DispositionReason(
            type=DispositionType.SUPERSEDED,
            explanation="Replaced by newer work",
            source_link="https://github.com/repo/pull/789",
        )
        assert reason.requires_source_link() is True

    def test_reason_requires_nonempty_explanation(self) -> None:
        with pytest.raises(ValueError):
            DispositionReason(
                type=DispositionType.RETENTION,
                explanation="",
            )

    def test_reason_requires_valid_type(self) -> None:
        with pytest.raises(TypeError):
            DispositionReason(
                type="invalid",  # type: ignore
                explanation="test",
            )


class TestTaskStateSnapshot:
    """Tests for TaskStateSnapshot."""

    def test_valid_task_state(self) -> None:
        state = TaskStateSnapshot(
            task_id="TASK-123",
            current_state="Done",
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
        )
        assert state.task_id == "TASK-123"
        assert state.current_state == "Done"
        assert state.has_active_worker is False

    def test_task_state_with_unavailable(self) -> None:
        state = TaskStateSnapshot(
            task_id="TASK-123",
            current_state="Done",
            has_active_worker=EvidenceUnavailable("Cannot determine"),
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
        )
        assert isinstance(state.has_active_worker, EvidenceUnavailable)

    def test_task_state_requires_nonempty_id(self) -> None:
        with pytest.raises(ValueError):
            TaskStateSnapshot(
                task_id="",
                current_state="Done",
                has_active_worker=False,
                has_open_review=False,
                has_active_child=False,
                has_unresolved_dependency=False,
            )


class TestAuditReferenceEvidence:
    """Tests for AuditReferenceEvidence."""

    def test_valid_done_audit_reference(self) -> None:
        fp = EvidenceFingerprint(
            digest="a" * 64,
            algorithm="sha256",
        )
        ref = AuditReferenceEvidence(
            audit_id="audit-123",
            audit_type="Done",
            verdict="pass",
            fingerprint=fp,
        )
        assert ref.audit_id == "audit-123"
        assert ref.audit_type == "Done"

    def test_valid_merged_audit_reference(self) -> None:
        fp = EvidenceFingerprint(
            digest="b" * 64,
            algorithm="sha256",
        )
        ref = AuditReferenceEvidence(
            audit_id="audit-456",
            audit_type="Merged",
            verdict="passed",
            fingerprint=fp,
        )
        assert ref.audit_type == "Merged"

    def test_audit_with_unavailable_verdict(self) -> None:
        ref = AuditReferenceEvidence(
            audit_id="audit-123",
            audit_type="Done",
            verdict=EvidenceUnavailable("Verdict not recorded"),
            fingerprint=EvidenceUnavailable("Fingerprint not available"),
        )
        assert isinstance(ref.verdict, EvidenceUnavailable)

    def test_audit_requires_valid_type(self) -> None:
        with pytest.raises(ValueError):
            AuditReferenceEvidence(
                audit_id="audit-123",
                audit_type="Invalid",  # type: ignore
                verdict="pass",
                fingerprint=EvidenceFingerprint(digest="a" * 64),
            )

    def test_audit_requires_nonempty_id(self) -> None:
        with pytest.raises(ValueError):
            AuditReferenceEvidence(
                audit_id="",
                audit_type="Done",
                verdict="pass",
                fingerprint=EvidenceFingerprint(digest="a" * 64),
            )


class TestArchivedEvidenceSnapshot:
    """Tests for ArchivedEvidenceSnapshot data structure."""

    def test_snapshot_safe_archival(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        task_state = TaskStateSnapshot(
            task_id="TASK-123",
            current_state="Done",
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
        )
        disposition = DispositionReason(
            type=DispositionType.RETENTION,
            explanation="Archived per retention policy",
        )
        prior_audit = AuditReferenceEvidence(
            audit_id="audit-123",
            audit_type="Done",
            verdict="pass",
            fingerprint=fp,
        )

        snapshot = ArchivedEvidenceSnapshot(
            task_state=task_state,
            prior_audit=prior_audit,
            disposition=disposition,
            failure_modes=[],
            restoration_guidance=None,
            task_id="TASK-123",
            project_id="proj-1",
            audit_id="archive-123",
            collected_at="2026-07-29T00:00:00Z",
        )

        assert snapshot.passed() is True
        assert snapshot.has_failures() is False

    def test_snapshot_with_failure_modes(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        task_state = TaskStateSnapshot(
            task_id="TASK-123",
            current_state="Done",
            has_active_worker=True,  # FAILURE
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
        )
        disposition = DispositionReason(
            type=DispositionType.RETENTION,
            explanation="Archived per retention policy",
        )
        prior_audit = AuditReferenceEvidence(
            audit_id="audit-123",
            audit_type="Done",
            verdict="pass",
            fingerprint=fp,
        )

        snapshot = ArchivedEvidenceSnapshot(
            task_state=task_state,
            prior_audit=prior_audit,
            disposition=disposition,
            failure_modes=[SafetyFailureMode.ACTIVE_WORKER.value],
            restoration_guidance=RestorationGuidance(
                restored_state="Done",
                required_actions=["Unassign active worker before archiving"],
                unsafe_condition="Task has active assigned worker",
            ),
        )

        assert snapshot.passed() is False
        assert snapshot.has_failures() is True

    def test_snapshot_with_unavailable_state(self) -> None:
        snapshot = ArchivedEvidenceSnapshot(
            task_state=EvidenceUnavailable("Cannot determine task state"),
            prior_audit=EvidenceUnavailable("No prior audit"),
            disposition=EvidenceUnavailable("No disposition reason"),
            failure_modes=[],
        )

        assert snapshot.passed() is False
        assert snapshot.has_failures() is True

    def test_snapshot_failed_prior_audit(self) -> None:
        task_state = TaskStateSnapshot(
            task_id="TASK-123",
            current_state="Done",
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
        )
        prior_audit = AuditReferenceEvidence(
            audit_id="audit-123",
            audit_type="Done",
            verdict="fail",  # FAILURE
            fingerprint=EvidenceFingerprint(digest="a" * 64),
        )

        snapshot = ArchivedEvidenceSnapshot(
            task_state=task_state,
            prior_audit=prior_audit,
            disposition=DispositionReason(
                type=DispositionType.RETENTION,
                explanation="Test",
            ),
            failure_modes=[],
        )

        assert snapshot.passed() is False


class TestArchivedEvidenceCollector:
    """Tests for ArchivedEvidenceCollector."""

    def test_collector_initialization(self) -> None:
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )
        assert collector.task_id == "TASK-123"
        assert collector.project_id == "proj-1"

    def test_safe_retention_qualified_done(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Completed and retained per policy",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
            current_fingerprint=fp,
        )

        assert snapshot.passed() is True
        assert len(snapshot.failure_modes) == 0

    def test_safe_retention_qualified_merged(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Merged",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Merged and retained per policy",
            prior_merged_audit_id="audit-456",
            prior_merged_verdict="pass",
            prior_merged_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=60,
            retention_days_required=30,
        )

        assert snapshot.passed() is True
        assert isinstance(snapshot.prior_audit, AuditReferenceEvidence)
        assert snapshot.prior_audit.audit_type == "Merged"

    def test_recent_item_not_retention_qualified(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Too soon",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=10,  # Less than retention period
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.RECENT_COMPLETION.value in snapshot.failure_modes

    def test_active_worker_blocks_archive(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=True,  # BLOCKS
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.ACTIVE_WORKER.value in snapshot.failure_modes
        assert snapshot.restoration_guidance is not None
        assert "Unassign active worker" in snapshot.restoration_guidance.required_actions[0]

    def test_active_retry_blocks_archive(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            has_active_retry=True,  # BLOCKS
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.ACTIVE_RETRY.value in snapshot.failure_modes

    def test_open_review_blocks_archive(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=True,  # BLOCKS
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.OPEN_REVIEW.value in snapshot.failure_modes

    def test_active_child_blocks_archive(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=True,  # BLOCKS
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.ACTIVE_CHILD.value in snapshot.failure_modes

    def test_unresolved_dependency_blocks_archive(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=True,  # BLOCKS
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.UNRESOLVED_DEPENDENCY.value in snapshot.failure_modes

    def test_changed_requirements_detected(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            requirement_changed_after_prior_audit=True,  # DETECTED
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.REQUIREMENT_CHANGED.value in snapshot.failure_modes

    def test_changed_sha_detected(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            sha_changed_after_prior_audit=True,  # DETECTED
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.SHA_CHANGED.value in snapshot.failure_modes

    def test_duplicate_requires_source_link(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.DUPLICATE,
            disposition_explanation="Duplicate of TASK-456",
            disposition_source_link=None,  # MISSING
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.DUPLICATE_NO_SOURCE.value in snapshot.failure_modes
        assert isinstance(snapshot.disposition, EvidenceInvalid)

    def test_duplicate_with_source_link_valid(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.DUPLICATE,
            disposition_explanation="Duplicate of TASK-456",
            disposition_source_link="https://github.com/repo/issues/456",  # PROVIDED
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is True
        assert isinstance(snapshot.disposition, DispositionReason)
        assert snapshot.disposition.source_link == "https://github.com/repo/issues/456"

    def test_obsolete_requires_source_link(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.OBSOLETE,
            disposition_explanation="No longer needed",
            disposition_source_link=None,  # MISSING
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.OBSOLETE_NO_SOURCE.value in snapshot.failure_modes

    def test_superseded_requires_source_link(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.SUPERSEDED,
            disposition_explanation="Replaced by newer work",
            disposition_source_link=None,  # MISSING
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.SUPERSEDED_NO_SOURCE.value in snapshot.failure_modes

    def test_no_disposition_reason_blocks_archive(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=None,  # MISSING
            disposition_explanation="",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.NO_DISPOSITION_REASON.value in snapshot.failure_modes

    def test_no_prior_audit_blocks_archive(self) -> None:
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="",  # MISSING
            prior_done_verdict="",
            prior_done_fingerprint=None,
            prior_merged_audit_id="",  # MISSING
            prior_merged_verdict="",
            prior_merged_fingerprint=None,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.NO_DONE_AUDIT.value in snapshot.failure_modes

    def test_restoration_guidance_for_active_worker(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=True,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.restoration_guidance is not None
        assert snapshot.restoration_guidance.restored_state == "Done"
        assert "Unassign" in snapshot.restoration_guidance.required_actions[0]
        assert "active" in snapshot.restoration_guidance.unsafe_condition
        assert "worker" in snapshot.restoration_guidance.unsafe_condition

    def test_restoration_guidance_for_recent_completion(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=5,  # TOO SOON
            retention_days_required=30,
        )

        assert snapshot.restoration_guidance is not None
        assert "Wait for retention period" in snapshot.restoration_guidance.required_actions[0]

    def test_multiple_failure_modes_restoration(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_worker=True,  # FAILURE 1
            has_open_review=True,  # FAILURE 2
            has_active_child=False,
            has_unresolved_dependency=True,  # FAILURE 3
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert len(snapshot.failure_modes) >= 3
        assert snapshot.restoration_guidance is not None
        assert len(snapshot.restoration_guidance.required_actions) >= 3

    def test_fingerprint_mismatch_detected(self) -> None:
        fp1 = EvidenceFingerprint(digest="a" * 64)
        fp2 = EvidenceFingerprint(digest="b" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp1,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
            current_fingerprint=fp2,  # MISMATCH
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.FINGERPRINT_MISMATCH.value in snapshot.failure_modes

    def test_failed_prior_audit_blocks_archive(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(
            task_id="TASK-123",
            project_id="proj-1",
        )

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Test",
            prior_done_audit_id="audit-123",
            prior_done_verdict="fail",  # FAILED
            prior_done_fingerprint=fp,
            has_active_worker=False,
            has_open_review=False,
            has_active_child=False,
            has_unresolved_dependency=False,
            days_since_completion=31,
            retention_days_required=30,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.DONE_AUDIT_FAILED.value in snapshot.failure_modes

    def test_direct_duplicate_uses_source_evidence_without_completion_audit(self) -> None:
        """A duplicate is safe only from structured source evidence, not a fake audit."""
        collector = ArchivedEvidenceCollector(task_id="TASK-123", project_id="proj-1")

        snapshot = collector.collect(
            current_state="Open",
            disposition_type=DispositionType.DUPLICATE,
            disposition_explanation="Duplicate of the canonical task",
            disposition_source_link="OOMPAH-456",
            days_since_completion=0,
            retention_days_required=30,
        )

        assert snapshot.passed() is True
        assert snapshot.prior_audit is None
        assert snapshot.pre_archive_state == "Open"

    def test_direct_obsolete_does_not_require_retention_age(self) -> None:
        collector = ArchivedEvidenceCollector(task_id="TASK-123", project_id="proj-1")

        snapshot = collector.collect(
            current_state="Backlog",
            disposition_type=DispositionType.OBSOLETE,
            disposition_explanation="The requested work is no longer needed",
            disposition_source_link="https://example.test/replacement",
            days_since_completion=0,
            retention_days_required=30,
        )

        assert snapshot.passed() is True
        assert SafetyFailureMode.RECENT_COMPLETION.value not in snapshot.failure_modes

    def test_active_claim_and_retry_are_recorded_in_snapshot(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(task_id="TASK-123", project_id="proj-1")

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Retained per policy",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_claim=True,
            has_active_retry=True,
            days_since_completion=31,
        )

        assert snapshot.passed() is False
        assert isinstance(snapshot.task_state, TaskStateSnapshot)
        assert snapshot.task_state.has_active_claim is True
        assert snapshot.task_state.has_active_retry is True
        assert SafetyFailureMode.ACTIVE_CLAIM.value in snapshot.failure_modes
        assert SafetyFailureMode.ACTIVE_RETRY.value in snapshot.failure_modes

    def test_unavailable_claim_evidence_fails_closed(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(task_id="TASK-123", project_id="proj-1")

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Retained per policy",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            has_active_claim=EvidenceUnavailable("claim store unavailable"),
            days_since_completion=31,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.MISSING_EVIDENCE.value in snapshot.failure_modes

    def test_retention_requires_done_or_merged_pre_archive_state(self) -> None:
        fp = EvidenceFingerprint(digest="a" * 64)
        collector = ArchivedEvidenceCollector(task_id="TASK-123", project_id="proj-1")

        snapshot = collector.collect(
            current_state="Open",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Retained per policy",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            prior_done_fingerprint=fp,
            days_since_completion=31,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.INVALID_PRE_ARCHIVE_STATE.value in snapshot.failure_modes
        assert snapshot.restoration_guidance is not None
        assert snapshot.restoration_guidance.restored_state == "Open"

    def test_missing_audit_fingerprint_is_unsafe(self) -> None:
        collector = ArchivedEvidenceCollector(task_id="TASK-123", project_id="proj-1")

        snapshot = collector.collect(
            current_state="Done",
            disposition_type=DispositionType.RETENTION,
            disposition_explanation="Retained per policy",
            prior_done_audit_id="audit-123",
            prior_done_verdict="pass",
            days_since_completion=31,
        )

        assert snapshot.passed() is False
        assert SafetyFailureMode.DONE_AUDIT_FAILED.value in snapshot.failure_modes
        assert SafetyFailureMode.MISSING_EVIDENCE.value in snapshot.failure_modes
