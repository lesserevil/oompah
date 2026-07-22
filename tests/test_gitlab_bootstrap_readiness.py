"""Tests for GitLab bootstrap readiness checks (OOMPAH-328).

Covers:
- check_gitlab_readiness() success scenario (all capabilities pass)
- Each capability failure scenario (dry-run + non-dry-run)
- Short-circuit: API access failure skips remaining checks
- webhook_url check (HTTPS required, empty URL fails)
- hook_create skipped when webhook_public_url not configured
- polling_fallback failure scenario
- dry_run mode avoids state-mutating calls
- Token values are never leaked in error messages
- Existing GitHub bootstrap/readiness tests remain green (no regressions here)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from oompah.project_bootstrap.gitlab_readiness import (
    CapabilityStatus,
    GitLabReadinessResult,
    MINIMUM_TOKEN_SCOPES,
    _check_api_access,
    _check_hook_create,
    _check_issue_access,
    _check_label_create,
    _check_mr_access,
    _check_pipeline_read,
    _check_polling_fallback,
    _check_state_branch_push,
    _check_webhook_url,
    check_gitlab_readiness,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_BASE_URL = "https://gitlab.example.com"
_TOKEN = "glpat-REDACTED-for-testing"
_NS = "my-group"
_PROJ = "my-repo"
_ENCODED = "my-group%2Fmy-repo"
_WEBHOOK_URL = "https://oompah.example.com"


def _mock_get(responses: dict[str, tuple[int, dict]]):
    """Return a mock for _gitlab_get that uses ``path`` as the lookup key."""
    def _fake_get(base_url, path, token, **kwargs):
        # Normalize: match on the path portion only (strip query string).
        key = path.split("?")[0]
        for k, v in responses.items():
            if key.endswith(k) or k in key:
                return v
        return (404, {})
    return _fake_get


def _mock_post(responses: dict[str, tuple[int, dict]]):
    """Return a mock for _gitlab_post that uses ``path`` as the lookup key."""
    def _fake_post(base_url, path, token, data=None, **kwargs):
        key = path.split("?")[0]
        for k, v in responses.items():
            if key.endswith(k) or k in key:
                return v
        return (404, {})
    return _fake_post


# ---------------------------------------------------------------------------
# check_gitlab_readiness — full success path
# ---------------------------------------------------------------------------


class TestCheckGitLabReadinessSuccess:
    """Full success: every capability returns ok."""

    def test_all_ok_dry_run(self):
        get_responses = {
            "/api/v4/user": (200, {"id": 1, "username": "bot"}),
            "/labels": (200, [{"id": 10, "name": "oompah:status:open"}]),
            "/issues": (200, []),
            "/merge_requests": (200, []),
            "/pipelines": (200, []),
            "/api/v4/projects/": (200, {
                "permissions": {
                    "project_access": {"access_level": 40},
                    "group_access": None,
                }
            }),
            "/protected_branches": (200, []),
            "/hooks": (200, []),
            "/branches": (200, [{"name": "main"}]),
        }
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            side_effect=_mock_get(get_responses),
        ):
            result = check_gitlab_readiness(
                forge_base_url=_BASE_URL,
                token=_TOKEN,
                namespace=_NS,
                project_name=_PROJ,
                webhook_public_url=_WEBHOOK_URL,
                dry_run=True,
            )

        assert isinstance(result, GitLabReadinessResult)
        assert result.all_ok is True
        assert result.dry_run is True
        failed = result.failed_capabilities()
        assert failed == [], f"Unexpected failures: {[c.name for c in failed]}"
        # All names should be covered
        names = {c.name for c in result.capabilities}
        assert "api_access" in names
        assert "label_create" in names
        assert "issue_access" in names
        assert "mr_access" in names
        assert "pipeline_read" in names
        assert "state_branch_push" in names
        assert "webhook_url" in names
        assert "hook_create" in names
        assert "polling_fallback" in names

    def test_summary_reports_all_ok(self):
        get_responses = {
            "/api/v4/user": (200, {"id": 1, "username": "bot"}),
            "/labels": (200, []),
            "/issues": (200, []),
            "/merge_requests": (200, []),
            "/pipelines": (200, []),
            "/api/v4/projects/": (200, {
                "permissions": {
                    "project_access": {"access_level": 40},
                    "group_access": None,
                }
            }),
            "/protected_branches": (200, []),
            "/hooks": (200, []),
            "/branches": (200, []),
        }
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            side_effect=_mock_get(get_responses),
        ):
            result = check_gitlab_readiness(
                forge_base_url=_BASE_URL,
                token=_TOKEN,
                namespace=_NS,
                project_name=_PROJ,
                webhook_public_url=_WEBHOOK_URL,
                dry_run=True,
            )

        summary = result.summary()
        assert "All checks passed" in summary
        assert "dry-run" in summary

    def test_raises_on_non_https_base_url(self):
        with pytest.raises(ValueError, match="https"):
            check_gitlab_readiness(
                forge_base_url="http://gitlab.example.com",
                token=_TOKEN,
                namespace=_NS,
                project_name=_PROJ,
            )


# ---------------------------------------------------------------------------
# API access failures
# ---------------------------------------------------------------------------


class TestApiAccessFailures:
    """check_gitlab_readiness short-circuits on API access failure."""

    def test_401_fails_with_remediation(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(401, {}),
        ):
            result = check_gitlab_readiness(
                forge_base_url=_BASE_URL,
                token=_TOKEN,
                namespace=_NS,
                project_name=_PROJ,
                dry_run=True,
            )

        assert result.all_ok is False
        api = next(c for c in result.capabilities if c.name == "api_access")
        assert api.status == CapabilityStatus.failed
        assert "401" in api.message
        assert api.remediation  # remediation is non-empty
        # Token must NOT appear in the error message
        assert _TOKEN not in api.message
        assert _TOKEN not in api.remediation

    def test_401_skips_downstream_api_checks(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(401, {}),
        ):
            result = check_gitlab_readiness(
                forge_base_url=_BASE_URL,
                token=_TOKEN,
                namespace=_NS,
                project_name=_PROJ,
                dry_run=True,
            )

        skipped = {c.name for c in result.capabilities if c.status == CapabilityStatus.skipped}
        assert "label_create" in skipped
        assert "issue_access" in skipped
        assert "mr_access" in skipped
        assert "pipeline_read" in skipped
        assert "state_branch_push" in skipped
        assert "hook_create" in skipped
        assert "polling_fallback" in skipped

    def test_unreachable_host_fails(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(0, {}),
        ):
            result = check_gitlab_readiness(
                forge_base_url=_BASE_URL,
                token=_TOKEN,
                namespace=_NS,
                project_name=_PROJ,
                dry_run=True,
            )

        api = next(c for c in result.capabilities if c.name == "api_access")
        assert api.status == CapabilityStatus.failed
        assert "reach" in api.message.lower() or "cannot" in api.message.lower()


# ---------------------------------------------------------------------------
# Label create failures
# ---------------------------------------------------------------------------


class TestLabelCreateFailures:
    """_check_label_create returns failure on 403."""

    def test_403_dry_run_fails(self):
        result = _check_label_create(
            _BASE_URL, _TOKEN, _ENCODED, dry_run=True
        )
        # We need to mock the GET call
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(403, {}),
        ):
            result = _check_label_create(
                _BASE_URL, _TOKEN, _ENCODED, dry_run=True
            )
        assert result.status == CapabilityStatus.failed
        assert "403" in result.message
        assert "Developer" in result.remediation or "Maintainer" in result.remediation

    def test_200_dry_run_passes(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(200, []),
        ):
            result = _check_label_create(
                _BASE_URL, _TOKEN, _ENCODED, dry_run=True
            )
        assert result.status == CapabilityStatus.ok
        assert "dry-run" in result.message

    def test_create_and_delete_non_dry_run(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_post",
            return_value=(201, {"id": 99, "name": "oompah-bootstrap-probe"}),
        ), patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_delete",
            return_value=204,
        ):
            result = _check_label_create(
                _BASE_URL, _TOKEN, _ENCODED, dry_run=False
            )
        assert result.status == CapabilityStatus.ok

    def test_409_conflict_treated_as_ok(self):
        """409 means the label already exists — still has create permission."""
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_post",
            return_value=(409, {}),
        ):
            result = _check_label_create(
                _BASE_URL, _TOKEN, _ENCODED, dry_run=False
            )
        assert result.status == CapabilityStatus.ok

    def test_403_non_dry_run_fails(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_post",
            return_value=(403, {}),
        ):
            result = _check_label_create(
                _BASE_URL, _TOKEN, _ENCODED, dry_run=False
            )
        assert result.status == CapabilityStatus.failed
        assert "403" in result.message


# ---------------------------------------------------------------------------
# Issue access failures
# ---------------------------------------------------------------------------


class TestIssueAccessFailures:
    def test_403_fails(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(403, {}),
        ):
            result = _check_issue_access(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.failed
        assert "403" in result.message
        assert result.remediation

    def test_404_project_not_found(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(404, {}),
        ):
            result = _check_issue_access(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.failed
        assert "404" in result.message
        assert "namespace" in result.remediation.lower() or "name" in result.remediation.lower()

    def test_200_passes(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(200, []),
        ):
            result = _check_issue_access(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.ok


# ---------------------------------------------------------------------------
# MR access failures
# ---------------------------------------------------------------------------


class TestMRAccessFailures:
    def test_403_fails(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(403, {}),
        ):
            result = _check_mr_access(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.failed
        assert "403" in result.message
        assert result.remediation

    def test_200_passes(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(200, []),
        ):
            result = _check_mr_access(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.ok


# ---------------------------------------------------------------------------
# Pipeline read failures
# ---------------------------------------------------------------------------


class TestPipelineReadFailures:
    def test_403_fails_with_ci_guidance(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(403, {}),
        ):
            result = _check_pipeline_read(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.failed
        assert "403" in result.message
        assert "CI" in result.remediation or "pipeline" in result.remediation.lower()

    def test_200_passes(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(200, []),
        ):
            result = _check_pipeline_read(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.ok


# ---------------------------------------------------------------------------
# State-branch push failures
# ---------------------------------------------------------------------------


class TestStateBranchPushFailures:
    def test_developer_access_level_passes(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(200, {
                "permissions": {
                    "project_access": {"access_level": 30},  # Developer
                    "group_access": None,
                }
            }),
        ):
            result = _check_state_branch_push(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.ok
        assert "30" in result.message

    def test_reporter_access_level_fails(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(200, {
                "permissions": {
                    "project_access": {"access_level": 20},  # Reporter
                    "group_access": None,
                }
            }),
        ):
            result = _check_state_branch_push(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.failed
        assert "20" in result.message
        assert "30" in result.message or "Developer" in result.remediation

    def test_group_access_used_as_fallback(self):
        """Group access_level can grant push even when project_access is None."""
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(200, {
                "permissions": {
                    "project_access": None,
                    "group_access": {"access_level": 40},  # Maintainer
                }
            }),
        ):
            result = _check_state_branch_push(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.ok
        assert "40" in result.message

    def test_zero_access_level_falls_back_to_protected_branches(self):
        """access_level=0 falls back to protected-branches API check."""
        call_count = [0]

        def mock_get(base_url, path, token, **kwargs):
            call_count[0] += 1
            if "projects/" in path and "branches" not in path and "hooks" not in path and "labels" not in path and "issues" not in path and "merge_requests" not in path and "pipelines" not in path:
                # Project detail call
                return (200, {"permissions": {"project_access": {"access_level": 0}, "group_access": None}})
            if "protected_branches" in path:
                return (200, [])
            return (404, {})

        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            side_effect=mock_get,
        ):
            result = _check_state_branch_push(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.ok
        assert "inferred" in result.message

    def test_403_on_project_detail_fails(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(403, {}),
        ):
            result = _check_state_branch_push(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.failed

    def test_remediation_mentions_state_branch_and_push(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(200, {
                "permissions": {
                    "project_access": {"access_level": 20},
                    "group_access": None,
                }
            }),
        ):
            result = _check_state_branch_push(_BASE_URL, _TOKEN, _ENCODED)
        assert "state" in result.remediation.lower() or "push" in result.remediation.lower()


# ---------------------------------------------------------------------------
# Webhook URL check
# ---------------------------------------------------------------------------


class TestWebhookURLCheck:
    def test_no_url_fails_with_remediation(self):
        result = _check_webhook_url(None)
        assert result.status == CapabilityStatus.failed
        assert "OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL" in result.message
        assert "https" in result.remediation.lower()

    def test_empty_string_fails(self):
        result = _check_webhook_url("")
        assert result.status == CapabilityStatus.failed

    def test_http_url_fails(self):
        result = _check_webhook_url("http://example.com")
        assert result.status == CapabilityStatus.failed
        assert "https" in result.message.lower() or "http" in result.message.lower()

    def test_https_url_passes(self):
        result = _check_webhook_url("https://oompah.example.com")
        assert result.status == CapabilityStatus.ok
        assert "oompah.example.com" in result.message

    def test_https_url_with_path_passes(self):
        result = _check_webhook_url("https://oompah.example.com/hooks")
        assert result.status == CapabilityStatus.ok

    def test_url_without_hostname_fails(self):
        result = _check_webhook_url("https://")
        assert result.status == CapabilityStatus.failed


# ---------------------------------------------------------------------------
# Hook create failures
# ---------------------------------------------------------------------------


class TestHookCreateFailures:
    def test_skipped_when_no_webhook_url(self):
        result = _check_hook_create(
            _BASE_URL, _TOKEN, _ENCODED,
            dry_run=True,
            webhook_public_url=None,
        )
        assert result.status == CapabilityStatus.skipped

    def test_dry_run_reads_list_403_fails(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(403, {}),
        ):
            result = _check_hook_create(
                _BASE_URL, _TOKEN, _ENCODED,
                dry_run=True,
                webhook_public_url=_WEBHOOK_URL,
            )
        assert result.status == CapabilityStatus.failed
        assert "Maintainer" in result.remediation

    def test_dry_run_200_passes(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(200, []),
        ):
            result = _check_hook_create(
                _BASE_URL, _TOKEN, _ENCODED,
                dry_run=True,
                webhook_public_url=_WEBHOOK_URL,
            )
        assert result.status == CapabilityStatus.ok
        assert "dry-run" in result.message

    def test_non_dry_run_creates_and_deletes_probe(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_post",
            return_value=(201, {"id": 42}),
        ) as mock_post, patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_delete",
            return_value=204,
        ) as mock_delete:
            result = _check_hook_create(
                _BASE_URL, _TOKEN, _ENCODED,
                dry_run=False,
                webhook_public_url=_WEBHOOK_URL,
            )
        assert result.status == CapabilityStatus.ok
        # Probe was created
        mock_post.assert_called_once()
        # Probe was deleted afterwards
        mock_delete.assert_called_once()
        # Probe URL should NOT be the real webhook URL - it uses a probe path
        call_data = mock_post.call_args[0][3]  # 4th positional arg = data dict
        assert "_oompah_probe" in call_data.get("url", "")

    def test_non_dry_run_403_fails(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_post",
            return_value=(403, {}),
        ):
            result = _check_hook_create(
                _BASE_URL, _TOKEN, _ENCODED,
                dry_run=False,
                webhook_public_url=_WEBHOOK_URL,
            )
        assert result.status == CapabilityStatus.failed
        assert "Maintainer" in result.remediation

    def test_422_from_gitlab_url_validation(self):
        """422 typically means GitLab rejected the URL (e.g. local IP blocked)."""
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_post",
            return_value=(422, {}),
        ):
            result = _check_hook_create(
                _BASE_URL, _TOKEN, _ENCODED,
                dry_run=False,
                webhook_public_url=_WEBHOOK_URL,
            )
        assert result.status == CapabilityStatus.failed
        assert "422" in result.message
        assert "reachable" in result.remediation.lower() or "public" in result.remediation.lower()


# ---------------------------------------------------------------------------
# Polling fallback failures
# ---------------------------------------------------------------------------


class TestPollingFallbackFailures:
    def test_403_fails_with_guidance(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(403, {}),
        ):
            result = _check_polling_fallback(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.failed
        assert "403" in result.message
        assert "poll" in result.remediation.lower() or "Reporter" in result.remediation

    def test_200_passes(self):
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(200, []),
        ):
            result = _check_polling_fallback(_BASE_URL, _TOKEN, _ENCODED)
        assert result.status == CapabilityStatus.ok
        assert "poll" in result.message.lower()


# ---------------------------------------------------------------------------
# Security: token never appears in output
# ---------------------------------------------------------------------------


class TestTokenSecurityNeverLeaked:
    """Token values must never appear in error messages or remediation strings."""

    def test_token_not_in_api_access_failure(self):
        secret_token = "glpat-SUPER-SECRET-DO-NOT-LOG"
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(401, {}),
        ):
            result = _check_api_access(_BASE_URL, secret_token)
        assert secret_token not in result.message
        assert secret_token not in result.remediation

    def test_token_not_in_any_result_on_full_failure(self):
        secret_token = "glpat-SUPER-SECRET-DO-NOT-LOG"
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            return_value=(401, {}),
        ):
            result = check_gitlab_readiness(
                forge_base_url=_BASE_URL,
                token=secret_token,
                namespace=_NS,
                project_name=_PROJ,
                dry_run=True,
            )
        full_output = result.summary()
        assert secret_token not in full_output
        for cap in result.capabilities:
            assert secret_token not in cap.message
            assert secret_token not in cap.remediation


# ---------------------------------------------------------------------------
# Minimum token scopes documented
# ---------------------------------------------------------------------------


class TestMinimumTokenScopesDocumented:
    """MINIMUM_TOKEN_SCOPES must document the 'api' scope."""

    def test_api_scope_in_minimum_token_scopes(self):
        assert "api" in MINIMUM_TOKEN_SCOPES

    def test_minimum_token_scopes_is_non_empty(self):
        assert len(MINIMUM_TOKEN_SCOPES) > 0


# ---------------------------------------------------------------------------
# check_gitlab_readiness with webhook_url from environment
# ---------------------------------------------------------------------------


class TestWebhookURLFromEnvironment:
    """When webhook_public_url=None, resolve from OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL."""

    def test_env_var_is_used_when_kwarg_not_set(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL", "https://env-hook.example.com")
        get_responses = {
            "/api/v4/user": (200, {"id": 1, "username": "bot"}),
            "/labels": (200, []),
            "/issues": (200, []),
            "/merge_requests": (200, []),
            "/pipelines": (200, []),
            "/api/v4/projects/": (200, {
                "permissions": {
                    "project_access": {"access_level": 40},
                    "group_access": None,
                }
            }),
            "/protected_branches": (200, []),
            "/hooks": (200, []),
            "/branches": (200, []),
        }
        with patch(
            "oompah.project_bootstrap.gitlab_readiness._gitlab_get",
            side_effect=_mock_get(get_responses),
        ):
            result = check_gitlab_readiness(
                forge_base_url=_BASE_URL,
                token=_TOKEN,
                namespace=_NS,
                project_name=_PROJ,
                webhook_public_url=None,
                dry_run=True,
            )
        webhook_cap = next(c for c in result.capabilities if c.name == "webhook_url")
        assert webhook_cap.status == CapabilityStatus.ok
        assert "env-hook.example.com" in webhook_cap.message


# ---------------------------------------------------------------------------
# GitLabReadinessResult helpers
# ---------------------------------------------------------------------------


class TestGitLabReadinessResultHelpers:
    def test_failed_capabilities_filters_correctly(self):
        from oompah.project_bootstrap.gitlab_readiness import CapabilityResult
        result = GitLabReadinessResult(
            all_ok=False,
            capabilities=[
                CapabilityResult("api_access", CapabilityStatus.ok, "ok"),
                CapabilityResult("label_create", CapabilityStatus.failed, "fail"),
                CapabilityResult("issue_access", CapabilityStatus.skipped, "skip"),
            ],
        )
        failed = result.failed_capabilities()
        assert len(failed) == 1
        assert failed[0].name == "label_create"

    def test_summary_contains_failure_indicator(self):
        from oompah.project_bootstrap.gitlab_readiness import CapabilityResult
        result = GitLabReadinessResult(
            all_ok=False,
            capabilities=[
                CapabilityResult(
                    "api_access",
                    CapabilityStatus.failed,
                    "Token auth failed",
                    "Create a token",
                ),
            ],
        )
        summary = result.summary()
        assert "failed" in summary.lower()
        assert "Token auth failed" in summary
        assert "Create a token" in summary

    def test_summary_dry_run_note(self):
        from oompah.project_bootstrap.gitlab_readiness import CapabilityResult
        result = GitLabReadinessResult(
            all_ok=True,
            capabilities=[
                CapabilityResult("api_access", CapabilityStatus.ok, "ok"),
            ],
            dry_run=True,
        )
        summary = result.summary()
        assert "dry-run" in summary


# ---------------------------------------------------------------------------
# Public API import test
# ---------------------------------------------------------------------------


def test_public_imports_from_project_bootstrap_package():
    """check_gitlab_readiness is importable from oompah.project_bootstrap."""
    from oompah.project_bootstrap import (
        check_gitlab_readiness,
        CapabilityResult,
        CapabilityStatus,
        GitLabReadinessResult,
        MINIMUM_TOKEN_SCOPES,
    )
    assert callable(check_gitlab_readiness)
    assert "api" in MINIMUM_TOKEN_SCOPES
