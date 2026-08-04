"""OOMPAH-735: dashboard filters informational recovery alerts.

Non-actionable integration_retry alerts represent normal automatic recovery
(fresh repair worker, scheduled bounded retry) and must not appear in the
global operator warning banner or the inline agent-bar warnings.  This test
verifies handleStateUpdate() applies the ``action_required !== false``
filter to the otherAlerts group.
"""

from __future__ import annotations

import os
import re

import pytest


def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "oompah",
        "templates",
        "dashboard.html",
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_script(html: str) -> str:
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in dashboard HTML"
    return max(matches, key=len)


def _get_func_body(script: str, fn_name: str) -> str:
    pattern = re.compile(rf"function\s+{re.escape(fn_name)}\s*\(([^)]*)\)\s*\{{")
    m = pattern.search(script)
    assert m, f"Could not find function {fn_name} in script"
    start = m.end() - 1
    depth = 0
    for i in range(start, len(script)):
        c = script[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return script[start : i + 1]
    raise AssertionError(f"Unbalanced braces for {fn_name}")


@pytest.fixture(scope="module")
def html() -> str:
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def handle_state_body(html: str) -> str:
    script = _extract_script(html)
    return _get_func_body(script, "handleStateUpdate")


def test_otherAlerts_filters_action_required_false(handle_state_body: str):
    """handleStateUpdate() must drop alerts with action_required === false.

    This ensures normal automatic recovery (fresh repair worker or scheduled
    bounded retry) is not surfaced as a global operator warning.
    """

    # Look for the filter clause that references the structured field.
    assert re.search(
        r"action_required\s*===\s*false", handle_state_body
    ), (
        "handleStateUpdate() must filter alerts by "
        "action_required === false so informational recovery activity "
        "is excluded from the global operator warning area"
    )


def test_otherAlerts_filter_documented(handle_state_body: str):
    """The filter must reference the source task identifier for the bug."""
    assert "OOMPAH-735" in handle_state_body, (
        "The action_required filter should reference OOMPAH-735 so future "
        "maintainers understand why informational alerts are dropped"
    )
