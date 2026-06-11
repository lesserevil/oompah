"""Tests for oompah.label_auth — authorization model for oompah:status:* label changes.

Covers:
- get_bot_login(): reads OOMPAH_BOT_LOGIN env var, defaults to "oompah"
- is_status_label(): recognises oompah:status:* prefix
- label_name_to_status(): converts label names to canonical status strings
- _status_to_label_name(): inverse of label_name_to_status
- is_authorized_status_actor(): bot + per-project owner allowlist
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from oompah.label_auth import (
    _status_to_label_name,
    get_bot_login,
    is_authorized_status_actor,
    is_status_label,
    label_name_to_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    authorized_logins: list[str] | None = None,
    *,
    tracker_owner: str | None = None,
) -> MagicMock:
    """Return a mock Project with the given authorized-login list."""
    project = MagicMock()
    project.status_label_authorized_logins = authorized_logins or []
    if tracker_owner is not None:
        project.tracker_owner = tracker_owner
    return project


# ===========================================================================
# get_bot_login
# ===========================================================================


class TestGetBotLogin:
    def test_default_is_oompah(self):
        with patch.dict("os.environ", {}, clear=False):
            # Remove OOMPAH_BOT_LOGIN if present
            import os
            old = os.environ.pop("OOMPAH_BOT_LOGIN", None)
            try:
                assert get_bot_login() == "oompah"
            finally:
                if old is not None:
                    os.environ["OOMPAH_BOT_LOGIN"] = old

    def test_reads_env_var(self):
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "my-bot[bot]"}):
            assert get_bot_login() == "my-bot[bot]"

    def test_empty_env_var_falls_back_to_default(self):
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": ""}):
            assert get_bot_login() == "oompah"


# ===========================================================================
# is_status_label
# ===========================================================================


class TestIsStatusLabel:
    def test_status_open(self):
        assert is_status_label("oompah:status:open") is True

    def test_status_in_progress(self):
        assert is_status_label("oompah:status:in-progress") is True

    def test_status_backlog(self):
        assert is_status_label("oompah:status:backlog") is True

    def test_non_status_label(self):
        assert is_status_label("bug") is False

    def test_priority_label(self):
        assert is_status_label("priority:0") is False

    def test_type_label(self):
        assert is_status_label("type:task") is False

    def test_empty_string(self):
        assert is_status_label("") is False

    def test_oompah_prefix_only(self):
        # Prefix without status: still matches because it starts with "oompah:status:"
        assert is_status_label("oompah:status:") is True

    def test_partial_prefix(self):
        assert is_status_label("oompah:") is False
        assert is_status_label("oompah:status") is False


# ===========================================================================
# label_name_to_status
# ===========================================================================


class TestLabelNameToStatus:
    def test_open(self):
        assert label_name_to_status("oompah:status:open") == "Open"

    def test_backlog(self):
        assert label_name_to_status("oompah:status:backlog") == "Backlog"

    def test_proposed(self):
        assert label_name_to_status("oompah:status:proposed") == "Proposed"

    def test_in_progress(self):
        assert label_name_to_status("oompah:status:in-progress") == "In Progress"

    def test_needs_ci_fix(self):
        assert label_name_to_status("oompah:status:needs-ci-fix") == "Needs CI Fix"

    def test_done(self):
        assert label_name_to_status("oompah:status:done") == "Done"

    def test_archived(self):
        assert label_name_to_status("oompah:status:archived") == "Archived"

    def test_merged(self):
        assert label_name_to_status("oompah:status:merged") == "Merged"

    def test_non_status_label_returns_none(self):
        assert label_name_to_status("bug") is None

    def test_empty_string_returns_none(self):
        assert label_name_to_status("") is None

    def test_unknown_slug_returns_none(self):
        assert label_name_to_status("oompah:status:unknown-slug") is None

    def test_in_review(self):
        assert label_name_to_status("oompah:status:in-review") == "In Review"

    def test_needs_human(self):
        assert label_name_to_status("oompah:status:needs-human") == "Needs Human"

    def test_needs_rebase(self):
        assert label_name_to_status("oompah:status:needs-rebase") == "Needs Rebase"


# ===========================================================================
# _status_to_label_name
# ===========================================================================


class TestStatusToLabelName:
    def test_open(self):
        assert _status_to_label_name("Open") == "oompah:status:open"

    def test_backlog(self):
        assert _status_to_label_name("Backlog") == "oompah:status:backlog"

    def test_proposed(self):
        assert _status_to_label_name("Proposed") == "oompah:status:proposed"

    def test_in_progress(self):
        assert _status_to_label_name("In Progress") == "oompah:status:in-progress"

    def test_done(self):
        assert _status_to_label_name("Done") == "oompah:status:done"

    def test_archived(self):
        assert _status_to_label_name("Archived") == "oompah:status:archived"

    def test_needs_ci_fix(self):
        assert _status_to_label_name("Needs CI Fix") == "oompah:status:needs-ci-fix"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown status"):
            _status_to_label_name("NotAStatus")

    def test_round_trip(self):
        """label_name_to_status and _status_to_label_name are inverses."""
        labels = [
            "oompah:status:proposed",
            "oompah:status:open",
            "oompah:status:backlog",
            "oompah:status:in-progress",
            "oompah:status:done",
            "oompah:status:merged",
            "oompah:status:archived",
            "oompah:status:needs-ci-fix",
            "oompah:status:needs-rebase",
            "oompah:status:in-review",
            "oompah:status:needs-human",
            "oompah:status:needs-answer",
        ]
        for label in labels:
            status = label_name_to_status(label)
            assert status is not None, f"{label!r} not in slug map"
            assert _status_to_label_name(status) == label


# ===========================================================================
# is_authorized_status_actor
# ===========================================================================


class TestIsAuthorizedStatusActor:
    """Tests for is_authorized_status_actor()."""

    def test_bot_login_is_always_authorized(self):
        """The oompah bot is authorized regardless of project settings."""
        project = _make_project([])
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
            assert is_authorized_status_actor("oompah", project) is True

    def test_bot_login_case_insensitive(self):
        """Bot login comparison is case-insensitive."""
        project = _make_project([])
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
            assert is_authorized_status_actor("Oompah", project) is True
            assert is_authorized_status_actor("OOMPAH", project) is True

    def test_custom_bot_login(self):
        """OOMPAH_BOT_LOGIN env var is respected."""
        project = _make_project([])
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "my-bot[bot]"}):
            assert is_authorized_status_actor("my-bot[bot]", project) is True
            assert is_authorized_status_actor("oompah", project) is False

    def test_project_owner_in_allowlist_is_authorized(self):
        """A login in status_label_authorized_logins is authorized."""
        project = _make_project(["alice", "bob"])
        assert is_authorized_status_actor("alice", project) is True
        assert is_authorized_status_actor("bob", project) is True

    def test_project_owner_allowlist_case_insensitive(self):
        """Project allowlist comparison is case-insensitive."""
        project = _make_project(["Alice"])
        assert is_authorized_status_actor("alice", project) is True
        assert is_authorized_status_actor("ALICE", project) is True

    def test_tracker_owner_is_authorized_by_default(self):
        """The configured tracker owner is authorized without an allowlist entry."""
        project = _make_project([], tracker_owner="lesserevil")
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
            assert is_authorized_status_actor("lesserevil", project) is True
            assert is_authorized_status_actor("LESSEREVIL", project) is True

    def test_unauthorized_user_not_in_allowlist(self):
        """A user not in the allowlist and not the bot is unauthorized."""
        project = _make_project(["alice"])
        assert is_authorized_status_actor("charlie", project) is False

    def test_empty_actor_login_is_unauthorized(self):
        """An empty actor login is always unauthorized."""
        project = _make_project(["alice"])
        assert is_authorized_status_actor("", project) is False

    def test_none_project_only_bot_is_authorized(self):
        """When project is None, only the bot is authorized."""
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
            assert is_authorized_status_actor("oompah", None) is True
            assert is_authorized_status_actor("alice", None) is False

    def test_project_without_attribute_only_bot_is_authorized(self):
        """When project has no status_label_authorized_logins, only the bot."""
        project = MagicMock(spec=[])  # no attributes
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
            assert is_authorized_status_actor("oompah", project) is True
            assert is_authorized_status_actor("alice", project) is False

    def test_empty_allowlist_only_bot_is_authorized(self):
        """Empty allowlist means only the bot is authorized."""
        project = _make_project([])
        with patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}):
            assert is_authorized_status_actor("oompah", project) is True
            assert is_authorized_status_actor("alice", project) is False

    def test_multiple_logins_all_authorized(self):
        """All logins in the allowlist are authorized."""
        project = _make_project(["alice", "bob", "charlie"])
        for login in ("alice", "bob", "charlie"):
            assert is_authorized_status_actor(login, project) is True
        assert is_authorized_status_actor("dave", project) is False
