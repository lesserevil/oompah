#!/usr/bin/env python3
"""Fail when Python sources contain unauthorized terminal tracker writes."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oompah.terminal_mutation_scanner import scan_paths, violations


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path.cwd()
    paths = [Path(value) for value in args] if args else [root / "oompah"]
    mutations = scan_paths(paths, root=root)
    unauthorized = violations(mutations)

    for mutation in unauthorized:
        print(f"ERROR: {mutation.describe()}", file=sys.stderr)
        print(
            "  Route the transition through TerminalTransitionCoordinator or "
            "document an exact allowlist entry in "
            "oompah/terminal_mutation_scanner.py.",
            file=sys.stderr,
        )

    if unauthorized:
        print(
            f"Found {len(unauthorized)} unauthorized terminal mutation(s).",
            file=sys.stderr,
        )
        return 1

    allowed_count = sum(mutation.allowed for mutation in mutations)
    print(
        f"Terminal mutation scan passed: {len(mutations)} identified, "
        f"{allowed_count} explicitly allowlisted."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
