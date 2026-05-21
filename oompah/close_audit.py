"""LLM self-audit: evaluate whether the agent's work satisfies acceptance criteria.

This module is the core of the close audit infrastructure (oompah-zlz_2-pkw5).
It is called from the orchestrator's _on_worker_exit path after the close gate
passes and before the completion verifier.  The flow:

1. Build an evidence bundle (issue metadata + diff summary + commit log + PR
   status + agent close reason).
2. Hash the bundle to produce a cache key (issue_id + acceptance_criteria
   content + commit range).
3. If the cache has a valid result, return it immediately (avoid redundant
   LLM calls on retry).
4. If not, send the evidence to the provider's fast model and parse the
   per-criterion pass/fail judgment.
5. Store the result in the cache for future use.

The orchestrator owns side effects (reopen, comment, escalate).  This module
is pure: it inspects state passed in and returns an AuditResult.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oompah.models import Issue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CriterionResult:
    """Pass/fail judgment for a single acceptance criterion."""

    criterion: str
    passed: bool
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "passed": self.passed,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CriterionResult:
        return cls(
            criterion=d.get("criterion", ""),
            passed=bool(d.get("passed", False)),
            reasoning=d.get("reasoning", ""),
        )


@dataclass
class AuditResult:
    """Per-criterion pass/fail judgment plus aggregate summary."""

    passed: bool  # overall: True iff ALL criteria passed
    criteria: list[CriterionResult] = field(default_factory=list)
    reasoning: str = ""  # overall reasoning
    cache_hit: bool = False  # True when we used the cache

    @property
    def failed_criteria(self) -> list[CriterionResult]:
        return [c for c in self.criteria if not c.passed]

    @property
    def passed_criteria(self) -> list[CriterionResult]:
        return [c for c in self.criteria if c.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "criteria": [c.to_dict() for c in self.criteria],
            "reasoning": self.reasoning,
            "cache_hit": self.cache_hit,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AuditResult:
        return cls(
            passed=bool(d.get("passed", False)),
            criteria=[CriterionResult.from_dict(c) for c in d.get("criteria", [])],
            reasoning=d.get("reasoning", ""),
            cache_hit=bool(d.get("cache_hit", False)),
        )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_CACHE_DIR = Path(__file__).parent.parent / ".oompah"
_CACHE_FILE = _CACHE_DIR / "close_audit_cache.json"
_CACHE_MAX_AGE_S = 3600  # 1 hour — evidence should not change within an hour


def _ensure_cache_dir() -> None:
    """Create .oompah dir if it doesn't exist."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_cache() -> dict[str, Any]:
    """Load cache from disk. Returns {} on missing / corrupt file."""
    try:
        if _CACHE_FILE.exists():
            with open(_CACHE_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("close_audit: failed to load cache: %s", exc)
    return {}


def _save_cache(cache: dict[str, Any]) -> None:
    """Persist cache to disk."""
    _ensure_cache_dir()
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except OSError as exc:
        logger.debug("close_audit: failed to save cache: %s", exc)


def _load_and_prune_cache() -> dict[str, Any]:
    """Load cache and prune stale entries (older than 1 hour)."""
    cache = _load_cache()
    now = time.time()
    pruned: dict[str, Any] = {}
    for key, entry in cache.items():
        age = now - entry.get("_cached_at", 0)
        if age < _CACHE_MAX_AGE_S:
            pruned[key] = entry
        else:
            logger.debug("close_audit: pruned stale cache entry (age=%.0fs)", age)
    if pruned != cache:
        _save_cache(pruned)
    return pruned


def _compute_cache_key(
    issue_id: str | None,
    acceptance_criteria: str,
    base_branch: str,
    commit_range: str | None,
) -> str:
    """Compute a stable SHA-256 hash for (issue_id, AC content, commit range)."""
    raw = "|".join([
        str(issue_id or ""),
        acceptance_criteria or "",
        base_branch or "",
        commit_range or "",
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _get_cached_result(
    cache_key: str,
) -> AuditResult | None:
    """Return cached AuditResult if available and fresh, else None."""
    cache = _load_and_prune_cache()
    entry = cache.get(cache_key)
    if entry is None:
        return None
    result_data = entry.get("result")
    if not isinstance(result_data, dict):
        return None
    result = AuditResult.from_dict(result_data)
    result.cache_hit = True
    return result


def _put_cached_result(cache_key: str, result: AuditResult) -> None:
    """Store AuditResult in cache with timestamp."""
    cache = _load_cache()
    cache[cache_key] = {
        "result": result.to_dict(),
        "_cached_at": time.time(),
    }
    _save_cache(cache)


# ---------------------------------------------------------------------------
# Evidence bundling
# ---------------------------------------------------------------------------


def _get_commit_range(
    repo_path: str,
    base_branch: str,
    branch: str,
) -> str:
    """Return a concise commit range string for the evidence bundle."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", f"{base_branch}..{branch}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return ""
        parts = r.stdout.strip().split()
        if len(parts) < 2:
            return parts[0] if parts else ""
        return f"{parts[0][:8]}..{parts[-1][:8]}"
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return ""


def _get_commit_summary(
    repo_path: str,
    commit_range: str,
    max_commits: int = 15,
) -> str:
    """Return a concise list of commit messages for the evidence bundle."""
    if not commit_range:
        return ""
    try:
        r = subprocess.run(
            [
                "git", "log",
                "--oneline", f"-{max_commits}",
                commit_range,
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return ""
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return ""


def _get_diff_summary(
    repo_path: str,
    base_branch: str,
    branch: str,
    max_files: int = 20,
    max_lines_per_file: int = 50,
) -> str:
    """Return a capped diff summary suitable for LLM consumption."""
    try:
        # Get changed files
        r1 = subprocess.run(
            ["git", "diff", "--name-only", f"{base_branch}...{branch}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r1.returncode != 0:
            return ""
        files = [f.strip() for f in r1.stdout.splitlines() if f.strip()][:max_files]

        pieces: list[str] = [f"Changed files ({len(files)}):"]
        pieces.extend(f"  - {f}" for f in files)

        # Include a brief diff for each file
        for f in files:
            try:
                r2 = subprocess.run(
                    ["git", "diff", f"{base_branch}...{branch}", "--", f],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if r2.returncode != 0:
                    continue
                lines = r2.stdout.splitlines()
                if len(lines) > max_lines_per_file:
                    lines = lines[:max_lines_per_file] + [
                        f"  ... ({len(lines) - max_lines_per_file} more lines)"
                    ]
                pieces.append(f"\n--- {f} ---")
                pieces.extend(f"  {l}" for l in lines)
            except (subprocess.TimeoutExpired, OSError):
                continue

        return "\n".join(pieces)
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return ""


def _get_pr_status(
    slug: str,
    branch: str,
    access_token: str | None,
) -> str:
    """Return a brief PR status for the evidence bundle."""
    if not slug or not branch:
        return ""

    token = access_token
    if not token:
        import os
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return ""

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    try:
        import httpx
        client = httpx.Client(timeout=10.0, follow_redirects=True)
        owner = slug.split("/")[0] if "/" in slug else ""
        url = f"https://api.github.com/repos/{slug}/pulls"

        # Check for open PRs from this branch
        resp = client.get(
            url,
            headers=headers,
            params={"head": f"{owner}:{branch}", "state": "open", "per_page": "5"},
        )
        if resp.status_code == 200:
            prs = resp.json()
            if prs:
                parts = []
                for pr in prs[:3]:
                    pr_num = pr.get("number", "?")
                    state = pr.get("state", "unknown")
                    merged = pr.get("merged", False)
                    parts.append(f"PR #{pr_num}: state={state}, merged={merged}")
                return "\n".join(parts)
    except Exception as exc:
        logger.debug("close_audit: PR status check failed: %s", exc)
    finally:
        try:
            client.close()
        except Exception:
            pass

    return ""


def build_evidence_bundle(
    issue: Issue,
    repo_path: str,
    base_branch: str,
    close_reason: str = "",
    access_token: str | None = None,
) -> dict[str, Any]:
    """Build a concise evidence bundle for the LLM audit.

    Returns a dict with:
    - issue_id, identifier, title
    - acceptance_criteria (from description)
    - description (shortened)
    - commit_range, commit_summary
    - diff_summary (capped)
    - pr_status
    - close_reason
    - labels
    """
    # Extract acceptance criteria
    from oompah.completion_verifier import extract_acceptance_section

    ac_section = extract_acceptance_section(issue.description)

    # Resolve branch
    branch = (issue.branch_name or issue.identifier or "").strip()

    # Resolve slug
    slug = ""
    if issue.project_id:
        try:
            from oompah.scm import extract_repo_slug
            proj = None
            # Try to get project via project_store
            # We need access to project_store — accept it as optional
        except Exception:
            pass

    # Get commit info
    commit_range = _get_commit_range(repo_path, base_branch, branch)
    commit_summary = _get_commit_summary(repo_path, commit_range)
    diff_summary = _get_diff_summary(repo_path, base_branch, branch)
    pr_status = _get_pr_status(slug, branch, access_token)

    # Shorten description for context
    desc = (issue.description or "").strip()
    if len(desc) > 2000:
        desc = desc[:2000] + "...\n(truncated for audit)"

    # Collect labels
    labels = issue.labels or []

    return {
        "issue_id": issue.id or "",
        "identifier": issue.identifier or "",
        "title": issue.title or "",
        "issue_type": issue.issue_type or "",
        "acceptance_criteria": ac_section,
        "description": desc,
        "commit_range": commit_range,
        "commit_summary": commit_summary,
        "diff_summary": diff_summary,
        "pr_status": pr_status,
        "close_reason": close_reason,
        "labels": labels,
    }


# ---------------------------------------------------------------------------
# LLM prompt construction
# ---------------------------------------------------------------------------


def build_audit_prompt(evidence: dict[str, Any]) -> str:
    """Build the LLM prompt for the close audit.

    Asks the model to evaluate each acceptance criterion individually
    and return structured output that we can parse.
    """
    title = evidence.get("title", "")
    description = evidence.get("description", "")
    ac = evidence.get("acceptance_criteria", "")
    commit_summary = evidence.get("commit_summary", "")
    diff_summary = evidence.get("diff_summary", "")
    pr_status = evidence.get("pr_status", "")
    close_reason = evidence.get("close_reason", "")

    prompt_parts: list[str] = [
        "You are auditing whether an autonomous coding agent has completed "
        "a task correctly. Evaluate each acceptance criterion against the "
        "evidence of work done.",
        "",
        f"Issue: {title}",
        "",
        "Acceptance criteria:",
    ]
    if ac:
        prompt_parts.append(f"```{ac}```")
    else:
        prompt_parts.append("(none — skip all criteria)")

    prompt_parts.extend([
        "",
        "Evidence of work:",
    ])

    if close_reason:
        prompt_parts.extend([
            f"Agent's close reason: {close_reason}",
            "",
        ])

    if commit_summary:
        prompt_parts.extend([
            "Commits:",
            f"```{commit_summary}```",
            "",
        ])

    if diff_summary:
        prompt_parts.extend([
            "Diff summary:",
            f"```{diff_summary}```",
            "",
        ])

    if pr_status:
        prompt_parts.extend([
            "PR status:",
            f"```{pr_status}```",
            "",
        ])

    prompt_parts.extend([
        "Instructions:",
        "For EACH acceptance criterion, output one line:",
        "CRITERION: <criterion text> | RESULT: PASS | REASON: <brief reason>",
        "or:",
        "CRITERION: <criterion text> | RESULT: FAIL | REASON: <brief reason>",
        "",
        "If there are no acceptance criteria, respond with:",
        "NO_CRITERIA",
        "",
        "Be strict: if the evidence does not clearly show the criterion is "
        "satisfied, mark it as FAIL.",
    ])

    return "\n".join(prompt_parts)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

# Pattern: CRITERION: <text> | RESULT: PASS/FAIL | REASON: <text>
_CRITERION_LINE_RE = re.compile(
    r"CRITERION:\s*(.+?)\s*\|\s*RESULT:\s*(PASS|FAIL)\s*\|\s*REASON:\s*(.*)",
    re.IGNORECASE | re.DOTALL,
)


def parse_audit_response(
    content: str | None,
    acceptance_criteria: list[str] | None = None,
) -> AuditResult:
    """Parse the LLM's audit response into an AuditResult.

    Accepts either structured CRITERION/RESULT/REASON lines, or a
    free-form response that mentions PASS/FAIL per criterion.

    When no structured output is found, the function tries to identify
    PASS/FAIL mentions for each known criterion.

    Falls back to a fail-open default (passed=True) on any parse error.
    """
    if not content:
        # No content returned — fail open
        return AuditResult(
            passed=True,
            criteria=[],
            reasoning="No response from LLM (fail open)",
        )

    content = content.strip()
    if not content or "NO_CRITERIA" in content:
        # No criteria to evaluate
        return AuditResult(
            passed=True,
            criteria=[],
            reasoning="No acceptance criteria to audit",
            cache_hit=False,
        )

    criteria_results: list[CriterionResult] = []

    # Try structured parsing first
    for line in content.splitlines():
        m = _CRITERION_LINE_RE.match(line.strip())
        if m:
            criterion_text = m.group(1).strip()
            result_str = m.group(2).upper()
            reason = m.group(3).strip()
            passed = result_str == "PASS"
            criteria_results.append(
                CriterionResult(
                    criterion=criterion_text,
                    passed=passed,
                    reasoning=reason,
                )
            )

    # If structured parsing found results, use them
    if criteria_results:
        overall = all(c.passed for c in criteria_results)
        reasoning_parts: list[str] = []
        for c in criteria_results:
            status = "PASS" if c.passed else "FAIL"
            reasoning_parts.append(f"[{status}] {c.criterion}: {c.reasoning}")
        return AuditResult(
            passed=overall,
            criteria=criteria_results,
            reasoning="; ".join(reasoning_parts),
        )

    # Fallback: try to match known criteria against PASS/FAIL mentions
    if acceptance_criteria:
        for crit in acceptance_criteria:
            crit_lower = crit.lower()[:80]  # Normalize for matching
            # Search for criterion reference + PASS/FAIL nearby
            crit_found = False
            for line in content.splitlines():
                line_lower = line.lower()
                if crit_lower in line_lower and ("fail" in line_lower or "miss" in line_lower):
                    criteria_results.append(
                        CriterionResult(
                            criterion=crit,
                            passed=False,
                            reasoning=line.strip(),
                        )
                    )
                    crit_found = True
                    break
            if not crit_found:
                # Assume PASS if we couldn't find a failure mention
                criteria_results.append(
                    CriterionResult(
                        criterion=crit,
                        passed=True,
                        reasoning="No failure detected in LLM response",
                    )
                )
        overall = all(c.passed for c in criteria_results)
        return AuditResult(
            passed=overall,
            criteria=criteria_results,
            reasoning="Parsed via criterion matching (fallback mode)",
        )

    # No structured output and no known criteria — fail open
    return AuditResult(
        passed=True,
        criteria=[],
        reasoning=f"Could not parse LLM response (fail open). Content: {content[:200]}",
    )


def render_feedback_comment(
    result: AuditResult,
    identifier: str,
) -> str:
    """Build the comment to post when close is rejected.

    Lists each failed criterion with the LLM's reasoning so the next
    agent knows what to fix.
    """
    parts = [f"**Close audit rejected for {identifier}.**", ""]

    if not result.failed_criteria:
        # This shouldn't happen if called from the reject path, but
        # guard anyway.
        parts.append("Audit returned PASS but close was rejected — check logs.")
        return "\n".join(parts)

    parts.append(
        f"{len(result.failed_criteria)} criterion(1) failed:"
    )
    parts.append("")

    for i, crit in enumerate(result.failed_criteria, 1):
        # Truncate long criterion text
        crit_text = crit.criterion[:150]
        if len(crit.criterion) > 150:
            crit_text += "..."
        parts.extend([
            f"{i}. **FAIL**: `{crit_text}`",
            f"   Reason: {crit.reasoning}",
            "",
        ])

    parts.append(
        "The bead has been re-opened. Review the above feedback and "
        "fix the failing criteria before closing again."
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main audit entry point
# ---------------------------------------------------------------------------


def _run_audit_sync(
    evidence: dict[str, Any],
    provider: Any,
) -> AuditResult:
    """Run the LLM audit synchronously (used internally by run_audit_sync)."""
    if provider is None:
        return AuditResult(
            passed=True,
            criteria=[],
            reasoning="No provider configured (fail open)",
        )

    base_url = (getattr(provider, "base_url", "") or "").rstrip("/")
    if not base_url:
        return AuditResult(
            passed=True,
            criteria=[],
            reasoning="No base_url on provider (fail open)",
        )

    prompt = build_audit_prompt(evidence)

    # Resolve model: prefer 'fast' role, fall back to default
    model = (getattr(provider, "model_roles", None) or {}).get("fast")
    if not model:
        model = getattr(provider, "default_model", None)
    if not model:
        models = getattr(provider, "models", None) or []
        if models:
            model = models[0]
    if not model:
        return AuditResult(
            passed=True,
            criteria=[],
            reasoning="No model resolved (fail open)",
        )

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.0,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {getattr(provider, 'api_key', None) or ''}",
        "User-Agent": "oompah/0.1 close-audit",
    }
    url = f"{base_url}/chat/completions"

    from oompah.api_agent import _build_ssl_context, _http_post

    try:
        ssl_ctx = _build_ssl_context()
        response = _http_post(url, headers, body, ssl_ctx)
    except Exception as exc:
        logger.warning("close_audit: LLM call failed for %s: %s", evidence.get("identifier"), exc)
        return AuditResult(
            passed=True,
            criteria=[],
            reasoning=f"LLM call failed (fail open): {exc}",
        )

    try:
        content = response["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("close_audit: unexpected response shape: %s", exc)
        return AuditResult(
            passed=True,
            criteria=[],
            reasoning=f"Unexpected response shape (fail open): {exc}",
        )

    # Extract acceptance criteria list for fallback parsing
    ac_raw = evidence.get("acceptance_criteria", "")
    acceptance_criteria_list: list[str] | None = None
    if ac_raw:
        # Split on numbered bullets, check boxes, or line starts
        acceptance_criteria_list = [
            line.strip().lstrip("-*•").strip()
            for line in ac_raw.splitlines()
            if line.strip() and (
                re.match(r"^\d+[\.)]", line.strip())
                or line.strip().startswith("```")
                or (line.strip().startswith("- ") and len(line.strip()) > 4)
            )
        ]
        if not acceptance_criteria_list:
            acceptance_criteria_list = None  # Let structured parsing handle it

    result = parse_audit_response(content, acceptance_criteria=acceptance_criteria_list)
    return result


def run_audit_sync(
    evidence: dict[str, Any],
    provider: Any,
) -> AuditResult:
    """Run the close audit: cache lookup → LLM call → cache write.

    If the cache key is already in the cache and fresh, returns the cached
    result.  Otherwise, runs the LLM call, parses the response, and
    stores the result in the cache before returning.

    Fail-open on any error.
    """
    # Compute cache key
    ac = evidence.get("acceptance_criteria", "")
    commit_range = evidence.get("commit_range", "")
    cache_key = _compute_cache_key(
        evidence.get("issue_id"),
        ac,
        "main",  # base_branch is embedded in commit_range
        commit_range,
    )

    # Check cache
    cached = _get_cached_result(cache_key)
    if cached is not None:
        logger.info(
            "close_audit: cache hit for %s (key=%s)",
            evidence.get("identifier", ""),
            cache_key[:12],
        )
        return cached

    # Run the LLM audit
    result = _run_audit_sync(evidence, provider)

    # Cache the result (even on failure — don't hammer the LLM)
    _put_cached_result(cache_key, result)

    return result
