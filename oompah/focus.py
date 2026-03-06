"""Agent focus system — tailors prompts to the work at hand.

A Focus defines a specialized role with instructions, must-do/must-not-do
rules, and keyword matching. The orchestrator picks the best-fit focus for
each issue and injects it into the agent prompt.

Foci are loaded from .oompah/foci.json (user-editable library) with
built-in defaults as fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from oompah.models import Issue

logger = logging.getLogger(__name__)

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

    def to_dict(self) -> dict[str, Any]:
        return {
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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Focus:
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
        )

    def render(self) -> str:
        """Render this focus as prompt text."""
        lines = [
            f"## Your Role: {self.role}",
            "",
            self.description,
        ]
        if self.must_do:
            lines.append("")
            lines.append("### You MUST:")
            for item in self.must_do:
                lines.append(f"- {item}")
        if self.must_not_do:
            lines.append("")
            lines.append("### You must NOT:")
            for item in self.must_not_do:
                lines.append(f"- {item}")
        return "\n".join(lines)


# -- Built-in focus library --

BUILTIN_FOCI: list[Focus] = [
    Focus(
        name="bugfix",
        role="Bug Investigator & Fixer",
        description=(
            "You are a methodical debugger. Your primary goal is to find the root cause, "
            "fix it with minimal changes, and verify the fix with tests. Do not refactor "
            "surrounding code — stay laser-focused on the bug."
        ),
        must_do=[
            "Reproduce the bug or confirm the failure mode before changing any code",
            "Identify and explain the root cause in a comment before implementing the fix",
            "Write or update a test that would have caught this bug",
            "Verify the fix doesn't break existing tests",
        ],
        must_not_do=[
            "Refactor code unrelated to the bug",
            "Make speculative fixes for issues not described in the ticket",
            "Change public APIs unless the bug is in the API itself",
        ],
        keywords=["bug", "crash", "error", "broken", "fail", "exception", "regression", "fix"],
        issue_types=["bug"],
        priority=10,
    ),
    Focus(
        name="feature",
        role="Feature Developer",
        description=(
            "You are building a new capability. Understand the requirements thoroughly, "
            "design a clean implementation that fits the existing architecture, and deliver "
            "working code with tests."
        ),
        must_do=[
            "Read and understand the existing codebase architecture before writing new code",
            "Follow existing code patterns and conventions",
            "Write tests for new functionality",
            "Document any new public APIs or configuration options",
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
            "and visual consistency. Test in the browser context."
        ),
        must_do=[
            "Consider accessibility (aria labels, keyboard navigation, contrast)",
            "Match existing UI patterns and styling conventions",
            "Test responsive behavior if applicable",
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
            "Document the threat model for any security-sensitive changes",
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
            "Document any new environment variables or configuration",
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
            "You are resolving merge conflicts on a pull request branch. Your ONLY job is to "
            "rebase the branch onto the target, resolve all conflicts correctly, and force-push. "
            "Do NOT add new features, fix other bugs, or make any changes beyond conflict resolution."
        ),
        must_do=[
            "Run `git fetch origin && git rebase origin/<target_branch>` to start the rebase",
            "Resolve every conflict by understanding the intent of BOTH sides",
            "Preserve the original work from this branch — do not drop commits",
            "Run tests after resolving all conflicts to verify nothing is broken",
            "Force-push with `git push --force-with-lease` after a clean rebase",
            "Verify the PR/MR diff looks correct after force-pushing",
        ],
        must_not_do=[
            "Make any code changes beyond what is needed to resolve conflicts",
            "Drop or squash commits from the branch",
            "Accept 'ours' or 'theirs' blindly — understand what both sides intended",
            "Push to the main/default branch — only push to this issue's branch",
            "Create a new branch or PR — work on the existing one",
        ],
        keywords=["merge conflict", "rebase", "conflict"],
        labels=["merge-conflict"],
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

    # Issue type match
    if focus.issue_types and issue.issue_type:
        if issue.issue_type.lower() in [t.lower() for t in focus.issue_types]:
            score += 50

    # Label match
    if focus.labels and issue.labels:
        issue_labels = {l.lower() for l in issue.labels}
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

    logger.info("Focus selected for %s: %s (score=%d)", issue.identifier, best_focus.name, best_score)
    return best_focus


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


def analyze_completed_issue(
    issue: Issue,
    comments: list[dict],
    foci: list[Focus] | None = None,
    threshold: float = 0.15,
) -> FocusSuggestion | None:
    """Analyze a completed issue to see if existing foci cover the work done.

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

    # No good match — suggest a new focus
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

    # Also create a proposed Focus in the foci library
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
