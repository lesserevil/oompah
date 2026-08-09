"""Static detection of tracker calls that can write task status.

All managed-task lifecycle mutations must enter through
``TaskTransitionService``.  This scanner is the CI-time architectural guard:
it rejects direct tracker mutations unless the exact function is a documented
persistence/protocol adapter or a proven status-free dynamic metadata writer.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

_UNCONDITIONAL_METHODS = {
    "close_issue": "Done",
    "archive_issue": "Archived",
    "reopen_issue": "active status",
    "mark_needs_human": "Needs Human",
}
_STATUS_METHODS = frozenset({"update_issue", "set_status"})
_STATUS_KEYWORDS = frozenset({"status", "state"})

AllowlistKey = tuple[str, str, str]

# Each entry identifies one reviewed persistence/protocol boundary or one
# dynamic metadata call whose status value is removed before invocation.  A
# key allows the exact method within the exact function; it does not allow a
# whole module or class.  New entries require a concrete architectural reason.
ALLOWLISTED_CALLS: dict[AllowlistKey, str] = {
    (
        "oompah/oompah_md_tracker.py",
        "OompahMarkdownTracker.close_issue",
        "update_issue",
    ): "Low-level native Markdown tracker status persistence adapter.",
    (
        "oompah/oompah_md_tracker.py",
        "OompahMarkdownTracker.reopen_issue",
        "update_issue",
    ): "Low-level native Markdown tracker status persistence adapter.",
    (
        "oompah/oompah_md_tracker.py",
        "OompahMarkdownTracker.archive_issue",
        "update_issue",
    ): "Low-level native Markdown tracker status persistence adapter.",
    (
        "oompah/oompah_md_tracker.py",
        "OompahMarkdownTracker.mark_needs_human",
        "update_issue",
    ): "Low-level native Markdown tracker status persistence adapter.",
    (
        "oompah/github_tracker.py",
        "GitHubIssueTracker.mark_needs_human",
        "update_issue",
    ): "Low-level GitHub tracker status persistence adapter.",
    (
        "oompah/provenance_suppression.py",
        "ProvenanceGuardedTracker.update_issue",
        "update_issue",
    ): (
        "Final managed-tracker authority facade: it checks durable provenance "
        "suppression before delegating an already-authorized protocol operation."
    ),
    (
        "oompah/provenance_suppression.py",
        "ProvenanceGuardedTracker.reopen_issue",
        "reopen_issue",
    ): (
        "Final managed-tracker authority facade: it checks durable provenance "
        "suppression before delegating an already-authorized protocol operation."
    ),
    (
        "oompah/provenance_suppression.py",
        "ProvenanceGuardedTracker.mark_needs_human",
        "mark_needs_human",
    ): (
        "Final managed-tracker authority facade: it checks durable provenance "
        "suppression before delegating an already-authorized protocol operation."
    ),
    (
        "oompah/provenance_suppression.py",
        "ProvenanceGuardedTracker.close_issue",
        "close_issue",
    ): (
        "Final managed-tracker authority facade: it checks durable provenance "
        "suppression before delegating an already-authorized protocol operation."
    ),
    (
        "oompah/provenance_suppression.py",
        "ProvenanceGuardedTracker.archive_issue",
        "archive_issue",
    ): (
        "Final managed-tracker authority facade: it checks durable provenance "
        "suppression before delegating an already-authorized protocol operation."
    ),
    (
        "oompah/terminal_transition_coordinator.py",
        "TerminalTransitionCoordinator.reconcile_completed_recurrence_sync._operation",
        "update_issue",
    ): "Low-level adapter that restores a previously authorized audit result.",
    (
        "oompah/terminal_transition_coordinator.py",
        "TerminalTransitionCoordinator.retry_failed_audit._operation",
        "update_issue",
    ): "Low-level terminal-audit adapter that stages a persisted retry.",
    (
        "oompah/terminal_transition_coordinator.py",
        "TerminalTransitionCoordinator._transition_locked",
        "update_issue",
    ): "Low-level terminal-audit adapter that stages a persisted transition.",
    (
        "oompah/terminal_transition_coordinator.py",
        "TerminalTransitionCoordinator._apply_result_locked",
        "update_issue",
    ): "Low-level adapter that applies a validated terminal-audit verdict.",
    (
        "oompah/terminal_transition_coordinator.py",
        "TerminalTransitionCoordinator._override_transition_locked",
        "update_issue",
    ): "Low-level adapter that applies a validated project-owner override.",
    (
        "oompah/github_intake_bridge.py",
        "sync_github_issue_intake_statuses_for_project",
        "update_issue",
    ): (
        "External customer-facing GitHub issue mirror; it does not mutate the "
        "native managed task."
    ),
    (
        "oompah/server.py",
        "api_update_issue._update_fields_under_project_lock",
        "update_issue",
    ): (
        "Status is popped and routed through TaskTransitionService before this "
        "bounded writer-thread call revalidates the committed status and applies "
        "status-free metadata."
    ),
}


@dataclass(frozen=True)
class TerminalMutation:
    """One statically identifiable direct tracker status mutation."""

    path: str
    line: int
    column: int
    function: str
    method: str
    target: str
    allowlist_reason: str | None = None

    @property
    def allowed(self) -> bool:
        return self.allowlist_reason is not None

    def describe(self) -> str:
        return (
            f"{self.path}:{self.line}:{self.column + 1}: "
            f"{self.function} calls {self.method}() for {self.target}"
        )


def _normalized_path(path: Path, root: Path | None) -> str:
    candidate = path.resolve()
    if root is not None:
        try:
            return candidate.relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def _status_target(node: ast.AST) -> str:
    """Return a concise source-level description of a status expression."""

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return "dynamic status"


def _dict_status_target(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Dict):
        return "dynamic **kwargs"
    for key, value in zip(node.keys, node.values, strict=True):
        if (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and key.value.strip().lower() in _STATUS_KEYWORDS
        ):
            return _status_target(value)
    return None


def _call_status_target(call: ast.Call, method: str) -> str | None:
    if method in _UNCONDITIONAL_METHODS:
        return _UNCONDITIONAL_METHODS[method]
    if method not in _STATUS_METHODS:
        return None

    for keyword in call.keywords:
        if keyword.arg is not None and keyword.arg.lower() in _STATUS_KEYWORDS:
            return _status_target(keyword.value)
        elif keyword.arg is None:
            target = _dict_status_target(keyword.value)
            if target is not None:
                return target

    # ``set_status(issue, DONE)`` is a common positional form.  ``update_issue``
    # has no stable positional status argument, so only inspect set_status.
    if method == "set_status" and len(call.args) >= 2:
        return _status_target(call.args[1])
    return None


class _MutationVisitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        path: str,
        allowlist: Mapping[AllowlistKey, str],
    ) -> None:
        self.path = path
        self.allowlist = allowlist
        self.scope: list[str] = []
        self.mutations: list[TerminalMutation] = []

    def _visit_scope(self, node: ast.AST, name: str) -> None:
        self.scope.append(name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self._visit_scope(node, node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_scope(node, node.name)

    def visit_AsyncFunctionDef(  # noqa: N802
        self, node: ast.AsyncFunctionDef
    ) -> None:
        self._visit_scope(node, node.name)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        method: str | None = None
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
        else:
            # Async/thread helpers commonly receive a bound tracker writer as
            # their first argument, for example
            # ``run_io(tracker.update_issue, task, status=OPEN)``.  Treat that
            # as the same mutation rather than allowing indirection to evade
            # the architectural boundary.
            for argument in node.args:
                if (
                    isinstance(argument, ast.Attribute)
                    and argument.attr
                    in (_STATUS_METHODS | _UNCONDITIONAL_METHODS.keys())
                ):
                    method = argument.attr
                    break
        if method is not None:
            target = _call_status_target(node, method)
            if target is not None:
                function = ".".join(self.scope) or "<module>"
                key = (self.path, function, method)
                reason = self.allowlist.get(key)
                self.mutations.append(
                    TerminalMutation(
                        path=self.path,
                        line=node.lineno,
                        column=node.col_offset,
                        function=function,
                        method=method,
                        target=target,
                        allowlist_reason=reason,
                    )
                )
        self.generic_visit(node)


def scan_source(
    source: str,
    *,
    path: str,
    allowlist: Mapping[AllowlistKey, str] = ALLOWLISTED_CALLS,
) -> list[TerminalMutation]:
    """Parse *source* and return its identifiable direct status mutations."""

    tree = ast.parse(source, filename=path)
    visitor = _MutationVisitor(path=path, allowlist=allowlist)
    visitor.visit(tree)
    return visitor.mutations


def scan_file(
    path: Path,
    *,
    root: Path | None = None,
    allowlist: Mapping[AllowlistKey, str] = ALLOWLISTED_CALLS,
) -> list[TerminalMutation]:
    """Scan one Python source file."""

    display_path = _normalized_path(path, root)
    return scan_source(
        path.read_text(encoding="utf-8"),
        path=display_path,
        allowlist=allowlist,
    )


def python_files(paths: Iterable[Path]) -> list[Path]:
    """Expand files and directories into a deterministic Python-file list."""

    files: set[Path] = set()
    for path in paths:
        if path.is_dir():
            files.update(
                candidate for candidate in path.rglob("*.py") if candidate.is_file()
            )
        elif path.suffix == ".py" and path.is_file():
            files.add(path)
    return sorted(files)


def scan_paths(
    paths: Iterable[Path],
    *,
    root: Path | None = None,
    allowlist: Mapping[AllowlistKey, str] = ALLOWLISTED_CALLS,
) -> list[TerminalMutation]:
    """Scan all Python files under *paths*."""

    mutations: list[TerminalMutation] = []
    for path in python_files(paths):
        mutations.extend(scan_file(path, root=root, allowlist=allowlist))
    return mutations


def violations(mutations: Iterable[TerminalMutation]) -> list[TerminalMutation]:
    """Return only mutations that have no exact allowlist entry."""

    return [mutation for mutation in mutations if not mutation.allowed]


__all__ = [
    "ALLOWLISTED_CALLS",
    "AllowlistKey",
    "TerminalMutation",
    "python_files",
    "scan_file",
    "scan_paths",
    "scan_source",
    "violations",
]
