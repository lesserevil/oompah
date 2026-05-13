"""Static-template tests for projects.html fetch error-handling (oompah-zlz_2-1tsm).

The /projects-manage page had an unhandled ``TypeError: Failed to fetch`` from
``loadProjects()`` when the initial GET /api/v1/projects request failed (network
hiccup, server reload, browser offline). The unhandled rejection was then
auto-reported via ``window.addEventListener('unhandledrejection')`` to
``/api/v1/errors`` which files a P3 bug bead.

These tests assert each fetch call site in ``oompah/templates/projects.html``
is wrapped in try/catch so a transient network failure becomes a user-visible
error (or alert) instead of a top-level unhandled rejection.

We use the same static-analysis approach as
``tests/test_dashboard_activity_summary.py`` and ``tests/test_console_ui.py``
— parse the template, extract the relevant JS function bodies, and assert
that the error-handling plumbing is present.
"""

from __future__ import annotations

import os
import re

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_projects_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "projects.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_main_script(html: str) -> str:
    """Return the largest <script> block — that's the page logic."""
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in projects.html"
    return max(matches, key=len)


def _get_func_body(script: str, fn_name: str) -> str:
    """Extract a top-level function body via balanced-brace scan.

    Supports both ``function foo()`` and ``async function foo()`` declarations.
    """
    pattern = re.compile(
        rf"(?:async\s+)?function\s+{re.escape(fn_name)}\s*\(([^)]*)\)\s*\{{"
    )
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
                return script[start + 1 : i]
    raise AssertionError(f"Could not find end of function {fn_name}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def html() -> str:
    return _load_projects_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_main_script(html)


# ---------------------------------------------------------------------------
# loadProjects — the function from the bug stack trace
# ---------------------------------------------------------------------------


class TestLoadProjectsErrorHandling:
    """``loadProjects`` is invoked at page load (top-level). Any rejected
    promise it returns becomes an unhandledrejection event, which the page's
    window handler POSTs to /api/v1/errors → P3 bug bead. The function MUST
    catch its own fetch failures."""

    def test_load_projects_has_try_catch(self, script: str) -> None:
        body = _get_func_body(script, "loadProjects")
        assert "try" in body and "catch" in body, (
            "loadProjects must wrap its fetch in try/catch so a network "
            "failure does not bubble up as an unhandled rejection"
        )

    def test_load_projects_handles_fetch_error(self, script: str) -> None:
        body = _get_func_body(script, "loadProjects")
        # The catch block should reference the error and render something
        # into the container — not silently swallow it.
        assert "catch (err)" in body or "catch(err)" in body
        assert "container.innerHTML" in body

    def test_load_projects_offers_retry_button(self, script: str) -> None:
        body = _get_func_body(script, "loadProjects")
        # When loadProjects fails, the user needs a way to retry without
        # reloading the page. The retry button must call loadProjects().
        assert 'onclick="loadProjects()"' in body, (
            "fetch-error UI must offer a Retry button that re-invokes loadProjects()"
        )

    def test_load_projects_error_state_is_accessible(self, script: str) -> None:
        body = _get_func_body(script, "loadProjects")
        # role=alert + aria-live polite so screen readers announce the error.
        assert 'role="alert"' in body
        assert 'aria-live="polite"' in body
        # The retry button should carry an aria-label.
        assert 'aria-label="Retry loading projects"' in body

    def test_load_projects_checks_response_ok(self, script: str) -> None:
        body = _get_func_body(script, "loadProjects")
        # A non-OK response (e.g. 500) should also surface the error, not
        # crash with "projects.map is not a function".
        assert "res.ok" in body

    def test_load_projects_logs_to_console(self, script: str) -> None:
        body = _get_func_body(script, "loadProjects")
        # We still want a console.error so devs can diagnose without
        # opening the network panel.
        assert "console.error" in body


# ---------------------------------------------------------------------------
# Mutator functions — must not leak unhandled rejections either
# ---------------------------------------------------------------------------


MUTATOR_FUNCTIONS = [
    "addProject",
    "toggleYolo",
    "toggleMergeQueue",
    "pauseProject",
    "resumeProject",
    "deleteProject",
    "saveProject",
    "showWorktrees",
]


class TestMutatorErrorHandling:
    """The action-button handlers (toggle/pause/resume/delete/save/etc.) each
    call fetch() and follow up with loadProjects(). If the fetch rejects with
    a TypeError, that rejection escapes and gets auto-filed as a bug bead too.
    They must all be wrapped."""

    @pytest.mark.parametrize("fn_name", MUTATOR_FUNCTIONS)
    def test_mutator_has_error_handling(self, script: str, fn_name: str) -> None:
        body = _get_func_body(script, fn_name)
        # Either the function itself wraps fetch in try/catch, or it routes
        # the call through the shared _runMutation helper (which wraps).
        has_inline_try = "try" in body and "catch" in body
        uses_helper = "_runMutation(" in body
        assert has_inline_try or uses_helper, (
            f"{fn_name} must guard its fetch with try/catch or _runMutation "
            "so a transient network error does not become an unhandled rejection"
        )


class TestRunMutationHelper:
    """The shared ``_runMutation`` helper is the chosen DRY surface for
    button-handler fetches. Make sure it exists and does the right thing."""

    def test_run_mutation_defined(self, script: str) -> None:
        body = _get_func_body(script, "_runMutation")
        assert body, "_runMutation helper must be defined"

    def test_run_mutation_wraps_fetch(self, script: str) -> None:
        body = _get_func_body(script, "_runMutation")
        assert "try" in body and "catch" in body
        assert "fetch(url, options)" in body

    def test_run_mutation_alerts_on_failure(self, script: str) -> None:
        body = _get_func_body(script, "_runMutation")
        # User-visible feedback for a button-click failure.
        assert "alert(" in body

    def test_run_mutation_handles_non_ok_response(self, script: str) -> None:
        body = _get_func_body(script, "_runMutation")
        assert "res.ok" in body
        # When the server returns a JSON error envelope we should surface it.
        assert "data.error" in body


# ---------------------------------------------------------------------------
# Regression guard — make sure the OLD unguarded form does not creep back in
# ---------------------------------------------------------------------------


class TestNoUnguardedTopLevelFetch:
    """The original bug shape was ``const res = await fetch('/api/v1/projects');``
    at the very top of ``loadProjects`` with no surrounding try. This regression
    test asserts we never re-introduce that exact pattern.
    """

    def test_load_projects_does_not_start_with_unguarded_fetch(
        self, script: str
    ) -> None:
        body = _get_func_body(script, "loadProjects").lstrip()
        # First non-comment statement must NOT be a bare `const res = await fetch(...)`.
        # We approximate by checking the first ~200 chars contain 'try' BEFORE 'fetch'.
        head = body[:400]
        try_pos = head.find("try")
        fetch_pos = head.find("fetch(")
        assert try_pos != -1, "loadProjects must contain a try block near the top"
        assert fetch_pos != -1, "loadProjects must still call fetch"
        assert try_pos < fetch_pos, (
            "fetch in loadProjects must be inside a try block; saw fetch before try"
        )
