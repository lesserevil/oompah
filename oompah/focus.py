"""Agent focus system — tailors prompts to the work at hand.

A Focus defines a specialized role with instructions, must-do/must-not-do
rules, and keyword matching. The orchestrator picks the best-fit focus for
each issue and injects it into the agent prompt.

Foci are loaded from .oompah/foci.json (user-editable library) with
built-in defaults as fallback.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from oompah.models import Issue, Project
from oompah.statuses import NEEDS_CI_FIX, NEEDS_REBASE, canonicalize_status

logger = logging.getLogger(__name__)

# Module-level cache for LLM-based focus triage. Keyed by a stable hash of
# the issue's content + active foci signature; entries persist for the
# process lifetime since re-triage only matters when issue text or the
# focus library changes (both reflected in the cache key).
_triage_cache: dict[str, tuple[str, str]] = {}

_STATUS_ROUTING_LABELS = {
    NEEDS_CI_FIX: "ci-fix",
    NEEDS_REBASE: "merge-conflict",
}


def _effective_issue_labels(issue: Issue) -> set[str]:
    labels = {label.lower() for label in (issue.labels or [])}
    status_label = _STATUS_ROUTING_LABELS.get(canonicalize_status(issue.state))
    if status_label:
        labels.add(status_label)
    return labels

# Hard timeout for the triage LLM call. Set to 60s because the configured
# default model on Godspeed (nvidia/MiniMax-M2.7-NVFP4) regularly takes
# 20-40s to generate even a 128-token response. Triage is one-shot per
# issue (cached afterward), so a slow first call is acceptable. If the
# call genuinely hangs beyond 60s the deterministic scorer takes over.
_TRIAGE_TIMEOUT_S = 60.0

DEFAULT_FOCI_PATH = ".oompah/foci.json"


@dataclass
class Focus:
    """A specialized agent role tailored to a class of work."""

    name: str
    role: str  # e.g. "Security Auditor", "Frontend Developer"
    description: str  # what the agent should focus on
    must_do: list[str] = field(default_factory=list)
    must_not_do: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)  # matched against title/description
    issue_types: list[str] = field(default_factory=list)  # matched against issue_type
    labels: list[str] = field(default_factory=list)  # matched against issue labels
    priority: int = 0  # higher = preferred when multiple foci match
    status: str = "active"  # active | inactive | proposed
    # Optional model overrides — when set, take precedence over the agent
    # profile's choice during dispatch. See plans/per-focus-models.md.
    model_role: str | None = None
    model: str | None = None
    provider_id: str | None = None
    # Allow agents working under this focus to emit images via the
    # attach_image tool. Defaults to False; opt-in per focus.
    allow_image_output: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "must_do": self.must_do,
            "must_not_do": self.must_not_do,
            "keywords": self.keywords,
            "issue_types": self.issue_types,
            "labels": self.labels,
            "priority": self.priority,
            "status": self.status,
        }
        if self.model_role is not None:
            d["model_role"] = self.model_role
        if self.model is not None:
            d["model"] = self.model
        if self.provider_id is not None:
            d["provider_id"] = self.provider_id
        if self.allow_image_output:
            d["allow_image_output"] = True
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Focus:
        def _opt_str(v: Any) -> str | None:
            if v is None:
                return None
            s = str(v).strip()
            return s or None

        return cls(
            name=str(d.get("name", "")),
            role=str(d.get("role", "")),
            description=str(d.get("description", "")),
            must_do=d.get("must_do", []),
            must_not_do=d.get("must_not_do", []),
            keywords=d.get("keywords", []),
            issue_types=d.get("issue_types", []),
            labels=d.get("labels", []),
            priority=int(d.get("priority", 0)),
            status=str(d.get("status", "active")),
            model_role=_opt_str(d.get("model_role")),
            model=_opt_str(d.get("model")),
            provider_id=_opt_str(d.get("provider_id")),
            allow_image_output=bool(d.get("allow_image_output", False)),
        )

    def render(self, project: Project | None = None) -> str:
        """Render this focus as prompt text.

        When ``project`` has a configured ``test_command``, every literal
        "Run tests" instruction in the focus's ``must_do`` list is rewritten
        to name that exact command so the agent does not have to infer the
        right test target from repo layout. The same command is appended as
        a hint when the focus has no explicit test step but the project
        has one configured. ``test_command_full`` and ``test_skip_paths``
        are surfaced as supplementary hints.
        """
        lines = [
            f"## Your Role: {self.role}",
            "",
            self.description,
        ]
        must_do = self._materialize_must_do(project)
        if must_do:
            lines.append("")
            lines.append("### You MUST:")
            for item in must_do:
                lines.append(f"- {item}")
        if self.must_not_do:
            lines.append("")
            lines.append("### You must NOT:")
            for item in self.must_not_do:
                lines.append(f"- {item}")
        # Append project-level test guidance whenever the project has
        # a configured test_command. This applies to ALL focuses so the
        # agent always sees the project's preferred command instead of
        # inferring one from the repo layout. Avoid duplicating the
        # message if a must_do bullet already names the command.
        if project is not None and project.test_command:
            extras: list[str] = []
            already_mentioned = any(
                project.test_command in item for item in must_do
            )
            if not already_mentioned:
                extras.append(
                    f"For pre-push verification, run `{project.test_command}` "
                    "(this project's configured test_command). Do not infer "
                    "a different test target."
                )
            if project.test_command_full:
                extras.append(
                    f"For broader pre-merge-queue coverage, "
                    f"`{project.test_command_full}` is also configured."
                )
            if project.test_skip_paths:
                extras.append(
                    "Skip these flaky/hardware/network paths during testing: "
                    + ", ".join(project.test_skip_paths)
                )
            if extras:
                lines.append("")
                lines.append("### Project Test Configuration")
                for item in extras:
                    lines.append(f"- {item}")
        return "\n".join(lines)

    def _materialize_must_do(self, project: Project | None) -> list[str]:
        """Return must_do with project test_command substituted where applicable.

        When ``project.test_command`` is set, replace any generic
        "Run tests..." bullet with a concrete "Run <test_command>..." line.
        Returns a copy; never mutates ``self.must_do``.
        """
        if project is None or not project.test_command:
            return list(self.must_do)
        cmd = project.test_command
        out: list[str] = []
        for item in self.must_do:
            stripped = item.strip()
            low = stripped.lower()
            # Match bullets that start with "Run tests" / "Run the tests"
            # — these are the ambiguous ones the issue calls out.
            if low.startswith("run tests") or low.startswith("run the tests"):
                # Preserve the rest of the original sentence (e.g. " ... to
                # verify nothing is broken") so callers keep their context.
                rest = stripped.split(None, 2)
                # rest[0]="Run", rest[1]="tests"|"the", rest[2]=remainder
                if len(rest) >= 3 and rest[1].lower() == "the":
                    # "Run the tests <rest>" → keep the part after "tests"
                    after = rest[2].split(None, 1)
                    tail = after[1] if len(after) > 1 else ""
                else:
                    tail = rest[2] if len(rest) >= 3 else ""
                tail = (" " + tail.strip()) if tail.strip() else ""
                out.append(f"Run `{cmd}`{tail}")
            else:
                out.append(item)
        return out


# -- Built-in focus library --

BUILTIN_FOCI: list[Focus] = [
    Focus(
        name="feature",
        role="Feature Developer",
        description=(
            "You are building a new capability. Understand the requirements thoroughly, "
            "design a clean implementation that fits the existing architecture, and deliver "
            "working code."
        ),
        must_do=[
            "Read and understand the existing codebase architecture before writing new code",
            "Follow existing code patterns and conventions",
        ],
        must_not_do=[
            "Over-engineer or add features beyond what the issue describes",
            "Introduce new dependencies without justification",
            "Change existing behavior unless explicitly required",
        ],
        keywords=["feature", "implement", "add", "new", "support", "create", "build"],
        issue_types=["feature"],
        priority=5,
    ),
    Focus(
        name="refactor",
        role="Refactoring Specialist",
        description=(
            "You are improving code quality without changing behavior. Every refactoring step "
            "must preserve existing functionality. Use tests as your safety net."
        ),
        must_do=[
            "Run existing tests before AND after every refactoring step",
            "Make small, incremental changes — commit frequently",
            "Preserve all existing behavior and public interfaces",
            "Explain the 'why' behind each structural change in comments",
        ],
        must_not_do=[
            "Change behavior — this is refactoring, not feature work",
            "Remove tests or weaken assertions",
            "Combine refactoring with feature changes in the same commit",
        ],
        keywords=["refactor", "cleanup", "restructure", "simplify", "extract", "reorganize", "technical debt"],
        issue_types=[],
        priority=5,
    ),
    Focus(
        name="frontend",
        role="Frontend Developer",
        description=(
            "You are working on user-facing UI code. Focus on usability, accessibility, "
            "and visual consistency."
        ),
        must_do=[
            "Consider accessibility (aria labels, keyboard navigation, contrast)",
            "Match existing UI patterns and styling conventions",
            "Keep JavaScript minimal and framework-consistent",
        ],
        must_not_do=[
            "Introduce new CSS frameworks or UI libraries without approval",
            "Break existing layouts while fixing one component",
            "Inline large amounts of CSS — follow the existing pattern",
        ],
        keywords=["ui", "frontend", "css", "html", "component", "layout", "dashboard", "page", "button", "form", "display", "render", "visual"],
        labels=["frontend", "ui"],
        priority=5,
    ),
    Focus(
        name="docs",
        role="Technical Writer",
        description=(
            "You are writing or improving documentation. Focus on clarity, accuracy, "
            "and helping the reader accomplish their goal."
        ),
        must_do=[
            "Verify all code examples actually work",
            "Use consistent terminology throughout",
            "Write for the target audience (developer, user, operator)",
            "Include practical examples, not just API signatures",
        ],
        must_not_do=[
            "Change code behavior — documentation only",
            "Write documentation that is longer than necessary",
            "Use jargon without explanation for user-facing docs",
        ],
        keywords=["docs", "documentation", "readme", "guide", "tutorial", "comment", "docstring"],
        issue_types=[],
        labels=["docs", "documentation"],
        priority=5,
    ),
    Focus(
        name="test",
        role="Test Engineer",
        description=(
            "You are writing or improving tests. Focus on coverage of important behavior, "
            "edge cases, and regression prevention. Tests should be clear, fast, and reliable."
        ),
        must_do=[
            "Cover the happy path, error cases, and edge cases",
            "Write tests that are independent and can run in any order",
            "Use descriptive test names that explain what is being tested",
            "Verify tests actually fail when the tested behavior is broken",
        ],
        must_not_do=[
            "Write tests that depend on external services or network",
            "Test implementation details — test behavior and contracts",
            "Write flaky tests that sometimes pass and sometimes fail",
        ],
        keywords=["test", "tests", "testing", "coverage", "spec", "assert", "verify"],
        issue_types=[],
        labels=["test", "testing"],
        priority=5,
    ),
    Focus(
        name="security",
        role="Security Auditor",
        description=(
            "You are reviewing and fixing security issues. Be thorough and methodical. "
            "Consider attack vectors, input validation, authentication, and data exposure."
        ),
        must_do=[
            "Identify all attack vectors related to the issue",
            "Check for OWASP Top 10 vulnerabilities in affected code",
            "Validate that fixes don't introduce new security holes",
        ],
        must_not_do=[
            "Dismiss edge cases as unlikely — attackers find edge cases",
            "Rely on client-side validation alone",
            "Store secrets, tokens, or credentials in code or logs",
        ],
        keywords=["security", "vulnerability", "xss", "injection", "csrf", "encrypt", "credential", "permission", "cve"],
        labels=["security"],
        priority=15,
    ),
    Focus(
        name="devops",
        role="DevOps Engineer",
        description=(
            "You are working on infrastructure, CI/CD, deployment, or operational tooling. "
            "Focus on reliability, reproducibility, and clear failure modes."
        ),
        must_do=[
            "Test changes in isolation before applying broadly",
            "Ensure rollback is possible for any deployment change",
            "Use version pinning for dependencies and base images",
        ],
        must_not_do=[
            "Make changes that can't be rolled back",
            "Use latest tags for production dependencies",
            "Skip health checks or readiness probes",
        ],
        keywords=["deploy", "docker", "ci", "cd", "pipeline", "kubernetes", "infrastructure", "terraform", "ansible"],
        labels=["devops", "infrastructure"],
        priority=5,
    ),
    Focus(
        name="merge_conflict",
        role="Merge Conflict Resolver",
        description=(
            "You are resolving merge conflicts on a review branch. Your ONLY job is to "
            "rebase the branch onto the target, resolve all conflicts correctly, and force-push. "
            "Do NOT add new features, fix other bugs, or make any changes beyond conflict resolution."
        ),
        must_do=[
            "Run `git fetch origin && git rebase origin/<target_branch>` to start the rebase",
            "Resolve every conflict by understanding the intent of BOTH sides",
            "Preserve the original work from this branch — do not drop commits",
            "Run tests after resolving all conflicts to verify nothing is broken",
            "Force-push with `git push --force-with-lease` after a clean rebase",
            "Verify the review diff looks correct after force-pushing",
        ],
        must_not_do=[
            "Make any code changes beyond what is needed to resolve conflicts",
            "Drop or squash commits from the branch",
            "Accept 'ours' or 'theirs' blindly — understand what both sides intended",
            "Push to the main/default branch — only push to this issue's branch",
            "Create a new branch or review — work on the existing one",
        ],
        keywords=["merge conflict", "rebase conflict", "resolve conflict"],
        labels=["merge-conflict"],
        priority=100,
    ),
    Focus(
        name="ci_fix",
        role="CI Failure Fixer",
        description=(
            "You are fixing CI test failures on an existing review branch. "
            "Your ONLY job is to make the failing tests pass on the SAME "
            "branch the original PR was opened from, by force-pushing the "
            "fix to that branch. Do NOT create a new branch or PR."
        ),
        must_do=[
            "Identify the existing branch from the task body (look for source_branch / branch X / PR #N notes).",
            "Check out that branch: git fetch origin && git checkout <branch> && git pull --ff-only",
            "Pull the failing job logs from GitHub Actions and read the actual errors. Do not assume — read.",
            "Reproduce the failure locally where possible. If the failure is platform-specific (Windows-only, target-specific matrix entry), work from log analysis.",
            "Make the MINIMAL fix that targets the actual failure. Run relevant tests locally before pushing.",
            "Push to the SAME branch with --force-with-lease if a rebase was needed, otherwise plain push.",
            "Verify on GitHub that the original PR's checks have re-run after your push.",
        ],
        must_not_do=[
            "Create a new branch named after this task.",
            "Open a new pull request.",
            "Modify code beyond what is needed to make the failing tests pass.",
            "Touch unrelated workflow files. Only edit .github/workflows/* if the failure is genuinely in that workflow.",
            "Make speculative fixes. If you cannot diagnose from logs, comment on the original PR with findings and close the task asking for human review.",
            "Refactor or 'improve' surrounding code while you're in there.",
        ],
        keywords=["ci fix", "ci-fix", "failed ci", "fix ci", "failing tests", "tier-", "matrix-verify", "github actions failure"],
        labels=["ci-fix"],
        issue_types=[],
        priority=100,
    ),
    Focus(
        name="chore",
        role="Maintenance Engineer",
        description=(
            "You are handling a small, well-defined maintenance task. Be quick, precise, "
            "and avoid scope creep. Get in, make the change, verify it works, get out."
        ),
        must_do=[
            "Keep changes minimal and focused on the task",
            "Verify the change works (run relevant tests or manual check)",
            "Commit with a clear message describing what changed and why",
        ],
        must_not_do=[
            "Expand scope beyond the issue description",
            "Refactor surrounding code while doing a chore",
            "Skip verification because the change looks trivial",
        ],
        keywords=["typo", "rename", "cleanup", "lint", "format", "update", "bump", "version", "dependency"],
        issue_types=["chore"],
        priority=0,
    ),
    Focus(
        name="epic_planner",
        role="Epic Planner",
        description=(
            "You are decomposing an epic into well-defined, actionable child tasks. "
            "Your job is to read the epic's goals, understand the scope, and create "
            "a complete set of sub-tasks that together fulfil the epic. Each task "
            "should be small enough to be completed in a single agent session."
        ),
        must_do=[
            "Read the epic description and any existing child tasks before creating new ones",
            "Create tasks that are concrete and independently actionable",
            "Give each task a clear title and a description with enough context to work independently",
            "Cover the full scope of the epic — don't leave gaps",
            "Set appropriate priorities and dependencies between tasks",
            "Use `oompah task child-create <epic-id> --title \"...\" --description \"...\"` to file each child task with an explicit parent-child link to the parent epic",
            "Set dependencies between children via `oompah task set-dependency <child-id> --depends-on <other-id>` where needed",
            "Set the epic status to 'Backlog' when planning is complete via `oompah task set-status <epic-id> Backlog`",
        ],
        must_not_do=[
            "Start implementing code — your job is planning, not coding",
            "Create tasks that are too large to finish in a single session",
            "Leave tasks without descriptions or context",
            "Duplicate tasks that already exist as children of the epic",
            "Close the epic yourself — it closes when all child tasks are done",
        ],
        keywords=["epic", "plan", "planning", "breakdown", "decompose", "children", "subtask", "tasks", "subtasks", "milestones"],
        issue_types=["epic"],
        labels=[],
        priority=8,
    ),
    Focus(
        name="duplicate_detector",
        role="Duplicate Investigator",
        description=(
            "You are investigating whether a fresh issue is a duplicate of an "
            "existing one. The issue shares a topic prefix or keywords with at "
            "least one previously-handled issue — your job is to determine "
            "whether they describe the same underlying problem."
        ),
        must_do=[
            "Search for similar tasks with `rg -n \"<query>\" .oompah/tasks docs plans README.md WORKFLOW.md` filtered by the shared topic prefix (e.g. for 'rogers-something' search 'rogers') or the bug/error description",
            "Read the description, error messages, and comments of any "
            "candidate duplicate with `oompah task view <identifier>` to confirm whether it covers the same ground",
            "If a confirmed duplicate exists: comment on the NEW issue linking "
            "to the original issue, then archive it using `oompah task set-status "
            "<identifier> Archived --summary "
            "\"duplicate-of:<original-id>\"`. Do NOT implement "
            "anything — the original already covers this",
            "If no clear duplicate is confirmed: continue with the work using "
            "the topic/resolution from the most likely match as your starting "
            "point, and close the candidate as non-duplicate if it truly "
            "represents a new problem",
        ],
        must_not_do=[
            "Start implementing code until you have confirmed whether this "
            "issue is a duplicate",
            "Implement two separate solutions for what is the same problem",
            "Assume a duplicate without reading the candidate's full description "
            "and comments — surface-level title match is not enough evidence",
            "Create a new branch or PR for this issue if it is a confirmed "
            "duplicate — close it and move on",
        ],
        keywords=[
            "duplicate", "similar", "already", "fixed", "exists",
            "related", "duplicate-of", "closed-as-duplicate",
            "rogers", "topic", "prefix", "same.*issue", "same.*problem",
        ],
        issue_types=["bug", "task", "feature", "chore"],
        priority=20,
    ),
]

# Default focus used when no specific focus matches
DEFAULT_FOCUS = Focus(
    name="general",
    role="Software Engineer",
    description=(
        "You are a general-purpose software engineer. Read the issue carefully, "
        "understand the codebase, implement the change, and verify it works."
    ),
    must_do=[
        "Read and understand the relevant code before making changes",
        "Follow existing code patterns and conventions",
        "Verify your changes work (tests, manual check, or both)",
    ],
    must_not_do=[
        "Make changes unrelated to the issue",
        "Over-engineer the solution",
    ],
    priority=-1,
)


def _text_matches(text: str, keywords: list[str]) -> int:
    """Count how many keywords appear in text as whole words. Case-insensitive."""
    if not text or not keywords:
        return 0
    text_lower = text.lower()
    count = 0
    for kw in keywords:
        # Use word boundary matching to avoid substring false positives
        if re.search(r'\b' + re.escape(kw.lower()) + r'\b', text_lower):
            count += 1
    return count


def score_focus(focus: Focus, issue: Issue) -> int:
    """Score how well a focus matches an issue. Higher = better fit."""
    score = 0

    # Handoff label: "needs:<focus_name>" is an explicit routing directive
    # and takes highest priority (score 200)
    if issue.labels:
        for label in issue.labels:
            if label.startswith("needs:"):
                requested_focus = label[len("needs:"):]
                if requested_focus.lower() == focus.name.lower():
                    score += 200

    # Keyword matches in title and description
    search_text = f"{issue.title or ''} {issue.description or ''}"
    keyword_hits = _text_matches(search_text, focus.keywords)
    score += keyword_hits * 10

    # Issue type match — if a focus specifies issue_types, prefer issues of those types.
    # A hard mismatch (return 0) only applies when there are no keyword or label hits.
    if focus.issue_types:
        if issue.issue_type and issue.issue_type.lower() in [t.lower() for t in focus.issue_types]:
            score += 50
        elif score == 0:
            return 0  # hard mismatch — no keyword/label hits and wrong type

    # Label match
    if focus.labels:
        issue_labels = _effective_issue_labels(issue)
        for fl in focus.labels:
            if fl.lower() in issue_labels:
                score += 30

    # Only add priority as tiebreaker if there was at least one real match
    if score > 0:
        score += focus.priority

    return score


def select_focus(issue: Issue, foci: list[Focus] | None = None) -> Focus:
    """Select the best-matching active focus for an issue.

    Only foci with status='active' are considered.

    Args:
        issue: The issue to match.
        foci: Optional list of foci to consider. If None, uses the full
              library (user foci + builtins).

    Returns:
        The best-matching Focus, or DEFAULT_FOCUS if nothing scores above 0.
    """
    if foci is None:
        foci = load_foci()

    best_focus = DEFAULT_FOCUS
    best_score = 0

    for focus in foci:
        if focus.status != "active":
            continue
        s = score_focus(focus, issue)
        if s > best_score:
            best_score = s
            best_focus = focus

    logger.info("Focus selected for %s: %s (score=%d via=score)",
                issue.identifier, best_focus.name, best_score)
    return best_focus


# ---------------------------------------------------------------------------
# Duplicate / fuzzy-similarity detection
# ---------------------------------------------------------------------------
#
# Design rationale (oompah-zlz_2-x6w3):
#
# The mechanical find-duplicates (exact title match) misses pattern-based
# duplicates like "rogers-how", "rogers-5hd", "rogers-zdn" where the same
# topic prefix ("rogers") is shared but suffixes differ.
#
# Strategy:
#  1. Title prefix extraction: extract the "topic" before the first
#     hyphen/underscore (e.g. "rogers" from "rogers-how").
#  2. Similarity scoring: weighted combination of
#      - same project + shared label + same type (baseline, ~0.5)
#      - same title prefix (pattern duplicate boost, +0.25)
#      - shared meaningful words from title (semantic overlap, +0.25)
#  3. find_similar_issues(): scan candidates for issues scoring ≥ min_score.
#  4. A "duplicate_detector" focus so agents can investigate closed/recent
#     issues when presented with a fresh candidate.

_MIN_PREFIX_LEN = 3  # minimum chars before first `-`/`_` to be significant
_MIN_SCORE_TO_FLAG = 0.5  # similarity score needed to flag as potential dup


def _extract_topic_prefix(title: str) -> str | None:
    """Extract the topic prefix from an issue title.

    Splits on the first hyphen OR underscore and uses everything before it
    as the prefix.  This correctly handles cases like 'rogers-how' which
    stores 'rogers' as the topic and the suffix 'how' as the variant spec.
    Longer compound-word prefixes with underscores (e.g. 'my_service_alive')
    are handled the same way: the first underscore acts as the separator.
    Falls back to returning the full title as-is when there is no hyphen or
    underscore (single-segment title).
    Returns ``None`` when the prefix is shorter than ``_MIN_PREFIX_LEN``
    or contains non-word characters.
    """
    if not title:
        return None
    t = title.strip()

    # Split on first hyphen OR underscore (whichever comes first)
    parts = re.split(r"[-_]", t, maxsplit=1)
    prefix = parts[0].lower()

    if len(prefix) < _MIN_PREFIX_LEN:
        return None
    # Must be word-like: lowercase letters, digits, underscores, or hyphens
    # (hyphens are allowed here since they belong to the prefix only on titles
    # with no _ split, e.g. "foo-bar" → prefix "foo-bar" returned as-is)
    if not re.fullmatch(r"[a-z0-9_-]+", prefix):
        return None
    return prefix


def _compute_similarity_score(a: Issue, b: Issue) -> float:
    """Return a 0.0–1.0 similarity score between two issues.

    Scores combine three signals:
    1. Basic structural match  (project + shared label + same type) → ~0.5
    2. Same title prefix        (pattern "rogers-*" duplicates)      → +0.25
    3. Shared meaningful words  (text-overlap in title words)        → +0.25

    Designed to catch "rogers-how / rogers-5hd / rogers-zdn" as high-score
    duplicates even when they share no labels.
    """
    score = 0.0

    # Signal 1: same project + same issue type → 0.25
    #            same project + same type + shared label → 0.5 (full structural match)
    same_project = bool(a.project_id and a.project_id == b.project_id)
    same_type = (
        a.issue_type is not None
        and b.issue_type is not None
        and a.issue_type.lower() == b.issue_type.lower()
    )
    a_labels = {l.lower() for l in (a.labels or [])}
    b_labels = {l.lower() for l in (b.labels or [])}
    has_shared_label = bool(a_labels & b_labels)

    if same_project and has_shared_label and same_type:
        score += 0.5
    elif same_project and same_type:
        score += 0.25
    elif same_project and has_shared_label:
        score += 0.15

    # Signal 2: same title prefix (pattern duplicate detection)
    prefix_a = _extract_topic_prefix(a.title or "")
    prefix_b = _extract_topic_prefix(b.title or "")
    if prefix_a and prefix_a == prefix_b:
        score += 0.25

    # Signal 3: shared meaningful words in title (case-insensitive, min 3 chars)
    def _title_words(title: str) -> set[str]:
        raw = (title or "").lower()
        # Strip the prefix (everything before first hyphen/underscore) to avoid
        # artificially boosting on the prefix itself.
        parts = re.split(r"[-_]", raw, maxsplit=1)
        suffix = parts[1] if len(parts) > 1 else raw
        return {
            w for w in re.findall(r"[a-z]{3,}", suffix)
            if w not in _STOP_WORDS
        }

    words_a = _title_words(a.title or "")
    words_b = _title_words(b.title or "")
    overlap = words_a & words_b
    if overlap:
        # Boost proportional to overlap (capped at +0.25 for full overlap)
        union = words_a | words_b
        score += min(0.25, 0.25 * len(overlap) / len(union))

    return min(score, 1.0)


def find_similar_issues(
    issue: Issue,
    candidates: list[Issue],
    min_score: float = _MIN_SCORE_TO_FLAG,
) -> list[tuple[Issue, float]]:
    """Find issues in ``candidates`` that are similar to ``issue``.

    Returns a list of ``(candidate, score)`` pairs, sorted descending by
    score, where ``score >= min_score``. The candidate itself is excluded
    (an issue cannot be similar to itself by identifier).

    Args:
        issue:   The issue to evaluate.
        candidates: Pool of other issues to compare against (may include
                   closed, in_progress, and open issues from the same project).
        min_score: Minimum similarity score to return (default 0.5).

    Returns:
        List of (similar_issue, score) sorted by score descending.
    """
    results: list[tuple[Issue, float]] = []
    for candidate in candidates:
        if candidate.identifier == issue.identifier:
            continue
        score = _compute_similarity_score(issue, candidate)
        if score >= min_score:
            results.append((candidate, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Agentic (LLM-based) focus triage
# ---------------------------------------------------------------------------
#
# Design recorded in plans/agentic-focus-triage.md. Quick recap:
#
# 1. Explicit `needs:<name>` label short-circuits both LLM and scorer
#    (user routing always wins).
# 2. LLM triage: provider's default_model gets a prompt listing the
#    issue + active foci; LLM returns ``name: reasoning``. We log the
#    reasoning so triage decisions are auditable later.
# 3. Sanity check (D): if the LLM picks a focus whose deterministic
#    score_focus() == 0 (zero keyword/label/type alignment), treat it
#    as a likely hallucination and fall back to deterministic top.
#    Strict threshold preserves the LLM's value over the scorer in
#    legitimate cases where keywords are weak.
# 4. Anything else that fails (bad provider, timeout, empty output,
#    unknown name, network error) → fall back to deterministic top.

def _build_triage_prompt(issue: Issue, foci: list[Focus]) -> str:
    """Render the triage prompt for the LLM.

    Output format the LLM is asked to follow:
        ``<focus_name>: <one-line reasoning>``
    Alternatively, ``default`` alone if no listed focus is a good fit.
    """
    description = (issue.description or "").strip()
    if len(description) > 1500:
        description = description[:1500] + " ..."
    labels = ", ".join(issue.labels or []) or "(none)"

    spec_lines: list[str] = []
    for f in foci:
        desc = (f.description or "").strip()
        if len(desc) > 200:
            desc = desc[:197] + "..."
        must_do = "; ".join((f.must_do or [])[:3]) or "(none listed)"
        spec_lines.append(
            f"- name: {f.name}\n"
            f"    role: {f.role}\n"
            f"    description: {desc}\n"
            f"    typical work: {must_do}"
        )

    return (
        "You are routing an engineering issue to the best-fit specialist.\n\n"
        "ISSUE\n"
        f"  identifier: {issue.identifier}\n"
        f"  title: {issue.title or ''}\n"
        f"  type: {issue.issue_type or 'task'}\n"
        f"  priority: {issue.priority}\n"
        f"  labels: {labels}\n"
        "  description:\n"
        f"    {description}\n\n"
        "SPECIALISTS\n  "
        + "\n  ".join(spec_lines) + "\n\n"
        "TASK\n"
        "Pick the single best-fit specialist by name and give a short reason.\n"
        "Output exactly one line in the format `name: reasoning`.\n"
        "If no specialist clearly fits better than the others, output\n"
        "`default: reasoning`.\n"
        "Do NOT add prose, quotes, or explanations beyond the single line."
    )


def _parse_triage_response(content: str) -> tuple[str | None, str]:
    """Parse the model's response into ``(name, reasoning)``.

    Returns ``(None, "")`` for completely empty/garbage output. The
    caller treats ``name == "default"`` as the explicit decline path.
    """
    if not content:
        return None, ""
    # Trim and take first non-empty line — models sometimes prefix with
    # markdown or explanation despite the prompt.
    line = ""
    for raw in content.splitlines():
        candidate = raw.strip().lstrip("-*•").strip()
        if candidate:
            line = candidate
            break
    if not line:
        return None, ""
    if ":" in line:
        name, reasoning = line.split(":", 1)
        return name.strip().strip("`'\"").lower() or None, reasoning.strip()
    # No colon — treat the whole line as a name (e.g. plain ``default``).
    return line.strip().strip("`'\"").lower() or None, ""


def _triage_cache_key(issue: Issue, foci: list[Focus]) -> str:
    """Stable hash of the inputs that affect the LLM's decision."""
    content = "|".join([
        issue.id or "",
        issue.title or "",
        issue.description or "",
        ",".join(sorted(issue.labels or [])),
        issue.issue_type or "",
        str(issue.priority if issue.priority is not None else ""),
    ])
    foci_sig = ",".join(sorted(
        f"{f.name}:{(f.description or '')[:120]}:{','.join(sorted(f.keywords or []))}"
        for f in foci if f.status == "active"
    ))
    return hashlib.sha256((content + "||" + foci_sig).encode("utf-8")).hexdigest()


async def _select_focus_llm(
    issue: Issue, foci: list[Focus], provider: Any,
) -> tuple[str | None, str]:
    """Call the provider's default_model to pick a focus.

    Returns ``(name, reasoning)`` or ``(None, "")`` on any failure.
    Network/HTTP/parsing failures are swallowed so the caller can fall
    through to the deterministic scorer.
    """
    if not provider or not getattr(provider, "default_model", None):
        return None, ""
    base_url = (provider.base_url or "").rstrip("/")
    if not base_url:
        return None, ""

    # Lazy import to keep focus.py from depending on api_agent at import time
    # (api_agent imports prompt which imports models — keep the dep DAG flat).
    from oompah.api_agent import _http_post, _build_ssl_context

    prompt = _build_triage_prompt(issue, foci)
    # Thinking models (e.g. MiniMax-M2.7) burn output budget on the
    # chain-of-thought trace and return content="" / null when the budget
    # runs out before the answer is emitted. 1024 leaves room for reasoning
    # plus the "name: reasoning" answer. Triage is one-shot per issue and
    # cached, so the extra tokens are negligible cost.
    payload = {
        "model": provider.default_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.0,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {provider.api_key or ''}",
        "User-Agent": "oompah/0.1",
    }

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                _http_post,
                f"{base_url}/chat/completions",
                headers, body, _build_ssl_context(),
            ),
            timeout=_TRIAGE_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("LLM triage timed out for %s", issue.identifier)
        return None, ""
    except Exception as exc:
        logger.warning("LLM triage failed for %s: %s", issue.identifier, exc)
        return None, ""

    try:
        content = response["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return None, ""
    return _parse_triage_response(content)


async def select_focus_async(
    issue: Issue,
    foci: list[Focus] | None = None,
    provider: Any = None,
) -> Focus:
    """LLM-augmented focus selection. Falls back to deterministic
    :func:`select_focus` on any failure or when no provider is given.

    Order of operations:
        1. ``needs:<focus>`` label short-circuit.
        2. LLM triage via ``provider.default_model`` (cached by content).
        3. Deterministic ``score_focus`` ranking (same as :func:`select_focus`).
    """
    if foci is None:
        foci = load_foci()
    active_foci = [f for f in foci if f.status == "active"]

    # Step 1: explicit handoff label wins.
    if issue.labels:
        wanted = None
        for label in issue.labels:
            if label.startswith("needs:"):
                wanted = label[len("needs:"):].strip().lower()
                break
        if wanted:
            for f in active_foci:
                if f.name.lower() == wanted:
                    logger.info(
                        "Focus selected for %s: %s (via=label)",
                        issue.identifier, f.name,
                    )
                    return f

    # Step 2: LLM triage.
    if provider is not None and active_foci:
        cache_key = _triage_cache_key(issue, active_foci)
        cached = _triage_cache.get(cache_key)
        if cached is not None:
            name, reasoning = cached
        else:
            name, reasoning = await _select_focus_llm(
                issue, active_foci, provider,
            )
            if name is not None:
                _triage_cache[cache_key] = (name, reasoning)

        if name == "default":
            logger.info(
                "Focus selected for %s: default (via=llm reasoning=%r)",
                issue.identifier, reasoning,
            )
            return DEFAULT_FOCUS

        if name:
            picked = next(
                (f for f in active_foci if f.name.lower() == name), None,
            )
            if picked is None:
                logger.warning(
                    "LLM picked unknown focus %r for %s; falling back. reasoning=%r",
                    name, issue.identifier, reasoning,
                )
            else:
                # Sanity check D: score must be > 0 (catch hallucinated
                # but plausible-looking names that have zero alignment
                # with the issue's keywords/labels/type).
                d_score = score_focus(picked, issue)
                if d_score > 0:
                    logger.info(
                        "Focus selected for %s: %s (via=llm score=%d reasoning=%r)",
                        issue.identifier, picked.name, d_score, reasoning,
                    )
                    return picked
                logger.warning(
                    "LLM picked %s for %s but deterministic score=0 "
                    "(likely hallucination); falling back. reasoning=%r",
                    picked.name, issue.identifier, reasoning,
                )

    # Step 3: deterministic fallback.
    return select_focus(issue, foci)


def load_foci(path: str | None = None) -> list[Focus]:
    """Load foci from user file + builtins. User foci override builtins by name."""
    foci_path = path or DEFAULT_FOCI_PATH
    user_foci: list[Focus] = []

    if os.path.exists(foci_path):
        try:
            with open(foci_path, "r") as f:
                data = json.load(f)
            user_foci = [Focus.from_dict(d) for d in data]
            logger.info("Loaded %d user foci from %s", len(user_foci), foci_path)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load foci from %s: %s", foci_path, exc)

    # Merge: user foci override builtins by name
    user_names = {f.name for f in user_foci}
    combined = list(user_foci)
    for builtin in BUILTIN_FOCI:
        if builtin.name not in user_names:
            combined.append(builtin)

    return combined


def save_foci(foci: list[Focus], path: str | None = None) -> None:
    """Save foci to the user file."""
    foci_path = path or DEFAULT_FOCI_PATH
    os.makedirs(os.path.dirname(foci_path) or ".", exist_ok=True)
    with open(foci_path, "w") as f:
        json.dump([fo.to_dict() for fo in foci], f, indent=2)


def _save_proposed_focus(focus: Focus, path: str | None = None) -> None:
    """Add a proposed focus to the user file, skipping if name already exists."""
    foci_path = path or DEFAULT_FOCI_PATH
    existing: list[Focus] = []
    if os.path.exists(foci_path):
        try:
            with open(foci_path, "r") as f:
                existing = [Focus.from_dict(d) for d in json.load(f)]
        except (json.JSONDecodeError, OSError):
            pass

    # Don't overwrite if a focus with this name already exists
    if any(f.name == focus.name for f in existing):
        return

    existing.append(focus)
    save_foci(existing, foci_path)


# -- Focus suggestions --

DEFAULT_SUGGESTIONS_PATH = ".oompah/focus_suggestions.json"


@dataclass
class FocusSuggestion:
    """A suggested new focus based on observed work patterns."""

    suggested_name: str
    suggested_role: str
    reason: str  # why this focus is needed
    source_issues: list[str]  # identifiers of issues that motivated this
    sample_keywords: list[str]  # extracted keywords from the work
    created_at: str = ""
    status: str = "pending"  # pending | accepted | dismissed

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggested_name": self.suggested_name,
            "suggested_role": self.suggested_role,
            "reason": self.reason,
            "source_issues": self.source_issues,
            "sample_keywords": self.sample_keywords,
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FocusSuggestion:
        return cls(
            suggested_name=str(d.get("suggested_name", "")),
            suggested_role=str(d.get("suggested_role", "")),
            reason=str(d.get("reason", "")),
            source_issues=d.get("source_issues", []),
            sample_keywords=d.get("sample_keywords", []),
            created_at=str(d.get("created_at", "")),
            status=str(d.get("status", "pending")),
        )


# Common word categories for extracting domain keywords from work
_DOMAIN_KEYWORDS = {
    "api", "database", "cache", "queue", "auth", "logging", "monitoring",
    "migration", "schema", "config", "validation", "parsing", "serialization",
    "websocket", "http", "grpc", "graphql", "rest", "oauth", "jwt", "ssl",
    "performance", "optimization", "profiling", "benchmark", "memory", "cpu",
    "concurrency", "async", "threading", "parallel", "distributed",
    "notification", "email", "webhook", "event", "callback", "scheduler",
    "backup", "restore", "export", "import", "etl", "pipeline",
    "plugin", "extension", "middleware", "adapter", "integration",
}

# Stop words to ignore
_STOP_WORDS = {
    "the", "a", "an", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "because", "but", "and",
    "or", "if", "while", "that", "this", "it", "its", "i", "my", "we",
    "our", "you", "your", "he", "she", "they", "them", "their",
}


def _extract_work_keywords(title: str, description: str | None,
                           comments: list[dict]) -> list[str]:
    """Extract meaningful keywords from an issue's work trail."""
    # Combine all text
    parts = [title or ""]
    if description:
        parts.append(description)
    for c in comments:
        text = c.get("text", "")
        # Skip system/dispatch comments
        if text.startswith("Agent dispatched") or text.startswith("Focus:"):
            continue
        parts.append(text)

    all_text = " ".join(parts).lower()
    # Extract words
    words = re.findall(r'\b[a-z]{3,}\b', all_text)

    # Count frequencies, excluding stop words
    freq: dict[str, int] = {}
    for w in words:
        if w in _STOP_WORDS:
            continue
        freq[w] = freq.get(w, 0) + 1

    # Prioritize domain keywords, then by frequency
    scored: list[tuple[str, float]] = []
    for word, count in freq.items():
        score = count
        if word in _DOMAIN_KEYWORDS:
            score *= 3  # boost domain terms
        scored.append((word, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [w for w, _ in scored[:15]]


def _work_matches_focus(focus: Focus, work_keywords: list[str]) -> float:
    """Score how well observed work matches a focus's domain. 0.0-1.0."""
    if not focus.keywords or not work_keywords:
        return 0.0

    focus_kw_set = {k.lower() for k in focus.keywords}
    work_kw_set = set(work_keywords)

    overlap = focus_kw_set & work_kw_set
    if not overlap:
        return 0.0

    # Jaccard-like: overlap relative to focus keywords
    return len(overlap) / len(focus_kw_set)


# -- Domain-specific rule templates for auto-proposed foci --
# Each entry: set of trigger keywords -> (description fragment, must_do list, must_not_do list)
_DOMAIN_RULES: list[tuple[set[str], str, list[str], list[str]]] = [
    (
        {"api", "http", "rest", "graphql", "grpc", "endpoint", "route"},
        "working with APIs, endpoints, and request handling",
        [
            "Validate all inputs at the API boundary",
            "Return appropriate HTTP status codes and error messages",
            "Maintain backward compatibility with existing API consumers",
            "Document new or changed endpoints",
        ],
        [
            "Change API contracts without considering downstream consumers",
            "Expose internal implementation details in API responses",
            "Skip input validation or error handling",
        ],
    ),
    (
        {"database", "migration", "schema", "query", "sql", "table", "index"},
        "database operations, schema changes, and data access",
        [
            "Write reversible migrations with both up and down steps",
            "Test migrations against realistic data volumes",
            "Add appropriate indexes for new query patterns",
            "Back up data before destructive schema changes",
        ],
        [
            "Run destructive migrations without a rollback plan",
            "Write queries that scan entire tables without indexes",
            "Mix schema changes with application logic in the same commit",
        ],
    ),
    (
        {"cache", "redis", "memcached", "caching", "ttl", "invalidation"},
        "caching layers, cache invalidation, and performance optimization through caching",
        [
            "Define clear cache invalidation rules for every cached value",
            "Set appropriate TTLs based on data freshness requirements",
            "Handle cache misses gracefully with fallback to source",
            "Monitor cache hit rates and memory usage",
        ],
        [
            "Cache without a clear invalidation strategy",
            "Assume cached data is always fresh",
            "Cache sensitive data (credentials, PII) without encryption",
        ],
    ),
    (
        {"auth", "oauth", "jwt", "token", "login", "session", "permission"},
        "authentication, authorization, and access control",
        [
            "Follow the principle of least privilege",
            "Validate tokens and sessions on every protected request",
            "Use constant-time comparison for secrets and tokens",
            "Log authentication events for audit trails",
        ],
        [
            "Store passwords or tokens in plaintext",
            "Trust client-side authorization checks alone",
            "Log sensitive credentials or tokens",
            "Implement custom cryptography when proven libraries exist",
        ],
    ),
    (
        {"async", "concurrency", "threading", "parallel", "queue", "worker"},
        "concurrent and asynchronous programming, task queues, and parallel processing",
        [
            "Identify and protect shared mutable state",
            "Handle task failures with retries and dead-letter queues",
            "Set appropriate timeouts for all async operations",
            "Test under concurrent load, not just sequential execution",
        ],
        [
            "Introduce race conditions by accessing shared state without synchronization",
            "Ignore task failures or silently swallow exceptions",
            "Create unbounded queues or thread pools",
        ],
    ),
    (
        {"config", "configuration", "settings", "environment", "env"},
        "configuration management, environment setup, and settings",
        [
            "Validate configuration at startup, fail fast on bad values",
            "Document all configuration options with defaults and examples",
            "Support environment variable overrides for deployment flexibility",
        ],
        [
            "Hardcode values that should be configurable",
            "Store secrets in configuration files committed to version control",
            "Change defaults without considering existing deployments",
        ],
    ),
    (
        {"monitoring", "logging", "metrics", "observability", "tracing"},
        "observability, logging, metrics collection, and system monitoring",
        [
            "Use structured logging with consistent field names",
            "Add metrics for key business and operational events",
            "Include correlation IDs for request tracing",
            "Set appropriate log levels (debug vs info vs error)",
        ],
        [
            "Log sensitive data (PII, credentials, tokens)",
            "Create high-cardinality metrics that explode storage",
            "Use print statements instead of proper logging",
        ],
    ),
    (
        {"performance", "optimization", "profiling", "benchmark", "memory", "cpu"},
        "performance analysis, optimization, and resource efficiency",
        [
            "Measure before and after with benchmarks, not assumptions",
            "Profile to find actual bottlenecks before optimizing",
            "Document performance requirements and test against them",
            "Consider memory, CPU, and I/O impacts together",
        ],
        [
            "Optimize without measuring — premature optimization wastes time",
            "Sacrifice code clarity for marginal performance gains",
            "Ignore regression testing after optimization changes",
        ],
    ),
    (
        {"webhook", "event", "callback", "notification", "email", "scheduler"},
        "event-driven systems, webhooks, notifications, and scheduled tasks",
        [
            "Make event handlers idempotent — they may be called more than once",
            "Implement retry logic with exponential backoff for failed deliveries",
            "Validate incoming webhook payloads and verify signatures",
            "Log event processing for debugging and audit",
        ],
        [
            "Assume events arrive exactly once or in order",
            "Block event processing on slow downstream services",
            "Skip payload validation on incoming webhooks",
        ],
    ),
    (
        {"integration", "adapter", "middleware", "plugin", "extension"},
        "system integration, adapters, and extensibility",
        [
            "Define clear interfaces between integrated systems",
            "Handle external system failures gracefully with fallbacks",
            "Version integration contracts to allow independent upgrades",
            "Test with realistic mock data from the external system",
        ],
        [
            "Tightly couple to external system internals",
            "Assume external systems are always available or fast",
            "Skip error handling for external API calls",
        ],
    ),
]

# Baseline rules applied to every auto-proposed focus
_BASE_MUST_DO = [
    "Read and understand the relevant code before making changes",
    "Verify your changes work (tests, manual check, or both)",
    "Keep changes focused on the task at hand",
]
_BASE_MUST_NOT_DO = [
    "Make changes unrelated to the issue",
    "Over-engineer the solution beyond what is needed",
]


def _generate_focus_rules(
    top_keywords: list[str],
    all_keywords: list[str],
    issue: Issue,
) -> tuple[str, list[str], list[str]]:
    """Generate a description, must_do, and must_not_do for a proposed focus.

    Uses domain keyword matching to find relevant rule templates, then
    composes them into a coherent set of rules.
    """
    kw_set = set(all_keywords)
    domain_parts: list[str] = []
    must_do: list[str] = list(_BASE_MUST_DO)
    must_not_do: list[str] = list(_BASE_MUST_NOT_DO)

    # Match domain rules by keyword overlap
    for trigger_kws, desc_fragment, rules_do, rules_not in _DOMAIN_RULES:
        overlap = trigger_kws & kw_set
        if overlap:
            domain_parts.append(desc_fragment)
            # Add rules that aren't already present
            for r in rules_do:
                if r not in must_do:
                    must_do.append(r)
            for r in rules_not:
                if r not in must_not_do:
                    must_not_do.append(r)

    # Build description from matched domains
    if domain_parts:
        domains_text = ", ".join(domain_parts[:3])
        description = (
            f"You are a specialist in {domains_text}. "
            f"This focus was identified from work on issues involving "
            f"{', '.join(top_keywords[:5])}. "
            f"Apply deep domain knowledge to deliver correct, well-tested changes."
        )
    else:
        # No domain match — build from keywords and issue type
        kw_text = ", ".join(top_keywords[:5])
        description = (
            f"You are a specialist in work involving {kw_text}. "
            f"This area was identified from completed {issue.issue_type} issues "
            f"that didn't fit existing focus areas. "
            f"Understand the domain deeply before making changes, "
            f"and ensure all work is tested and verified."
        )
        # Add issue-type-specific rules
        if issue.issue_type == "bug":
            must_do.append("Reproduce the issue before attempting a fix")
            must_do.append("Write a regression test that covers this failure mode")
            must_not_do.append("Apply speculative fixes without understanding the root cause")
        elif issue.issue_type == "feature":
            must_do.append("Follow existing code patterns and conventions")
            must_do.append("Write tests for new functionality")
            must_not_do.append("Introduce new dependencies without justification")

    return description, must_do, must_not_do


# Minimum number of distinct source issues before a suggestion is promoted
# to a proposed focus. A single issue is not enough evidence.
MIN_ISSUES_FOR_PROPOSAL = 3

# Minimum number of domain keywords (from _DOMAIN_KEYWORDS) that must appear
# in the work to consider it a coherent new domain worth a focus.
MIN_DOMAIN_KEYWORDS = 3


def analyze_completed_issue(
    issue: Issue,
    comments: list[dict],
    foci: list[Focus] | None = None,
    threshold: float = 0.4,
) -> FocusSuggestion | None:
    """Analyze a completed issue to see if existing foci cover the work done.

    Only suggests a new focus when there is overwhelming evidence that no
    existing focus covers the work: the best match must be below the threshold
    (default 0.4), AND the work must contain enough domain-specific keywords
    to represent a coherent specialty. Even then, a proposed focus is only
    written to disk after multiple distinct issues have triggered the same
    suggestion.

    Args:
        issue: The closed issue.
        comments: Comments from the issue trail.
        foci: Available foci to compare against. Defaults to full library.
        threshold: Minimum match score to consider a focus as covering the work.

    Returns:
        A FocusSuggestion if no existing focus adequately covers the work,
        or None if existing foci are sufficient.
    """
    if foci is None:
        foci = load_foci()

    work_keywords = _extract_work_keywords(issue.title, issue.description, comments)
    if not work_keywords:
        return None  # not enough signal

    # Require a minimum number of domain-specific keywords to avoid
    # suggesting foci for generic or one-off work.
    domain_hits = sum(1 for kw in work_keywords if kw in _DOMAIN_KEYWORDS)
    if domain_hits < MIN_DOMAIN_KEYWORDS:
        logger.debug(
            "Issue %s has only %d domain keywords (need %d), skipping suggestion",
            issue.identifier, domain_hits, MIN_DOMAIN_KEYWORDS,
        )
        return None

    # Score each focus against the actual work
    best_match = 0.0
    best_focus_name = ""
    for focus in foci:
        score = _work_matches_focus(focus, work_keywords)
        if score > best_match:
            best_match = score
            best_focus_name = focus.name

    if best_match >= threshold:
        logger.debug(
            "Issue %s work matches focus '%s' (score=%.2f), no suggestion needed",
            issue.identifier, best_focus_name, best_match,
        )
        return None

    # No good match — record a suggestion but don't propose a focus yet.
    # A proposed focus is only written after MIN_ISSUES_FOR_PROPOSAL distinct
    # issues have contributed to the same suggestion.
    top_kw = work_keywords[:5]
    suggested_name = "_".join(top_kw[:2]) if len(top_kw) >= 2 else top_kw[0] if top_kw else "unknown"
    suggested_role = f"{' '.join(w.capitalize() for w in top_kw[:3])} Specialist"

    # Generate meaningful description, must_do, and must_not_do
    description, must_do, must_not_do = _generate_focus_rules(
        top_kw, work_keywords, issue,
    )

    from datetime import datetime, timezone
    suggestion = FocusSuggestion(
        suggested_name=suggested_name,
        suggested_role=suggested_role,
        reason=(
            f"Issue '{issue.title}' (type: {issue.issue_type}) completed work "
            f"that doesn't match any existing focus well (best match: "
            f"'{best_focus_name}' at {best_match:.0%}). "
            f"Top work keywords: {', '.join(top_kw)}"
        ),
        source_issues=[issue.identifier],
        sample_keywords=work_keywords[:10],
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    # Only promote to a proposed focus after enough distinct issues have
    # triggered the same suggestion — one issue is noise, three is a pattern.
    existing_suggestions = load_suggestions()
    existing = next(
        (s for s in existing_suggestions
         if s.suggested_name == suggested_name and s.status == "pending"),
        None,
    )
    # Count how many unique issues will back this suggestion after merging
    merged_issues = set(suggestion.source_issues)
    if existing:
        merged_issues |= set(existing.source_issues)

    if len(merged_issues) >= MIN_ISSUES_FOR_PROPOSAL:
        proposed = Focus(
            name=suggested_name,
            role=suggested_role,
            description=description,
            must_do=must_do,
            must_not_do=must_not_do,
            keywords=work_keywords[:10],
            issue_types=[issue.issue_type] if issue.issue_type else [],
            status="proposed",
        )
        _save_proposed_focus(proposed)
        logger.info(
            "Focus proposal promoted for '%s' (%s) — backed by %d issues",
            suggested_name, suggested_role, len(merged_issues),
        )
    else:
        logger.info(
            "Focus suggestion recorded for '%s' — %d/%d issues needed before proposal",
            suggested_name, len(merged_issues), MIN_ISSUES_FOR_PROPOSAL,
        )

    logger.info(
        "Focus suggestion for %s: '%s' (%s) — no existing focus matched well",
        issue.identifier, suggested_name, suggested_role,
    )
    return suggestion


def load_suggestions(path: str | None = None) -> list[FocusSuggestion]:
    """Load focus suggestions from disk."""
    suggestions_path = path or DEFAULT_SUGGESTIONS_PATH
    if not os.path.exists(suggestions_path):
        return []
    try:
        with open(suggestions_path, "r") as f:
            data = json.load(f)
        return [FocusSuggestion.from_dict(d) for d in data]
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load focus suggestions: %s", exc)
        return []


def save_suggestion(suggestion: FocusSuggestion, path: str | None = None) -> None:
    """Append a focus suggestion, merging with existing source issues if same name."""
    suggestions_path = path or DEFAULT_SUGGESTIONS_PATH
    existing = load_suggestions(suggestions_path)

    # Merge if we already have a suggestion with the same name
    merged = False
    for s in existing:
        if s.suggested_name == suggestion.suggested_name and s.status == "pending":
            # Add source issues and deduplicate
            s.source_issues = list(set(s.source_issues + suggestion.source_issues))
            # Update keywords with union
            s.sample_keywords = list(set(s.sample_keywords + suggestion.sample_keywords))[:15]
            s.reason = suggestion.reason  # use latest reason
            merged = True
            break

    if not merged:
        existing.append(suggestion)

    os.makedirs(os.path.dirname(suggestions_path) or ".", exist_ok=True)
    with open(suggestions_path, "w") as f:
        json.dump([s.to_dict() for s in existing], f, indent=2)


def update_suggestion_status(name: str, status: str, path: str | None = None) -> bool:
    """Update a suggestion's status (accepted, dismissed)."""
    suggestions_path = path or DEFAULT_SUGGESTIONS_PATH
    suggestions = load_suggestions(suggestions_path)
    for s in suggestions:
        if s.suggested_name == name:
            s.status = status
            os.makedirs(os.path.dirname(suggestions_path) or ".", exist_ok=True)
            with open(suggestions_path, "w") as f:
                json.dump([x.to_dict() for x in suggestions], f, indent=2)
            return True
    return False
