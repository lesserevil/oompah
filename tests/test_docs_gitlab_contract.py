"""Documentation contract tests for GitLab operator documentation (OOMPAH-328).

These tests assert that required security guidance and configuration documentation
is present in user-facing docs. They function as living contracts: if the
documented minimum requirements change, these tests must be updated to match.

Covered documents:
- docs/project-bootstrap.md  — GitLab section
- docs/managed-project-onboarding.md — GitLab intake section
- docs/operator-runbook.md — GitLab configuration guidance
- docs/gitlab-issue-intake.md — GitLab intake prerequisites
"""

from __future__ import annotations

from pathlib import Path

import pytest

DOCS_ROOT = Path(__file__).parent.parent / "docs"


def _read_doc(name: str) -> str:
    path = DOCS_ROOT / name
    assert path.exists(), f"Expected doc not found: {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# docs/project-bootstrap.md
# ---------------------------------------------------------------------------


class TestProjectBootstrapDocGitLab:
    """docs/project-bootstrap.md must cover GitLab bootstrap requirements."""

    @pytest.fixture(autouse=True)
    def doc(self):
        self.text = _read_doc("project-bootstrap.md")

    def test_gitlab_section_exists(self):
        assert "GitLab" in self.text, (
            "docs/project-bootstrap.md must have a GitLab section"
        )

    def test_minimum_token_scopes_documented(self):
        # Must mention 'api' scope as the minimum requirement
        assert "api" in self.text.lower(), (
            "docs/project-bootstrap.md must document the minimum GitLab token scope ('api')"
        )

    def test_merge_train_non_support_documented(self):
        assert (
            "merge train" in self.text.lower()
            or "merge-train" in self.text.lower()
        ), (
            "docs/project-bootstrap.md must document that merge trains are not supported in v1"
        )

    def test_auto_merge_semantics_documented(self):
        # Must mention merge-when-pipeline-succeeds or auto-merge
        assert (
            "merge_when_pipeline_succeeds" in self.text
            or "merge-when-pipeline-succeeds" in self.text
            or "auto-merge" in self.text.lower()
            or "auto merge" in self.text.lower()
        ), (
            "docs/project-bootstrap.md must document GitLab auto-merge semantics "
            "(merge-when-pipeline-succeeds)"
        )

    def test_webhook_url_requirement_documented(self):
        assert "OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL" in self.text, (
            "docs/project-bootstrap.md must document the "
            "OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL configuration requirement"
        )

    def test_webhook_https_requirement_documented(self):
        # The webhook URL must require HTTPS — security contract
        assert "https" in self.text.lower(), (
            "docs/project-bootstrap.md must document that GitLab webhook URLs require HTTPS"
        )

    def test_recovery_procedures_exist(self):
        # Must have some recovery or troubleshooting guidance
        assert (
            "recovery" in self.text.lower()
            or "troubleshoot" in self.text.lower()
            or "remediation" in self.text.lower()
            or "fix" in self.text.lower()
        ), (
            "docs/project-bootstrap.md must include GitLab recovery/troubleshooting procedures"
        )

    def test_github_compatibility_note(self):
        # Must note that GitHub projects are unaffected
        assert "GitHub" in self.text, (
            "docs/project-bootstrap.md must document GitHub compatibility "
            "(existing GitHub projects unaffected)"
        )

    def test_state_branch_push_documented(self):
        # Must mention the state branch push requirement
        assert (
            "state" in self.text.lower()
            and "branch" in self.text.lower()
        ), (
            "docs/project-bootstrap.md must document state-branch push requirements"
        )

    def test_dry_run_documented(self):
        assert "dry" in self.text.lower() or "dry-run" in self.text.lower(), (
            "docs/project-bootstrap.md must document the dry-run bootstrap check option"
        )


# ---------------------------------------------------------------------------
# docs/gitlab-issue-intake.md
# ---------------------------------------------------------------------------


class TestGitLabIntakeDocContract:
    """docs/gitlab-issue-intake.md must document security prerequisites."""

    @pytest.fixture(autouse=True)
    def doc(self):
        self.text = _read_doc("gitlab-issue-intake.md")

    def test_token_scope_requirement(self):
        # Must mention 'api' as minimum scope
        assert "'api'" in self.text or '"api"' in self.text or "`api`" in self.text, (
            "docs/gitlab-issue-intake.md must document that the GitLab token "
            "requires at minimum 'api' scope"
        )

    def test_webhook_secret_requirement(self):
        assert "webhook_secret" in self.text or "webhook secret" in self.text.lower(), (
            "docs/gitlab-issue-intake.md must document the webhook_secret requirement"
        )

    def test_https_webhook_url_requirement(self):
        assert "OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL" in self.text, (
            "docs/gitlab-issue-intake.md must document OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL"
        )

    def test_webhook_fails_closed_without_secret(self):
        # The doc must note that missing secrets cause auth failures
        assert (
            "401" in self.text
            or "secret" in self.text.lower()
            and ("fail" in self.text.lower() or "reject" in self.text.lower())
        ), (
            "docs/gitlab-issue-intake.md must document that webhooks fail closed "
            "when no secret is configured"
        )

    def test_self_managed_guidance(self):
        assert (
            "self-managed" in self.text.lower()
            or "self managed" in self.text.lower()
            or "forge_base_url" in self.text
        ), (
            "docs/gitlab-issue-intake.md must document self-managed GitLab configuration"
        )


# ---------------------------------------------------------------------------
# docs/managed-project-onboarding.md
# ---------------------------------------------------------------------------


class TestOnboardingDocGitLabContract:
    """docs/managed-project-onboarding.md must cover GitLab intake guidance."""

    @pytest.fixture(autouse=True)
    def doc(self):
        self.text = _read_doc("managed-project-onboarding.md")

    def test_gitlab_intake_mentioned(self):
        assert "GitLab" in self.text, (
            "docs/managed-project-onboarding.md must mention GitLab intake"
        )

    def test_gitlab_intake_doc_referenced(self):
        assert "gitlab-issue-intake" in self.text.lower(), (
            "docs/managed-project-onboarding.md must reference the GitLab intake doc"
        )

    def test_gitlab_token_requirement_mentioned(self):
        assert (
            "gitlab" in self.text.lower()
            and "token" in self.text.lower()
        ), (
            "docs/managed-project-onboarding.md must mention GitLab token requirements"
        )


# ---------------------------------------------------------------------------
# docs/operator-runbook.md
# ---------------------------------------------------------------------------


class TestOperatorRunbookGitLabContract:
    """docs/operator-runbook.md must include GitLab configuration guidance."""

    @pytest.fixture(autouse=True)
    def doc(self):
        self.text = _read_doc("operator-runbook.md")

    def test_github_token_documented(self):
        # The existing GITHUB_TOKEN documentation must still be present
        assert "GITHUB_TOKEN" in self.text, (
            "docs/operator-runbook.md must still document GITHUB_TOKEN "
            "(GitHub compatibility preserved)"
        )

    def test_gitlab_token_documented(self):
        assert (
            "GITLAB_TOKEN" in self.text
            or "gitlab_token" in self.text.lower()
            or ("GitLab" in self.text and "token" in self.text.lower())
        ), (
            "docs/operator-runbook.md must document GitLab token configuration"
        )

    def test_forge_kind_documented(self):
        assert "forge_kind" in self.text or "forge-kind" in self.text.lower() or "GitLab" in self.text, (
            "docs/operator-runbook.md must mention forge_kind or GitLab configuration"
        )
