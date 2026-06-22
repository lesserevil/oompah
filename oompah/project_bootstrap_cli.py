"""Command-line interface for applying oompah project bootstrap templates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from oompah.project_bootstrap import (
    apply_project_bootstrap_updates,
    check_project_bootstrap_drift,
    preview_project_bootstrap_updates,
)


def _repo_path(raw: str | None) -> Path:
    return Path(raw or ".").expanduser().resolve()


def _print_status(repo: Path) -> None:
    status = check_project_bootstrap_drift(repo)
    print(f"Repository: {repo}")
    print(f"All current: {'yes' if status.all_current else 'no'}")
    if status.drifted:
        print("\nPending updates:")
        for drift in status.drifted:
            if drift.current is None:
                print(f"  - {drift.path} (missing)")
            else:
                print(f"  - {drift.path} (outdated)")
    if status.protected:
        print("\nProtected project-owned files:")
        for drift in status.protected:
            print(f"  - {drift.path}: {drift.reason}")
    if status.current:
        print("\nCurrent oompah-managed files:")
        for drift in status.current:
            print(f"  - {drift.path}")


def _cmd_status(args: argparse.Namespace) -> None:
    _print_status(_repo_path(args.repo))


def _cmd_preview(args: argparse.Namespace) -> None:
    diff = preview_project_bootstrap_updates(_repo_path(args.repo))
    if diff:
        print(diff, end="" if diff.endswith("\n") else "\n")


def _cmd_apply(args: argparse.Namespace) -> None:
    result = apply_project_bootstrap_updates(
        _repo_path(args.repo),
        git_user_name=args.git_user_name,
        git_user_email=args.git_user_email,
        branch=args.branch,
        commit_message=args.message,
        commit=args.commit,
        push=args.push,
        dry_run=args.dry_run,
    )
    if result.error:
        sys.exit(f"ERROR: {result.error}")

    if args.dry_run:
        print("Dry run: no files written.")
    if result.applied:
        print("Applied:")
        for path in result.applied:
            print(f"  - {path}")
    else:
        print("No bootstrap updates needed.")
    if result.protected:
        print("Protected project-owned files left unchanged:")
        for path in result.protected:
            print(f"  - {path}")
    if result.commit_sha:
        print(f"Commit: {result.commit_sha}")
    if result.pushed:
        print(f"Pushed: origin {args.branch}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oompah project-bootstrap",
        description=(
            "Inspect or apply oompah's canonical managed-project bootstrap "
            "templates to a repository."
        ),
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_status = sub.add_parser("status", help="Show bootstrap drift status")
    p_status.add_argument("repo", nargs="?", help="Repository path (default: .)")

    p_preview = sub.add_parser("preview", help="Print a unified diff preview")
    p_preview.add_argument("repo", nargs="?", help="Repository path (default: .)")

    p_apply = sub.add_parser("apply", help="Apply pending bootstrap updates")
    p_apply.add_argument("repo", nargs="?", help="Repository path (default: .)")
    p_apply.add_argument("--branch", default="main", help="Branch to push when --push is used")
    p_apply.add_argument(
        "--commit",
        action="store_true",
        help="Commit the bootstrap update after writing files",
    )
    p_apply.add_argument(
        "--push",
        action="store_true",
        help="Push the commit to origin/branch; implies --commit",
    )
    p_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Report paths that would be written without changing files",
    )
    p_apply.add_argument(
        "--message",
        default="chore: refresh oompah project bootstrap files",
        help="Commit message used with --commit",
    )
    p_apply.add_argument("--git-user-name", default=None)
    p_apply.add_argument("--git-user-email", default=None)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "push", False):
        args.commit = True

    dispatch: dict[str, Any] = {
        "status": _cmd_status,
        "preview": _cmd_preview,
        "apply": _cmd_apply,
    }
    dispatch[args.subcommand](args)

