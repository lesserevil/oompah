"""Tests for oompah.intake_approval — requestor approval detection for intake.

Covers:
- is_approval_command(): explicit /oompah approve detection
- is_authorized_approver(): requestor, bot, owner, and unauthorized actors
- compute_proposal_fingerprint(): SHA-256 stability and normalization
- is_approval_stale(): fingerprint mismatch detection
- build_intake_approval(): end-to-end approval recording
- IntakeApproval.to_dict() / from_dict(): round-trip serialization
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from oompah.intake_approval import (
    IntakeApproval,
    build_intake_approval,
    compute_proposal_fingerprint,
    is_approval_command,
    is_approval_stale,
    is_authorized_approver,
    is_plain_requestor_approval_comment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    authorized_logins: list[str] | None = None,
    *,
    tracker_owner: str | None = None,
    status_actor_login: str | None = None,
) -> MagicMock:
    """Return a mock Project with given intake-authorization settings."""
    project = MagicMock()
    project.status_label_authorized_logins = authorized_logins or []
    project.status_actor_login = status_actor_login
    project.tracker_owner = tracker_owner
    return project


# ===========================================================================
# is_approval_command
# ===========================================================================


class TestIsApprovalCommand:
    """Tests for the /oompah approve command parser."""

    def test_exact_command_is_recognized(self):
        assert is_approval_command("/oompah approve") is True

    def test_case_insensitive_upper(self):
        assert is_approval_command("/OOMPAH APPROVE") is True

    def test_case_insensitive_mixed(self):
        assert is_approval_command("/Oompah Approve") is True

    def test_leading_whitespace_allowed(self):
        assert is_approval_command("  /oompah approve") is True

    def test_command_on_second_line(self):
        assert is_approval_command("Some preamble text\n/oompah approve") is True

    def test_command_with_trailing_text(self):
        """Text after the command token on the same line is allowed."""
        assert is_approval_command("/oompah approve LGTM") is True

    def test_command_with_newline_after(self):
        assert is_approval_command("/oompah approve\nSome note below") is True

    def test_lgtm_comment_is_not_approval(self):
        """Ambiguous 'LGTM' should NOT be treated as approval."""
        assert is_approval_command("LGTM") is False

    def test_looks_good_is_not_approval(self):
        assert is_approval_command("Looks good to me!") is False

    def test_approve_keyword_alone_is_not_approval(self):
        assert is_approval_command("approved") is False

    def test_thumbs_up_is_not_approval(self):
        assert is_approval_command(":+1:") is False

    def test_approve_mid_sentence_is_not_approval(self):
        """The command must be at the start of a line — not mid-sentence."""
        assert is_approval_command("This looks good, /oompah approve") is False

    def test_empty_string_returns_false(self):
        assert is_approval_command("") is False

    def test_none_like_empty_comment(self):
        assert is_approval_command("") is False

    def test_partial_command_not_recognized(self):
        assert is_approval_command("/oompah") is False

    def test_reject_command_is_not_approval(self):
        assert is_approval_command("/oompah reject") is False

    def test_different_slash_command_not_approval(self):
        assert is_approval_command("/approve") is False


class TestIsPlainRequestorApprovalComment:
    """Tests for clear plain-language requestor approval detection."""

    def test_approval_and_backlog_request_is_recognized(self):
        assert (
            is_plain_requestor_approval_comment(
                "I approve this. Please add it to the backlog."
            )
            is True
        )

    def test_first_person_approval_is_recognized(self):
        assert is_plain_requestor_approval_comment("I approve this scope.") is True

    def test_explicit_backlog_request_is_recognized(self):
        assert is_plain_requestor_approval_comment("Please move this to Backlog.") is True

    def test_scope_approval_is_recognized(self):
        assert (
            is_plain_requestor_approval_comment("The proposed scope is approved.")
            is True
        )

    def test_lgtm_is_ambiguous(self):
        assert is_plain_requestor_approval_comment("LGTM") is False

    def test_looks_good_is_ambiguous(self):
        assert is_plain_requestor_approval_comment("Looks good to me.") is False

    def test_approved_keyword_alone_is_ambiguous(self):
        assert is_plain_requestor_approval_comment("approved") is False

    def test_change_request_is_not_approval(self):
        assert (
            is_plain_requestor_approval_comment(
                "I approve the direction, but please make changes first."
            )
            is False
        )

    def test_negative_approval_is_not_approval(self):
        assert (
            is_plain_requestor_approval_comment(
                "I do not approve this. Please do not add it to the backlog."
            )
            is False
        )

    def test_slash_command_is_not_plain_approval(self):
        assert is_plain_requestor_approval_comment("/oompah approve") is False

    def test_quoted_approval_is_ignored(self):
        assert (
            is_plain_requestor_approval_comment(
                "> I approve this. Please add it to the backlog.\nNeeds more detail."
            )
            is False
        )


# ===========================================================================
# is_authorized_approver
# ===========================================================================


class TestIsAuthorizedApprover:
    """Tests for the approval authorization logic."""

    # --- requestor --------------------------------------------------------

    def test_requestor_is_authorized(self):
        project = _make_project()
        authorized, override = is_authorized_approver("alice", "alice", project)
        assert authorized is True
        assert override is False

    def test_requestor_case_insensitive(self):
        project = _make_project()
        authorized, override = is_authorized_approver("Alice", "alice", project)
        assert authorized is True
        assert override is False

    # --- bot --------------------------------------------------------------

    def test_bot_is_authorized_not_override(self):
        project = _make_project()
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
            authorized, override = is_authorized_approver("oompah", "alice", project)
        assert authorized is True
        assert override is False

    def test_bot_custom_login(self):
        project = _make_project()
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "my-bot[bot]"}):
            authorized, override = is_authorized_approver(
                "my-bot[bot]", "alice", project
            )
        assert authorized is True
        assert override is False

    def test_bot_case_insensitive(self):
        project = _make_project()
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
            authorized, override = is_authorized_approver("OOMPAH", "alice", project)
        assert authorized is True
        assert override is False

    # --- owner override ---------------------------------------------------

    def test_tracker_owner_is_authorized_as_override(self):
        project = _make_project(tracker_owner="repo-admin")
        authorized, override = is_authorized_approver("repo-admin", "alice", project)
        assert authorized is True
        assert override is True

    def test_tracker_owner_case_insensitive(self):
        project = _make_project(tracker_owner="Repo-Admin")
        authorized, override = is_authorized_approver("repo-admin", "alice", project)
        assert authorized is True
        assert override is True

    def test_status_actor_is_authorized_as_override(self):
        project = _make_project(status_actor_login="status-actor")
        authorized, override = is_authorized_approver(
            "STATUS-ACTOR",
            "alice",
            project,
        )
        assert authorized is True
        assert override is True

    def test_authorized_login_list_is_override(self):
        project = _make_project(authorized_logins=["pm-user", "tech-lead"])
        authorized, override = is_authorized_approver("pm-user", "alice", project)
        assert authorized is True
        assert override is True

    def test_authorized_login_list_case_insensitive(self):
        project = _make_project(authorized_logins=["PM-User"])
        authorized, override = is_authorized_approver("pm-user", "alice", project)
        assert authorized is True
        assert override is True

    # --- unauthorized actors ----------------------------------------------

    def test_non_requestor_non_owner_is_rejected(self):
        project = _make_project()
        authorized, override = is_authorized_approver("random-user", "alice", project)
        assert authorized is False
        assert override is False

    def test_empty_actor_is_rejected(self):
        project = _make_project()
        authorized, override = is_authorized_approver("", "alice", project)
        assert authorized is False
        assert override is False

    def test_none_project_still_authorizes_requestor(self):
        authorized, override = is_authorized_approver("alice", "alice", None)
        assert authorized is True
        assert override is False

    def test_none_project_still_authorizes_bot(self):
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
            authorized, override = is_authorized_approver("oompah", "alice", None)
        assert authorized is True
        assert override is False

    def test_none_project_rejects_random_user(self):
        authorized, override = is_authorized_approver("random", "alice", None)
        assert authorized is False
        assert override is False


# ===========================================================================
# compute_proposal_fingerprint
# ===========================================================================


class TestComputeProposalFingerprint:
    """Tests for the SHA-256 fingerprint of an issue body."""

    def test_returns_64_char_hex(self):
        fp = compute_proposal_fingerprint("some content")
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_same_content_same_fingerprint(self):
        assert compute_proposal_fingerprint("hello") == compute_proposal_fingerprint(
            "hello"
        )

    def test_different_content_different_fingerprint(self):
        assert compute_proposal_fingerprint("hello") != compute_proposal_fingerprint(
            "world"
        )

    def test_leading_trailing_whitespace_normalized(self):
        """Cosmetic whitespace must not change the fingerprint."""
        assert compute_proposal_fingerprint("  hello  ") == compute_proposal_fingerprint(
            "hello"
        )

    def test_empty_body_has_stable_fingerprint(self):
        fp1 = compute_proposal_fingerprint("")
        fp2 = compute_proposal_fingerprint("")
        assert fp1 == fp2

    def test_none_treated_as_empty(self):
        # type: ignore[arg-type]
        fp_none = compute_proposal_fingerprint(None)  # type: ignore[arg-type]
        fp_empty = compute_proposal_fingerprint("")
        assert fp_none == fp_empty

    def test_material_edit_changes_fingerprint(self):
        body1 = "Implement feature X"
        body2 = "Implement feature X with additional requirement Y"
        assert compute_proposal_fingerprint(body1) != compute_proposal_fingerprint(
            body2
        )


# ===========================================================================
# is_approval_stale
# ===========================================================================


class TestIsApprovalStale:
    """Tests for stale approval detection."""

    def _make_approval(self, fingerprint: str) -> IntakeApproval:
        return IntakeApproval(
            actor="alice",
            approved_at="2026-01-01T12:00:00+00:00",
            proposal_fingerprint=fingerprint,
        )

    def test_same_fingerprint_not_stale(self):
        fp = compute_proposal_fingerprint("same body")
        approval = self._make_approval(fp)
        assert is_approval_stale(approval, fp) is False

    def test_different_fingerprint_is_stale(self):
        fp_old = compute_proposal_fingerprint("original body")
        fp_new = compute_proposal_fingerprint("edited body")
        approval = self._make_approval(fp_old)
        assert is_approval_stale(approval, fp_new) is True

    def test_empty_fingerprint_mismatch_is_stale(self):
        fp_real = compute_proposal_fingerprint("some body")
        approval = self._make_approval("")
        assert is_approval_stale(approval, fp_real) is True


# ===========================================================================
# build_intake_approval
# ===========================================================================


class TestBuildIntakeApproval:
    """Tests for the primary approval-building entry point."""

    _BODY = "Implement feature Z as described"

    def _fp(self) -> str:
        return compute_proposal_fingerprint(self._BODY)

    # --- requestor approval -----------------------------------------------

    def test_requestor_approval_is_recorded(self):
        project = _make_project()
        approval = build_intake_approval(
            actor="alice",
            requestor="alice",
            proposal_fingerprint=self._fp(),
            project=project,
        )
        assert approval is not None
        assert approval.actor == "alice"
        assert approval.proposal_fingerprint == self._fp()
        assert approval.is_owner_override is False

    # --- owner override approval ------------------------------------------

    def test_owner_override_approval_is_recorded(self):
        project = _make_project(tracker_owner="admin-user")
        approval = build_intake_approval(
            actor="admin-user",
            requestor="alice",
            proposal_fingerprint=self._fp(),
            project=project,
        )
        assert approval is not None
        assert approval.actor == "admin-user"
        assert approval.is_owner_override is True

    def test_authorized_login_override_approval(self):
        project = _make_project(authorized_logins=["tech-lead"])
        approval = build_intake_approval(
            actor="tech-lead",
            requestor="alice",
            proposal_fingerprint=self._fp(),
            project=project,
        )
        assert approval is not None
        assert approval.is_owner_override is True

    # --- non-requestor rejection ------------------------------------------

    def test_non_requestor_approval_returns_none(self):
        project = _make_project()
        approval = build_intake_approval(
            actor="random-user",
            requestor="alice",
            proposal_fingerprint=self._fp(),
            project=project,
        )
        assert approval is None

    def test_empty_actor_returns_none(self):
        project = _make_project()
        approval = build_intake_approval(
            actor="",
            requestor="alice",
            proposal_fingerprint=self._fp(),
            project=project,
        )
        assert approval is None

    # --- timestamp handling -----------------------------------------------

    def test_timestamp_is_set_when_not_provided(self):
        project = _make_project()
        approval = build_intake_approval(
            actor="alice",
            requestor="alice",
            proposal_fingerprint=self._fp(),
            project=project,
        )
        assert approval is not None
        # Should be a parseable ISO timestamp
        parsed = datetime.fromisoformat(approval.approved_at)
        assert parsed is not None

    def test_custom_timestamp_is_preserved(self):
        project = _make_project()
        ts = "2026-06-01T10:00:00+00:00"
        approval = build_intake_approval(
            actor="alice",
            requestor="alice",
            proposal_fingerprint=self._fp(),
            project=project,
            approved_at=ts,
        )
        assert approval is not None
        assert approval.approved_at == ts

    # --- stale approval invalidation ------------------------------------

    def test_stale_approval_detected_after_body_edit(self):
        """After a material edit, the approval fingerprint no longer matches."""
        original_body = "Feature A description"
        edited_body = "Feature A description — materially changed"

        fp_original = compute_proposal_fingerprint(original_body)
        fp_edited = compute_proposal_fingerprint(edited_body)

        project = _make_project()
        approval = build_intake_approval(
            actor="alice",
            requestor="alice",
            proposal_fingerprint=fp_original,
            project=project,
        )
        assert approval is not None
        # Approval is still valid against the original body
        assert is_approval_stale(approval, fp_original) is False
        # After the edit, the same approval is stale
        assert is_approval_stale(approval, fp_edited) is True


# ===========================================================================
# IntakeApproval serialization
# ===========================================================================


class TestIntakeApprovalSerialization:
    """Tests for to_dict / from_dict round-trip."""

    def _sample(self) -> IntakeApproval:
        return IntakeApproval(
            actor="alice",
            approved_at="2026-06-01T12:00:00+00:00",
            proposal_fingerprint="abc123",
            is_owner_override=False,
        )

    def test_round_trip(self):
        original = self._sample()
        restored = IntakeApproval.from_dict(original.to_dict())
        assert restored.actor == original.actor
        assert restored.approved_at == original.approved_at
        assert restored.proposal_fingerprint == original.proposal_fingerprint
        assert restored.is_owner_override == original.is_owner_override

    def test_to_dict_contains_expected_keys(self):
        d = self._sample().to_dict()
        assert set(d.keys()) == {
            "actor",
            "approved_at",
            "proposal_fingerprint",
            "is_owner_override",
        }

    def test_from_dict_defaults_for_missing_keys(self):
        restored = IntakeApproval.from_dict({})
        assert restored.actor == ""
        assert restored.approved_at == ""
        assert restored.proposal_fingerprint == ""
        assert restored.is_owner_override is False

    def test_owner_override_round_trip(self):
        original = IntakeApproval(
            actor="admin",
            approved_at="2026-06-01T12:00:00+00:00",
            proposal_fingerprint="xyz",
            is_owner_override=True,
        )
        restored = IntakeApproval.from_dict(original.to_dict())
        assert restored.is_owner_override is True
