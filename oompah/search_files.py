"""Bounded Python-regular-expression search for agent tool catalogs.

This module is also the process boundary for untrusted regular expressions.
The parent tool runner gives the worker a short wall-clock timeout, so a
pathological-but-valid expression cannot stall the orchestration process.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import Any


MAX_OUTPUT_CHARS = 64_000
MAX_MATCHES = 100
MAX_CONTEXT_LINES = 20
MAX_FILE_BYTES = 8_000_000
MAX_TOTAL_BYTES = 64_000_000
SEARCH_SECONDS = 14.0

_TRUNCATION = (
    "... (search output truncated by Oompah before provider transport; "
    "narrow pattern/path or reduce context to continue)"
)


def _safe_resolve(workspace: Path, relative: str) -> Path:
    resolved = (workspace / relative).resolve()
    root = workspace.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(
            f"Path traversal blocked: {relative!r} resolves outside workspace"
        )
    return resolved


def _candidate_files(search_path: Path) -> Any:
    if search_path.is_file():
        yield search_path
        return
    if not search_path.is_dir():
        return

    for root, directories, filenames in os.walk(search_path, followlinks=False):
        directories.sort()
        filenames.sort()
        root_path = Path(root)
        for filename in filenames:
            yield root_path / filename


def _matches_include(relative: str, include: str) -> bool:
    if not include:
        return True
    return fnmatch.fnmatchcase(relative, include) or fnmatch.fnmatchcase(
        Path(relative).name, include
    )


def _render_file_matches(
    relative: str,
    lines: list[str],
    matcher: re.Pattern[str],
    *,
    context: int,
    remaining_matches: int,
) -> tuple[list[str], int]:
    match_lines: list[int] = []
    for index, line in enumerate(lines):
        if matcher.search(line):
            match_lines.append(index)
            if len(match_lines) >= remaining_matches:
                break
    if not match_lines:
        return [], 0

    selected: dict[int, bool] = {}
    for match_index in match_lines:
        start = max(0, match_index - context)
        end = min(len(lines), match_index + context + 1)
        for index in range(start, end):
            selected[index] = selected.get(index, False) or index == match_index

    rendered: list[str] = []
    previous: int | None = None
    for index in sorted(selected):
        if previous is not None and index != previous + 1:
            rendered.append("--")
        separator = ":" if selected[index] else "-"
        rendered.append(f"{relative}{separator}{index + 1}{separator}{lines[index]}")
        previous = index
    return rendered, len(match_lines)


def search_workspace(workspace: Path, args: dict[str, Any]) -> str:
    """Search workspace files line-by-line using a bounded Python regex."""

    pattern = args.get("pattern")
    if not isinstance(pattern, str):
        return "Error: pattern must be a string"
    try:
        matcher = re.compile(pattern)
    except re.error as exc:
        return f"Error: invalid Python regex: {exc}"

    raw_context = args.get("context", 0)
    if (
        isinstance(raw_context, bool)
        or not isinstance(raw_context, int)
        or not 0 <= raw_context <= MAX_CONTEXT_LINES
    ):
        return f"Error: context must be an integer from 0 to {MAX_CONTEXT_LINES}"
    context = raw_context

    include = args.get("include", "")
    if not isinstance(include, str):
        return "Error: include must be a glob string"
    relative_path = args.get("path", ".")
    if not isinstance(relative_path, str):
        return "Error: path must be a string"
    try:
        search_path = _safe_resolve(workspace, relative_path)
    except ValueError as exc:
        return f"Error: {exc}"
    if not search_path.exists():
        return f"Error: search path not found: {relative_path}"

    root = workspace.resolve()
    deadline = time.monotonic() + SEARCH_SECONDS
    scanned_bytes = 0
    matches = 0
    rendered: list[str] = []
    truncated = False

    for candidate in _candidate_files(search_path):
        if time.monotonic() >= deadline or scanned_bytes >= MAX_TOTAL_BYTES:
            truncated = True
            break
        try:
            resolved = candidate.resolve()
            if resolved != root and root not in resolved.parents:
                # Never follow an in-workspace symlink to operator data.
                continue
            relative = resolved.relative_to(root).as_posix()
            if not _matches_include(relative, include):
                continue
            metadata = resolved.stat()
            if not stat.S_ISREG(metadata.st_mode):
                continue
            size = metadata.st_size
            if size > MAX_FILE_BYTES or scanned_bytes + size > MAX_TOTAL_BYTES:
                truncated = True
                continue
            data = resolved.read_bytes()
        except (OSError, ValueError):
            continue
        scanned_bytes += len(data)
        if b"\x00" in data:
            continue

        lines = data.decode("utf-8", errors="replace").splitlines()
        file_output, file_matches = _render_file_matches(
            relative,
            lines,
            matcher,
            context=context,
            remaining_matches=MAX_MATCHES - matches,
        )
        if not file_matches:
            continue
        rendered.extend(file_output)
        matches += file_matches
        if matches >= MAX_MATCHES:
            truncated = True
            break

    if not rendered:
        suffix = f"\n{_TRUNCATION}" if truncated else ""
        return f"No matches found for {pattern!r}{suffix}"

    output = "\n".join(rendered)
    if truncated or len(output) > MAX_OUTPUT_CHARS:
        content_limit = MAX_OUTPUT_CHARS - len(_TRUNCATION) - 1
        output = output[:content_limit]
        output = f"{output.rstrip()}\n{_TRUNCATION}"
    return output


def main() -> int:
    try:
        request = json.load(sys.stdin)
        workspace = Path(request["workspace"])
        args = request["args"]
        if not isinstance(args, dict):
            raise ValueError("args must be an object")
        result = search_workspace(workspace, args)
    except Exception as exc:  # noqa: BLE001 - subprocess returns a safe error
        result = f"Error searching: {exc}"
    sys.stdout.write(result[:MAX_OUTPUT_CHARS])
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through tool process
    raise SystemExit(main())
