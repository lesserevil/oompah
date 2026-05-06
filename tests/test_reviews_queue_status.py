"""Tests for the per-PR queue-status surfaced on /reviews
(oompah-zlz_2-btf.3).

Covers:
- Template (oompah/templates/reviews.html):
    * The queue-status CSS classes are defined for every state in the AC.
    * The deriveQueueStatus() JS helper exists and dispatches all 8 states.
    * The Sort selector is wired (sort-select id, queue option, onSortChange).
    * The queue-status chip and emoji are rendered next to each PR.
- Behaviour (deriveQueueStatus executed via node, when available):
    * Each AC state is produced for the right combination of fields.
- API contract (/api/v1/reviews):
    * The list payload preserves auto_merge_enabled and mergeable_state for
      each review (they already flow through ReviewRequest.to_dict, but the
      contract was not previously test-covered).
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
# Helpers — load the reviews.html template once per module
# ---------------------------------------------------------------------------


def _load_reviews_html() -> str:
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "oompah", "templates", "reviews.html"
    )
    with open(template_path, "r") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def html() -> str:
    return _load_reviews_html()


# ---------------------------------------------------------------------------
# (1) CSS classes for every queue state from the AC
# ---------------------------------------------------------------------------


class TestQueueStatusCSS:
    """Every queue state in the AC must have a corresponding CSS class.

    AC states (oompah-zlz_2-btf.3):
        in queue, ready, blocked: needs config, behind base, conflict,
        draft, ci pending, ci failed, plus an unknown/—.
    """

    @pytest.mark.parametrize("css_class", [
        "queue-status",
        "queue-in-queue",
        "queue-ready",
        "queue-blocked-config",
        "queue-behind",
        "queue-conflict",
        "queue-draft",
        "queue-ci-pending",
        "queue-ci-failed",
        "queue-unknown",
    ])
    def test_css_class_present(self, html: str, css_class: str):
        assert ("." + css_class) in html, f"missing CSS class .{css_class}"


# ---------------------------------------------------------------------------
# (2) deriveQueueStatus JS helper
# ---------------------------------------------------------------------------


class TestDeriveQueueStatusJS:
    """The JS function that maps fields → label/cls/emoji/sortRank.

    We can't run JS from pytest; instead we assert that the function
    declaration exists and that every AC label is present in its body.
    """

    def test_function_declaration_present(self, html: str):
        assert "function deriveQueueStatus(" in html, \
            "deriveQueueStatus() not declared in reviews.html"

    @pytest.mark.parametrize("label", [
        "in queue",
        "ready",
        "blocked: needs config",
        "behind base",
        "conflict",
        "draft",
        "ci pending",
        "ci failed",
    ])
    def test_label_present_in_function(self, html: str, label: str):
        # Match by quoted string literal so we don't false-positive on, e.g.,
        # the word "ready" appearing in unrelated CSS or comments.
        pattern = re.compile(r"label:\s*['\"]" + re.escape(label) + r"['\"]")
        assert pattern.search(html), \
            f"deriveQueueStatus() does not emit the AC label {label!r}"

    def test_function_inspects_required_fields(self, html: str):
        """The body must read the four queue fields from the review object
        — drift here is the most common bug class for this feature."""
        # Find the function body and assert each field reference is inside it.
        match = re.search(
            r"function deriveQueueStatus\(.*?\)\s*\{(.*?)\n\}",
            html, re.DOTALL,
        )
        assert match, "could not extract deriveQueueStatus() body"
        body = match.group(1)
        for field in ("auto_merge_enabled", "mergeable_state",
                       "ci_status", "has_conflicts", "draft"):
            assert field in body, f"deriveQueueStatus() never reads {field}"

    def test_returns_sort_rank(self, html: str):
        """Sorting by Queue requires every branch to emit sortRank."""
        match = re.search(
            r"function deriveQueueStatus\(.*?\)\s*\{(.*?)\n\}",
            html, re.DOTALL,
        )
        body = match.group(1)
        # Each return that emits a label must also emit sortRank — count them.
        labels = len(re.findall(r"label:\s*['\"]", body))
        ranks = len(re.findall(r"sortRank:\s*\d+", body))
        assert ranks >= labels, (
            f"deriveQueueStatus(): {labels} labels but only {ranks} sortRank "
            "values — sort dropdown will be inconsistent"
        )


# ---------------------------------------------------------------------------
# (3) Sort selector wired into the template
# ---------------------------------------------------------------------------


class TestSortSelector:
    def test_sort_select_present(self, html: str):
        assert 'id="sort-select"' in html

    def test_sort_select_has_queue_option(self, html: str):
        assert re.search(
            r'<option\s+value="queue"', html
        ), "sort-select must have a queue option"

    def test_sort_change_handler_wired(self, html: str):
        assert "function onSortChange(" in html
        assert "onchange=\"onSortChange()\"" in html


# ---------------------------------------------------------------------------
# (4) Queue chip / tooltip rendered per review card
# ---------------------------------------------------------------------------


class TestQueueChipRender:
    def test_queue_chip_emitted_in_render_card(self, html: str):
        # The renderReviewCard() body must build a chip with the queue
        # state's class and the raw mergeable_state in the title attribute.
        assert "queueChipHtml" in html, "queue chip not produced by renderReviewCard"
        assert "mergeable_state=" in html, (
            "tooltip must show raw mergeable_state for diagnostics "
            "(see AC: 'Hover/tooltip on the column entry shows the raw "
            "GitHub mergeable_state value')"
        )
        assert "auto_merge_enabled=" in html, (
            "tooltip must show auto_merge_enabled for diagnostics"
        )


# ---------------------------------------------------------------------------
# (5) Behavioural test — execute deriveQueueStatus via node, when available
# ---------------------------------------------------------------------------


def _extract_derive_function(html: str) -> str:
    match = re.search(
        r"// deriveQueueStatus.*?function deriveQueueStatus\(.*?\n\}",
        html, re.DOTALL,
    )
    assert match, "could not extract deriveQueueStatus() from template"
    return match.group(0)


# (review fields, expected label) — exercises every branch of
# deriveQueueStatus including the AC-priority fallthroughs.
_CASES = [
    ({"has_conflicts": True, "auto_merge_enabled": True,
      "mergeable_state": "clean"}, "conflict"),
    ({"mergeable_state": "dirty"}, "conflict"),
    ({"draft": True, "mergeable_state": "clean"}, "draft"),
    ({"mergeable_state": "draft"}, "draft"),
    ({"auto_merge_enabled": True, "mergeable_state": "clean"}, "in queue"),
    ({"auto_merge_enabled": True, "mergeable_state": "behind"}, "in queue"),
    ({"auto_merge_enabled": True, "mergeable_state": ""}, "in queue"),
    ({"auto_merge_enabled": False, "mergeable_state": "behind"}, "behind base"),
    ({"ci_status": "failed", "mergeable_state": "blocked"}, "ci failed"),
    ({"ci_status": "pending", "mergeable_state": "unknown"}, "ci pending"),
    ({"mergeable_state": "blocked"}, "blocked: needs config"),
    ({"ci_status": "passed", "mergeable_state": "clean"}, "ready"),
    ({"ci_status": "passed", "mergeable_state": "unstable"}, "ready"),
    ({}, "—"),
]


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not available — skipping JS execution test",
)
class TestDeriveQueueStatusBehaviour:
    """Execute deriveQueueStatus() in node and assert it agrees with the AC.

    This is the strongest regression guard: it catches off-by-one logic
    changes that pure string-grep tests miss (e.g. swapping sortRank
    values or mis-ordering the priority chain)."""

    def test_all_cases(self, tmp_path, html: str):
        fn = _extract_derive_function(html)
        cases_js = json.dumps(_CASES)
        script = textwrap.dedent(f"""
            {fn}
            const cases = {cases_js};
            const results = [];
            for (const [r, expected] of cases) {{
                const out = deriveQueueStatus(r);
                results.push({{
                    review: r,
                    expected: expected,
                    label: out.label,
                    sortRank: out.sortRank,
                }});
            }}
            process.stdout.write(JSON.stringify(results));
        """)
        path = tmp_path / "derive_test.js"
        path.write_text(script)
        proc = subprocess.run(
            ["node", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, (
            f"node failed: stderr={proc.stderr!r}"
        )
        results = json.loads(proc.stdout)
        failures = [
            (r["review"], r["expected"], r["label"])
            for r in results
            if r["label"] != r["expected"]
        ]
        assert not failures, (
            "deriveQueueStatus mismatches:\n"
            + "\n".join(f"  {rev} -> got {got!r}, expected {exp!r}"
                       for rev, exp, got in failures)
        )

    def test_sort_ranks_unique_per_label(self, tmp_path, html: str):
        """Each AC label must map to a stable sortRank so 'Sort by Queue'
        groups identical states together."""
        fn = _extract_derive_function(html)
        cases_js = json.dumps(_CASES)
        script = textwrap.dedent(f"""
            {fn}
            const cases = {cases_js};
            const out = {{}};
            for (const [r, _] of cases) {{
                const x = deriveQueueStatus(r);
                if (!(x.label in out)) out[x.label] = x.sortRank;
                else if (out[x.label] !== x.sortRank) {{
                    out["__conflict__" + x.label] = [out[x.label], x.sortRank];
                }}
            }}
            process.stdout.write(JSON.stringify(out));
        """)
        path = tmp_path / "derive_rank.js"
        path.write_text(script)
        proc = subprocess.run(
            ["node", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout)
        conflicts = {k: v for k, v in out.items() if k.startswith("__conflict__")}
        assert not conflicts, f"label-to-rank conflicts: {conflicts}"


# ---------------------------------------------------------------------------
# (6) /api/v1/reviews API contract — auto_merge_enabled + mergeable_state
# ---------------------------------------------------------------------------


class TestReviewsApiSurfacesQueueFields:
    """A regression guard: the /api/v1/reviews payload must keep surfacing
    the fields the /reviews page now consumes."""

    def test_to_dict_includes_queue_fields(self):
        # Avoid importing oompah.scm at module import time — httpx may not
        # be available in some test environments. Skip gracefully.
        try:
            from oompah.scm import ReviewRequest
        except ModuleNotFoundError:
            pytest.skip("oompah.scm unavailable (no httpx)")

        rr = ReviewRequest(
            id="42", title="t", url="u", author="a", state="open",
            source_branch="b", target_branch="main",
            created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
            auto_merge_enabled=True, mergeable_state="clean",
        )
        d = rr.to_dict()
        assert d["auto_merge_enabled"] is True
        assert d["mergeable_state"] == "clean"

    def test_to_dict_defaults_safe_for_gitlab(self):
        try:
            from oompah.scm import ReviewRequest
        except ModuleNotFoundError:
            pytest.skip("oompah.scm unavailable (no httpx)")

        rr = ReviewRequest(
            id="42", title="t", url="u", author="a", state="open",
            source_branch="b", target_branch="main",
            created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        )
        d = rr.to_dict()
        # Defaults are safe for the deriveQueueStatus heuristic.
        assert d["auto_merge_enabled"] is False
        assert d["mergeable_state"] == ""
