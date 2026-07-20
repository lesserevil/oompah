"""``oompah admin`` CLI — operator commands for state-branch migration (OOMPAH-259).

Commands:
  oompah admin validate-state-branch <project-id>
      Run pre-migration validation and print a pass/fail table.

  oompah admin migrate-state-branch <project-id> [--stage A|B|C] [--rollback]
      Advance or reverse the migration stage for the named project.
      Dry-run by default; add --confirm to apply.

  oompah admin state-branch-status <project-id>
      Print branch name, last push time, pending mutations, alert status.

The CLI communicates with the running oompah service via the HTTP API so that
the service's ProjectStore remains the single authoritative writer of project
configuration.  A running service is required for migrate and rollback; the
validate and status commands read git state directly and do not need the
service.

Design reference: plans/state-branch-design.md § 7.2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _server_url() -> str:
    """Return the oompah server URL from OOMPAH_SERVER_URL or the default."""
    return os.environ.get("OOMPAH_SERVER_URL", "http://127.0.0.1:8090").rstrip("/")


def _api(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    """Make an HTTP request to the oompah API.

    Returns (status_code, parsed_json).  Raises SystemExit on network error.
    """
    try:
        import urllib.request
        import urllib.error

        url = _server_url() + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as exc:
            try:
                body_bytes = exc.read()
                parsed = json.loads(body_bytes)
            except Exception:
                parsed = {"error": {"message": exc.reason}}
            return exc.code, parsed
    except ConnectionRefusedError:
        sys.exit(
            f"ERROR: Cannot connect to oompah at {_server_url()}. "
            "Is the service running? (make start)"
        )
    except OSError as exc:
        sys.exit(f"ERROR: Network error: {exc}")


def _resolve_project(project_id: str) -> dict:
    """Fetch project details from the running service."""
    status, data = _api("GET", f"/api/v1/projects/{project_id}")
    if status == 404:
        sys.exit(f"ERROR: Project {project_id!r} not found in the running service.")
    if status != 200:
        msg = data.get("error", {}).get("message", "unknown error")
        sys.exit(f"ERROR: Could not fetch project {project_id!r}: {msg}")
    return data


# ---------------------------------------------------------------------------
# validate-state-branch
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> None:
    """Run pre-migration validation checks and print a table."""
    status, data = _api(
        "POST",
        f"/api/v1/projects/{args.project_id}/state-branch/validate",
    )
    if status == 404:
        sys.exit(f"ERROR: Project {args.project_id!r} not found.")
    if status not in (200, 207):
        msg = data.get("error", {}).get("message", "unknown error")
        sys.exit(f"ERROR: Validation failed: {msg}")

    checks = data.get("checks", [])
    all_passed = data.get("all_passed", False)

    # Print table
    col_w = max((len(c["name"]) for c in checks), default=20)
    print()
    print(f"{'Check':<{col_w}}  {'Result'}")
    print("-" * (col_w + 10))
    for chk in checks:
        result_str = "PASS" if chk["passed"] else "FAIL"
        msg = chk.get("message", "")
        print(f"{chk['name']:<{col_w}}  {result_str}")
        if msg and not chk["passed"]:
            print(f"  {msg}")
    print()
    if all_passed:
        print("All checks passed. Safe to migrate.")
        sys.exit(0)
    else:
        failed = [c["name"] for c in checks if not c["passed"]]
        print(f"FAILED checks: {', '.join(failed)}")
        print("Fix all failures before running migrate-state-branch.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# migrate-state-branch
# ---------------------------------------------------------------------------


def cmd_migrate(args: argparse.Namespace) -> None:
    """Run a migration stage (or rollback)."""
    if not args.confirm and not args.dry_run:
        args.dry_run = True  # default

    stage = args.stage or None
    rollback = getattr(args, "rollback", False)

    if rollback:
        action = "rollback"
    elif stage:
        action = stage
    else:
        # Default to next stage based on current project config.
        action = None

    body: dict = {}
    if action:
        body["action"] = action
    body["dry_run"] = bool(args.dry_run)
    body["confirm"] = bool(args.confirm)

    if args.dry_run and not args.confirm:
        print(f"DRY RUN — pass --confirm to apply changes.")
        print(f"  Project: {args.project_id}")
        print(f"  Action:  {action or '(auto-detect next stage)'}")
        print()

    status, data = _api(
        "POST",
        f"/api/v1/projects/{args.project_id}/state-branch/migrate",
        body=body,
    )
    if status == 404:
        sys.exit(f"ERROR: Project {args.project_id!r} not found.")
    if status not in (200, 202):
        msg = data.get("error", {}).get("message", "unknown error")
        sys.exit(f"ERROR: Migration failed: {msg}")

    result = data
    print(f"Stage:       {result.get('stage', '-')}")
    print(f"Status:      {'OK' if result.get('ok') else 'FAILED'}")
    if result.get("already_done"):
        print("Note:        already at this stage (idempotent no-op)")
    if result.get("message"):
        print(f"Message:     {result['message']}")
    if result.get("error"):
        print(f"Error:       {result['error']}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run and not args.confirm:
        print()
        print("(dry run — no changes applied; re-run with --confirm to apply)")


# ---------------------------------------------------------------------------
# state-branch-status
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    """Print state-branch status for a project."""
    status, data = _api(
        "GET",
        f"/api/v1/projects/{args.project_id}/state-branch/status",
    )
    if status == 404:
        sys.exit(f"ERROR: Project {args.project_id!r} not found.")
    if status != 200:
        msg = data.get("error", {}).get("message", "unknown error")
        sys.exit(f"ERROR: Could not fetch status: {msg}")

    project_data = data.get("project", {})
    branch_data = data.get("state_branch", {})
    migration = data.get("migration", {})

    print(f"\nProject: {project_data.get('id', args.project_id)}")
    print(f"State-branch enabled:  {project_data.get('state_branch_enabled', False)}")
    print(f"Shadow write active:   {project_data.get('state_branch_shadow_write', False)}")
    print(f"Migration stage:       {project_data.get('state_branch_migration_stage', '')!r}")
    print()
    if branch_data:
        print(f"Branch:                {branch_data.get('branch', '-')}")
        print(f"Last push:             {branch_data.get('last_push_at') or 'never'}")
        print(f"Pending mutations:     {branch_data.get('pending_mutations', 0)}")
        print(f"Push failures:         {branch_data.get('push_failures', 0)}")
        alert = branch_data.get("alert")
        print(f"Alert:                 {alert or 'none'}")
    else:
        print("State branch health:   (not enabled or not yet initialised)")

    if migration:
        print()
        print(f"Branch exists (local):  {migration.get('branch_exists_local', '?')}")
        print(f"Branch exists (remote): {migration.get('branch_exists_remote', '?')}")
        print(
            f"Tasks on default branch: {migration.get('tasks_on_default_branch', '?')}"
        )
        if migration.get("last_state_branch_commit"):
            print(f"Last state commit:     {migration['last_state_branch_commit']}")

    # Check for sync divergence when --check-sync is passed.
    if getattr(args, "check_sync", False):
        _check_sync(args.project_id, data)


def _check_sync(project_id: str, status_data: dict) -> None:
    """Check shadow-write sync divergence (for Stage A monitoring)."""
    status, data = _api(
        "GET",
        f"/api/v1/projects/{project_id}/state-branch/sync-check",
    )
    if status == 200:
        synced = data.get("synced", None)
        diffs = data.get("diffs", [])
        print()
        if synced is True:
            print("Shadow sync:           IN SYNC ✓")
        elif synced is False:
            print(f"Shadow sync:           DIVERGED — {len(diffs)} file(s) differ")
            for d in diffs[:5]:
                print(f"  {d}")
            if len(diffs) > 5:
                print(f"  ... ({len(diffs) - 5} more)")
        else:
            print("Shadow sync:           n/a (shadow writes not active)")
    elif status == 404:
        print("Shadow sync:           (endpoint not available)")
    else:
        print(f"Shadow sync:           error {status}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oompah admin",
        description="Operator commands for oompah service administration.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate-state-branch
    p_val = sub.add_parser(
        "validate-state-branch",
        help="Run pre-migration validation checks.",
    )
    p_val.add_argument("project_id", help="Project ID (e.g. proj-14849f1b)")
    p_val.set_defaults(func=cmd_validate)

    # migrate-state-branch
    p_mig = sub.add_parser(
        "migrate-state-branch",
        help="Advance or reverse the migration stage.",
    )
    p_mig.add_argument("project_id", help="Project ID")
    stage_group = p_mig.add_mutually_exclusive_group()
    stage_group.add_argument(
        "--stage",
        choices=["A", "B", "C"],
        help="Target migration stage (A=shadow write, B=state-branch only, C=cleanup).",
    )
    stage_group.add_argument(
        "--rollback",
        action="store_true",
        help="Roll back to legacy default-branch mode.",
    )
    confirm_group = p_mig.add_mutually_exclusive_group()
    confirm_group.add_argument(
        "--confirm",
        action="store_true",
        help="Apply the migration (required to make changes; default is dry-run).",
    )
    confirm_group.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Print what would happen without making changes (default).",
    )
    p_mig.set_defaults(func=cmd_migrate, dry_run=False)

    # state-branch-status
    p_stat = sub.add_parser(
        "state-branch-status",
        help="Show state-branch health for a project.",
    )
    p_stat.add_argument("project_id", help="Project ID")
    p_stat.add_argument(
        "--check-sync",
        action="store_true",
        help="Also check shadow-write sync divergence (for Stage A monitoring).",
    )
    p_stat.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
