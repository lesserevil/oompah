"""Static detection of tracker calls that can write terminal task states.

The runtime enforcement sweep repairs terminal writes that bypass the
coordinator.  This scanner is the earlier, CI-time guard: it rejects new
direct mutations unless the exact call site is part of the small documented
coordinator/persistence compatibility allowlist.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

_TERMINAL_NAMES = frozenset({"DONE", "MERGED", "ARCHIVED"})
_TERMINAL_VALUES = frozenset({"done", "merged", "archived"})
_UNCONDITIONAL_METHODS = {
    "close_issue": "Done",
    "archive_issue": "Archived",
}
_STATUS_METHODS = frozenset({"update_issue", "set_status"})
_STATUS_KEYWORDS = frozenset({"status", "state"})

AllowlistKey = tuple[str, str, str]

# Each entry identifies one existing compatibility or persistence boundary.
# New entries require a concrete reason and a matching source comment.
ALLOWLISTED_CALLS: dict[AllowlistKey, str] = {
    (
        "oompah/error_watcher.py",
        "ErrorWatcher.auto_close_for_issue",
        "close_issue",
    ): (
        "Closes an oompah-generated transient diagnostic only after the "
        "originating retry succeeds; this tracker-local recovery path may not "
        "have managed-project coordinator context."
    ),
    (
        "oompah/oompah_md_tracker.py",
        "OompahMarkdownTracker.archive_issue",
        "update_issue",
    ): "Low-level tracker persistence implementation for Archived.",
    (
        "oompah/orchestrator.py",
        "Orchestrator._reset_orphaned_in_progress",
        "update_issue",
    ): (
        "Reasserts Done only for an issue already present in the durable "
        "completed set; the enforcement sweep still verifies its audit metadata."
    ),
    (
        "oompah/orchestrator.py",
        "Orchestrator._defer_review_handoff",
        "update_issue",
    ): (
        "Compatibility write for a completed branch whose review is deferred "
        "solely by the project review-capacity limit."
    ),
    (
        "oompah/orchestrator.py",
        "Orchestrator._mark_stale_in_review_done",
        "update_issue",
    ): (
        "Reconciles a shared child only after Git containment proves its work "
        "is present on the epic branch."
    ),
    (
        "oompah/orchestrator.py",
        "Orchestrator._on_worker_exit",
        "close_issue",
    ): (
        "Compatibility close for a merge-conflict repair worker after the "
        "repair gate succeeds; terminal enforcement supplies the audit backstop."
    ),
    (
        "oompah/terminal_transition_coordinator.py",
        "TerminalTransitionCoordinator._apply_result_locked",
        "update_issue",
    ): "Applies a validated, persisted terminal-audit verdict.",
    (
        "oompah/terminal_transition_coordinator.py",
        "TerminalTransitionCoordinator._override_transition_locked",
        "update_issue",
    ): "Applies a validated, persisted project-owner override.",
    (
        "oompah/terminal_audit_enforcement.py",
        "TerminalAuditEnforcement._reconcile_incompatible_shared_epic_merged",
        "update_issue",
    ): (
        "Restores a legacy incompatible Merged child to its already completed "
        "Done audit during serialized startup recovery; it does not create an "
        "audit."
    ),
    (
        "oompah/orchestrator.py",
        "Orchestrator._supersede_wrong_epic_rebase_helper",
        "update_issue",
    ): (
        "Archives an auto-generated rebase helper task whose recorded target "
        "branch no longer matches the authoritative parent; only transitions "
        "unclaimed tasks in Open, In-Progress, or Needs-Rebase state after a "
        "fresh re-read confirms no worker has claimed it; the terminal "
        "enforcement sweep provides the audit backstop."
    ),
}


@dataclass(frozen=True)
class TerminalMutation:
    """One statically identifiable terminal tracker mutation."""

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


def _terminal_target(node: ast.AST) -> str | None:
    value: str | None = None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value
    elif isinstance(node, ast.Name):
        value = node.id
    elif isinstance(node, ast.Attribute):
        value = node.attr
    if value is None:
        return None

    normalized = value.strip().replace("-", "_").replace(" ", "_")
    upper = normalized.upper()
    if upper in _TERMINAL_NAMES:
        return upper.title()
    lower = normalized.lower()
    if lower in _TERMINAL_VALUES:
        return lower.title()
    return None


def _dict_terminal_target(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Dict):
        return None
    for key, value in zip(node.keys, node.values, strict=True):
        if (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and key.value.strip().lower() in _STATUS_KEYWORDS
        ):
            target = _terminal_target(value)
            if target is not None:
                return target
    return None


def _call_terminal_target(call: ast.Call, method: str) -> str | None:
    if method in _UNCONDITIONAL_METHODS:
        return _UNCONDITIONAL_METHODS[method]
    if method not in _STATUS_METHODS:
        return None

    for keyword in call.keywords:
        if keyword.arg is not None and keyword.arg.lower() in _STATUS_KEYWORDS:
            target = _terminal_target(keyword.value)
            if target is not None:
                return target
        elif keyword.arg is None:
            target = _dict_terminal_target(keyword.value)
            if target is not None:
                return target

    # ``set_status(issue, DONE)`` is a common positional form.  ``update_issue``
    # has no stable positional status argument, so only inspect set_status.
    if method == "set_status" and len(call.args) >= 2:
        return _terminal_target(call.args[1])
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
        self.allowlist_uses: dict[AllowlistKey, int] = {}

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
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            target = _call_terminal_target(node, method)
            if target is not None:
                function = ".".join(self.scope) or "<module>"
                key = (self.path, function, method)
                reason = self.allowlist.get(key)
                if reason is not None:
                    use_count = self.allowlist_uses.get(key, 0)
                    self.allowlist_uses[key] = use_count + 1
                    # A key permits one existing call, not a whole function.
                    # A second mutation of the same kind therefore remains a
                    # violation until it receives separate review.
                    if use_count:
                        reason = None
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
    """Parse *source* and return its identifiable terminal mutations."""

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
