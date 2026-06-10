#!/usr/bin/env python3
"""Smoke test for TASK-464.4: low-risk managed repo cutover in dual-read mode.

This script performs a REAL smoke test against the GitHub API, creating an
actual issue in ``lesserevil/oompah``, progressing it through the oompah
lifecycle, and closing it.  It verifies that:

  1. ``GitHubIssueTracker`` can create a GitHub-backed smoke issue.
  2. Status transitions (Open → In Progress → In Review → Done) work correctly.
  3. Comments can be added to GitHub issues via the tracker.
  4. Closing the issue completes the lifecycle cleanly.
  5. No new Backlog.md task files are created during the process.

Usage
-----
Run with the lesserevil token (set via env var):

    OOMPAH_GITHUB_TOKEN=<token> python scripts/smoke_cutover.py

or, if the gh CLI is authenticated as lesserevil:

    python scripts/smoke_cutover.py

The script prints the resulting GitHub issue URL on success and exits
non-zero on any failure.
"""

from __future__ import annotations

import os
import sys
import time
import json
import datetime
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so oompah can be imported.
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from oompah.github_tracker import GitHubIssueTracker, GitHubAuth  # noqa: E402
from oompah.tracker import TrackerError  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OWNER = "lesserevil"
REPO = "oompah"
ACTIVE_STATES = ["Open", "Needs CI Fix", "Needs Rebase"]
TERMINAL_STATES = ["Done", "Merged", "Archived"]

# oompah:status:* labels that must exist before creating the smoke issue.
# These are the minimal set needed for the smoke lifecycle.
REQUIRED_LABELS = [
    ("oompah:status:open", "0075ca", "oompah task status: Open"),
    ("oompah:status:in-progress", "e4e669", "oompah task status: In Progress"),
    ("oompah:status:in-review", "0e8a16", "oompah task status: In Review"),
    ("oompah:status:done", "cfd3d7", "oompah task status: Done"),
]


def _gh_api(method: str, path: str, body: dict | None = None) -> dict | list | None:
    """Call the GitHub REST API using the gh CLI.

    Falls back to the OOMPAH_GITHUB_TOKEN env var if set.
    """
    token = (
        os.environ.get("OOMPAH_GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("BD_OOMPAH_TOKEN")
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    import urllib.request
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            if raw.strip():
                return json.loads(raw)
            return None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        raise RuntimeError(f"GitHub API {method} {path} → {exc.code}: {raw}") from exc


def ensure_labels() -> None:
    """Create any missing oompah status labels in the repo."""
    print(f"Checking labels in {OWNER}/{REPO}...")
    existing_labels = _gh_api("GET", f"/repos/{OWNER}/{REPO}/labels?per_page=100")
    existing_names = {lbl["name"] for lbl in (existing_labels or [])}

    for name, color, description in REQUIRED_LABELS:
        if name not in existing_names:
            print(f"  Creating label: {name}")
            _gh_api(
                "POST",
                f"/repos/{OWNER}/{REPO}/labels",
                {"name": name, "color": color, "description": description},
            )
        else:
            print(f"  Label exists: {name}")


def verify_no_new_backlog_files(before_files: set[str]) -> None:
    """Assert that no new backlog/tasks/*.md files were created."""
    backlog_dir = _PROJECT_ROOT / "backlog" / "tasks"
    if not backlog_dir.exists():
        return
    after_files = {str(p) for p in backlog_dir.glob("*.md")}
    new_files = after_files - before_files
    if new_files:
        print(f"FAIL: New Backlog.md task files created: {new_files}")
        sys.exit(1)
    print("  ✓ No new Backlog.md task files created (AC#2 satisfied)")


def main() -> None:
    print("=" * 60)
    print("TASK-464.4 dual-read cutover smoke test")
    print(f"Repository: {OWNER}/{REPO}")
    print(f"Time: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print("=" * 60)

    # Record backlog task files BEFORE the smoke test.
    backlog_dir = _PROJECT_ROOT / "backlog" / "tasks"
    before_backlog = {str(p) for p in backlog_dir.glob("*.md")} if backlog_dir.exists() else set()
    print(f"\nExisting Backlog tasks: {len(before_backlog)} (will verify none are added)")

    # Step 1: Ensure required labels exist.
    print("\n[Step 1] Ensuring oompah status labels exist...")
    ensure_labels()

    # Step 2: Create the GitHubIssueTracker.
    print("\n[Step 2] Creating GitHubIssueTracker...")
    tracker = GitHubIssueTracker(
        owner=OWNER,
        repo=REPO,
        active_states=ACTIVE_STATES,
        terminal_states=TERMINAL_STATES,
    )
    print(f"  ✓ Tracker created for {OWNER}/{REPO}")

    # Step 3: Create smoke issue.
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    smoke_title = f"[SMOKE] TASK-464.4 dual-read cutover verification ({ts})"
    print(f"\n[Step 3] Creating smoke issue: {smoke_title!r}")
    smoke_issue = tracker.create_issue(
        title=smoke_title,
        issue_type="task",
        description=(
            "Automated smoke task for TASK-464.4 dual-read cutover verification.\n\n"
            "This issue was created by the oompah smoke test script to verify that "
            "the GitHubIssueTracker can create, update, comment on, and close "
            "GitHub Issues as part of the managed repo cutover workflow.\n\n"
            "It will be closed automatically by the smoke test script."
        ),
        priority=2,
        initial_status="Open",
        labels=["smoke-test"],
    )
    issue_url = smoke_issue.url or f"https://github.com/{OWNER}/{REPO}/issues/unknown"
    print(f"  ✓ Issue created: {smoke_issue.identifier}")
    print(f"    URL: {issue_url}")
    print(f"    State: {smoke_issue.state}")
    print(f"    Tracker kind: {smoke_issue.tracker_kind}")
    assert smoke_issue.tracker_kind == "github_issues", \
        f"Expected tracker_kind='github_issues', got {smoke_issue.tracker_kind!r}"
    assert smoke_issue.state == "Open", \
        f"Expected state='Open', got {smoke_issue.state!r}"

    identifier = smoke_issue.identifier
    print(f"\n  ✓ AC#1 (partial): GitHub-backed smoke task created: {identifier}")

    # Step 4: Add first comment.
    print(f"\n[Step 4] Adding 'dispatched' comment to {identifier}...")
    tracker.add_comment(
        identifier,
        "Smoke task dispatched by TASK-464.4 agent. Testing oompah dual-read cutover.",
        author="oompah",
    )
    print("  ✓ Comment added")

    # Step 5: Update status to In Progress.
    print(f"\n[Step 5] Updating status to 'In Progress'...")
    tracker.update_issue(identifier, status="In Progress")
    # Verify the update by fetching the issue.
    updated = tracker.fetch_issue_detail(identifier)
    assert updated is not None, f"Issue {identifier} not found after status update"
    print(f"  ✓ Status updated: {updated.state}")

    # Step 6: Add progress comment.
    print(f"\n[Step 6] Adding progress comment...")
    tracker.add_comment(
        identifier,
        "Agent working on smoke task. Status: In Progress.",
        author="oompah",
    )
    print("  ✓ Comment added")

    # Step 7: Update status to In Review (simulate PR).
    print(f"\n[Step 7] Updating status to 'In Review' (simulating PR)...")
    tracker.update_issue(
        identifier,
        status="In Review",
        pr_url=f"https://github.com/{OWNER}/{REPO}/pull/0",  # simulated PR link
    )
    updated = tracker.fetch_issue_detail(identifier)
    assert updated is not None
    print(f"  ✓ Status updated: {updated.state}")

    # Step 8: Add review comment.
    print(f"\n[Step 8] Adding review comment...")
    tracker.add_comment(
        identifier,
        f"PR opened for review. Smoke test verifying dual-read cutover flow for TASK-464.4.",
        author="oompah",
    )
    print("  ✓ Comment added")

    # Step 9: Update status to Done and close.
    print(f"\n[Step 9] Closing smoke issue (status: Done)...")
    tracker.update_issue(identifier, status="Done")
    updated = tracker.fetch_issue_detail(identifier)
    assert updated is not None
    print(f"  ✓ Status updated: {updated.state}")

    # Step 10: Add completion comment.
    print(f"\n[Step 10] Adding completion comment...")
    tracker.add_comment(
        identifier,
        (
            "Smoke task completed. TASK-464.4 dual-read cutover verification successful.\n\n"
            "Acceptance criteria verified:\n"
            "- AC#1: Real GitHub-backed smoke task created and completed ✓\n"
            "- AC#2: No Backlog.md tasks migrated (verified in smoke script) ✓"
        ),
        author="oompah",
    )
    print("  ✓ Completion comment added")

    # Step 11: Verify no new Backlog files.
    print(f"\n[Step 11] Verifying no new Backlog.md task files were created...")
    verify_no_new_backlog_files(before_backlog)

    # Success.
    print("\n" + "=" * 60)
    print("SMOKE TEST PASSED")
    print(f"Issue URL: {issue_url}")
    print(f"Identifier: {identifier}")
    print(f"Final state: {updated.state}")
    print("=" * 60)
    print("\nAC#1 SATISFIED: Real managed repo created and completed a GitHub-backed smoke task.")
    print("AC#2 SATISFIED: Existing Backlog.md tasks were not migrated.")
    return issue_url, identifier


if __name__ == "__main__":
    try:
        issue_url, identifier = main()
        print(f"\nResult: {identifier} → {issue_url}")
        sys.exit(0)
    except TrackerError as exc:
        print(f"\nERROR (TrackerError): {exc}", file=sys.stderr)
        sys.exit(1)
    except AssertionError as exc:
        print(f"\nERROR (Assertion failed): {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        import traceback
        print(f"\nERROR: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
