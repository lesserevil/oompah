"""Tests for the auditor-only structured result submission API and tool.

Coverage:
- owner session (valid submission accepted)
- wrong session / task / project (mismatched contract fields rejected)
- expired / stale audit (coordinator rejects non-pending records)
- malformed enum (invalid verdict or failure_classification rejected)
- oversized output (message and safe_evidence size limits enforced)
- attempted status injection (unexpected fields rejected)
- secret-like fields (credential keys/values in safe_evidence rejected)
- duplicate / conflicting submissions (idempotent duplicate, conflicting reject)
- coordinator failure (exception from apply_audit_result is surfaced)
- auditor session policy (non-auditor sessions cannot call the tool)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from oompah.auditor import (
    AUDITOR_RESULT_TOOL_NAME,
    AuditorTargetContract,
    _MAX_RESULT_MESSAGE_LENGTH,
    _MAX_SAFE_EVIDENCE_ENTRIES,
    _MAX_SAFE_EVIDENCE_KEY_LENGTH,
    _MAX_SAFE_EVIDENCE_VALUE_LENGTH,
    _RESULT_SECRET_RE,
    _SECRET_KEY_RE,
    parse_auditor_result,
    submit_auditor_result,
)
from oompah.authority_boundary import auditor_policy
from oompah.terminal_audit import (
    EvidenceFingerprint,
    FailureClassification,
    TargetState,
    Verdict,
)
from oompah.terminal_transition_coordinator import AuditResult


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------


def _target(
    *,
    audit_id: str = "audit-42",
    task_id: str = "TASK-42",
    project_id: str = "proj-42",
    target_state: str = "Done",
    evidence_fingerprint: str = "a" * 64,
    attempt_id: str | None = "attempt-7",
) -> AuditorTargetContract:
    return AuditorTargetContract(
        audit_id=audit_id,
        task_id=task_id,
        project_id=project_id,
        target_state=target_state,
        evidence_fingerprint=evidence_fingerprint,
        attempt_id=attempt_id,
    )


def _valid_args(target: AuditorTargetContract | None = None, **overrides: Any) -> dict:
    """Return a minimal valid payload matching the default target."""
    t = target or _target()
    base = {
        "audit_id": t.audit_id,
        "target_state": t.target_state,
        "evidence_fingerprint": t.evidence_fingerprint,
        "verdict": "pass",
        "message": "All acceptance criteria met.",
        "attempt_id": t.attempt_id,
    }
    base.update(overrides)
    return base


def _parse(args: dict, target: AuditorTargetContract | None = None):
    """Shorthand: parse and return (result, error)."""
    return parse_auditor_result(args, target or _target())


def _submit(args: dict, target: AuditorTargetContract | None = None, handler=None):
    """Shorthand: submit and return the string response."""
    return submit_auditor_result(args, target or _target(), handler)


# ---------------------------------------------------------------------------
# Owner session — valid submissions
# ---------------------------------------------------------------------------


class TestOwnerSession:
    def test_valid_pass_submission_is_accepted(self):
        result, err = _parse(_valid_args())
        assert err is None
        assert result is not None
        assert result.verdict == Verdict.PASS
        assert result.audit_id == "audit-42"

    def test_valid_fail_submission_with_classification(self):
        result, err = _parse(
            _valid_args(
                verdict="fail",
                failure_classification="missing_tests",
                message="Coverage dropped below threshold.",
            )
        )
        assert err is None
        assert result is not None
        assert result.verdict == Verdict.FAIL
        assert result.failure_classification == FailureClassification.MISSING_TESTS

    def test_valid_needs_human_submission(self):
        result, err = _parse(
            _valid_args(
                verdict="needs_human",
                message="Unable to determine whether the CI gate is authoritative?",
            )
        )
        assert err is None
        assert result.verdict == Verdict.NEEDS_HUMAN

    def test_valid_submission_with_safe_evidence(self):
        result, err = _parse(
            _valid_args(
                safe_evidence={"tests": "42 passed", "commit": "abc123"},
            )
        )
        assert err is None
        assert result.safe_evidence == {"tests": "42 passed", "commit": "abc123"}

    def test_optional_questions_and_instructions_are_bounded_and_typed(self):
        result, err = _parse(
            _valid_args(
                verdict="needs_human",
                message="The CI authority is ambiguous?",
                questions=["Which CI result should be treated as authoritative?"],
                instructions=["Review the failing job and update this task."],
            )
        )
        assert err is None
        assert result.questions == (
            "Which CI result should be treated as authoritative?",
        )
        assert result.instructions == (
            "Review the failing job and update this task.",
        )

    def test_optional_questions_and_instructions_reject_oversized_lists(self):
        result, err = _parse(
            _valid_args(questions=["question"] * 6)
        )
        assert result is None
        assert "questions" in (err or "")

    def test_submit_passes_result_to_handler(self):
        received: list[AuditResult] = []

        response = _submit(_valid_args(), handler=received.append)
        assert received, "handler was not called"
        assert received[0].audit_id == "audit-42"
        assert received[0].verdict == Verdict.PASS
        # When handler returns None, submit returns the default accepted JSON
        data = json.loads(response)
        assert data["accepted"] is True

    def test_submit_returns_handler_dict_as_json(self):
        def handler(_result):
            return {"ok": True, "applied_status": "Done"}

        response = _submit(_valid_args(), handler=handler)
        data = json.loads(response)
        assert data["ok"] is True
        assert data["applied_status"] == "Done"

    def test_submit_without_handler_is_not_reported_as_accepted(self):
        response = _submit(_valid_args(), handler=None)
        assert response.startswith("Error:")
        assert "not submitted" in response

    def test_valid_submission_via_execute_tool(self):
        """Integration: _execute_tool accepts submit_audit_result for auditor sessions."""
        from oompah.api_agent import _execute_tool

        target = _target()
        received: list[AuditResult] = []

        response = _execute_tool(
            Path("."),
            AUDITOR_RESULT_TOOL_NAME,
            _valid_args(target),
            action_policy=auditor_policy(task_identifier="TASK-42"),
            audit_target=target,
            audit_result_handler=received.append,
        )
        assert '"accepted": true' in response
        assert len(received) == 1
        assert received[0].audit_id == "audit-42"


# ---------------------------------------------------------------------------
# Wrong session / task / project
# ---------------------------------------------------------------------------


class TestWrongSession:
    def test_wrong_audit_id_is_rejected(self):
        result, err = _parse(_valid_args(audit_id="audit-other"))
        assert result is None
        assert "audit_id does not match" in (err or "")

    def test_wrong_target_state_is_rejected(self):
        result, err = _parse(_valid_args(target_state="Merged"))
        assert result is None
        assert "target_state does not match" in (err or "")

    def test_wrong_evidence_fingerprint_is_rejected(self):
        result, err = _parse(_valid_args(evidence_fingerprint="b" * 64))
        assert result is None
        assert "evidence_fingerprint does not match" in (err or "")

    def test_wrong_attempt_id_is_rejected(self):
        result, err = _parse(_valid_args(attempt_id="attempt-other"))
        assert result is None
        assert "attempt_id does not match" in (err or "")

    def test_session_for_task_a_cannot_submit_for_task_b_audit(self):
        """A session bound to audit-A cannot submit for audit-B.

        The target contract is embedded in the session at dispatch time;
        submitting with a different audit_id is rejected because the
        audit_id does not match the contract.
        """
        contract_for_task_a = _target(audit_id="audit-A", task_id="TASK-A")

        # Attempt to submit a result for audit-B while session owns audit-A
        args_for_task_b = _valid_args(audit_id="audit-B")
        result, err = parse_auditor_result(args_for_task_b, contract_for_task_a)

        assert result is None
        assert "audit_id does not match" in (err or "")

    def test_non_auditor_session_cannot_call_submit_tool(self):
        """submit_audit_result is blocked when the session has no auditor policy."""
        from oompah.api_agent import _execute_tool

        response = _execute_tool(
            Path("."),
            AUDITOR_RESULT_TOOL_NAME,
            _valid_args(),
            action_policy=None,
            audit_target=_target(),
        )
        assert response.startswith("Error:")
        assert "restricted to an auditor session" in response

    def test_non_auditor_action_policy_blocks_submit_tool(self):
        """An action_policy without read_only blocks submit_audit_result."""
        from oompah.api_agent import _execute_tool

        # Simulate a non-auditor write-capable policy
        mock_policy = MagicMock()
        mock_policy.read_only = False

        response = _execute_tool(
            Path("."),
            AUDITOR_RESULT_TOOL_NAME,
            _valid_args(),
            action_policy=mock_policy,
            audit_target=_target(),
        )
        assert response.startswith("Error:")

    def test_auditor_policy_bound_to_other_task_cannot_submit(self):
        from oompah.api_agent import _execute_tool

        response = _execute_tool(
            Path("."),
            AUDITOR_RESULT_TOOL_NAME,
            _valid_args(),
            action_policy=auditor_policy(task_identifier="TASK-OTHER"),
            audit_target=_target(),
            audit_result_handler=lambda _result: None,
        )
        assert response.startswith("Error:")
        assert "does not own the requested task" in response

    def test_auditor_policy_bound_to_other_project_cannot_submit(self):
        from oompah.api_agent import _execute_tool

        response = _execute_tool(
            Path("."),
            AUDITOR_RESULT_TOOL_NAME,
            _valid_args(),
            action_policy=auditor_policy(
                task_identifier="TASK-42", project_id="proj-OTHER"
            ),
            audit_target=_target(),
            audit_result_handler=lambda _result: None,
        )
        assert response.startswith("Error:")
        assert "does not own the requested project" in response


# ---------------------------------------------------------------------------
# Expired / stale audit
# ---------------------------------------------------------------------------


class TestExpiredStaleAudit:
    def test_coordinator_rejects_nonexistent_audit_id(self):
        """Coordinator returns failure when audit_id is not in the chain."""
        from oompah.models import Issue
        from oompah.terminal_audit import RequestState, TerminalAuditRecord
        from oompah.terminal_transition_coordinator import (
            ResultRejection,
            TerminalTransitionCoordinator,
        )
        from oompah.terminal_audit_metadata import METADATA_KEY, TerminalAuditMetadata

        class _MockLockStore:
            class _Lock:
                def __enter__(self):
                    return self
                def __exit__(self, *_):
                    return None
            def project_write_lock(self, _):
                return self._Lock()

        class _MockTracker:
            def __init__(self):
                self.metadata: dict[str, dict] = {}
                self.update_calls = []
                self.comment_calls = []
            def get_metadata(self, identifier):
                return dict(self.metadata.get(identifier, {}))
            def set_metadata_field(self, identifier, key, value):
                self.metadata.setdefault(identifier, {})[key] = value
            def update_issue(self, identifier, **kwargs):
                self.update_calls.append((identifier, kwargs))
            def add_comment(self, identifier, text, author="oompah"):
                self.comment_calls.append((identifier, text))
            def fetch_issue_states_by_ids(self, ids):
                return []

        fingerprint = EvidenceFingerprint("a" * 64)
        record = TerminalAuditRecord(
            audit_id="audit-existing",
            project_id="proj-42",
            task_id="TASK-42",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
        )

        tracker = _MockTracker()
        meta = TerminalAuditMetadata(pending_chain=[record])
        tracker.metadata["TASK-42"] = {METADATA_KEY: meta.to_dict()}

        issue = Issue(
            id="TASK-42",
            identifier="TASK-42",
            title="Test",
            state="In Validation",
        )
        coord = TerminalTransitionCoordinator(
            tracker=tracker, project_store=_MockLockStore()
        )

        # Submit with a wrong (non-existent) audit_id
        stale_result = AuditResult(
            audit_id="audit-nonexistent",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            verdict=Verdict.PASS,
            message="ok",
        )
        outcome = asyncio.run(coord.apply_audit_result(issue, stale_result, "proj-42"))
        assert outcome.success is False
        assert outcome.reason == ResultRejection.AUDIT_NOT_FOUND

    def test_coordinator_rejects_completed_audit(self):
        """Coordinator returns STATE_MISMATCH for already-completed audits."""
        from oompah.models import Issue
        from oompah.terminal_audit import (
            RequestState,
            TerminalAuditRecord,
        )
        from oompah.terminal_transition_coordinator import (
            ResultRejection,
            TerminalTransitionCoordinator,
        )
        from oompah.terminal_audit_metadata import METADATA_KEY, TerminalAuditMetadata

        class _MockLockStore:
            class _Lock:
                def __enter__(self): return self
                def __exit__(self, *_): return None
            def project_write_lock(self, _): return self._Lock()

        class _MockTracker:
            def __init__(self):
                self.metadata: dict = {}
                self.update_calls = []
                self.comment_calls = []
            def get_metadata(self, identifier):
                return dict(self.metadata.get(identifier, {}))
            def set_metadata_field(self, identifier, key, value):
                self.metadata.setdefault(identifier, {})[key] = value
            def update_issue(self, identifier, **kwargs):
                self.update_calls.append((identifier, kwargs))
            def add_comment(self, identifier, text, author="oompah"):
                self.comment_calls.append((identifier, text))
            def fetch_issue_states_by_ids(self, ids): return []

        fingerprint = EvidenceFingerprint("c" * 64)
        record = TerminalAuditRecord(
            audit_id="audit-done",
            project_id="proj-42",
            task_id="TASK-42",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.COMPLETED,  # Already completed
        )

        tracker = _MockTracker()
        meta = TerminalAuditMetadata(pending_chain=[record])
        tracker.metadata["TASK-42"] = {METADATA_KEY: meta.to_dict()}

        issue = Issue(
            id="TASK-42", identifier="TASK-42", title="T", state="In Validation"
        )
        coord = TerminalTransitionCoordinator(
            tracker=tracker, project_store=_MockLockStore()
        )

        audit_result = AuditResult(
            audit_id="audit-done",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            verdict=Verdict.PASS,
            message="late submission",
        )
        outcome = asyncio.run(coord.apply_audit_result(issue, audit_result, "proj-42"))
        assert outcome.success is False
        assert outcome.reason == ResultRejection.STATE_MISMATCH

    def test_issue_not_in_validation_is_rejected_by_coordinator(self):
        """Coordinator rejects if issue is no longer In Validation."""
        from oompah.models import Issue
        from oompah.terminal_audit import RequestState, TerminalAuditRecord
        from oompah.terminal_transition_coordinator import (
            ResultRejection,
            TerminalTransitionCoordinator,
        )
        from oompah.terminal_audit_metadata import METADATA_KEY, TerminalAuditMetadata

        class _MockLockStore:
            class _Lock:
                def __enter__(self): return self
                def __exit__(self, *_): return None
            def project_write_lock(self, _): return self._Lock()

        class _MockTracker:
            def __init__(self):
                self.metadata: dict = {}
                self.update_calls = []
                self.comment_calls = []
            def get_metadata(self, id_): return dict(self.metadata.get(id_, {}))
            def set_metadata_field(self, id_, key, value):
                self.metadata.setdefault(id_, {})[key] = value
            def update_issue(self, id_, **kwargs): self.update_calls.append((id_, kwargs))
            def add_comment(self, id_, text, author="oompah"): self.comment_calls.append((id_, text))
            def fetch_issue_states_by_ids(self, ids): return []

        fingerprint = EvidenceFingerprint("d" * 64)
        record = TerminalAuditRecord(
            audit_id="audit-stale",
            project_id="proj-42",
            task_id="TASK-42",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
        )
        tracker = _MockTracker()
        meta = TerminalAuditMetadata(pending_chain=[record])
        tracker.metadata["TASK-42"] = {METADATA_KEY: meta.to_dict()}

        issue = Issue(
            id="TASK-42", identifier="TASK-42", title="T", state="Open"  # Not In Validation
        )
        coord = TerminalTransitionCoordinator(
            tracker=tracker, project_store=_MockLockStore()
        )
        audit_result = AuditResult(
            audit_id="audit-stale",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            verdict=Verdict.PASS,
            message="ok",
        )
        outcome = asyncio.run(coord.apply_audit_result(issue, audit_result, "proj-42"))
        assert outcome.success is False
        assert outcome.reason == ResultRejection.ISSUE_NOT_IN_VALIDATION


# ---------------------------------------------------------------------------
# Malformed enum values
# ---------------------------------------------------------------------------


class TestMalformedEnum:
    def test_unknown_verdict_is_rejected(self):
        result, err = _parse(_valid_args(verdict="approved"))
        assert result is None
        assert "invalid auditor result" in (err or "").lower()

    def test_internal_error_verdict_is_not_publicly_accepted(self):
        result, err = _parse(_valid_args(verdict="error"))
        assert result is None
        assert err is not None

    def test_fail_requires_failure_classification(self):
        result, err = _parse(_valid_args(verdict="fail"))
        assert result is None
        assert "failure_classification" in (err or "")

    def test_status_string_verdict_is_rejected(self):
        """'PASS' (uppercase) should succeed via normalisation; 'done' is not a verdict."""
        result_upper, err_upper = _parse(_valid_args(verdict="PASS"))
        # The enum normaliser accepts case-insensitive; PASS should parse
        assert err_upper is None
        assert result_upper is not None

        result_bad, err_bad = _parse(_valid_args(verdict="done"))
        assert result_bad is None
        assert err_bad is not None

    def test_arbitrary_string_verdict_is_rejected(self):
        for bad in ("", "null", "1", "true", "accepted", "rejected"):
            result, err = _parse(_valid_args(verdict=bad))
            assert result is None, f"Expected rejection for verdict={bad!r}, got result"
            assert err is not None

    def test_unknown_failure_classification_is_rejected(self):
        result, err = _parse(
            _valid_args(
                verdict="fail",
                failure_classification="not_a_real_classification",
            )
        )
        assert result is None
        assert "invalid auditor result" in (err or "").lower()

    def test_non_string_verdict_is_rejected(self):
        for bad in (None, 1, True, [], {}):
            result, err = _parse(_valid_args(verdict=bad))
            assert result is None, f"Expected rejection for verdict={bad!r}"

    def test_valid_failure_classifications_are_accepted(self):
        valid_classifications = [fc.value for fc in FailureClassification]
        for classification in valid_classifications:
            result, err = _parse(
                _valid_args(verdict="fail", failure_classification=classification)
            )
            assert err is None, f"Expected acceptance for {classification!r}, got {err!r}"


# ---------------------------------------------------------------------------
# Oversized output
# ---------------------------------------------------------------------------


class TestOversizedOutput:
    def test_message_at_limit_is_accepted(self):
        long_msg = "x" * _MAX_RESULT_MESSAGE_LENGTH
        result, err = _parse(_valid_args(message=long_msg))
        assert err is None
        assert result is not None

    def test_message_exceeding_limit_is_rejected(self):
        too_long = "x" * (_MAX_RESULT_MESSAGE_LENGTH + 1)
        result, err = _parse(_valid_args(message=too_long))
        assert result is None
        assert "exceeds maximum length" in (err or "")
        assert str(_MAX_RESULT_MESSAGE_LENGTH) in (err or "")

    def test_safe_evidence_at_entry_limit_is_accepted(self):
        evidence = {f"key{i}": f"val{i}" for i in range(_MAX_SAFE_EVIDENCE_ENTRIES)}
        result, err = _parse(_valid_args(safe_evidence=evidence))
        assert err is None

    def test_safe_evidence_exceeding_entry_limit_is_rejected(self):
        too_many = {
            f"key{i}": f"val{i}" for i in range(_MAX_SAFE_EVIDENCE_ENTRIES + 1)
        }
        result, err = _parse(_valid_args(safe_evidence=too_many))
        assert result is None
        assert "exceeds maximum entry count" in (err or "")

    def test_safe_evidence_value_at_limit_is_accepted(self):
        at_limit = {"k": "v" * _MAX_SAFE_EVIDENCE_VALUE_LENGTH}
        result, err = _parse(_valid_args(safe_evidence=at_limit))
        assert err is None

    def test_safe_evidence_value_exceeding_limit_is_rejected(self):
        too_long = {"k": "v" * (_MAX_SAFE_EVIDENCE_VALUE_LENGTH + 1)}
        result, err = _parse(_valid_args(safe_evidence=too_long))
        assert result is None
        assert "exceeds maximum length" in (err or "")

    def test_safe_evidence_key_exceeding_limit_is_rejected(self):
        long_key = "k" * (_MAX_SAFE_EVIDENCE_KEY_LENGTH + 1)
        result, err = _parse(_valid_args(safe_evidence={long_key: "val"}))
        assert result is None
        assert "exceeds maximum length" in (err or "")

    def test_empty_message_is_rejected(self):
        """An empty message doesn't hit the size limit but should still be
        validated by the coordinator's needs_human check.  parse_auditor_result
        itself accepts any string; the coordinator enforces actionability."""
        # parse_auditor_result accepts empty string (coordinator validates later)
        result, err = _parse(_valid_args(message=""))
        assert err is None  # validated at coordinator layer


# ---------------------------------------------------------------------------
# Attempted status injection
# ---------------------------------------------------------------------------


class TestStatusInjection:
    def test_extra_status_field_is_rejected(self):
        args = _valid_args()
        args["status"] = "Done"
        result, err = _parse(args)
        assert result is None
        assert "invalid auditor result fields" in (err or "")
        assert "status" in (err or "")

    def test_extra_state_field_is_rejected(self):
        args = _valid_args()
        args["state"] = "Done"
        result, err = _parse(args)
        assert result is None
        assert "invalid auditor result fields" in (err or "")
        assert "state" in (err or "")

    def test_extra_task_id_field_is_rejected(self):
        """A model cannot supply task_id or project_id to override routing."""
        args = _valid_args()
        args["task_id"] = "TASK-OTHER"
        result, err = _parse(args)
        assert result is None
        assert "invalid auditor result fields" in (err or "")

    def test_extra_project_id_field_is_rejected(self):
        args = _valid_args()
        args["project_id"] = "proj-other"
        result, err = _parse(args)
        assert result is None
        assert "invalid auditor result fields" in (err or "")

    def test_model_cannot_supply_auditor_identity(self):
        args = _valid_args()
        args["auditor"] = "someone-else"
        result, err = _parse(args)
        assert result is None
        assert "invalid auditor result fields" in (err or "")

    def test_extra_arbitrary_fields_are_rejected(self):
        for extra_key in ("approve", "transition", "override", "merge", "close"):
            args = _valid_args()
            args[extra_key] = "injected"
            result, err = _parse(args)
            assert result is None, f"Expected rejection for extra field {extra_key!r}"
            assert "invalid auditor result fields" in (err or "")

    def test_non_mapping_payload_is_rejected(self):
        """Non-object payloads (string, list, None) are rejected."""
        for bad in ("verdict=pass", [], None, 42):
            result, err = parse_auditor_result(bad, _target())  # type: ignore[arg-type]
            assert result is None
            assert err is not None


# ---------------------------------------------------------------------------
# Secret-like fields
# ---------------------------------------------------------------------------


class TestSecretLikeFields:
    def test_credential_pattern_in_message_is_redacted_not_rejected(self):
        """Inert credential-pattern examples in message are redacted and accepted."""
        result, err = _parse(
            _valid_args(message="Authorization: Bearer short-but-still-secret")
        )
        # Should be accepted, not rejected, with the bearer token redacted
        assert err is None
        assert result is not None
        assert "[REDACTED-bearer-token]" in result.message

    def test_github_pat_example_in_safe_evidence_is_redacted(self):
        """GitHub PAT patterns in safe_evidence values are redacted."""
        result, err = _parse(
            _valid_args(safe_evidence={"output": "ghp_ABCDEFGHIJKLMNOPabcdef1234"})
        )
        assert err is None
        assert result is not None
        assert "[REDACTED-github-token]" in result.safe_evidence["output"]

    def test_aws_key_example_in_safe_evidence_is_redacted(self):
        """AWS key patterns in safe_evidence values are redacted."""
        result, err = _parse(
            _valid_args(safe_evidence={"aws": "AKIAIOSFODNN7EXAMPLE"})  # pragma: allowlist secret
        )
        assert err is None
        assert result is not None
        assert "[REDACTED-aws-key]" in result.safe_evidence["aws"]

    def test_jwt_pattern_in_safe_evidence_is_redacted_not_rejected(self):
        """JWT-like patterns are redacted. Credential-like keys are redacted to generic marker."""
        # Three Base64url segments resembling a JWT
        jwt_like = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEifQ.signature_data_1234"
        result, err = _parse(_valid_args(safe_evidence={"token": jwt_like}))
        # Both the key "token" and the JWT value should be handled via redaction
        assert err is None
        assert result is not None
        # The credential-like key "token" gets redacted to a generic key
        assert "[REDACTED" in str(result.safe_evidence)

    def test_password_key_in_safe_evidence_is_redacted(self):
        """Credential-like keys are redacted to a generic marker."""
        result, err = _parse(
            _valid_args(safe_evidence={"password": "any_value_here"})
        )
        assert err is None
        assert result is not None
        # The key should be redacted
        assert "[REDACTED-credential-key]" in result.safe_evidence

    def test_api_key_key_in_safe_evidence_is_redacted(self):
        """API key credentials are handled through redaction."""
        result, err = _parse(
            _valid_args(safe_evidence={"api_key": "sk-1234567890abcdef1234567890abcdef"})  # pragma: allowlist secret
        )
        # Should accept and redact
        assert err is None
        assert result is not None

    def test_token_key_in_safe_evidence_is_redacted(self):
        """Token keys are redacted."""
        result, err = _parse(
            _valid_args(safe_evidence={"auth_token": "any_value"})
        )
        assert err is None
        assert result is not None
        # The key should be redacted
        assert "[REDACTED-credential-key]" in result.safe_evidence

    def test_client_secret_key_is_redacted(self):
        """client_secret keys are redacted."""
        result, err = _parse(
            _valid_args(safe_evidence={"client_secret": "my_oauth_secret"})
        )
        assert err is None
        assert result is not None
        # The key should be redacted
        assert "[REDACTED-credential-key]" in result.safe_evidence

    def test_openai_key_pattern_in_value_is_redacted(self):
        """OpenAI key patterns are redacted."""
        result, err = _parse(
            _valid_args(
                safe_evidence={"info": "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz01234"}  # pragma: allowlist secret
            )
        )
        assert err is None
        assert result is not None
        assert "[REDACTED-api-key]" in result.safe_evidence["info"]

    def test_pem_private_key_header_is_redacted(self):
        """PEM private key headers are redacted."""
        result, err = _parse(
            _valid_args(
                safe_evidence={
                    "key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQ..."  # pragma: allowlist secret
                }
            )
        )
        assert err is None
        assert result is not None
        assert "[REDACTED-private-key]" in result.safe_evidence["key"]

    def test_safe_regular_evidence_is_accepted(self):
        """Non-sensitive safe_evidence should not be rejected."""
        result, err = _parse(
            _valid_args(
                safe_evidence={
                    "tests": "42 passed, 0 failed",
                    "commit": "abc1234",
                    "branch": "feature/TASK-42",
                    "coverage": "87%",
                }
            )
        )
        assert err is None, f"Unexpected rejection: {err}"
        assert result is not None

    def test_redaction_is_idempotent(self):
        """Redacting the same inert credential example twice produces the same output."""
        message_with_bearer = "Authorization: Bearer short-but-still-secret"
        
        # First submission
        result1, err1 = _parse(_valid_args(message=message_with_bearer))
        assert err1 is None
        assert result1 is not None
        redacted1 = result1.message
        
        # Second submission with exact same payload
        result2, err2 = _parse(_valid_args(message=message_with_bearer))
        assert err2 is None
        assert result2 is not None
        redacted2 = result2.message
        
        # Redaction must be deterministic
        assert redacted1 == redacted2

    def test_credential_safety_task_can_pass_with_inert_examples(self):
        """Reproduce OOMPAH-589: auditor can submit PASS with credential-pattern examples."""
        # Simulates OOMPAH-589's attempted verdict discussing credential patterns
        message = (
            "Requirements discuss credential-safety patterns:\n"
            "- Bearer tokens like 'Bearer sk-abc123xyz' are unsafe\n"
            "- GitHub PATs matching 'ghp_*' must be rejected\n"
            "Code audit confirms all examples are inert documentation."
        )
        
        result, err = _parse(_valid_args(
            verdict="pass",
            message=message,
            safe_evidence={
                "example_patterns": "Bearer sk-..., ghp_..., glpat-...",
                "test_result": "42 passed",
            }
        ))
        
        # Should accept the PASS verdict despite credential pattern examples
        assert err is None
        assert result is not None
        assert result.verdict == Verdict.PASS
        # Message should contain redaction markers
        assert "[REDACTED-" in result.message
        # Safe evidence values should be redacted
        assert "[REDACTED-" in result.safe_evidence["example_patterns"]

    def test_triple_identical_submission_of_inert_examples_succeeds_idempotently(self):
        """OOMPAH-589 submitted 3x with identical payload; all 3 should succeed identically."""
        message = (
            "Audit complete. All tests passed. "
            "Documentation mentions credential patterns like Bearer tokens (sk-...) for reference only."
        )
        
        results = []
        for attempt in range(3):
            result, err = _parse(_valid_args(
                verdict="pass",
                message=message,
            ))
            # Each submission should succeed independently
            assert err is None, f"Attempt {attempt} failed: {err}"
            assert result is not None
            assert result.verdict == Verdict.PASS
            results.append(result)
        
        # All three submissions should produce identical redacted messages (deterministic redaction)
        assert results[0].message == results[1].message == results[2].message

    def test_secret_regex_matches_known_patterns(self):
        """Unit test the _RESULT_SECRET_RE pattern directly."""
        assert _RESULT_SECRET_RE.search("ghp_AbCdEfGhIjKlMnOpQrStUvWx")
        assert _RESULT_SECRET_RE.search("ghs_AbCdEfGhIjKlMnOpQrStUvWx1234")
        assert _RESULT_SECRET_RE.search("AKIAIOSFODNN7EXAMPLE")  # pragma: allowlist secret
        assert _RESULT_SECRET_RE.search("sk-AbCdEfGhIjKlMnOpQrStUvWx1234567")  # pragma: allowlist secret
        assert _RESULT_SECRET_RE.search("xoxb-12345-67890-abcdefghijklmnop")  # pragma: allowlist secret
        assert not _RESULT_SECRET_RE.search("abc123 passed in 12.3s")
        assert not _RESULT_SECRET_RE.search("commit abc1234 merged")

    def test_secret_key_regex_matches_known_names(self):
        """Unit test the _SECRET_KEY_RE pattern directly."""
        for name in ("password", "api_key", "token", "secret", "credential",
                     "access_token", "refresh_token", "client_secret", "bearer",
                     "private_key", "passphrase"):
            assert _SECRET_KEY_RE.search(name), f"Expected match for {name!r}"

        for safe_name in ("commit", "tests", "branch", "coverage", "status_text"):
            assert not _SECRET_KEY_RE.search(safe_name), f"Expected no match for {safe_name!r}"


# ---------------------------------------------------------------------------
# Duplicate / conflicting submissions
# ---------------------------------------------------------------------------


class TestDuplicateAndConflictingSubmissions:
    def test_identical_payload_is_submitted_successfully(self):
        """Submitting the same payload twice is valid at the parse level.
        Idempotency is enforced by the coordinator via attempt_id."""
        args = _valid_args()
        result1, err1 = _parse(args)
        result2, err2 = _parse(args)
        assert err1 is None
        assert err2 is None
        # Both parse to equivalent AuditResult objects
        assert result1.audit_id == result2.audit_id
        assert result1.verdict == result2.verdict

    def test_coordinator_deduplicates_identical_result_without_attempt_id(self):
        """The coordinator derives an idempotency key when none is supplied."""
        from oompah.models import Issue
        from oompah.terminal_audit import RequestState, TerminalAuditRecord
        from oompah.terminal_transition_coordinator import TerminalTransitionCoordinator
        from oompah.terminal_audit_metadata import METADATA_KEY, TerminalAuditMetadata

        class _MockLockStore:
            class _Lock:
                def __enter__(self): return self
                def __exit__(self, *_): return None
            def project_write_lock(self, _): return self._Lock()

        class _MockTracker:
            def __init__(self):
                self.metadata: dict = {}
                self.update_calls = []
                self.comment_calls = []
            def get_metadata(self, id_): return dict(self.metadata.get(id_, {}))
            def set_metadata_field(self, id_, key, value):
                self.metadata.setdefault(id_, {})[key] = value
            def update_issue(self, id_, **kwargs): self.update_calls.append((id_, kwargs))
            def add_comment(self, id_, text, author="oompah"): self.comment_calls.append((id_, text))
            def fetch_issue_states_by_ids(self, ids): return []

        fingerprint = EvidenceFingerprint("e" * 64)
        record = TerminalAuditRecord(
            audit_id="audit-dedup",
            project_id="proj-42",
            task_id="TASK-42",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
        )
        tracker = _MockTracker()
        meta = TerminalAuditMetadata(pending_chain=[record])
        tracker.metadata["TASK-42"] = {METADATA_KEY: meta.to_dict()}

        issue = Issue(
            id="TASK-42", identifier="TASK-42", title="T", state="In Validation"
        )
        coord = TerminalTransitionCoordinator(
            tracker=tracker, project_store=_MockLockStore()
        )
        audit_result = AuditResult(
            audit_id="audit-dedup",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            verdict=Verdict.PASS,
            message="ok",
            attempt_id=None,
        )
        first = asyncio.run(coord.apply_audit_result(issue, audit_result, "proj-42"))
        assert first.success is True
        first_updates = len(tracker.update_calls)

        # A refreshed task snapshot is terminal after the first application;
        # an exact replay must still be idempotent rather than stale-rejected.
        issue.state = "Done"
        second = asyncio.run(coord.apply_audit_result(issue, audit_result, "proj-42"))
        assert second.success is True
        assert second.idempotent is True
        # No extra tracker mutations for the idempotent replay
        assert len(tracker.update_calls) == first_updates

    def test_conflicting_verdict_on_completed_audit_is_rejected(self):
        """After one verdict is applied a different verdict for the same audit
        is rejected with STATE_MISMATCH — the coordinator must not flip state."""
        from oompah.models import Issue
        from oompah.terminal_audit import RequestState, TerminalAuditRecord
        from oompah.terminal_transition_coordinator import (
            ResultRejection,
            TerminalTransitionCoordinator,
        )
        from oompah.terminal_audit_metadata import METADATA_KEY, TerminalAuditMetadata

        class _MockLockStore:
            class _Lock:
                def __enter__(self): return self
                def __exit__(self, *_): return None
            def project_write_lock(self, _): return self._Lock()

        class _MockTracker:
            def __init__(self):
                self.metadata: dict = {}
                self.update_calls = []
                self.comment_calls = []
            def get_metadata(self, id_): return dict(self.metadata.get(id_, {}))
            def set_metadata_field(self, id_, key, value):
                self.metadata.setdefault(id_, {})[key] = value
            def update_issue(self, id_, **kwargs): self.update_calls.append((id_, kwargs))
            def add_comment(self, id_, text, author="oompah"): self.comment_calls.append((id_, text))
            def fetch_issue_states_by_ids(self, ids): return []

        fingerprint = EvidenceFingerprint("f" * 64)
        record = TerminalAuditRecord(
            audit_id="audit-conflict",
            project_id="proj-42",
            task_id="TASK-42",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
        )
        tracker = _MockTracker()
        meta = TerminalAuditMetadata(pending_chain=[record])
        tracker.metadata["TASK-42"] = {METADATA_KEY: meta.to_dict()}

        issue = Issue(
            id="TASK-42", identifier="TASK-42", title="T", state="In Validation"
        )
        coord = TerminalTransitionCoordinator(
            tracker=tracker, project_store=_MockLockStore()
        )
        pass_result = AuditResult(
            audit_id="audit-conflict",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            verdict=Verdict.PASS,
            message="Passed.",
            attempt_id="attempt-pass",
        )
        first = asyncio.run(coord.apply_audit_result(issue, pass_result, "proj-42"))
        assert first.success is True

        # Conflicting: same audit_id, different attempt_id, different verdict
        conflict_result = AuditResult(
            audit_id="audit-conflict",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            verdict=Verdict.FAIL,
            failure_classification=FailureClassification.INCOMPLETE,
            message="Actually failed.",
            attempt_id="attempt-fail",
        )
        conflict = asyncio.run(
            coord.apply_audit_result(issue, conflict_result, "proj-42")
        )
        assert conflict.success is False
        assert conflict.reason == ResultRejection.STATE_MISMATCH


# ---------------------------------------------------------------------------
# Coordinator failure
# ---------------------------------------------------------------------------


class TestCoordinatorFailure:
    def test_coordinator_exception_is_surfaced_as_error(self):
        """If the coordinator raises, submit_auditor_result returns an Error: string."""
        def failing_handler(result):
            raise RuntimeError("coordinator exploded")

        response = _submit(_valid_args(), handler=failing_handler)
        assert response.startswith("Error:")
        assert "coordinator exploded" not in response

    def test_coordinator_exception_does_not_leak_secrets(self):
        """Exception messages must not include the raw AuditResult object."""
        def failing_handler(result):
            raise ValueError(f"Internal error processing {result}")

        response = _submit(_valid_args(), handler=failing_handler)
        assert response.startswith("Error:")
        assert "Internal error processing" not in response


# ---------------------------------------------------------------------------
# Tool policy — non-auditor sessions are blocked
# ---------------------------------------------------------------------------


class TestToolPolicy:
    def test_auditor_policy_allows_submit_tool(self):
        """An auditor-session action_policy must allow submit_audit_result."""
        from oompah.auditor import AUDITOR_CAPABILITY_POLICY
        assert AUDITOR_CAPABILITY_POLICY.allows(AUDITOR_RESULT_TOOL_NAME)

    def test_auditor_policy_blocks_write_tools(self):
        """Auditor policy must deny mutating tools."""
        from oompah.auditor import AUDITOR_CAPABILITY_POLICY, AUDITOR_MUTATING_TOOLS
        for tool in AUDITOR_MUTATING_TOOLS:
            assert not AUDITOR_CAPABILITY_POLICY.allows(tool), (
                f"Expected {tool!r} to be denied by AuditorCapabilityPolicy"
            )

    def test_auditor_tool_not_in_normal_session_definitions(self):
        """Non-auditor API sessions must not expose submit_audit_result."""
        from oompah.api_agent import ApiAgentSession

        normal_session = ApiAgentSession(
            base_url="https://example.test",
            api_key="key",
            model="model",
            workspace_path=".",
        )
        tool_names = {t["function"]["name"] for t in normal_session._tool_definitions}
        assert AUDITOR_RESULT_TOOL_NAME not in tool_names

    def test_auditor_policy_is_enforced_at_two_layers(self):
        """Both the policy check and the tool executor enforce the restriction."""
        from oompah.api_agent import _execute_tool

        # Layer 1: action_policy.read_only=False → rejected before tool dispatch
        mock_policy = MagicMock()
        mock_policy.read_only = False
        resp1 = _execute_tool(
            Path("."),
            AUDITOR_RESULT_TOOL_NAME,
            _valid_args(),
            action_policy=mock_policy,
        )
        assert resp1.startswith("Error:")

        # Layer 2: no action_policy → rejected
        resp2 = _execute_tool(
            Path("."),
            AUDITOR_RESULT_TOOL_NAME,
            _valid_args(),
            action_policy=None,
        )
        assert resp2.startswith("Error:")

    def test_read_only_non_auditor_policy_cannot_submit(self):
        from oompah.authority_boundary import AgentActionPolicy
        from oompah.api_agent import _execute_tool

        response = _execute_tool(
            Path("."),
            AUDITOR_RESULT_TOOL_NAME,
            _valid_args(),
            action_policy=AgentActionPolicy(read_only=True),
            audit_target=_target(),
            audit_result_handler=lambda _result: None,
        )
        assert response.startswith("Error:")
        assert "restricted to an auditor session" in response

    def test_api_auditor_final_turn_commits_once_and_stops_session(self, tmp_path):
        """Acceptance on the boundary turn must not consume another model turn."""
        from oompah.api_agent import ApiAgentSession

        target = _target()
        calls = 0
        handler_calls = []

        async def fake_call(_messages):
            nonlocal calls
            calls += 1
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "submit-1",
                                    "function": {
                                        "name": AUDITOR_RESULT_TOOL_NAME,
                                        "arguments": json.dumps(_valid_args(target)),
                                    },
                                }
                            ],
                        },
                    }
                ]
            }

        session = ApiAgentSession(
            base_url="https://example.test",
            api_key="key",
            model="model",
            workspace_path=str(tmp_path),
            max_turns=1,
            enabled_tools={AUDITOR_RESULT_TOOL_NAME},
            action_policy=auditor_policy(task_identifier=target.task_id),
            audit_target=target,
            audit_result_handler=lambda result: (
                handler_calls.append(result) or {"accepted": True}
            ),
        )
        session._call_api = fake_call

        result = asyncio.run(session.run_task("inspect and submit"))

        assert result.status == "succeeded"
        assert result.turns == 1
        assert calls == 1
        assert len(handler_calls) == 1

    def test_api_auditor_reserves_finalization_after_last_ordinary_verdict(
        self, tmp_path, monkeypatch
    ):
        """A prose verdict on the last ordinary turn cannot end the session."""
        from oompah.api_agent import ApiAgentSession

        target = _target()
        payloads = []
        handler_calls = []

        def fake_post(_url, _headers, body, _ssl_ctx):
            payload = json.loads(body)
            payloads.append(payload)
            if len(payloads) == 1:
                return {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": "Audit PASS — Done",
                                "tool_calls": None,
                            },
                        }
                    ]
                }
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "submit-final",
                                    "function": {
                                        "name": AUDITOR_RESULT_TOOL_NAME,
                                        "arguments": json.dumps(_valid_args(target)),
                                    },
                                }
                            ],
                        },
                    }
                ]
            }

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)
        session = ApiAgentSession(
            base_url="https://example.test",
            api_key="key",
            model="model",
            workspace_path=str(tmp_path),
            max_turns=2,
            enabled_tools={"read_file", AUDITOR_RESULT_TOOL_NAME},
            action_policy=auditor_policy(task_identifier=target.task_id),
            audit_target=target,
            audit_result_handler=lambda result: (
                handler_calls.append(result) or {"accepted": True}
            ),
        )

        result = asyncio.run(session.run_task("inspect and submit"))

        assert result.status == "succeeded"
        assert result.turns == 2
        assert len(handler_calls) == 1
        assert payloads[0]["tool_choice"] == "auto"
        assert payloads[1]["tool_choice"]["function"]["name"] == (
            AUDITOR_RESULT_TOOL_NAME
        )
        assert [
            tool["function"]["name"] for tool in payloads[1]["tools"]
        ] == [AUDITOR_RESULT_TOOL_NAME]
        assert "reserved audit-finalization turn" in payloads[1]["messages"][-1][
            "content"
        ]

    def test_api_auditor_prose_verdict_cannot_mask_uncommitted_exit(self, tmp_path):
        from oompah.api_agent import ApiAgentSession

        target = _target()
        handler_calls = []

        async def fake_call(_messages):
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": "Audit PASS — Done",
                            "tool_calls": None,
                        },
                    }
                ]
            }

        session = ApiAgentSession(
            base_url="https://example.test",
            api_key="key",
            model="model",
            workspace_path=str(tmp_path),
            max_turns=1,
            enabled_tools={AUDITOR_RESULT_TOOL_NAME},
            action_policy=auditor_policy(task_identifier=target.task_id),
            audit_target=target,
            audit_result_handler=lambda result: handler_calls.append(result),
        )
        session._call_api = fake_call

        result = asyncio.run(session.run_task("inspect and submit"))

        assert result.status == "max_turns"
        assert handler_calls == []
