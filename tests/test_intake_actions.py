"""Tests for intake action permission checks and audit comments."""

from __future__ import annotations

from types import SimpleNamespace

from oompah.intake_actions import (
    PROMOTE_TO_BACKLOG,
    REQUEST_CHANGES,
    REQUESTOR_APPROVE,
    action_permissions,
    build_audit_comment,
    check_permission,
    parse_audit_marker,
)
from oompah.models import Issue


def _project(owner: str = "owner", authorized: list[str] | None = None):
    return SimpleNamespace(
        tracker_owner=owner,
        status_label_authorized_logins=authorized or [],
    )


def _issue(state: str = "Proposed", requestor: str = "alice") -> Issue:
    return Issue(
        id="owner/repo#1",
        identifier="owner/repo#1",
        title="Proposed work",
        state=state,
        requestor_login=requestor,
    )


def test_requestor_can_approve_without_owner_permissions():
    project = _project(owner="owner", authorized=[])
    issue = _issue(requestor="alice")

    decision = check_permission(REQUESTOR_APPROVE, "alice", issue, project)

    assert decision.allowed is True


def test_non_requestor_cannot_use_requestor_approval():
    project = _project(owner="owner", authorized=["pm"])
    issue = _issue(requestor="alice")

    decision = check_permission(REQUESTOR_APPROVE, "pm", issue, project)

    assert decision.allowed is False
    assert decision.code == "not_requestor"


def test_project_owner_can_promote_to_backlog():
    project = _project(owner="owner", authorized=[])
    issue = _issue()

    decision = check_permission(PROMOTE_TO_BACKLOG, "owner", issue, project)

    assert decision.allowed is True


def test_allowlisted_owner_can_request_changes():
    project = _project(owner="owner", authorized=["pm"])
    issue = _issue()

    decision = check_permission(REQUEST_CHANGES, "pm", issue, project)

    assert decision.allowed is True


def test_unauthorized_user_cannot_perform_owner_action():
    project = _project(owner="owner", authorized=[])
    issue = _issue()

    decision = check_permission(PROMOTE_TO_BACKLOG, "mallory", issue, project)

    assert decision.allowed is False
    assert decision.code == "owner_required"


def test_intake_actions_only_apply_to_proposed_issues():
    project = _project(owner="owner", authorized=[])
    issue = _issue(state="Backlog")

    decision = check_permission(PROMOTE_TO_BACKLOG, "owner", issue, project)

    assert decision.allowed is False
    assert decision.code == "invalid_state"


def test_action_permissions_return_visibility_booleans_for_actor():
    project = _project(owner="owner", authorized=["pm"])
    issue = _issue(requestor="alice")

    requestor_perms = action_permissions(issue, project, "alice")
    owner_perms = action_permissions(issue, project, "pm")

    assert requestor_perms["can_requestor_approve"] is True
    assert requestor_perms["can_promote_to_backlog"] is False
    assert owner_perms["can_requestor_approve"] is False
    assert owner_perms["can_request_changes"] is True
    assert owner_perms["can_override_readiness"] is True
    assert owner_perms["can_promote_to_backlog"] is True


def test_audit_comment_contains_machine_readable_marker():
    issue = _issue(requestor="alice")

    comment = build_audit_comment(
        REQUESTOR_APPROVE,
        "alice",
        issue,
        message="Scope looks right.",
    )

    marker = parse_audit_marker(comment)
    assert marker == {"action": REQUESTOR_APPROVE, "actor": "alice"}
    assert "Intake action: requestor scope approval" in comment
    assert "Scope looks right." in comment
