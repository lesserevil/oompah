"""Close gate: refuse agent close when branch has unmerged commits AND no open PR.

Motivating evidence (issue oompah-zlz_2-gz8w):

* trickle-icl, oompah-zlz_2-7nr, oompah-zlz_2-0hzh/yiuy/ag7h:
  agents committed+pushed work to a feature branch, then called
  ``bd close`` without ever opening a PR. The work sits stranded on
  origin and never reaches main.

Design
------

The gate intercepts every agent-driven close (i.e. every call that
flows through ``Orchestrator._on_worker_exit``). Operator-driven closes
that go through the API or dashboard do NOT flow through that path, so
the gate automatically applies only to agent closes.

Skip rules (fail-open without checking):
* Issue is an epic.
* Issue has the ``decomposed`` label.
* Branch is 0 commits ahead of the base branch (nothing to merge).
* Forge API call fails or times out (fail-open, log WARNING).
* Close was triggered by an operator-style reason: "no-op",
  "superseded", "wontfix" (manual override patterns).

Gate logic:
1. Resolve the branch name: ``issue.branch_name or issue.identifier``.
2. ``git rev-list <base>..<branch> --count`` in the project's repo dir.
   * 0 → no unmerged commits → allow close.
3. Query GitHub for PRs with ``head=<branch>`` in states ``open`` and
   ``closed`` (checking merged_at for closed ones).
   * open PR exists → allow close (agent handed off to CI/queue).
   * merged PR exists → allow close.
   * no open/merged PR → refuse.

Refusal output:
* Do NOT apply the close; the bead remains in_progress/open.
* Post a diagnostic comment (author=oompah) with the required
  ``gh pr create`` command.
* Reopen the bead so the existing dispatch/retry cycle picks it up.
* Log a structured telemetry event ``close_refused_unmerged_work``.

Telemetry event (logged at INFO via ``json.dumps``):
    {
        "event": "close_refused_unmerged_work",
        "issue_id": "<id>",
        "issue_identifier": "<identifier>",
        "branch": "<branch>",
        "commits_ahead": <int>,
        "open_prs": <int>,
        "agent_profile": "<profile>",
        "focus": "<focus>",
        "attempt": <int>,
    }
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

import httpx

from oompah.models import Issue

logger = logging.getLogger(__name__)

# Close reasons that indicate an operator-driven manual override.
# When a close carries one of these reasons, the gate is bypassed.
_OPERATOR_CLOSE_REASONS = frozenset({
    "no-op", "noop", "superseded", "wontfix", "won't fix",
    "duplicate", "manual", "operator",
})

# Timeout for forge API calls inside the gate check.
_FORGE_TIMEOUT_S = 10.0


@dataclass
class CloseGateResult:
    """Outcome of the close gate check."""

    allowed: bool
    # Why the gate was skipped (empty when the gate ran and allowed)
    skip_reason: str = ""
    # Git commit count ahead of base
    commits_ahead: int = 0
    # PR counts found
    open_prs: int = 0
    merged_prs: int = 0
    # Short sha + subject lines for the refusal comment
    commit_lines: list[str] = field(default_factory=list)
    # PR links for the refusal comment (closed+merged)
    merged_pr_links: list[str] = field(default_factory=list)
    # Internal error message (gate failed open)
    error: str = ""


def _count_commits_ahead(
    repo_path: str,
    base_branch: str,
    branch: str,
) -> tuple[int, list[str], str]:
    """Return (count, commit_lines, error).

    ``commit_lines`` is a list of "<sha> <subject>" strings for the
    refusal comment (max 20). ``error`` is non-empty when the command
    failed; callers should fail-open in that case.
    """
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"origin/{base_branch}..{branch}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as exc:
        return 0, [], f"git rev-list --count failed: {exc}"
    if result.returncode != 0:
        # Branch may not exist on remote — try with local base
        try:
            result2 = subprocess.run(
                ["git", "rev-list", "--count", f"{base_branch}..{branch}"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as exc:
            return 0, [], f"git rev-list --count (local) failed: {exc}"
        if result2.returncode != 0:
            return 0, [], f"git rev-list --count failed: {result.stderr.strip()}"
        result = result2

    try:
        count = int(result.stdout.strip())
    except ValueError:
        return 0, [], f"git rev-list --count unexpected output: {result.stdout!r}"

    if count == 0:
        return 0, [], ""

    # Fetch commit summaries for the refusal comment (up to 20).
    try:
        log_result = subprocess.run(
            [
                "git", "log",
                "--oneline", "-20",
                f"origin/{base_branch}..{branch}",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = (
            [l.strip() for l in log_result.stdout.splitlines() if l.strip()]
            if log_result.returncode == 0
            else []
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        lines = []

    return count, lines, ""


def _query_prs_for_branch(
    token: str | None,
    slug: str,
    branch: str,
    base_branch: str,
) -> tuple[int, int, list[str], str]:
    """Query GitHub for PRs with head=branch.

    Returns (open_count, merged_count, merged_pr_links, error).
    ``error`` is non-empty when the query failed; callers should
    fail-open.

    We query both open and closed PRs (separate calls) because the
    GitHub ``/pulls`` endpoint doesn't support a combined filter.
    For closed PRs we filter to those with ``merged_at`` non-null.
    """
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # owner/repo format expected from slug
    base_url = f"https://api.github.com/repos/{slug}/pulls"

    open_count = 0
    merged_count = 0
    merged_links: list[str] = []

    try:
        client = httpx.Client(timeout=_FORGE_TIMEOUT_S, follow_redirects=True)

        # Open PRs
        resp_open = client.get(
            base_url,
            headers=headers,
            params={"head": branch, "state": "open", "per_page": "10"},
        )
        if resp_open.status_code == 200:
            for pr in resp_open.json():
                if isinstance(pr, dict):
                    pr_base = (pr.get("base") or {}).get("ref", "")
                    if pr_base == base_branch or not base_branch:
                        open_count += 1
        elif resp_open.status_code in (401, 403, 404):
            # Auth issue or repo not found — fail-open
            return 0, 0, [], f"GitHub open-PR query HTTP {resp_open.status_code}"
        else:
            logger.debug(
                "close_gate: open-PR query returned HTTP %d for %s branch=%s",
                resp_open.status_code, slug, branch,
            )

        # Closed PRs (filter to merged)
        resp_closed = client.get(
            base_url,
            headers=headers,
            params={"head": branch, "state": "closed", "per_page": "10"},
        )
        if resp_closed.status_code == 200:
            for pr in resp_closed.json():
                if not isinstance(pr, dict):
                    continue
                pr_base = (pr.get("base") or {}).get("ref", "")
                if base_branch and pr_base != base_branch:
                    continue
                if pr.get("merged_at"):
                    merged_count += 1
                    url = pr.get("html_url") or ""
                    num = pr.get("number") or ""
                    if url:
                        merged_links.append(f"PR #{num}: {url}")

    except httpx.TimeoutException as exc:
        return 0, 0, [], f"GitHub PR query timed out: {exc}"
    except (httpx.HTTPError, Exception) as exc:
        return 0, 0, [], f"GitHub PR query error: {exc}"
    finally:
        try:
            client.close()
        except Exception:
            pass

    return open_count, merged_count, merged_links, ""


def check_close_gate(
    issue: Issue,
    *,
    repo_path: str,
    slug: str,
    base_branch: str,
    access_token: str | None = None,
    close_reason: str = "",
    entry_profile: str = "",
    entry_focus: str = "",
    entry_attempt: int = 0,
) -> CloseGateResult:
    """Run the close gate check.

    Args:
        issue: The issue being closed.
        repo_path: Filesystem path to the project's git clone (used for
            ``git rev-list``).
        slug: GitHub ``owner/repo`` slug for the forge API query.
        base_branch: The base branch name (e.g. "main").
        access_token: GitHub personal access token (optional; resolves
            from gh CLI or GH_TOKEN env if absent).
        close_reason: The close reason string provided by the agent.
        entry_profile: Agent profile name (for telemetry).
        entry_focus: Focus name (for telemetry).
        entry_attempt: Retry attempt count (for telemetry).

    Returns:
        A :class:`CloseGateResult`. When ``allowed=True`` the close may
        proceed. When ``allowed=False`` the caller should post a
        refusal comment, reopen the bead, and log telemetry.
    """
    # ------------------------------------------------------------------
    # Skip rules
    # ------------------------------------------------------------------
    if (issue.issue_type or "").strip().lower() == "epic":
        return CloseGateResult(allowed=True, skip_reason="epic")

    labels = {(l or "").strip().lower() for l in (issue.labels or [])}
    if "decomposed" in labels:
        return CloseGateResult(allowed=True, skip_reason="decomposed")

    # Operator manual override reasons
    if close_reason:
        reason_lower = close_reason.strip().lower()
        for pattern in _OPERATOR_CLOSE_REASONS:
            if pattern in reason_lower:
                return CloseGateResult(allowed=True, skip_reason=f"operator_reason={close_reason}")

    # ------------------------------------------------------------------
    # Git commit check
    # ------------------------------------------------------------------
    branch = (issue.branch_name or issue.identifier or "").strip()
    if not branch:
        logger.debug("close_gate: no branch resolved for %s — skipping", issue.identifier)
        return CloseGateResult(allowed=True, skip_reason="no_branch")

    if not repo_path:
        logger.debug("close_gate: no repo_path for %s — skipping", issue.identifier)
        return CloseGateResult(allowed=True, skip_reason="no_repo_path")

    commits_ahead, commit_lines, git_error = _count_commits_ahead(
        repo_path, base_branch, branch,
    )
    if git_error:
        logger.warning(
            "close_gate: git check failed for %s branch=%s: %s — failing open",
            issue.identifier, branch, git_error,
        )
        return CloseGateResult(allowed=True, skip_reason="git_error", error=git_error)

    if commits_ahead == 0:
        # Branch is empty or already on base — no unmerged work
        return CloseGateResult(allowed=True, skip_reason="no_commits_ahead")

    # ------------------------------------------------------------------
    # Forge PR check
    # ------------------------------------------------------------------
    if not slug:
        logger.warning(
            "close_gate: no slug for %s — failing open (cannot check PRs)",
            issue.identifier,
        )
        return CloseGateResult(
            allowed=True,
            skip_reason="no_slug",
            commits_ahead=commits_ahead,
            commit_lines=commit_lines,
        )

    # Resolve token: explicit arg → GH_TOKEN env → gh CLI
    token = access_token
    if not token:
        import os
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        try:
            import subprocess as _sp
            r = _sp.run(
                ["gh", "auth", "token"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                token = r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # head parameter for GitHub PR search: "owner:branch" format
    owner = slug.split("/")[0] if "/" in slug else ""
    head_param = f"{owner}:{branch}" if owner else branch

    open_prs, merged_prs, merged_links, forge_error = _query_prs_for_branch(
        token, slug, head_param, base_branch,
    )

    if forge_error:
        logger.warning(
            "close_gate: forge query failed for %s branch=%s: %s — failing open",
            issue.identifier, branch, forge_error,
        )
        return CloseGateResult(
            allowed=True,
            skip_reason="forge_error",
            commits_ahead=commits_ahead,
            commit_lines=commit_lines,
            error=forge_error,
        )

    if open_prs > 0 or merged_prs > 0:
        return CloseGateResult(
            allowed=True,
            commits_ahead=commits_ahead,
            open_prs=open_prs,
            merged_prs=merged_prs,
            merged_pr_links=merged_links,
        )

    # ------------------------------------------------------------------
    # Refusal: unmerged commits + no open/merged PR
    # ------------------------------------------------------------------
    # Log structured telemetry
    telemetry = {
        "event": "close_refused_unmerged_work",
        "issue_id": issue.id or "",
        "issue_identifier": issue.identifier or "",
        "branch": branch,
        "commits_ahead": commits_ahead,
        "open_prs": open_prs,
        "agent_profile": entry_profile,
        "focus": entry_focus,
        "attempt": entry_attempt,
    }
    logger.info("close_gate_telemetry: %s", json.dumps(telemetry))

    return CloseGateResult(
        allowed=False,
        commits_ahead=commits_ahead,
        open_prs=open_prs,
        merged_prs=merged_prs,
        commit_lines=commit_lines,
        merged_pr_links=merged_links,
    )


def build_refusal_comment(
    issue: Issue,
    result: CloseGateResult,
    base_branch: str,
) -> str:
    """Build the diagnostic comment to post on the bead when close is refused."""
    branch = (issue.branch_name or issue.identifier or "").strip()
    n = result.commits_ahead
    commit_noun = "commit" if n == 1 else "commits"

    lines: list[str] = [
        f"Close refused by orchestrator: branch `{branch}` has {n} {commit_noun} "
        f"not on `{base_branch}` and no open PR targets `{base_branch}` from this branch.",
        "",
        "Diagnostic:",
        f"  Unmerged commits: {n}",
    ]

    if result.commit_lines:
        for cl in result.commit_lines[:10]:
            lines.append(f"    {cl}")
    if n > len(result.commit_lines) and result.commit_lines:
        remaining = n - len(result.commit_lines)
        lines.append(f"    ... and {remaining} more")

    lines.append(f"  Open PRs from this branch: {result.open_prs}")
    if result.merged_prs == 0:
        lines.append(f"  Merged PRs from this branch: 0")
    else:
        lines.append(f"  Merged PRs from this branch: {result.merged_prs}")
        for link in result.merged_pr_links:
            lines.append(f"    {link}")

    title = (issue.title or issue.identifier or "").replace('"', "'")
    iid = issue.identifier or ""
    lines.extend([
        "",
        "Required: open a PR before closing.",
        f'  gh pr create --base {base_branch} --head {branch} --title "{iid}: {title}" --body "..."',
        "",
        "Bead reopened. Re-dispatch on the next tick will see this comment in its prompt context.",
    ])

    return "\n".join(lines)
