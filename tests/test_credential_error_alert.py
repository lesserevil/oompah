"""Tests for credential-error alert detection (TASK-404).

When an agent/task is retrying with a credential-related error (e.g.
``OpenAIError: Missing credentials``), ``get_snapshot()`` must include an
alert with ``source`` starting with ``cred_error:`` so the dashboard can
surface a visible warning banner.  The alert must clear automatically once
the task is no longer retrying.

Acceptance criteria verified here:
- Credential error in retry_attempts → cred_error alert in snapshot
- Non-credential error → no cred_error alert
- No retrying tasks → no cred_error alert
- Alert message identifies the affected task identifier
- Alert message does NOT contain API keys, tokens, or raw provider config
- _is_credential_error covers common credential-error patterns
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.models import AgentProfile, ModelProvider, RetryEntry
from oompah.orchestrator import Orchestrator, _is_credential_error


# ---------------------------------------------------------------------------
# Module-level helper function — _is_credential_error
# ---------------------------------------------------------------------------


class TestIsCredentialError:
    """Unit tests for the _is_credential_error() helper."""

    def test_missing_credentials_phrase(self):
        assert _is_credential_error(
            "OpenAIError: Missing credentials. Please pass an `api_key`"
        )

    def test_authentication_error_phrase(self):
        assert _is_credential_error("AuthenticationError: invalid API key")

    def test_authentication_error_class_only(self):
        assert _is_credential_error("authenticationerror")

    def test_authentication_error_underscore(self):
        assert _is_credential_error("authentication_error: bad key")

    def test_invalid_api_key(self):
        assert _is_credential_error("Error: invalid api key provided")

    def test_incorrect_api_key(self):
        assert _is_credential_error("incorrect api key specified")

    def test_authentication_failed(self):
        assert _is_credential_error("Authentication failed: no token")

    def test_invalid_api_key_underscore(self):
        assert _is_credential_error("invalid_api_key")

    def test_no_api_key(self):
        assert _is_credential_error("No api key found in environment")

    def test_api_key_not_found(self):
        assert _is_credential_error("api key not found")

    def test_permission_denied_is_not_credential(self):
        # HTTP 403 / OS permission errors are NOT credential failures.
        assert not _is_credential_error("PermissionDenied: 403")

    def test_access_denied_is_not_credential(self):
        # Generic filesystem / HTTP access-denied is too broad to match.
        assert not _is_credential_error("access denied for resource")

    def test_case_insensitive(self):
        assert _is_credential_error("MISSING CREDENTIALS")
        assert _is_credential_error("AuthenticationError")
        assert _is_credential_error("INVALID API KEY")

    def test_rate_limit_error_is_not_credential(self):
        assert not _is_credential_error("429: rate limit exceeded")

    def test_generic_error_is_not_credential(self):
        assert not _is_credential_error("timed out")

    def test_connection_refused_is_not_credential(self):
        assert not _is_credential_error(
            "URL error: [Errno 61] Connection refused"
        )

    def test_empty_string_is_false(self):
        assert not _is_credential_error("")

    def test_none_is_false(self):
        assert not _is_credential_error(None)

    def test_max_turns_is_not_credential(self):
        assert not _is_credential_error("max_turns")

    def test_stalled_is_not_credential(self):
        assert not _is_credential_error("stalled")


# ---------------------------------------------------------------------------
# Orchestrator.get_snapshot() — credential-error alerts
# ---------------------------------------------------------------------------


def _make_orchestrator(tmp_path) -> Orchestrator:
    """Minimal Orchestrator with mocked stores."""
    project_store = MagicMock()
    project_store.list_all.return_value = []

    cfg = ServiceConfig()
    cfg.agent_profiles = [
        AgentProfile(name="default", command="cli", provider_id=None)
    ]

    orch = Orchestrator(
        config=cfg,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )

    mock_ps = MagicMock()
    mock_ps.get_default.return_value = None
    orch.provider_store = mock_ps

    return orch


def _add_retry(
    orch: Orchestrator,
    issue_id: str = "issue-1",
    identifier: str = "TASK-389",
    attempt: int = 1,
    error: str | None = None,
) -> None:
    """Insert a RetryEntry directly into the orchestrator state (no timer needed)."""
    import time

    orch.state.retry_attempts[issue_id] = RetryEntry(
        issue_id=issue_id,
        identifier=identifier,
        attempt=attempt,
        due_at_ms=time.monotonic() * 1000 + 60_000,
        timer_handle=None,
        error=error,
    )


class TestGetSnapshotCredentialAlerts:
    """get_snapshot() must inject cred_error alerts for credential-related retries."""

    def test_credential_error_retry_produces_alert(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        _add_retry(
            orch,
            issue_id="issue-1",
            identifier="TASK-389",
            attempt=2,
            error="OpenAIError: Missing credentials. Please pass an `api_key`",
        )
        snapshot = orch.get_snapshot()
        cred_alerts = [
            a for a in snapshot["alerts"]
            if a.get("source", "").startswith("cred_error:")
        ]
        assert len(cred_alerts) == 1, "expected exactly one credential alert"
        alert = cred_alerts[0]
        assert alert["level"] == "error"
        assert "TASK-389" in alert["message"]
        assert "credentials" in alert["message"].lower() or "credential" in alert["message"].lower()

    def test_alert_message_includes_task_identifier(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        _add_retry(
            orch,
            identifier="TASK-397",
            error="AuthenticationError: invalid api key",
        )
        snapshot = orch.get_snapshot()
        cred_alerts = [
            a for a in snapshot["alerts"]
            if a.get("source", "").startswith("cred_error:")
        ]
        assert any("TASK-397" in a["message"] for a in cred_alerts)

    def test_alert_source_encodes_identifier(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        _add_retry(
            orch,
            issue_id="issue-1",
            identifier="TASK-389",
            error="Missing credentials",
        )
        snapshot = orch.get_snapshot()
        cred_alerts = [
            a for a in snapshot["alerts"]
            if a.get("source", "").startswith("cred_error:")
        ]
        assert cred_alerts[0]["source"] == "cred_error:TASK-389"

    def test_non_credential_error_produces_no_cred_alert(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        _add_retry(
            orch,
            identifier="TASK-389",
            error="timed out after 300s",
        )
        snapshot = orch.get_snapshot()
        cred_alerts = [
            a for a in snapshot["alerts"]
            if a.get("source", "").startswith("cred_error:")
        ]
        assert cred_alerts == [], "timeout error should not produce a credential alert"

    def test_no_retrying_tasks_produces_no_cred_alert(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        # No retry_attempts added
        snapshot = orch.get_snapshot()
        cred_alerts = [
            a for a in snapshot["alerts"]
            if a.get("source", "").startswith("cred_error:")
        ]
        assert cred_alerts == []

    def test_multiple_credential_retries_produce_multiple_alerts(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        _add_retry(
            orch,
            issue_id="issue-1",
            identifier="TASK-389",
            attempt=1,
            error="Missing credentials",
        )
        _add_retry(
            orch,
            issue_id="issue-2",
            identifier="TASK-397",
            attempt=2,
            error="AuthenticationError",
        )
        snapshot = orch.get_snapshot()
        cred_alerts = [
            a for a in snapshot["alerts"]
            if a.get("source", "").startswith("cred_error:")
        ]
        assert len(cred_alerts) == 2
        identifiers_in_alerts = {a["message"] for a in cred_alerts}
        # Both task identifiers must appear somewhere in the alerts
        assert any("TASK-389" in m for m in identifiers_in_alerts)
        assert any("TASK-397" in m for m in identifiers_in_alerts)

    def test_cred_alert_clears_when_retry_removed(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        _add_retry(
            orch,
            issue_id="issue-1",
            identifier="TASK-389",
            error="Missing credentials",
        )
        # Alert is present while the retry is pending
        snap_before = orch.get_snapshot()
        assert any(
            a.get("source", "").startswith("cred_error:")
            for a in snap_before["alerts"]
        )
        # Remove the retry (simulating a successful run)
        del orch.state.retry_attempts["issue-1"]
        snap_after = orch.get_snapshot()
        assert not any(
            a.get("source", "").startswith("cred_error:")
            for a in snap_after["alerts"]
        ), "credential alert must clear once the retry is no longer pending"

    def test_alert_message_does_not_contain_raw_credentials(self, tmp_path):
        """Alert message must NOT echo back raw credential values."""
        orch = _make_orchestrator(tmp_path)
        secret_api_key = "sk-secret-api-key-value-12345"  # pragma: allowlist secret
        _add_retry(
            orch,
            identifier="TASK-389",
            error=f"AuthenticationError: invalid api key '{secret_api_key}'",
        )
        snapshot = orch.get_snapshot()
        cred_alerts = [
            a for a in snapshot["alerts"]
            if a.get("source", "").startswith("cred_error:")
        ]
        assert cred_alerts, "should have a cred alert"
        for alert in cred_alerts:
            assert secret_api_key not in alert["message"], (
                "alert message must not contain the raw API key value"
            )

    def test_existing_alerts_preserved_alongside_cred_alerts(self, tmp_path):
        """Credential alerts are additive — they must not replace existing alerts."""
        orch = _make_orchestrator(tmp_path)
        orch._alerts = [
            {"level": "warning", "source": "rate_limit", "message": "Rate limited"}
        ]
        _add_retry(
            orch,
            identifier="TASK-389",
            error="Missing credentials",
        )
        snapshot = orch.get_snapshot()
        sources = [a.get("source") for a in snapshot["alerts"]]
        assert "rate_limit" in sources
        assert any(s.startswith("cred_error:") for s in sources)

    def test_snapshot_retrying_array_still_present(self, tmp_path):
        """get_snapshot() retrying array must still be populated correctly."""
        orch = _make_orchestrator(tmp_path)
        _add_retry(
            orch,
            issue_id="issue-1",
            identifier="TASK-389",
            attempt=3,
            error="Missing credentials",
        )
        snapshot = orch.get_snapshot()
        assert snapshot["counts"]["retrying"] == 1
        assert snapshot["retrying"][0]["issue_identifier"] == "TASK-389"
