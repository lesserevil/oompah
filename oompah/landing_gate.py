"""Landing gate: detect agent runs that completed without landing.

Motivating evidence (issue oompah-zlz_2-kc2k.1):

* oompah-zlz_2-rxwe.1: agent ran 6 sessions across 3 profiles,
  described implementation correctly, passed inline smoke tests,
  then exited with "Agent finished (no more tool calls)" without
  marking the task done or running ``git push``. The work was stranded in the
  worktree.
* oompah-zlz_2-kc2k: prior attempts showed the same pattern.

Pattern: task has acceptance-criteria information → agent runs
normally but never commits, pushes, or closes → oompah must retry with
the normal profile escalation path before asking a human for help.

Design
------

The gate runs alongside the completion verifier in
``Orchestrator._on_worker_exit`` (reason == "normal", issue not closed).
It runs after the completion verifier so stage-2 acceptance checks are
already resolved — we only annotate the retry reason here, not correctness.

Gate logic:

1. Resolve branch: ``issue.work_branch or issue.branch_name or issue.identifier``.
2. ``git ls-remote --heads origin <branch>`` — does the branch exist on
   origin at all?  If not → no push happened → gate triggers.
3. If branch does exist on origin: check
   ``git log --oneline <base>..origin/<branch> --count``.  Any commits?
   If yes → work was pushed, just not closed → allow escalation (agent
   may have pusher access but no task close rights).  The retry loop
   will pick it up and close it.
4. If branch does not exist on origin AND no commits locally → agent
   produced no deployable output → gate triggers.
5. If branch does not exist on origin AND commits exist locally but not
   pushed → same as above; gate triggers.

On trigger:

* Post a diagnostic comment on the task.
* Log a telemetry event.
* Keep the task in the retry/escalation pipeline until the configured
  retry ceiling is reached.

Skip rules (fail-open):

* Issue is an epic (children close it, not the epic itself).
* Branch is 0 commits ahead of base — nothing was intended to be
  deployed.
* Any git operation fails — fail open, log WARNING, allow escalation.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

import httpx

from oompah.models import Issue
from oompah.statuses import DECOMPOSED, canonicalize_status

logger = logging.getLogger(__name__)

# Timeout for git operations inside the gate.
_GIT_TIMEOUT_S = 10.0


@dataclass
class LandingGateResult:
    """Outcome of the landing gate check."""

    allowed: bool
    # Why the gate was skipped (empty when the gate ran and allowed)
    skip_reason: str = ""
    # Number of commits ahead of base on origin (0 if branch not on origin)
    commits_on_origin: int = 0
    # Whether the branch exists at all on origin
    branch_on_origin: bool = False
    # Local commits not yet pushed
    local_only_commits: int = 0
    # Internal error (gate failed open)
    error: str = ""
    # The effective branch that was actually checked (may differ from the
    # issue's own branch when epic_strategy=shared maps the child to its
    # parent's epic branch).
    effective_branch: str = ""


def _branch_for_issue(issue: Issue) -> str:
    """Return the best branch name known for an issue."""
    for value in (
        getattr(issue, "work_branch", None),
        getattr(issue, "branch_name", None),
        getattr(issue, "identifier", None),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def check_landing_gate(
    issue: Issue,
    workspace_path: str,
    base_branch: str,
    *,
    effective_branch: str | None = None,
) -> LandingGateResult:
    """Check whether the agent completed without landing.

    Returns ``LandingGateResult(allowed=True)`` when the agent appears
    to have done its job and the escalation/retry cycle can proceed.
    Returns ``LandingGateResult(allowed=False)`` when the agent completed
    without landing, so we should post a diagnostic and defer rather
    than waste tokens on a profile escalation.

    Args:
        effective_branch: When provided, use this branch name for landing
            detection instead of deriving it from the issue. Used when
            ``epic_strategy='shared'`` maps a child issue's work onto its
            parent's epic branch (e.g. ``epic-TASK-706`` for child
            ``TASK-706.1``).
    """
    result = LandingGateResult(allowed=True)

    # --- skip rules ---
    if (issue.issue_type or "").strip().lower() == "epic":
        result.skip_reason = "issue is an epic"
        return result

    label_set = {(l or "").strip().lower() for l in (issue.labels or [])}
    if (
        "decomposed" in label_set
        or canonicalize_status(getattr(issue, "state", None)) == DECOMPOSED
    ):
        result.skip_reason = "issue is decomposed"
        return result

    # Resolve the effective landing branch. For shared-epic children the
    # caller passes the shared epic branch name; for all other cases we
    # fall back to the issue's own branch or identifier.
    if effective_branch:
        branch = effective_branch.strip()
    else:
        branch = _branch_for_issue(issue)
    result.effective_branch = branch

    if not branch:
        result.skip_reason = "no branch name and no identifier"
        return result

    # --- Step 1: does the branch exist on origin? ---
    try:
        r = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
        branch_on_origin = bool(r.stdout.strip())
    except (subprocess.TimeoutExpired, OSError) as exc:
        result.error = f"git ls-remote failed: {exc}"
        logger.warning("landing_gate: %s for %s: %s", branch, issue.identifier, exc)
        result.skip_reason = f"git ls-remote error: {exc}"
        return result

    result.branch_on_origin = branch_on_origin

    if not branch_on_origin:
        # --- Step 2a: branch never pushed — check local commits ---
        try:
            r_local = subprocess.run(
                [
                    "git", "rev-list", "--count",
                    f"origin/{base_branch}..{branch}",
                ],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT_S,
            )
            if r_local.returncode == 0:
                try:
                    result.local_only_commits = int(r_local.stdout.strip())
                except ValueError:
                    result.local_only_commits = 0
        except (subprocess.TimeoutExpired, OSError):
            pass

        if result.local_only_commits > 0:
            # Local commits exist but never pushed — agent did real work
            # but didn't push. Allow escalation (next dispatch will have
            # retries), but note the absence of a push.
            result.skip_reason = (
                f"branch never pushed ({result.local_only_commits} local commits)"
            )
            return result
        else:
            # No commits at all — agent produced no deployable output.
            result.allowed = False
            return result

    # --- Step 2b: branch on origin — check how far ahead ---
    try:
        r_ahead = subprocess.run(
            [
                "git", "rev-list", "--count",
                f"origin/{base_branch}..origin/{branch}",
            ],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
        if r_ahead.returncode == 0:
            try:
                result.commits_on_origin = int(r_ahead.stdout.strip())
            except ValueError:
                result.commits_on_origin = 0
    except (subprocess.TimeoutExpired, OSError) as exc:
        result.error = f"git rev-list ahead check failed: {exc}"
        logger.warning("landing_gate: ahead check failed for %s: %s", branch, exc)

    # Branch exists on origin with commits ahead — agent landed.
    # Escalation loop will close it or retry; don't block.
    result.skip_reason = (
        f"branch on origin with {result.commits_on_origin} commits "
        f"(agent landed normally)"
    )
    return result


def build_telemetry_event(
    result: LandingGateResult,
    issue: Issue,
    branch: str,
    agent_profile: str | None,
    focus: str | None,
    attempt: int,
    reopen_count: int,
) -> dict[str, Any]:
    """Build the structured telemetry event for logging."""
    event: dict[str, Any] = {
        "event": "landing_gate_retry_scheduled",
        "issue_id": issue.id,
        "issue_identifier": issue.identifier,
        "branch": branch,
        "branch_on_origin": result.branch_on_origin,
        "commits_on_origin": result.commits_on_origin,
        "local_only_commits": result.local_only_commits,
        "skip_reason": result.skip_reason,
        "agent_profile": agent_profile or "",
        "focus": focus or "",
        "attempt": attempt,
        "reopen_count": reopen_count,
    }
    # Include effective_branch when it differs from the nominal branch so
    # operators can see that a shared-epic branch was checked instead.
    if result.effective_branch and result.effective_branch != branch:
        event["effective_branch"] = result.effective_branch
    return event
