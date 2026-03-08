"""Tests for collapsed inactive epics in swimlane view.

Epics with no children in backlog, open, or in_progress (i.e. 'inactive' epics)
should be auto-collapsed in the swimlane view by default. User manual toggles
should override this auto-collapse behavior.

See issue: oompah-mus
"""

import os
import re

import pytest


def _load_dashboard_html() -> str:
    """Load dashboard HTML from the templates directory."""
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_script(html: str) -> str:
    """Extract the main (largest) <script> block from the dashboard HTML."""
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in dashboard HTML"
    return max(matches, key=len)


@pytest.fixture(scope="module")
def script():
    html = _load_dashboard_html()
    return _extract_script(html)


class TestIsEpicInactiveFunction:
    """Verify that the isEpicInactive helper function exists and has correct logic."""

    def test_isEpicInactive_function_exists(self, script):
        """isEpicInactive function must be defined."""
        assert "function isEpicInactive(" in script

    def test_isEpicInactive_checks_deferred(self, script):
        """isEpicInactive must check the deferred count."""
        func_match = re.search(
            r"function isEpicInactive\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert func_match, "Could not find isEpicInactive function body"
        body = func_match.group(1)
        assert "deferred" in body

    def test_isEpicInactive_checks_open(self, script):
        """isEpicInactive must check the open count."""
        func_match = re.search(
            r"function isEpicInactive\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert func_match
        body = func_match.group(1)
        assert "open" in body

    def test_isEpicInactive_checks_in_progress(self, script):
        """isEpicInactive must check the in_progress count."""
        func_match = re.search(
            r"function isEpicInactive\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert func_match
        body = func_match.group(1)
        assert "in_progress" in body

    def test_isEpicInactive_uses_children_counts(self, script):
        """isEpicInactive must use children_counts from the epic."""
        func_match = re.search(
            r"function isEpicInactive\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert func_match
        body = func_match.group(1)
        assert "children_counts" in body

    def test_isEpicInactive_does_not_check_closed(self, script):
        """isEpicInactive should NOT use the closed count to determine inactivity.

        An epic with only closed children is inactive — having closed items
        does not make an epic 'active'.
        """
        func_match = re.search(
            r"function isEpicInactive\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert func_match
        body = func_match.group(1)
        # The return statement should check deferred, open, in_progress but NOT closed
        return_match = re.search(r"return\b(.+);", body, re.DOTALL)
        assert return_match, "isEpicInactive must have a return statement"
        return_expr = return_match.group(1)
        assert "counts.closed" not in return_expr, \
            "isEpicInactive return expression should not check counts.closed"


class TestUserToggledSwimlanes:
    """Verify that user toggle tracking exists to override auto-collapse."""

    def test_userToggledSwimlanes_global_declared(self, script):
        """userToggledSwimlanes must be declared to track explicit user toggles."""
        assert "let userToggledSwimlanes" in script or "var userToggledSwimlanes" in script

    def test_userToggledSwimlanes_initialized_as_object(self, script):
        """userToggledSwimlanes should be initialized as an empty object."""
        assert re.search(r"(?:let|var)\s+userToggledSwimlanes\s*=\s*\{\}", script)

    def test_toggleSwimlane_sets_userToggled(self, script):
        """toggleSwimlane() must mark the swimlane as user-toggled."""
        toggle_match = re.search(
            r"function toggleSwimlane\(.*?\)\s*\{(.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert toggle_match, "Could not find toggleSwimlane function"
        body = toggle_match.group(1)
        assert "userToggledSwimlanes" in body
        # It should set userToggledSwimlanes[id] = true
        assert re.search(r"userToggledSwimlanes\[id\]\s*=\s*true", body)


class TestAutoCollapseInRenderSwimlane:
    """Verify that renderSwimlaneView auto-collapses inactive epics."""

    def test_renderSwimlaneView_calls_isEpicInactive(self, script):
        """renderSwimlaneView must call isEpicInactive to determine auto-collapse."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert render_match, "Could not find renderSwimlaneView function"
        body = render_match.group(1)
        assert "isEpicInactive(" in body

    def test_renderSwimlaneView_checks_userToggled_before_autoCollapse(self, script):
        """Auto-collapse should only apply when user has NOT explicitly toggled."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert render_match
        body = render_match.group(1)
        assert "userToggledSwimlanes" in body
        # The logic should be: if user toggled, use their preference;
        # otherwise use auto-collapse
        assert re.search(
            r"userToggledSwimlanes\[epic\.id\].*collapsedSwimlanes\[epic\.id\].*autoCollapse",
            body,
            re.DOTALL,
        ) or re.search(
            r"userToggledSwimlanes\[epic\.id\].*\?.*collapsedSwimlanes\[epic\.id\].*:.*autoCollapse",
            body,
        )

    def test_autoCollapse_variable_computed_from_isEpicInactive(self, script):
        """The autoCollapse value must come from isEpicInactive."""
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert render_match
        body = render_match.group(1)
        assert re.search(r"(?:const|let|var)\s+autoCollapse\s*=\s*isEpicInactive\(epic\)", body)


class TestCollapsedSwimlanesSyncedBack:
    """Verify that collapsedSwimlanes is synced with computed isCollapsed."""

    def test_collapsedSwimlanes_updated_with_computed_value(self, script):
        """collapsedSwimlanes[epic.id] should be set to the computed isCollapsed value.

        This ensures that when the user later toggles, the starting state is correct.
        """
        render_match = re.search(
            r"function renderSwimlaneView\(.*?\)\s*\{(.*)",
            script,
            re.DOTALL,
        )
        assert render_match
        body = render_match.group(1)
        assert "collapsedSwimlanes[epic.id] = isCollapsed" in body


class TestServerChildrenCounts:
    """Verify that the server includes children_counts in WebSocket serialization."""

    def test_fetch_and_serialize_includes_children_counts(self):
        """_fetch_and_serialize_issues must compute and include children_counts for epics."""
        import inspect
        from oompah.server import _fetch_and_serialize_issues

        source = inspect.getsource(_fetch_and_serialize_issues)
        # Must build epic child counts
        assert "children_counts" in source
        # Must iterate issues to count children per state
        assert "epics" in source
        assert "child_state" in source or "deferred" in source

    def test_fetch_and_serialize_computes_epic_map(self):
        """The function must identify epics and build a counts map."""
        import inspect
        from oompah.server import _fetch_and_serialize_issues

        source = inspect.getsource(_fetch_and_serialize_issues)
        # Should create an epics dict with state count keys
        assert '"deferred": 0' in source or "'deferred': 0" in source
        assert '"open": 0' in source or "'open': 0" in source
        assert '"in_progress": 0' in source or "'in_progress': 0" in source
        assert '"closed": 0' in source or "'closed': 0" in source

    def test_fetch_and_serialize_adds_counts_to_epic_entries(self):
        """Epic entries in the result must have children_counts attached."""
        import inspect
        from oompah.server import _fetch_and_serialize_issues

        source = inspect.getsource(_fetch_and_serialize_issues)
        # Must conditionally add children_counts to epic entries
        assert 'entry["children_counts"]' in source or "entry['children_counts']" in source
