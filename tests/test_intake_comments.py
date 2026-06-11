"""Tests for oompah.intake_comments (#281)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from oompah.intake_comments import (
    SCOPE_EPIC_NEEDED,
    ValidatorResult,
    build_intake_comment,
    compute_fingerprint,
    post_intake_comment_if_needed,
    should_post_intake_comment,
)
from oompah.intake_schema import (
    IntakeReadiness,
    IntakeScopeKind,
    ValidatorResult as StoredValidatorResult,
    intake_to_raw,
)
from oompah.issue_validator import (
    MissingField,
    ScopeClassification,
    ValidationResult as IssueValidationResult,
)


IDENTIFIER = "lesserevil/oompah#281"


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 11, hour, minute, tzinfo=timezone.utc)


def _iso(hour: int, minute: int = 0) -> str:
    return _dt(hour, minute).isoformat()


def _result(
    *missing_fields: str,
    scope: str = "small_task",
    suggested_fixes: dict[str, str] | None = None,
) -> ValidatorResult:
    return ValidatorResult(
        is_ready=False,
        missing_fields=list(missing_fields),
        suggested_fixes=suggested_fixes or {},
        scope=scope,
    )


class FakeTracker:
    def __init__(self, metadata: dict[str, object] | None = None) -> None:
        self.metadata = dict(metadata or {})
        self.comments: list[dict[str, str]] = []
        self.set_calls: list[tuple[str, str, object]] = []

    def get_metadata(self, identifier: str) -> dict[str, object]:
        assert identifier == IDENTIFIER
        return dict(self.metadata)

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        assert identifier == IDENTIFIER
        self.metadata[key] = value
        self.set_calls.append((identifier, key, value))

    def add_comment(
        self,
        identifier: str,
        text: str,
        author: str = "oompah",
    ) -> dict[str, str]:
        assert identifier == IDENTIFIER
        comment = {"text": text, "author": author}
        self.comments.append(comment)
        return comment


class TestCommentText:
    def test_missing_information_comment_names_fields_and_suggestions(self):
        result = _result(
            "acceptance criteria",
            "problem_statement",
            suggested_fixes={
                "acceptance criteria": "Add testable bullet points.",
                "problem_statement": "Describe the user-visible problem.",
            },
        )

        comment = build_intake_comment(result, "alice")

        assert comment.startswith("@alice, this issue is missing")
        assert "- **acceptance criteria** - Add testable bullet points." not in comment
        assert "- **acceptance criteria**" in comment
        assert "Add testable bullet points." in comment
        assert "- **a clear problem statement**" in comment
        assert "Describe the user-visible problem." in comment
        assert "Please update the issue" in comment

    def test_author_prefix_is_not_embedded_in_comment_body(self):
        comment = build_intake_comment(_result("acceptance_criteria"), "alice")

        assert not comment.startswith("**oompah**:")


class TestFingerprint:
    def test_fingerprint_is_stable_for_field_order_and_actor_case(self):
        a = compute_fingerprint(
            _result("problem statement", "acceptance_criteria"),
            "Alice",
        )
        b = compute_fingerprint(
            _result("acceptance criteria", "problem_statement"),
            "alice",
        )

        assert a == b

    def test_fingerprint_changes_when_requested_actor_changes(self):
        result = _result("acceptance_criteria")

        assert compute_fingerprint(result, "alice") != compute_fingerprint(
            result,
            "bob",
        )


class TestShouldPostIntakeComment:
    def test_suppresses_same_result_when_only_previous_comment_updated_issue(self):
        result = _result("acceptance_criteria")
        fingerprint = compute_fingerprint(result, "alice")
        existing = {
            "fingerprint": fingerprint,
            "requested_actor": "alice",
            "posted_at": _iso(12, 5),
            "issue_updated_at": _iso(12, 0),
        }

        assert should_post_intake_comment(existing, fingerprint, _dt(12, 5)) is False

    def test_reposts_same_result_after_requestor_updates_issue(self):
        result = _result("acceptance_criteria")
        fingerprint = compute_fingerprint(result, "alice")
        existing = {
            "fingerprint": fingerprint,
            "requested_actor": "alice",
            "posted_at": _iso(12, 5),
            "issue_updated_at": _iso(12, 0),
        }

        assert should_post_intake_comment(existing, fingerprint, _dt(12, 6)) is True

    def test_reposts_when_validator_fingerprint_changes(self):
        old = _result("acceptance_criteria")
        new = _result("acceptance_criteria", "problem_statement")
        existing = {
            "fingerprint": compute_fingerprint(old, "alice"),
            "requested_actor": "alice",
            "posted_at": _iso(12, 5),
            "issue_updated_at": _iso(12, 0),
        }

        assert (
            should_post_intake_comment(
                existing,
                compute_fingerprint(new, "alice"),
                _dt(12, 5),
            )
            is True
        )


class TestPostIntakeComment:
    def test_posts_comment_with_author_and_updates_metadata(self):
        readiness = IntakeReadiness(
            missing_fields=[],
            scope=IntakeScopeKind.SMALL,
            requestor_approved=True,
            requestor_actor="alice",
            last_validator_result=StoredValidatorResult.PASS,
            last_validated_at=_iso(11, 0),
        )
        tracker = FakeTracker({"oompah.intake": intake_to_raw(readiness)})

        with patch("oompah.intake_comments._now_iso", return_value=_iso(12, 5)):
            posted = post_intake_comment_if_needed(
                tracker,
                IDENTIFIER,
                _result("acceptance criteria"),
                "alice",
                issue_updated_at=_dt(12, 0),
            )

        assert posted is True
        assert tracker.comments == [
            {
                "author": "oompah",
                "text": tracker.comments[0]["text"],
            }
        ]
        assert tracker.comments[0]["text"].startswith("@alice")
        assert not tracker.comments[0]["text"].startswith("**oompah**:")

        record = tracker.metadata["oompah.intake_comment"]
        assert isinstance(record, dict)
        assert record["requested_actor"] == "alice"
        assert record["posted_at"] == _iso(12, 5)
        assert record["issue_updated_at"] == _iso(12, 0)

        intake = tracker.metadata["oompah.intake"]
        assert isinstance(intake, dict)
        assert intake["missing_fields"] == ["acceptance_criteria"]
        assert intake["requestor_approved"] is True
        assert intake["requestor_actor"] == "alice"
        assert intake["last_validator_result"] == "fail"
        assert intake["last_validated_at"] == _iso(12, 5)

    def test_duplicate_poll_does_not_post_second_comment(self):
        tracker = FakeTracker()
        result = _result("acceptance_criteria")

        with patch("oompah.intake_comments._now_iso", return_value=_iso(12, 5)):
            assert post_intake_comment_if_needed(
                tracker,
                IDENTIFIER,
                result,
                "alice",
                issue_updated_at=_dt(12, 0),
            )

        assert post_intake_comment_if_needed(
            tracker,
            IDENTIFIER,
            result,
            "alice",
            issue_updated_at=_dt(12, 5),
        ) is False
        assert len(tracker.comments) == 1

    def test_same_result_reposts_after_requestor_update(self):
        tracker = FakeTracker()
        result = _result("acceptance_criteria")

        with patch("oompah.intake_comments._now_iso", return_value=_iso(12, 5)):
            assert post_intake_comment_if_needed(
                tracker,
                IDENTIFIER,
                result,
                "alice",
                issue_updated_at=_dt(12, 0),
            )

        with patch("oompah.intake_comments._now_iso", return_value=_iso(12, 10)):
            assert post_intake_comment_if_needed(
                tracker,
                IDENTIFIER,
                result,
                "alice",
                issue_updated_at=_dt(12, 6),
            )

        assert len(tracker.comments) == 2
        record = tracker.metadata["oompah.intake_comment"]
        assert isinstance(record, dict)
        assert record["posted_at"] == _iso(12, 10)

    def test_changed_result_posts_updated_request(self):
        tracker = FakeTracker()

        with patch("oompah.intake_comments._now_iso", return_value=_iso(12, 5)):
            assert post_intake_comment_if_needed(
                tracker,
                IDENTIFIER,
                _result("acceptance_criteria"),
                "alice",
                issue_updated_at=_dt(12, 0),
            )

        with patch("oompah.intake_comments._now_iso", return_value=_iso(12, 6)):
            assert post_intake_comment_if_needed(
                tracker,
                IDENTIFIER,
                _result("acceptance_criteria", "problem_statement"),
                "alice",
                issue_updated_at=_dt(12, 5),
            )

        assert len(tracker.comments) == 2
        assert "a clear problem statement" in tracker.comments[1]["text"]
        intake = tracker.metadata["oompah.intake"]
        assert isinstance(intake, dict)
        assert intake["missing_fields"] == [
            "acceptance_criteria",
            "problem_statement",
        ]

    def test_ready_result_does_not_post(self):
        tracker = FakeTracker()
        result = ValidatorResult(is_ready=True, missing_fields=[])

        posted = post_intake_comment_if_needed(
            tracker,
            IDENTIFIER,
            result,
            "alice",
            issue_updated_at=_dt(12, 0),
        )

        assert posted is False
        assert tracker.comments == []
        assert tracker.metadata == {}

    def test_adapts_readiness_validator_result(self):
        tracker = FakeTracker()
        validation = IssueValidationResult(
            ready=False,
            issue_type="task",
            scope=ScopeClassification.EPIC_NEEDED,
            missing_fields=[
                MissingField(
                    field="acceptance criteria",
                    reason="Required for verification.",
                    suggested_fix="Add concrete pass/fail bullets.",
                )
            ],
        )

        with patch("oompah.intake_comments._now_iso", return_value=_iso(12, 5)):
            posted = post_intake_comment_if_needed(
                tracker,
                IDENTIFIER,
                validation,
                "alice",
                issue_updated_at=_dt(12, 0),
            )

        assert posted is True
        assert "Add concrete pass/fail bullets." in tracker.comments[0]["text"]
        assert "Scope note" in tracker.comments[0]["text"]
        intake = tracker.metadata["oompah.intake"]
        assert isinstance(intake, dict)
        assert intake["scope"] == "needs_decomposition"
        assert intake["decomposition_status"] == "pending"
