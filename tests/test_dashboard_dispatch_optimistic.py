"""Tests for client-side optimistic dispatch update in dashboard.html.

When an agent dispatches, the "state" WebSocket message arrives within
100-500ms but the "issues" push is throttled to once every 3s (see
oompah/server.py _ISSUES_THROTTLE_MS). This created a visible mismatch
where the chip appeared in the agent bar but the bead's card lagged in
the "open" column for up to 3s before snapping to "in_progress".

The fix in handleStateUpdate() diffs running[] vs lastRunningAgents and
optimistically marks newly-running issues as in_progress in the local
in-memory boardData, then re-renders. The next throttled "issues" push
clears the optimistic override once the server confirms.

See issue: oompah-zlz_2-3pg
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import textwrap

import pytest


# ---------------------------------------------------------------------------
# Helpers — load dashboard.html and extract the JS <script> block
# ---------------------------------------------------------------------------

def _load_dashboard_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "dashboard.html"
    )
    with open(template_path, "r") as f:
        return f.read()


def _extract_script(html: str) -> str:
    matches = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert matches, "Could not find any <script> block in dashboard HTML"
    return max(matches, key=len)


@pytest.fixture(scope="module")
def html() -> str:
    return _load_dashboard_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    return _extract_script(html)


# ---------------------------------------------------------------------------
# (1) Static structural tests — verify the optimistic dispatch logic exists
# ---------------------------------------------------------------------------

class TestDispatchOptimisticStructure:
    """Verify the dispatch-optimistic update block is present in handleStateUpdate."""

    def test_handle_state_update_function_exists(self, script: str):
        """handleStateUpdate must still be defined."""
        assert "function handleStateUpdate(" in script

    def test_diffs_against_last_running_agents(self, script: str):
        """The handler must read previous running keys from lastRunningAgents."""
        # The optimistic block builds a Set from lastRunningAgents.
        assert re.search(
            r"new\s+Set\(\s*lastRunningAgents\s*\.filter",
            script,
        ), "must build a project-scoped Set from lastRunningAgents to diff"

    def test_filters_running_for_new_dispatches(self, script: str):
        """Must filter running[] by project-scoped running-agent key."""
        assert re.search(
            r"!previousRunningKeys\.has\(\s*runningAgentIssueKey\(r\)\s*\)",
            script,
        ), "must compute new dispatches by exclusion against previous project-scoped keys"

    def test_uses_issue_identifier_and_project_id_fields(self, script: str):
        """Must key running entries by issue_identifier plus project_id."""
        assert "function runningAgentIssueKey(agent)" in script
        assert "agent && agent.issue_identifier" in script
        assert "agent && agent.project_id" in script

    def test_writes_optimistic_in_progress(self, script: str):
        """Must set optimisticUpdates[key] = {state: 'in_progress', ...}."""
        # Look for an assignment that sets state to 'in_progress' inside the
        # state handler region. We don't constrain the exact structure but
        # require the in_progress literal in proximity to optimisticUpdates.
        # Find the handleStateUpdate function body.
        match = re.search(
            r"function handleStateUpdate\([^)]*\)\s*\{(.*?)\n\}\n",
            script,
            re.DOTALL,
        )
        assert match, "could not extract handleStateUpdate body"
        body = match.group(1)
        assert "optimisticUpdates[key]" in body, (
            "handleStateUpdate must write to optimisticUpdates on dispatch"
        )
        assert "'in_progress'" in body or '"in_progress"' in body, (
            "handleStateUpdate must mark dispatched issues as in_progress"
        )

    def test_does_not_speculate_on_removed_running(self, script: str):
        """Removed running entries should not trigger speculative state changes.

        We only optimistically mark NEW dispatches (running entries that
        weren't there before). When an entry is removed, we wait for the
        next 'issues' push because we don't know if the agent succeeded,
        failed, or is being retried.
        """
        match = re.search(
            r"function handleStateUpdate\([^)]*\)\s*\{(.*?)\n\}\n",
            script,
            re.DOTALL,
        )
        assert match
        body = match.group(1)
        # The diff should not iterate "lastRunningAgents.filter(... !running.has(...))"
        # i.e. there's no removed-set computation.
        assert not re.search(
            r"lastRunningAgents\.\s*\w*\(\s*[a-zA-Z_]+\s*=>\s*!\s*\w+\.has",
            body,
        ), "must not compute removed-set or speculate on agent termination"

    def test_re_renders_board_after_optimistic_update(self, script: str):
        """When new dispatches are detected, must call renderBoard(boardData) to apply."""
        match = re.search(
            r"function handleStateUpdate\([^)]*\)\s*\{(.*?)\n\}\n",
            script,
            re.DOTALL,
        )
        assert match
        body = match.group(1)
        # Look for a renderBoard call inside handleStateUpdate. The drag-drop
        # path doesn't render from inside handleStateUpdate — it's only
        # reached via this optimistic dispatch path now.
        assert "renderBoard(boardData)" in body, (
            "handleStateUpdate must re-render the board after optimistic update"
        )

    def test_optimistic_update_has_expiry(self, script: str):
        """Optimistic update entries must include an expiry to self-clean."""
        match = re.search(
            r"function handleStateUpdate\([^)]*\)\s*\{(.*?)\n\}\n",
            script,
            re.DOTALL,
        )
        assert match
        body = match.group(1)
        # The optimistic update assignment should set an expiry timestamp.
        assert re.search(r"expiry:\s*Date\.now\(\)\s*\+", body), (
            "optimistic dispatch entries must include expiry: Date.now() + N"
        )


# ---------------------------------------------------------------------------
# (2) Behavioural tests — execute the diff logic in node when available
# ---------------------------------------------------------------------------

# Re-implement the dispatch-diff logic standalone for behavioural testing.
# We feed it (lastRunningAgents, running) and assert the produced
# optimisticUpdates map matches expectations.
_DIFF_FN_JS = textwrap.dedent("""
    // Mirror of the production code in handleStateUpdate (dashboard.html).
    function optimisticIssueKey(identifier, projectId) {
        const id = identifier || '';
        const pid = projectId || '';
        return pid ? pid + '::' + id : id;
    }

    function runningAgentIssueKey(agent) {
        return optimisticIssueKey(agent && agent.issue_identifier, agent && agent.project_id);
    }

    function computeNewDispatchAgents(lastRunningAgents, running) {
        const previousRunningKeys = new Set(
            lastRunningAgents
                .filter(r => r.issue_identifier)
                .map(r => runningAgentIssueKey(r))
        );
        return running
            .filter(r => r.issue_identifier && !previousRunningKeys.has(runningAgentIssueKey(r)));
    }

    function computeNewDispatchIds(lastRunningAgents, running) {
        return computeNewDispatchAgents(lastRunningAgents, running).map(r => r.issue_identifier);
    }

    function computeNewDispatchKeys(lastRunningAgents, running) {
        return computeNewDispatchAgents(lastRunningAgents, running).map(r => runningAgentIssueKey(r));
    }
""")


_CASES: list[tuple[list[dict], list[dict], list[str]]] = [
    # (lastRunningAgents, running, expected_new_dispatch_ids)
    # Empty -> empty
    ([], [], []),
    # First dispatch: running has one entry, none previously
    ([], [{"issue_identifier": "oompah-1"}], ["oompah-1"]),
    # Two new at once
    ([], [{"issue_identifier": "oompah-1"}, {"issue_identifier": "oompah-2"}],
     ["oompah-1", "oompah-2"]),
    # Steady state: same agent running, no new dispatches
    ([{"issue_identifier": "oompah-1"}], [{"issue_identifier": "oompah-1"}], []),
    # Only-removal: agent finished. Should NOT speculate (returns []).
    ([{"issue_identifier": "oompah-1"}], [], []),
    # Mixed: one continuing, one new
    ([{"issue_identifier": "oompah-1"}],
     [{"issue_identifier": "oompah-1"}, {"issue_identifier": "oompah-2"}],
     ["oompah-2"]),
    # Mixed: one removed, one new (only new is reported)
    ([{"issue_identifier": "oompah-1"}],
     [{"issue_identifier": "oompah-2"}],
     ["oompah-2"]),
    # Defensive: missing issue_identifier (falsy) is filtered out
    ([], [{"issue_identifier": ""}, {"issue_identifier": None},
          {"issue_identifier": "oompah-3"}],
     ["oompah-3"]),
    # Defensive: previous lastRunningAgents had falsy IDs (filtered)
    ([{"issue_identifier": ""}, {"issue_identifier": "oompah-1"}],
     [{"issue_identifier": "oompah-1"}, {"issue_identifier": "oompah-2"}],
     ["oompah-2"]),
]


_KEY_CASES: list[tuple[list[dict], list[dict], list[str]]] = [
    # Same TASK id in a different project is a new dispatch.
    (
        [{"issue_identifier": "TASK-260", "project_id": "proj-oompah"}],
        [
            {"issue_identifier": "TASK-260", "project_id": "proj-oompah"},
            {"issue_identifier": "TASK-260", "project_id": "proj-trickle"},
        ],
        ["proj-trickle::TASK-260"],
    ),
    # Same TASK id in the same project is steady-state, not a new dispatch.
    (
        [{"issue_identifier": "TASK-260", "project_id": "proj-trickle"}],
        [{"issue_identifier": "TASK-260", "project_id": "proj-trickle"}],
        [],
    ),
]


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not available — skipping JS execution test",
)
class TestDispatchDiffBehaviour:
    """Execute the diff logic in node and assert against acceptance criteria."""

    def test_all_cases(self, tmp_path):
        cases_js = json.dumps(_CASES)
        script = _DIFF_FN_JS + textwrap.dedent(f"""
            const cases = {cases_js};
            const results = [];
            for (const [last, running, expected] of cases) {{
                const got = computeNewDispatchIds(last, running);
                results.push({{
                    last: last,
                    running: running,
                    expected: expected,
                    got: got,
                }});
            }}
            process.stdout.write(JSON.stringify(results));
        """)
        path = tmp_path / "diff_test.js"
        path.write_text(script)
        proc = subprocess.run(
            ["node", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, f"node failed: stderr={proc.stderr!r}"
        results = json.loads(proc.stdout)
        failures = [
            (r["last"], r["running"], r["expected"], r["got"])
            for r in results
            if r["got"] != r["expected"]
        ]
        assert not failures, (
            "diff mismatches:\n"
            + "\n".join(
                f"  last={last} running={running} expected={exp} got={got}"
                for last, running, exp, got in failures
            )
        )

    def test_project_scoped_duplicate_task_ids(self, tmp_path):
        cases_js = json.dumps(_KEY_CASES)
        script = _DIFF_FN_JS + textwrap.dedent(f"""
            const cases = {cases_js};
            const results = [];
            for (const [last, running, expected] of cases) {{
                const got = computeNewDispatchKeys(last, running);
                results.push({{
                    last: last,
                    running: running,
                    expected: expected,
                    got: got,
                }});
            }}
            process.stdout.write(JSON.stringify(results));
        """)
        path = tmp_path / "project_scoped_diff_test.js"
        path.write_text(script)
        proc = subprocess.run(
            ["node", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, f"node failed: stderr={proc.stderr!r}"
        results = json.loads(proc.stdout)
        failures = [
            (r["last"], r["running"], r["expected"], r["got"])
            for r in results
            if r["got"] != r["expected"]
        ]
        assert not failures, (
            "project-scoped diff mismatches:\n"
            + "\n".join(
                f"  last={last} running={running} expected={exp} got={got}"
                for last, running, exp, got in failures
            )
        )


# ---------------------------------------------------------------------------
# (3) End-to-end behavioural test — apply optimistic + render outcome
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not available — skipping JS execution test",
)
class TestDispatchOptimisticAppliesToBoard:
    """Verify the full flow: diff -> set optimisticUpdates -> applyOptimisticOverrides
    correctly moves the issue from open to in_progress.

    No double-counting (acceptance criterion): the bead must NOT appear in
    both 'open' and 'in_progress' columns simultaneously.
    """

    def _extract_apply_optimistic(self, script: str) -> str:
        helper = re.search(
            r"function issueMatchesOptimisticUpdate\(.*?\n\}\n",
            script,
            re.DOTALL,
        )
        assert helper, "could not extract issueMatchesOptimisticUpdate()"
        match = re.search(
            r"function applyOptimisticOverrides\(.*?\n\}\n",
            script,
            re.DOTALL,
        )
        assert match, "could not extract applyOptimisticOverrides()"
        return helper.group(0) + "\n" + match.group(0)

    def test_dispatch_moves_issue_from_open_to_in_progress(
        self, tmp_path, script: str
    ):
        """After diff + optimistic update, the issue moves from open to in_progress."""
        apply_fn = self._extract_apply_optimistic(script)
        js = _DIFF_FN_JS + apply_fn + textwrap.dedent("""
            // Initial board has the issue in 'open'
            const boardData = {
                open: [{identifier: "oompah-1", state: "open"}],
                in_progress: [],
                closed: [],
            };
            const optimisticUpdates = {};

            // Simulate the dispatch diff.
            const lastRunningAgents = [];
            const running = [{issue_identifier: "oompah-1"}];
            const newAgents = computeNewDispatchAgents(lastRunningAgents, running);

            // Apply the optimistic update like handleStateUpdate does.
            for (const agent of newAgents) {
                const key = runningAgentIssueKey(agent);
                optimisticUpdates[key] = {
                    identifier: agent.issue_identifier,
                    project_id: agent.project_id || '',
                    state: "in_progress",
                    priority: undefined,
                    expiry: Date.now() + 10000,
                };
            }

            // Now run applyOptimisticOverrides — this is what renderBoard
            // calls internally. It mutates boardData in-place.
            const result = applyOptimisticOverrides(boardData);

            process.stdout.write(JSON.stringify({
                openIds: result.open.map(i => i.identifier),
                inProgressIds: result.in_progress.map(i => i.identifier),
                inProgressStates: result.in_progress.map(i => i.state),
            }));
        """)
        path = tmp_path / "apply_test.js"
        path.write_text(js)
        proc = subprocess.run(
            ["node", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, f"node failed: stderr={proc.stderr!r}"
        out = json.loads(proc.stdout)

        # Acceptance: card moved from open -> in_progress
        assert "oompah-1" not in out["openIds"], (
            "after dispatch optimistic update, issue must NOT be in open column"
        )
        assert "oompah-1" in out["inProgressIds"], (
            "after dispatch optimistic update, issue must be in in_progress column"
        )
        # Acceptance: no double-counting
        assert out["openIds"].count("oompah-1") == 0
        assert out["inProgressIds"].count("oompah-1") == 1
        # State field also updated
        assert "in_progress" in out["inProgressStates"]

    def test_dispatch_moves_duplicate_task_id_only_in_matching_project(
        self, tmp_path, script: str
    ):
        """Duplicate Backlog task ids across projects must not move the wrong card."""
        apply_fn = self._extract_apply_optimistic(script)
        js = _DIFF_FN_JS + apply_fn + textwrap.dedent("""
            const boardData = {
                open: [
                    {identifier: "TASK-260", project_id: "proj-oompah", state: "open"},
                    {identifier: "TASK-260", project_id: "proj-trickle", state: "open"},
                ],
                in_progress: [],
                closed: [],
            };
            const optimisticUpdates = {};

            const lastRunningAgents = [];
            const running = [
                {issue_identifier: "TASK-260", project_id: "proj-trickle"},
            ];
            const newAgents = computeNewDispatchAgents(lastRunningAgents, running);
            for (const agent of newAgents) {
                const key = runningAgentIssueKey(agent);
                optimisticUpdates[key] = {
                    identifier: agent.issue_identifier,
                    project_id: agent.project_id || '',
                    state: "in_progress",
                    priority: undefined,
                    expiry: Date.now() + 10000,
                };
            }

            const result = applyOptimisticOverrides(boardData);
            process.stdout.write(JSON.stringify({
                openProjects: result.open.map(i => i.project_id),
                inProgressProjects: result.in_progress.map(i => i.project_id),
            }));
        """)
        path = tmp_path / "duplicate_project_task_id.js"
        path.write_text(js)
        proc = subprocess.run(
            ["node", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, f"node failed: stderr={proc.stderr!r}"
        out = json.loads(proc.stdout)

        assert out["openProjects"] == ["proj-oompah"]
        assert out["inProgressProjects"] == ["proj-trickle"]

    def test_stale_issues_push_does_not_clear_optimistic_update(
        self, tmp_path, script: str
    ):
        """A stale websocket issues payload must not clear the local override.

        This is the rubber-band regression: the stale payload says the issue is
        still open, applyOptimisticOverrides moves it locally to in_progress,
        and the optimistic marker must remain until a raw server payload also
        says in_progress.
        """
        apply_fn = self._extract_apply_optimistic(script)
        js = apply_fn + textwrap.dedent("""
            const boardData = {
                open: [{identifier: "oompah-1", state: "open"}],
                in_progress: [],
                closed: [],
            };
            const optimisticUpdates = {
                "oompah-1": {
                    state: "in_progress",
                    priority: undefined,
                    expiry: Date.now() + 10000,
                },
            };

            const result = applyOptimisticOverrides(boardData);

            process.stdout.write(JSON.stringify({
                openIds: result.open.map(i => i.identifier),
                inProgressIds: result.in_progress.map(i => i.identifier),
                optimisticKeysCount: Object.keys(optimisticUpdates).length,
            }));
        """)
        path = tmp_path / "stale_push.js"
        path.write_text(js)
        proc = subprocess.run(
            ["node", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, f"node failed: stderr={proc.stderr!r}"
        out = json.loads(proc.stdout)

        assert "oompah-1" not in out["openIds"]
        assert "oompah-1" in out["inProgressIds"]
        assert out["optimisticKeysCount"] == 1, (
            "stale server data must not clear the optimistic override"
        )

    def test_server_confirmation_clears_after_stale_payload(
        self, tmp_path, script: str
    ):
        """After stale payloads are masked, the next confirming payload clears."""
        apply_fn = self._extract_apply_optimistic(script)
        js = apply_fn + textwrap.dedent("""
            const optimisticUpdates = {
                "oompah-1": {
                    state: "in_progress",
                    priority: undefined,
                    expiry: Date.now() + 10000,
                },
            };

            // First payload is stale: still says open.
            applyOptimisticOverrides({
                open: [{identifier: "oompah-1", state: "open"}],
                in_progress: [],
                closed: [],
            });

            // Later payload confirms: raw server state is now in_progress.
            applyOptimisticOverrides({
                open: [],
                in_progress: [{identifier: "oompah-1", state: "in_progress"}],
                closed: [],
            });

            process.stdout.write(JSON.stringify({
                optimisticKeysCount: Object.keys(optimisticUpdates).length,
            }));
        """)
        path = tmp_path / "confirm_after_stale.js"
        path.write_text(js)
        proc = subprocess.run(
            ["node", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, f"node failed: stderr={proc.stderr!r}"
        out = json.loads(proc.stdout)
        assert out["optimisticKeysCount"] == 0, (
            "confirmed server data must clear the optimistic override"
        )

    def test_no_speculation_on_running_removal(self, tmp_path, script: str):
        """When an agent is removed from running[], no optimistic update fires."""
        apply_fn = self._extract_apply_optimistic(script)
        js = _DIFF_FN_JS + apply_fn + textwrap.dedent("""
            // Issue was already in_progress; agent is now removed from running.
            const boardData = {
                open: [],
                in_progress: [{identifier: "oompah-1", state: "in_progress"}],
                closed: [],
            };
            const optimisticUpdates = {};
            const lastRunningAgents = [{issue_identifier: "oompah-1"}];
            const running = [];

            const newIds = computeNewDispatchIds(lastRunningAgents, running);

            // The diff must NOT produce any new dispatch IDs on removal.
            process.stdout.write(JSON.stringify({
                newIdsCount: newIds.length,
                optimisticKeysCount: Object.keys(optimisticUpdates).length,
            }));
        """)
        path = tmp_path / "no_speculate.js"
        path.write_text(js)
        proc = subprocess.run(
            ["node", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, f"node failed: stderr={proc.stderr!r}"
        out = json.loads(proc.stdout)
        assert out["newIdsCount"] == 0, (
            "removing an agent from running[] must NOT trigger optimistic update"
        )
        assert out["optimisticKeysCount"] == 0

    def test_optimistic_clears_when_server_confirms(self, tmp_path, script: str):
        """After the next 'issues' push has the issue in_progress, the optimistic
        override is cleared by applyOptimisticOverrides (existing behaviour).
        """
        apply_fn = self._extract_apply_optimistic(script)
        js = _DIFF_FN_JS + apply_fn + textwrap.dedent("""
            // Server has now caught up — fresh issues push has the issue in_progress.
            const boardData = {
                open: [],
                in_progress: [{identifier: "oompah-1", state: "in_progress"}],
                closed: [],
            };
            const optimisticUpdates = {
                "oompah-1": {
                    state: "in_progress",
                    priority: undefined,
                    expiry: Date.now() + 10000,
                },
            };

            applyOptimisticOverrides(boardData);

            process.stdout.write(JSON.stringify({
                optimisticKeysCount: Object.keys(optimisticUpdates).length,
            }));
        """)
        path = tmp_path / "clear_test.js"
        path.write_text(js)
        proc = subprocess.run(
            ["node", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, f"node failed: stderr={proc.stderr!r}"
        out = json.loads(proc.stdout)
        assert out["optimisticKeysCount"] == 0, (
            "optimistic override must be cleared once server confirms"
        )
