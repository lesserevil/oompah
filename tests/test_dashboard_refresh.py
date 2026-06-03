"""Tests for dashboard refresh behavior."""

from __future__ import annotations

import re
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


def test_refresh_board_fetches_rest_payload_even_when_websocket_is_open():
    script = _dashboard_script()
    match = re.search(
        r"async function refreshBoard\(\) \{(?P<body>.*?)\n\}",
        script,
        re.DOTALL,
    )

    assert match is not None
    body = match.group("body")
    ws_send = body.index("ws.send(JSON.stringify({action: 'refresh'}));")
    fetch = body.index("const data = await fetchIssues();")

    assert ws_send < fetch
    assert "return;" not in body[ws_send:fetch]
