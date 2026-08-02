"""Source-contract tests for dashboard WebSocket liveness handling."""

from __future__ import annotations

from pathlib import Path


def _dashboard_script() -> str:
    html = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")
    start = html.index("<script>") + len("<script>")
    end = html.rindex("</script>")
    return html[start:end]


def _connect_function(script: str) -> str:
    start = script.index("function connectWebSocket()")
    end = script.index("function selectedProjectFilterValue()", start)
    return script[start:end]


def test_heartbeat_tracks_freshness_and_closes_stale_socket():
    script = _dashboard_script()
    body = _connect_function(script)

    assert "wsHeartbeatTimer" in script
    assert "wsLastFreshAt" in script
    assert "WS_STALE_TIMEOUT_MS" in script
    assert "setInterval(checkWebSocketLiveness, WS_HEARTBEAT_INTERVAL_MS)" in body
    assert "Date.now() - wsLastFreshAt >= WS_STALE_TIMEOUT_MS" in script
    assert "socket.close()" in script
    assert "setWebSocketStatus('Reconnecting...')" in script


def test_reconnect_is_guarded_and_uses_bounded_backoff():
    script = _dashboard_script()

    assert "if (!wsShouldReconnect || wsReconnectTimer !== null) return;" in script
    assert "WS_RECONNECT_MAX_DELAY_MS" in script
    assert "Math.min(" in script
    assert "wsReconnectTimer = null;" in script
    assert "clearWebSocketReconnectTimer();" in script
    assert "ws.readyState === WebSocket.CLOSING" in script


def test_reconnect_requests_backfill_and_handles_navigation_lifecycle():
    script = _dashboard_script()
    body = _connect_function(script)

    assert "socket.send(JSON.stringify({action: 'refresh'}));" in body
    assert "window.addEventListener('pagehide'" in script
    assert "closeWebSocket({reconnect: false})" in script
    assert "window.addEventListener('pageshow'" in script
    assert "wsShouldReconnect = true;" in script
    assert "wsLastFreshAt = Date.now();" in body
    assert "msg.type === 'pong'" in body


def test_authenticated_ws_url_and_console_backfill_are_preserved():
    body = _connect_function(_dashboard_script())

    assert "location.protocol === 'https:' ? 'wss:' : 'ws:'" in body
    assert "location.host + '/ws'" in body
    assert "_backfillConsoleTranscript(_activeConsoleProject)" in body


def test_dashboard_tracks_epoch_delivery_and_applied_revisions():
    script = _dashboard_script()

    for name in (
        "wsEpoch",
        "wsDeliverySeq",
        "wsLastAppliedStateRevision",
        "wsLastAppliedIssueRevision",
        "wsReconciling",
        "wsBufferedMessages",
    ):
        assert name in script


def test_gap_and_regression_gate_incremental_messages_before_rendering():
    script = _dashboard_script()
    body = _connect_function(script)

    assert "_observeWebSocketEnvelope(msg)" in body
    assert "_markWebSocketStale('delivery-gap')" in script
    assert "_markWebSocketStale('sequence-regression')" in script
    assert "if (wsReconciling && msg.type !== 'full_sync'" in body
    assert "_bufferWebSocketMessage(msg)" in body
    assert "_routeWebSocketMessage(msg)" in body


def test_heartbeat_watermark_and_epoch_change_trigger_reconciliation():
    script = _dashboard_script()
    body = _connect_function(script)

    assert "_heartbeatNeedsFullSync(msg)" in body
    assert "_markWebSocketStale('heartbeat-watermark')" in body
    assert "_markWebSocketStale('epoch-change')" in script
    assert "current_state_revision" in script
    assert "current_issue_revision" in script


def test_full_sync_commits_revisions_and_delivery_watermark():
    script = _dashboard_script()

    body = script[script.index("function _applyFullSyncMessage("):]
    assert "wsLastAppliedStateRevision = stateRevision" in body
    assert "wsLastAppliedIssueRevision = issueRevision" in body
    assert "wsLastFullSyncDeliverySeq = msg.delivery_seq" in body
    assert "wsBufferedMessages = []" in body
    assert "wsReconciling = false" in body
    assert "clearFullSyncRetryTimer()" in body


def test_full_sync_retry_is_bounded_and_coalesced():
    script = _dashboard_script()

    assert "WS_FULL_SYNC_RETRY_MAX_DELAY_MS" in script
    assert "wsFullSyncRetryTimer !== null" in script
    assert "if (!wsReconciling || wsFullSyncPending" in script
    assert "_scheduleFullSyncRetry()" in script
    assert "setTimeout(() =>" in script
