"""Regression coverage for the terminal-mutation CI source guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from oompah.terminal_mutation_scanner import (
    ALLOWLISTED_CALLS,
    scan_paths,
    scan_source,
    violations,
)
from scripts.find_terminal_mutations import main


@pytest.mark.parametrize(
    ("statement", "method", "target"),
    [
        ("tracker.close_issue(issue)", "close_issue", "Done"),
        ("tracker.archive_issue(issue)", "archive_issue", "Archived"),
        ("tracker.update_issue(issue, status=DONE)", "update_issue", "Done"),
        ("tracker.update_issue(issue, status='Merged')", "update_issue", "Merged"),
        (
            "tracker.update_issue(issue, **{'status': ARCHIVED})",
            "update_issue",
            "Archived",
        ),
        ("tracker.set_status(issue, TargetState.DONE)", "set_status", "Done"),
    ],
)
def test_scanner_detects_terminal_mutation_forms(
    statement: str,
    method: str,
    target: str,
) -> None:
    found = scan_source(
        f"def mutate(tracker, issue):\n    {statement}\n",
        path="oompah/example.py",
        allowlist={},
    )

    assert [(item.method, item.target, item.function) for item in found] == [
        (method, target, "mutate")
    ]
    assert len(violations(found)) == 1


@pytest.mark.parametrize(
    "source",
    [
        "def compare(issue):\n    return issue.state == DONE\n",
        "def update(tracker, issue):\n    tracker.update_issue(issue, status=OPEN)\n",
        "def update(tracker, issue, status):\n    tracker.update_issue(issue, status=status)\n",
        "class Tracker:\n    def close_issue(self, issue):\n        return issue\n",
    ],
)
def test_scanner_ignores_comparisons_nonterminal_and_definitions(source: str) -> None:
    assert scan_source(source, path="oompah/example.py", allowlist={}) == []


def test_allowlist_requires_exact_path_function_and_method() -> None:
    source = """
class TerminalTransitionCoordinator:
    def _apply_result_locked(self, tracker, issue):
        tracker.update_issue(issue, status=DONE)
"""
    allowed = scan_source(
        source,
        path="oompah/terminal_transition_coordinator.py",
    )
    wrong_function = scan_source(
        source.replace("_apply_result_locked", "new_bypass"),
        path="oompah/terminal_transition_coordinator.py",
    )

    assert len(allowed) == 1
    assert allowed[0].allowed
    assert "validated" in (allowed[0].allowlist_reason or "")
    assert len(violations(wrong_function)) == 1


def test_allowlist_key_permits_only_one_existing_call() -> None:
    source = """
class TerminalTransitionCoordinator:
    def _apply_result_locked(self, tracker, first, second):
        tracker.update_issue(first, status=DONE)
        tracker.update_issue(second, status=DONE)
"""
    found = scan_source(
        source,
        path="oompah/terminal_transition_coordinator.py",
    )

    assert len(found) == 2
    assert found[0].allowed
    assert not found[1].allowed
    assert violations(found) == [found[1]]


def test_allowlist_entries_have_actionable_reasons() -> None:
    assert ALLOWLISTED_CALLS
    for (path, function, method), reason in ALLOWLISTED_CALLS.items():
        assert path.startswith("oompah/")
        assert function and "." in function
        assert method in {"close_issue", "archive_issue", "update_issue", "set_status"}
        assert len(reason.strip()) >= 20


def test_repository_has_no_unauthorized_terminal_mutations() -> None:
    root = Path(__file__).resolve().parents[1]
    found = scan_paths([root / "oompah"], root=root)

    assert found, "scanner should identify the documented compatibility boundaries"
    assert violations(found) == []
    assert {
        (item.path, item.function, item.method)
        for item in found
        if item.allowed
    }.issubset(ALLOWLISTED_CALLS)


def test_cli_fails_for_violation_and_passes_for_safe_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    unsafe = tmp_path / "unsafe.py"
    unsafe.write_text(
        "def bypass(tracker, issue):\n"
        "    tracker.close_issue(issue)\n",
        encoding="utf-8",
    )
    safe = tmp_path / "safe.py"
    safe.write_text(
        "def inspect(issue):\n"
        "    return issue.state == 'Done'\n",
        encoding="utf-8",
    )

    assert main([str(unsafe)]) == 1
    error = capsys.readouterr().err
    assert "close_issue()" in error
    assert "Found 1 unauthorized terminal mutation" in error

    assert main([str(safe)]) == 0
    output = capsys.readouterr().out
    assert "Terminal mutation scan passed" in output
