"""Source control management abstraction.

Provides a unified interface over GitHub and GitLab for operations like
listing pull/merge requests. Implementations use direct HTTP API calls
for performance (no subprocess overhead).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import urllib.parse
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NotRequired, TypedDict

import httpx

from oompah.secrets import register_secret

logger = logging.getLogger(__name__)


class CIStatus(str, Enum):
    """Forge-neutral CI verdicts returned by :class:`SCMProvider`.

    The enum subclasses ``str`` deliberately: persisted review payloads and
    existing consumers comparing a status with a string keep their established
    behaviour while providers gain one finite, documented vocabulary.
    """

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    UNKNOWN = "unknown"


# ``CIState`` is the contract name used by forge integrations. Keep the
# status spelling as a public compatibility alias for existing callers.
CIState = CIStatus


class ProtectedWorkflowEvidenceDisposition(str, Enum):
    """Completeness of an exact protected-workflow evidence observation.

    This vocabulary is deliberately separate from :class:`CIStatus`.  In
    particular, ``CIStatus.PASSED`` is aggregate scheduling information and
    must never be promoted into terminal-gate authority.  Only ``COMPLETE``
    results returned by the rich evidence API carry attestable records.
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ProtectedWorkflowEvidenceRequest:
    """Operator-pinned identity used to collect one protected workflow run.

    ``review_id`` may be omitted because recovery work can retain only its
    immutable source branch and audit SHA.  Providers must then discover one
    and only one merged review matching all source/head/target fields.

    Required job and step names are exact, case-sensitive identities.  A
    complete observation contains exactly ``required_job_names`` and each job
    contains every ``required_step_names`` entry exactly once.  The workflow
    blob and GitHub App ID are pinned here rather than inferred from a green
    aggregate check result.
    """

    source_repository: str
    source_branch: str
    head_sha: str
    target_branch: str
    workflow_id: int
    workflow_path: str
    workflow_blob_sha: str
    app_id: int
    required_job_names: tuple[str, ...]
    required_step_names: tuple[str, ...] = ()
    event: str = "pull_request"
    review_id: str | None = None


@dataclass(frozen=True)
class ProtectedReviewEvidence:
    """Immutable forge observation binding a merged review to exact refs."""

    review_id: str
    state: str
    source_repository: str
    source_branch: str
    head_sha: str
    target_repository: str
    target_branch: str
    base_sha: str
    merge_sha: str
    merged_at: str


@dataclass(frozen=True)
class ProtectedWorkflowMetadataEvidence:
    """Immutable identity of the workflow definition registered by GitHub."""

    workflow_id: int
    name: str
    path: str
    state: str
    node_id: str


@dataclass(frozen=True)
class ProtectedWorkflowRunEvidence:
    """One exact workflow run and its latest, explicitly selected attempt."""

    run_id: int
    run_attempt: int
    workflow_id: int
    workflow_path: str
    event: str
    head_repository: str
    head_branch: str
    head_sha: str
    status: str
    conclusion: str
    check_suite_id: int
    html_url: str


@dataclass(frozen=True)
class ProtectedWorkflowStepEvidence:
    """One named step from an attempt-specific Actions job."""

    number: int
    name: str
    status: str
    conclusion: str


@dataclass(frozen=True)
class ProtectedWorkflowCheckEvidence:
    """Exact check-run identity corresponding to an Actions job."""

    check_run_id: int
    name: str
    head_sha: str
    status: str
    conclusion: str
    check_suite_id: int
    app_id: int
    app_slug: str
    details_url: str


@dataclass(frozen=True)
class ProtectedWorkflowJobEvidence:
    """One job from an exact workflow run attempt and its bound check run."""

    job_id: int
    name: str
    run_id: int
    run_attempt: int
    head_sha: str
    status: str
    conclusion: str
    steps: tuple[ProtectedWorkflowStepEvidence, ...]
    check: ProtectedWorkflowCheckEvidence


@dataclass(frozen=True)
class ProtectedWorkflowCheckSuiteEvidence:
    """Check-suite identity binding every job/check to the workflow run."""

    check_suite_id: int
    head_sha: str
    status: str
    conclusion: str
    app_id: int
    app_slug: str
    latest_check_runs_count: int


@dataclass(frozen=True)
class ProtectedGitCommitEvidence:
    """Immutable git tree and ordered parent identities for one commit."""

    sha: str
    tree_sha: str
    parent_shas: tuple[str, ...]


@dataclass(frozen=True)
class ProtectedWorkflowEvidence:
    """Complete evidence for one exact protected review workflow attempt.

    Consumers still bind this record to their independently configured command
    and audit fingerprint.  The record only establishes forge facts; it does
    not itself grant quality-gate authority.
    """

    repository: str
    review: ProtectedReviewEvidence
    workflow: ProtectedWorkflowMetadataEvidence
    workflow_blob_sha: str
    workflow_blob_commit_sha: str
    run: ProtectedWorkflowRunEvidence
    check_suite: ProtectedWorkflowCheckSuiteEvidence
    jobs: tuple[ProtectedWorkflowJobEvidence, ...]
    head_commit: ProtectedGitCommitEvidence
    merge_commit: ProtectedGitCommitEvidence


@dataclass(frozen=True)
class ProtectedWorkflowEvidenceResult:
    """Fail-closed result of protected-workflow evidence collection."""

    disposition: ProtectedWorkflowEvidenceDisposition
    evidence: ProtectedWorkflowEvidence | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if (
            self.disposition is ProtectedWorkflowEvidenceDisposition.COMPLETE
        ) != (self.evidence is not None):
            raise ValueError(
                "only a complete protected-workflow result may carry evidence"
            )


class CapabilityWarning(TypedDict):
    """A structured explanation for a non-fatal unavailable capability."""

    type: str
    message: str
    capability: NotRequired[str]


def unavailable_capability_warning(capability: str, message: str | None = None) -> CapabilityWarning:
    """Build the standard warning emitted when an optional contract feature is absent."""
    return {
        "type": "capability_unavailable",
        "capability": capability,
        "message": message or f"Provider does not support {capability}.",
    }


def normalize_ci_status(value: str | CIStatus | None) -> CIStatus:
    """Convert legacy CI values to the contract's complete state set."""
    try:
        return CIStatus(value or CIStatus.UNKNOWN)
    except ValueError:
        return CIStatus.UNKNOWN

# Branches that must never be auto-deleted as part of post-merge cleanup.
# Even if such a branch is a PR/MR *head* (e.g. a release->main back-merge),
# deleting it would destroy a long-lived integration branch. Long-lived
# prefixes plus the obvious permanent branches.
_PROTECTED_BRANCH_PREFIXES = (
    "release/",
    "hotfix/",
    "gh-readonly-queue/",
    "__",
)
_PROTECTED_BRANCH_NAMES = {"main", "master", "develop", "dev", "trunk"}


def _is_protected_branch(branch: str, default_branch: str = "") -> bool:
    """Return True if ``branch`` must never be auto-deleted by merge cleanup.

    Covers permanent branches (main/master/develop/dev/trunk and the repo's
    default branch) and long-lived prefixes (release/, hotfix/, GitHub's merge
    queue refs, and dolt's ``__`` internal refs).
    """
    if not branch:
        return True
    if branch in _PROTECTED_BRANCH_NAMES:
        return True
    if default_branch and branch == default_branch:
        return True
    return branch.startswith(_PROTECTED_BRANCH_PREFIXES)


# Shared HTTP client — reuses connections across calls (connection pooling).
# Created lazily to avoid import-time side effects.
_http_client: httpx.Client | None = None


def _get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(timeout=15.0, follow_redirects=True)
    return _http_client


@dataclass
class ReviewRequest:
    """A pull request (GitHub) or merge request (GitLab)."""

    id: str  # PR/MR number
    title: str
    url: str
    author: str
    state: str  # open, closed, merged
    source_branch: str
    target_branch: str
    created_at: str
    updated_at: str
    description: str = ""
    labels: list[str] = field(default_factory=list)
    draft: bool = False
    reviewers: list[str] = field(default_factory=list)
    ci_status: CIStatus = CIStatus.UNKNOWN
    ci_warnings: list[CapabilityWarning] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    needs_rebase: bool = False
    has_conflicts: bool = False
    # Provider-normalized merge-queue state. GitHub populates this from
    # ``auto_merge`` and merge-queue membership. GitLab sets it only from
    # authoritative active merge-train membership.
    auto_merge_enabled: bool = False
    mergeable_state: str = ""
    # True when at least one file changed by this review appears in the
    # project's top-N churn-magnet list (oompah-zlz_2-rxwe.2). Populated
    # by the orchestrator's churn-magnet check in _yolo_review_actions_sync.
    churn_magnet: bool = False
    churn_magnet_files: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    # Exact source SHA reported by the forge for this review.  Unlike the
    # current branch tip, this remains authoritative when a reused branch is
    # advanced after an older review merged.
    head_sha: str = ""
    base_sha: str = ""
    # Repository identity is part of an exact review generation too.  Branch
    # names and pull-request numbers alone cannot distinguish an in-repository
    # task branch from a same-named fork branch.
    source_repository: str = ""
    target_repository: str = ""

    def __post_init__(self) -> None:
        """Normalize legacy provider strings at the contract boundary.

        Providers historically assigned raw CI strings to this field. Keeping
        that input accepted avoids a flag day while ensuring consumers always
        receive one of the four documented verdicts.
        """
        self.ci_status = normalize_ci_status(self.ci_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "author": self.author,
            "state": self.state,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "description": self.description,
            "labels": self.labels,
            "draft": self.draft,
            "reviewers": self.reviewers,
            "ci_status": self.ci_status,
            "ci_warnings": self.ci_warnings,
            "additions": self.additions,
            "deletions": self.deletions,
            "needs_rebase": self.needs_rebase,
            "has_conflicts": self.has_conflicts,
            "auto_merge_enabled": self.auto_merge_enabled,
            "mergeable_state": self.mergeable_state,
            "head_sha": self.head_sha,
            "base_sha": self.base_sha,
            "source_repository": self.source_repository,
            "target_repository": self.target_repository,
            "files": self.files,
            "churn_magnet": self.churn_magnet,
            "churn_magnet_files": self.churn_magnet_files,
        }


class SCMProvider(ABC):
    """Forge-neutral source-control contract.

    Required operations return their documented empty/false result on an
    ordinary remote failure; providers must not leak forge-specific HTTP
    failures into workflows. Optional operations have safe defaults and expose
    their absence through :meth:`get_capability_warnings`. Implementations may
    still log transport failures for operators.
    """

    @abstractmethod
    def list_open_reviews(self, repo: str) -> list[ReviewRequest]:
        """List all open pull/merge requests for a repo.

        Args:
            repo: Repository identifier. Format depends on provider:
                  GitHub: "owner/repo"
                  GitLab: "group/project" or project ID
        Returns an empty list when the repository is unavailable or cannot be
        read.  It must not raise for an ordinary provider/API failure.
        """
        ...

    @abstractmethod
    def list_merged_branches(self, repo: str) -> set[str]:
        """Return source branch names of recently merged reviews, or an empty set on failure."""
        ...

    @abstractmethod
    def list_merged_reviews(self, repo: str) -> list[ReviewRequest]:
        """Return recently merged reviews, or an empty list when unavailable."""
        ...

    @abstractmethod
    def find_pr_for_branch(
        self, repo: str, branch_name: str,
    ) -> ReviewRequest | None:
        """Find the most recent PR/MR whose source/head branch matches.

        Returns a ``ReviewRequest`` whose ``state`` field is one of
        ``"open"``, ``"closed"`` (closed without merge), or
        ``"merged"``. Returns ``None`` when no PR/MR for that branch
        exists.

        Returns ``None`` when the review cannot be found or the provider is
        unavailable. Used by the epic auto-close gate (oompah-zlz_2-lvcd) to verify
        a child's branch was merged before closing the parent epic.
        """
        ...

    @abstractmethod
    def get_review(self, repo: str, review_id: str) -> ReviewRequest | None:
        """Get one review, returning ``None`` when it is absent or unreadable."""
        ...

    @abstractmethod
    def create_review(
        self, repo: str, title: str, source_branch: str,
        target_branch: str = "main", description: str = "",
    ) -> ReviewRequest | None:
        """Create a review, returning ``None`` when creation is rejected or unavailable."""
        ...

    @abstractmethod
    def rebase_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        """Rebase a pull/merge request onto its target branch.

        Returns:
            (success, message) tuple.
        """
        ...

    @abstractmethod
    def needs_rebase(self, repo: str, review_id: str) -> bool:
        """Check whether a review needs rebase; return ``False`` when this cannot be determined."""
        ...

    @abstractmethod
    def merge_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        """Merge a pull/merge request.

        Returns:
            (success, message) tuple.
        """
        ...

    def merge_review_exact(
        self,
        repo: str,
        review_id: str,
        expected_head_sha: str,
    ) -> tuple[bool, str]:
        """Merge only when the forge can atomically bind the expected head."""

        return False, "Provider does not support exact-head review merge"

    def enable_auto_merge_exact(
        self,
        repo: str,
        review_id: str,
        expected_head_sha: str,
    ) -> tuple[bool, str]:
        """Enable auto-merge only with an immutable expected-head fence."""

        return False, "Provider does not support exact-head auto-merge"

    @abstractmethod
    def close_review(
        self,
        repo: str,
        review_id: str,
        comment: str = "",
    ) -> tuple[bool, str]:
        """Close a pull/merge request without merging it.

        Args:
            repo: Repository identifier.
            review_id: PR/MR number.
            comment: Optional provider-visible audit comment to add before
                closing. Comment failures should not prevent closure.

        Returns:
            (success, message) tuple.
        """
        ...

    @abstractmethod
    def enable_auto_merge(self, repo: str, review_id: str) -> tuple[bool, str]:
        """Enable auto-merge on a pull/merge request (enqueue mode).

        For GitHub this enables the platform's auto-merge feature so the PR
        will be merged automatically once CI passes and all required reviews
        are satisfied — including when the repo uses a merge queue.

        For GitLab, this falls back to a direct merge (merge trains are a
        separate feature not adopted in this rollout).

        Returns:
            (success, message) tuple.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the provider is authenticated and reachable; never raise for a probe failure."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g. 'github', 'gitlab')."""
        ...

    @abstractmethod
    def get_review_files(self, repo: str, review_id: str) -> list[str]:
        """Return file paths changed by the review.

        Args:
            repo: Repository identifier.
            review_id: PR/MR number.

        Returns:
            List of file paths (e.g. ``["src/foo.py", "README.md"]``), or an
            empty list when the operation is unavailable or fails.
        """
        ...

    @abstractmethod
    def add_review_label(self, repo: str, review_id: str, label: str) -> None:
        """Add a label to a review.

        Args:
            repo: Repository identifier.
            review_id: PR/MR number.
            label: Label name to add.
        Provider/API failures must be logged and treated as non-fatal.
        """
        ...

    @abstractmethod
    def remove_review_label(self, repo: str, review_id: str, label: str) -> None:
        """Remove a label from a review.

        Args:
            repo: Repository identifier.
            review_id: PR/MR number.
            label: Label name to remove.
        Provider/API failures must be logged and treated as non-fatal.
        """
        ...

    def get_pr_commits(self, repo: str, review_id: str) -> list[str]:
        """Return the commit SHAs included in a pull/merge request.

        Returns commits in chronological order (oldest first) as full
        40-character SHA strings.  Returns an empty list when the PR/MR
        cannot be found, the provider API returns an error, or the
        provider does not support this operation.

        The default implementation returns an empty list so that
        sub-classes that have not yet implemented this method degrade
        gracefully rather than raising.

        Args:
            repo: Repository identifier (e.g. ``"owner/name"``).
            review_id: PR/MR number as a string.

        Returns:
            List of commit SHAs (full length), oldest first.  May be
            empty when the PR has no commits or on API error.
        """
        return []

    def get_review_commits(self, repo: str, review_id: str) -> list[str]:
        """Return review commit SHAs in chronological order.

        This is the forge-neutral spelling for shared workflow consumers.
        It delegates to ``get_pr_commits`` as a compatibility bridge for
        existing providers until they can rename their implementation.
        """
        return self.get_pr_commits(repo, review_id)

    def get_review_comments(self, repo: str, review_id: str) -> list[dict[str, Any]]:
        """Return normalized review comments, or an empty list if unavailable.

        Comments are optional because forge APIs expose different comment
        models. Callers must use :meth:`get_capability_warnings` when they need
        to distinguish an empty discussion from an unavailable feature.
        """
        return []

    def observe_branch_landing(
        self,
        repo: str,
        source_branch: str,
        target_branch: str,
    ) -> bool | None:
        """Observe whether an exact source branch landed on an exact target.

        ``True`` and ``False`` are authoritative provider observations;
        ``None`` means the provider cannot distinguish absence from an API or
        transport failure.  The default deliberately fails closed because the
        legacy review-list methods collapse those cases into empty results.
        """
        return None

    def get_capability_warnings(self, capabilities: set[str]) -> list[CapabilityWarning]:
        """Report unsupported optional capabilities without raising exceptions.

        The base implementation supports the contract's required operations
        and reports optional review comments as unavailable. Providers should
        override this when their supported feature set differs.
        """
        return [
            unavailable_capability_warning(capability)
            for capability in sorted(capabilities & {"review_comments"})
        ]

    def get_branch_head_sha(self, repo: str, branch: str) -> str | None:
        """Return the HEAD commit SHA for *branch*, or ``None``.

        Used by post-merge release CI monitoring to identify the commit to
        check CI status against.  Returns ``None`` when the branch does not
        exist, the provider API is unavailable, or the provider subclass has
        not implemented this method.

        The default implementation returns ``None`` so that sub-classes that
        have not yet implemented this method degrade gracefully.

        Args:
            repo: Repository identifier (e.g. ``"owner/name"``).
            branch: Branch name (without ``refs/heads/`` prefix).

        Returns:
            Full 40-character SHA string, or ``None``.
        """
        return None

    def get_branch_ci_status(self, repo: str, branch: str) -> CIStatus:
        """Return the CI status for the HEAD commit of *branch*.

        Combines :meth:`get_branch_head_sha` with
        :meth:`get_ci_status_for_sha` to produce a single CI verdict for a
        branch tip.  Returns ``unknown`` when the branch HEAD SHA cannot be
        determined or CI status cannot be fetched.

        The default implementation calls
        :meth:`get_branch_head_sha` and then :meth:`get_ci_status_for_sha`.
        Sub-classes may override for efficiency.

        Args:
            repo: Repository identifier (e.g. ``"owner/name"``).
            branch: Branch name (without ``refs/heads/`` prefix).

        Returns:
            One of :class:`CIStatus` (including ``unknown``).
        """
        sha = self.get_branch_head_sha(repo, branch)
        if not sha:
            return CIStatus.UNKNOWN
        return normalize_ci_status(self.get_ci_status_for_sha(repo, sha))

    def get_ci_status_for_sha(self, repo: str, sha: str) -> CIStatus:
        """Return the CI status for a specific commit SHA.

        The default implementation returns ``unknown`` so that sub-classes that
        have not yet implemented this method degrade gracefully.

        Args:
            repo: Repository identifier.
            sha: Full 40-character commit SHA.

        Returns:
            One of :class:`CIStatus` (including ``unknown``).
        """
        return CIStatus.UNKNOWN

    def collect_protected_workflow_evidence(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
    ) -> ProtectedWorkflowEvidenceResult:
        """Collect immutable exact-run evidence for a protected workflow.

        This contract is intentionally independent of aggregate CI status.
        Providers that cannot prove every requested identity return an
        explicit unavailable result; they must never synthesize authority from
        :meth:`get_ci_status_for_sha` or an empty legacy response.
        """
        return ProtectedWorkflowEvidenceResult(
            disposition=ProtectedWorkflowEvidenceDisposition.UNAVAILABLE,
            reason=(
                f"{self.provider_name()} does not expose protected-workflow "
                "evidence"
            ),
        )


def _resolve_gh_token() -> str | None:
    """Resolve GitHub token from environment or gh CLI config."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        register_secret(token)
        return token
    try:
        r = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            token = r.stdout.strip()
            register_secret(token)
            return token
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _resolve_gitlab_token(hostname: str = "gitlab.com") -> str | None:
    """Resolve GitLab token from environment or glab CLI config."""
    token = os.environ.get("GITLAB_TOKEN") or os.environ.get("GITLAB_API_TOKEN")
    if token:
        register_secret(token)
        return token
    try:
        r = subprocess.run(
            ["glab", "auth", "token", "--hostname", hostname],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            token = r.stdout.strip()
            register_secret(token)
            return token
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _read_pr_detail_cache_ttl() -> float:
    """Read OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS env var, default 60s.

    The TTL bounds how long a cache entry can survive without being
    re-fetched, even if its (head_sha, updated_at) key still matches
    the LIST view. See ``GitHubProvider._pr_detail_cache`` for the
    rationale (oompah-zlz_2-1of).

    Non-positive or unparseable values fall back to the 60s default.
    """
    raw = os.environ.get("OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS")
    if raw is None:
        return 60.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 60.0
    if value <= 0:
        return 60.0
    return value


def _read_ci_registration_grace_seconds() -> float:
    """Read the bounded wait for CI checks to register on a PR head.

    GitHub may return successful, empty status and check-run responses for
    several seconds after a PR is created or synchronized.  The grace period
    lets :meth:`GitHubProvider.list_open_reviews` distinguish that transient
    state from a PR whose exact head SHA genuinely has no CI.
    """
    raw = os.environ.get("OOMPAH_CI_REGISTRATION_GRACE_SECONDS")
    if raw is None:
        return 60.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 60.0
    if value <= 0:
        return 60.0
    return value


class _ProtectedEvidenceUnavailable(RuntimeError):
    """The forge could not provide a requested evidence component."""


class _ProtectedEvidencePartial(RuntimeError):
    """The forge response was present but incomplete or inconsistent."""


def _is_full_git_sha(value: Any) -> bool:
    """Return whether *value* is one lower/upper-case 40-digit SHA-1."""
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _positive_int(value: Any) -> int | None:
    """Return a positive integer without accepting booleans or coercions."""
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _positive_int_string(value: Any) -> int | None:
    """Return a positive base-10 integer represented canonically as text."""
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        return None
    parsed = int(value)
    if parsed <= 0 or str(parsed) != value:
        return None
    return parsed


class GitHubProvider(SCMProvider):
    """GitHub implementation using the REST API via httpx."""

    # Class-level cache of per-PR DETAIL fetch results (oompah-zlz_2-aza).
    #
    # The orchestrator's review_check tick creates a fresh ``GitHubProvider``
    # for every project on every tick (see ``_fetch_all_reviews`` in
    # ``orchestrator.py``), so a per-instance cache would be cleared every
    # poll cycle and never produce a hit. Sharing the cache at the class
    # level lets us amortise the per-PR DETAIL fetch across ticks while
    # still being correctly invalidated whenever GitHub reports a new
    # ``head.sha`` or ``updated_at`` on the cheap LIST endpoint.
    #
    # Key   : (repo_full_name, pr_num_str)
    # Value : (head_sha, updated_at, mergeable, mergeable_state_raw,
    #          entry_time_monotonic)
    #
    # ``mergeable`` is True/False/None (None = GitHub still computing).
    # ``mergeable_state_raw`` is GitHub's lower-case string ("clean",
    # "dirty", "behind", "blocked", "unknown", or "").
    # ``entry_time_monotonic`` is ``time.monotonic()`` at write time and
    # is consulted against ``_PR_DETAIL_CACHE_TTL_SECONDS`` for a TTL
    # fallback (oompah-zlz_2-1of). The TTL exists because GitHub does
    # NOT always bump ``updated_at`` when it asynchronously recomputes
    # mergeable_state after a base-branch commit lands — a cached
    # "clean" entry could otherwise survive forever even though the PR
    # has gone DIRTY.
    _pr_detail_cache: dict[
        tuple[str, str], tuple[str, str, bool | None, str, float]
    ] = {}
    _pr_detail_cache_lock: threading.Lock = threading.Lock()
    # TTL fallback for cache freshness. Read once at class-definition
    # time; tests override by assigning to the class attribute.
    # Configurable via OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS env var.
    _PR_DETAIL_CACHE_TTL_SECONDS: float = _read_pr_detail_cache_ttl()

    # Bounded empty-CI observations keyed by (repo, PR number).
    #
    # Value: (head_sha, first_empty_observation_monotonic)
    #
    # The orchestrator creates a new provider each tick, so this state must be
    # shared across instances.  A changed head SHA replaces the entry and
    # starts a fresh registration window, which prevents a synchronized PR
    # from inheriting the previous head's no-CI verdict.  If the exact SHA
    # remains check-free for the full grace period it is positively classified
    # as no-CI and may retain normal YOLO behavior.  (OOMPAH-449)
    _ci_head_observations: dict[tuple[str, str], tuple[str, float]] = {}
    _ci_head_observations_lock: threading.Lock = threading.Lock()
    _CI_REGISTRATION_GRACE_SECONDS: float = (
        _read_ci_registration_grace_seconds()
    )
    _EMPTY_CHECK_SET = "__empty_check_set__"

    def __init__(self, access_token: str | None = None) -> None:
        # When an explicit token is provided (e.g. from project config), skip
        # the env/CLI fallback so per-project auth wins over the global default.
        self._token: str | None = access_token
        register_secret(access_token)
        self._token_resolved = bool(access_token)
        # Capacity acquisition needs to distinguish a confirmed empty forge
        # listing from the provider's historical empty-on-error fallback.
        self.last_open_reviews_fetch_ok = True
        # Historical review lookup must likewise distinguish a confirmed 404
        # from a transport/server failure that legacy callers receive as None.
        self.last_review_fetch_ok = True

    def _headers(self) -> dict[str, str]:
        if not self._token_resolved:
            self._token = _resolve_gh_token()
            self._token_resolved = True
        h: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _api(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"https://api.github.com{path}"
        return _get_http_client().request(method, url, headers=self._headers(), **kwargs)

    def _protected_evidence_json(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        """Fetch one evidence endpoint without legacy empty-on-error semantics."""
        try:
            response = self._api("GET", path, params=dict(params or {}))
        except httpx.HTTPError as exc:
            raise _ProtectedEvidenceUnavailable(
                f"GitHub evidence request failed for {path}: {type(exc).__name__}"
            ) from exc
        if response.status_code != 200:
            raise _ProtectedEvidenceUnavailable(
                f"GitHub evidence request for {path} returned HTTP "
                f"{response.status_code}"
            )
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise _ProtectedEvidenceUnavailable(
                f"GitHub evidence response for {path} was not JSON"
            ) from exc

    def _protected_evidence_list_pages(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> list[Any]:
        """Exhaust a GitHub list endpoint, rejecting truncated pagination."""
        collected: list[Any] = []
        base_params = dict(params or {})
        per_page = 100
        for page in range(1, 101):
            page_params = {**base_params, "per_page": per_page, "page": page}
            try:
                payload = self._protected_evidence_json(path, params=page_params)
            except _ProtectedEvidenceUnavailable as exc:
                if page > 1:
                    raise _ProtectedEvidencePartial(
                        f"GitHub pagination became unavailable for {path} "
                        f"at page {page}"
                    ) from exc
                raise
            if not isinstance(payload, list):
                raise _ProtectedEvidencePartial(
                    f"GitHub evidence response for {path} was not a list"
                )
            collected.extend(payload)
            if len(payload) < per_page:
                return collected
        raise _ProtectedEvidencePartial(
            f"GitHub evidence pagination for {path} exceeded 100 pages"
        )

    def _protected_evidence_counted_pages(
        self,
        path: str,
        *,
        item_field: str,
        params: Mapping[str, Any] | None = None,
    ) -> list[Any]:
        """Exhaust an Actions endpoint whose payload carries ``total_count``."""
        collected: list[Any] = []
        base_params = dict(params or {})
        expected_total: int | None = None
        per_page = 100
        for page in range(1, 101):
            page_params = {**base_params, "per_page": per_page, "page": page}
            try:
                payload = self._protected_evidence_json(path, params=page_params)
            except _ProtectedEvidenceUnavailable as exc:
                if page > 1:
                    raise _ProtectedEvidencePartial(
                        f"GitHub pagination became unavailable for {path} "
                        f"at page {page}"
                    ) from exc
                raise
            if not isinstance(payload, Mapping):
                raise _ProtectedEvidencePartial(
                    f"GitHub evidence response for {path} was not an object"
                )
            total = payload.get("total_count")
            if (
                not isinstance(total, int)
                or isinstance(total, bool)
                or total < 0
            ):
                raise _ProtectedEvidencePartial(
                    f"GitHub evidence response for {path} has invalid total_count"
                )
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                raise _ProtectedEvidencePartial(
                    f"GitHub evidence total_count changed while paging {path}"
                )
            items = payload.get(item_field)
            if not isinstance(items, list):
                raise _ProtectedEvidencePartial(
                    f"GitHub evidence response for {path} has invalid {item_field}"
                )
            if len(items) > per_page:
                raise _ProtectedEvidencePartial(
                    f"GitHub evidence response for {path} exceeded page size"
                )
            collected.extend(items)
            if len(collected) == expected_total:
                return collected
            if len(collected) > expected_total or not items:
                raise _ProtectedEvidencePartial(
                    f"GitHub evidence pagination for {path} was incomplete"
                )
        raise _ProtectedEvidencePartial(
            f"GitHub evidence pagination for {path} exceeded 100 pages"
        )

    @staticmethod
    def _protected_commit_evidence(payload: Any) -> ProtectedGitCommitEvidence:
        if not isinstance(payload, Mapping):
            raise _ProtectedEvidencePartial("GitHub commit evidence was not an object")
        sha = payload.get("sha")
        tree = payload.get("tree")
        parents = payload.get("parents")
        if (
            not _is_full_git_sha(sha)
            or not isinstance(tree, Mapping)
            or not _is_full_git_sha(tree.get("sha"))
            or not isinstance(parents, list)
        ):
            raise _ProtectedEvidencePartial("GitHub commit evidence was malformed")
        parent_shas: list[str] = []
        for parent in parents:
            if not isinstance(parent, Mapping) or not _is_full_git_sha(
                parent.get("sha")
            ):
                raise _ProtectedEvidencePartial(
                    "GitHub commit parent evidence was malformed"
                )
            parent_shas.append(str(parent["sha"]))
        if len(parent_shas) != len(set(parent_shas)):
            raise _ProtectedEvidencePartial(
                "GitHub commit parent evidence contained duplicates"
            )
        return ProtectedGitCommitEvidence(
            sha=str(sha),
            tree_sha=str(tree["sha"]),
            parent_shas=tuple(parent_shas),
        )

    @staticmethod
    def _protected_review_association_matches(
        association: Any,
        *,
        review_id: str,
        source_branch: str,
        head_sha: str,
        target_branch: str,
    ) -> bool:
        if not isinstance(association, Mapping):
            return False
        head = association.get("head")
        base = association.get("base")
        return (
            str(association.get("number") or "") == review_id
            and isinstance(head, Mapping)
            and head.get("ref") == source_branch
            and head.get("sha") == head_sha
            and isinstance(base, Mapping)
            and base.get("ref") == target_branch
        )

    def collect_protected_workflow_evidence(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
    ) -> ProtectedWorkflowEvidenceResult:
        """Collect strict GitHub evidence for one protected PR workflow.

        Collection starts from GitHub's commit-associated pull requests so an
        active terminal-audit attempt needs only its already-bound source
        branch, selected SHA, and target branch.  Every subsequent object is
        checked against that identity.  HTTP/permission failures are reported
        as unavailable, while structurally incomplete, duplicated, or
        mismatched observations are partial.  Neither disposition carries
        evidence and no aggregate :class:`CIStatus` method participates.
        """
        try:
            evidence = self._collect_protected_workflow_evidence(repo, request)
        except _ProtectedEvidenceUnavailable as exc:
            return ProtectedWorkflowEvidenceResult(
                disposition=ProtectedWorkflowEvidenceDisposition.UNAVAILABLE,
                reason=str(exc),
            )
        except _ProtectedEvidencePartial as exc:
            return ProtectedWorkflowEvidenceResult(
                disposition=ProtectedWorkflowEvidenceDisposition.PARTIAL,
                reason=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary is fail-closed
            logger.exception(
                "Unexpected protected-workflow evidence failure for %s", repo
            )
            return ProtectedWorkflowEvidenceResult(
                disposition=ProtectedWorkflowEvidenceDisposition.UNAVAILABLE,
                reason=(
                    "unexpected protected-workflow evidence failure: "
                    f"{type(exc).__name__}"
                ),
            )
        return ProtectedWorkflowEvidenceResult(
            disposition=ProtectedWorkflowEvidenceDisposition.COMPLETE,
            evidence=evidence,
        )

    def _collect_protected_workflow_evidence(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
    ) -> ProtectedWorkflowEvidence:
        """Implementation for :meth:`collect_protected_workflow_evidence`."""
        self._validate_protected_evidence_request(repo, request)
        review = self._collect_protected_review_evidence(repo, request)
        workflow = self._collect_protected_workflow_metadata(repo, request)
        head_commit = self._protected_commit_evidence(
            self._protected_evidence_json(
                f"/repos/{repo}/git/commits/{request.head_sha}"
            )
        )
        merge_commit = self._protected_commit_evidence(
            self._protected_evidence_json(
                f"/repos/{repo}/git/commits/{review.merge_sha}"
            )
        )
        if head_commit.sha != request.head_sha:
            raise _ProtectedEvidencePartial("GitHub returned the wrong head commit")
        if merge_commit.sha != review.merge_sha:
            raise _ProtectedEvidencePartial("GitHub returned the wrong merge commit")
        workflow_blob_sha = self._collect_protected_workflow_blob(
            repo,
            request,
            review.merge_sha,
        )
        run, run_payload = self._collect_protected_workflow_run(
            repo,
            request,
            review,
            workflow,
        )
        check_suite = self._collect_protected_check_suite(
            repo,
            request,
            review,
            run,
        )
        jobs = self._collect_protected_workflow_jobs(
            repo,
            request,
            review,
            workflow,
            run,
            run_payload,
        )
        if check_suite.latest_check_runs_count != len(jobs):
            raise _ProtectedEvidencePartial(
                "GitHub check-suite count did not match attempt-specific jobs"
            )
        if any(job.check.app_slug != check_suite.app_slug for job in jobs):
            raise _ProtectedEvidencePartial(
                "GitHub check-run apps did not match the check-suite app"
            )
        return ProtectedWorkflowEvidence(
            repository=repo,
            review=review,
            workflow=workflow,
            workflow_blob_sha=workflow_blob_sha,
            workflow_blob_commit_sha=review.merge_sha,
            run=run,
            check_suite=check_suite,
            jobs=jobs,
            head_commit=head_commit,
            merge_commit=merge_commit,
        )

    @staticmethod
    def _validate_protected_evidence_request(
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
    ) -> None:
        string_fields = (
            repo,
            request.source_repository,
            request.source_branch,
            request.target_branch,
            request.workflow_path,
        )
        if any(not isinstance(value, str) or not value.strip() for value in string_fields):
            raise _ProtectedEvidencePartial(
                "protected-workflow evidence identity contains a blank field"
            )
        if not _is_full_git_sha(request.head_sha):
            raise _ProtectedEvidencePartial(
                "protected-workflow evidence head SHA is invalid"
            )
        if not _is_full_git_sha(request.workflow_blob_sha):
            raise _ProtectedEvidencePartial(
                "protected-workflow evidence workflow blob SHA is invalid"
            )
        if _positive_int(request.workflow_id) is None:
            raise _ProtectedEvidencePartial(
                "protected-workflow evidence workflow ID is invalid"
            )
        if _positive_int(request.app_id) is None:
            raise _ProtectedEvidencePartial(
                "protected-workflow evidence app ID is invalid"
            )
        if request.event != "pull_request":
            raise _ProtectedEvidencePartial(
                "protected-workflow evidence event must be pull_request"
            )
        if (
            not request.workflow_path.startswith(".github/workflows/")
            or ".." in request.workflow_path.split("/")
            or "\\" in request.workflow_path
        ):
            raise _ProtectedEvidencePartial(
                "protected-workflow evidence workflow path is invalid"
            )
        if (
            not request.required_job_names
            or any(not name for name in request.required_job_names)
            or len(set(request.required_job_names))
            != len(request.required_job_names)
        ):
            raise _ProtectedEvidencePartial(
                "protected-workflow evidence required jobs are empty or duplicated"
            )
        if (
            any(not name for name in request.required_step_names)
            or len(set(request.required_step_names))
            != len(request.required_step_names)
        ):
            raise _ProtectedEvidencePartial(
                "protected-workflow evidence required steps are invalid"
            )
        if request.review_id is not None and _positive_int_string(
            request.review_id
        ) is None:
            raise _ProtectedEvidencePartial(
                "protected-workflow evidence review ID is invalid"
            )

    def _collect_protected_review_evidence(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
    ) -> ProtectedReviewEvidence:
        associated = self._protected_evidence_list_pages(
            f"/repos/{repo}/commits/{request.head_sha}/pulls"
        )
        matching: list[Mapping[str, Any]] = []
        for candidate in associated:
            if not isinstance(candidate, Mapping):
                raise _ProtectedEvidencePartial(
                    "GitHub commit-associated review was malformed"
                )
            review_id = str(candidate.get("number") or "")
            if request.review_id is not None and review_id != request.review_id:
                continue
            head = candidate.get("head")
            base = candidate.get("base")
            head_repo = head.get("repo") if isinstance(head, Mapping) else None
            base_repo = base.get("repo") if isinstance(base, Mapping) else None
            if (
                candidate.get("state") == "closed"
                and isinstance(candidate.get("merged_at"), str)
                and bool(candidate.get("merged_at"))
                and isinstance(head, Mapping)
                and isinstance(head_repo, Mapping)
                and head_repo.get("full_name") == request.source_repository
                and head.get("ref") == request.source_branch
                and head.get("sha") == request.head_sha
                and isinstance(base, Mapping)
                and isinstance(base_repo, Mapping)
                and base_repo.get("full_name") == repo
                and base.get("ref") == request.target_branch
            ):
                matching.append(candidate)
        if len(matching) != 1:
            raise _ProtectedEvidencePartial(
                "GitHub did not return one unique merged review for the exact "
                "source/head/target identity"
            )
        discovered_id = str(matching[0].get("number") or "")
        if _positive_int_string(discovered_id) is None:
            raise _ProtectedEvidencePartial("GitHub review ID was malformed")
        detail = self._protected_evidence_json(
            f"/repos/{repo}/pulls/{discovered_id}"
        )
        if not isinstance(detail, Mapping):
            raise _ProtectedEvidencePartial("GitHub review detail was malformed")
        head = detail.get("head")
        base = detail.get("base")
        head_repo = head.get("repo") if isinstance(head, Mapping) else None
        base_repo = base.get("repo") if isinstance(base, Mapping) else None
        merge_sha = detail.get("merge_commit_sha")
        merged_at = detail.get("merged_at")
        if (
            str(detail.get("number") or "") != discovered_id
            or detail.get("state") != "closed"
            or detail.get("merged") is not True
            or not isinstance(merged_at, str)
            or not merged_at
            or not _is_full_git_sha(merge_sha)
            or not isinstance(head, Mapping)
            or not isinstance(head_repo, Mapping)
            or head_repo.get("full_name") != request.source_repository
            or head.get("ref") != request.source_branch
            or head.get("sha") != request.head_sha
            or not isinstance(base, Mapping)
            or not isinstance(base_repo, Mapping)
            or base_repo.get("full_name") != repo
            or base.get("ref") != request.target_branch
            or not _is_full_git_sha(base.get("sha"))
        ):
            raise _ProtectedEvidencePartial(
                "GitHub review detail did not match the exact merged identity"
            )
        return ProtectedReviewEvidence(
            review_id=discovered_id,
            state="merged",
            source_repository=request.source_repository,
            source_branch=request.source_branch,
            head_sha=request.head_sha,
            target_repository=repo,
            target_branch=request.target_branch,
            base_sha=str(base["sha"]),
            merge_sha=str(merge_sha),
            merged_at=merged_at,
        )

    def _collect_protected_workflow_metadata(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
    ) -> ProtectedWorkflowMetadataEvidence:
        payload = self._protected_evidence_json(
            f"/repos/{repo}/actions/workflows/{request.workflow_id}"
        )
        if not isinstance(payload, Mapping):
            raise _ProtectedEvidencePartial("GitHub workflow metadata was malformed")
        workflow_id = _positive_int(payload.get("id"))
        if (
            workflow_id != request.workflow_id
            or payload.get("path") != request.workflow_path
            or payload.get("state") != "active"
            or not isinstance(payload.get("name"), str)
            or not payload.get("name")
            or not isinstance(payload.get("node_id"), str)
            or not payload.get("node_id")
        ):
            raise _ProtectedEvidencePartial(
                "GitHub workflow metadata did not match the pinned identity"
            )
        return ProtectedWorkflowMetadataEvidence(
            workflow_id=workflow_id,
            name=str(payload["name"]),
            path=request.workflow_path,
            state="active",
            node_id=str(payload["node_id"]),
        )

    def _collect_protected_workflow_blob(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
        merge_sha: str,
    ) -> str:
        encoded_path = urllib.parse.quote(request.workflow_path, safe="/")
        payload = self._protected_evidence_json(
            f"/repos/{repo}/contents/{encoded_path}",
            params={"ref": merge_sha},
        )
        if (
            not isinstance(payload, Mapping)
            or payload.get("type") != "file"
            or payload.get("path") != request.workflow_path
            or payload.get("sha") != request.workflow_blob_sha
            or not _is_full_git_sha(payload.get("sha"))
        ):
            raise _ProtectedEvidencePartial(
                "GitHub workflow blob did not match the pinned merge revision"
            )
        return str(payload["sha"])

    def _collect_protected_workflow_run(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
        review: ProtectedReviewEvidence,
        workflow: ProtectedWorkflowMetadataEvidence,
    ) -> tuple[ProtectedWorkflowRunEvidence, Mapping[str, Any]]:
        path = (
            f"/repos/{repo}/actions/workflows/{request.workflow_id}/runs"
        )
        runs = self._protected_evidence_counted_pages(
            path,
            item_field="workflow_runs",
            params={"event": request.event, "head_sha": request.head_sha},
        )
        if len(runs) != 1:
            raise _ProtectedEvidencePartial(
                "GitHub did not return one unique workflow run for the exact head"
            )
        listing_run = self._parse_protected_workflow_run(
            runs[0],
            repo=repo,
            request=request,
            review=review,
            workflow=workflow,
        )
        detail = self._protected_evidence_json(
            f"/repos/{repo}/actions/runs/{listing_run.run_id}"
        )
        detail_run = self._parse_protected_workflow_run(
            detail,
            repo=repo,
            request=request,
            review=review,
            workflow=workflow,
        )
        if detail_run != listing_run:
            raise _ProtectedEvidencePartial(
                "GitHub workflow-run detail changed from the paginated listing"
            )
        if not isinstance(detail, Mapping):
            raise _ProtectedEvidencePartial("GitHub workflow-run detail was malformed")
        return detail_run, detail

    def _parse_protected_workflow_run(
        self,
        payload: Any,
        *,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
        review: ProtectedReviewEvidence,
        workflow: ProtectedWorkflowMetadataEvidence,
    ) -> ProtectedWorkflowRunEvidence:
        if not isinstance(payload, Mapping):
            raise _ProtectedEvidencePartial("GitHub workflow run was malformed")
        run_id = _positive_int(payload.get("id"))
        run_attempt = _positive_int(payload.get("run_attempt"))
        workflow_id = _positive_int(payload.get("workflow_id"))
        check_suite_id = _positive_int(payload.get("check_suite_id"))
        repository = payload.get("repository")
        head_repository = payload.get("head_repository")
        associations = payload.get("pull_requests")
        if not isinstance(associations, list):
            raise _ProtectedEvidencePartial(
                "GitHub workflow run omitted pull-request associations"
            )
        matching_associations = [
            association
            for association in associations
            if self._protected_review_association_matches(
                association,
                review_id=review.review_id,
                source_branch=request.source_branch,
                head_sha=request.head_sha,
                target_branch=request.target_branch,
            )
        ]
        # GitHub legitimately empties these advisory associations after some
        # reviews merge.  The run remains strongly bound by the workflow
        # endpoint's exact head filter plus repository/branch/SHA fields.  If
        # GitHub does supply associations, however, accept only one exact one.
        if associations and (
            len(associations) != 1 or len(matching_associations) != 1
        ):
            raise _ProtectedEvidencePartial(
                "GitHub workflow run was not uniquely bound to the merged review"
            )
        if (
            run_id is None
            or run_attempt is None
            or workflow_id != request.workflow_id
            or check_suite_id is None
            or payload.get("path") != request.workflow_path
            or payload.get("event") != request.event
            or payload.get("head_branch") != request.source_branch
            or payload.get("head_sha") != request.head_sha
            or payload.get("status") != "completed"
            or payload.get("conclusion") != "success"
            or not isinstance(repository, Mapping)
            or repository.get("full_name") != repo
            or not isinstance(head_repository, Mapping)
            or head_repository.get("full_name") != request.source_repository
            or not isinstance(payload.get("html_url"), str)
            or not payload.get("html_url")
        ):
            raise _ProtectedEvidencePartial(
                "GitHub workflow run did not match the pinned successful identity"
            )
        return ProtectedWorkflowRunEvidence(
            run_id=run_id,
            run_attempt=run_attempt,
            workflow_id=workflow_id,
            workflow_path=workflow.path,
            event=request.event,
            head_repository=request.source_repository,
            head_branch=request.source_branch,
            head_sha=request.head_sha,
            status="completed",
            conclusion="success",
            check_suite_id=check_suite_id,
            html_url=str(payload["html_url"]),
        )

    def _collect_protected_check_suite(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
        review: ProtectedReviewEvidence,
        run: ProtectedWorkflowRunEvidence,
    ) -> ProtectedWorkflowCheckSuiteEvidence:
        payload = self._protected_evidence_json(
            f"/repos/{repo}/check-suites/{run.check_suite_id}"
        )
        if not isinstance(payload, Mapping):
            raise _ProtectedEvidencePartial("GitHub check suite was malformed")
        app = payload.get("app")
        app_id = app.get("id") if isinstance(app, Mapping) else None
        app_slug = app.get("slug") if isinstance(app, Mapping) else None
        count = payload.get("latest_check_runs_count")
        if (
            _positive_int(payload.get("id")) != run.check_suite_id
            or payload.get("head_sha") != request.head_sha
            or payload.get("status") != "completed"
            or payload.get("conclusion") != "success"
            or _positive_int(app_id) != request.app_id
            or not isinstance(app_slug, str)
            or not app_slug
            or _positive_int(count) is None
        ):
            raise _ProtectedEvidencePartial(
                "GitHub check suite did not match the pinned successful identity"
            )
        associations = payload.get("pull_requests")
        if not isinstance(associations, list):
            raise _ProtectedEvidencePartial(
                "GitHub check suite omitted pull-request associations"
            )
        matching_associations = [
            association
            for association in associations
            if self._protected_review_association_matches(
                association,
                review_id=review.review_id,
                source_branch=request.source_branch,
                head_sha=request.head_sha,
                target_branch=request.target_branch,
            )
        ]
        if associations and (
            len(associations) != 1 or len(matching_associations) != 1
        ):
            raise _ProtectedEvidencePartial(
                "GitHub check suite was not uniquely bound to the merged review"
            )
        return ProtectedWorkflowCheckSuiteEvidence(
            check_suite_id=run.check_suite_id,
            head_sha=request.head_sha,
            status="completed",
            conclusion="success",
            app_id=request.app_id,
            app_slug=app_slug,
            latest_check_runs_count=int(count),
        )

    def _collect_protected_workflow_jobs(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
        review: ProtectedReviewEvidence,
        workflow: ProtectedWorkflowMetadataEvidence,
        run: ProtectedWorkflowRunEvidence,
        run_payload: Mapping[str, Any],
    ) -> tuple[ProtectedWorkflowJobEvidence, ...]:
        jobs_url = run_payload.get("jobs_url")
        expected_jobs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run.run_id}/jobs"
        if jobs_url != expected_jobs_url:
            raise _ProtectedEvidencePartial(
                "GitHub workflow run exposed an unexpected jobs URL"
            )
        path = (
            f"/repos/{repo}/actions/runs/{run.run_id}/attempts/"
            f"{run.run_attempt}/jobs"
        )
        payloads = self._protected_evidence_counted_pages(
            path,
            item_field="jobs",
        )
        if not payloads:
            raise _ProtectedEvidencePartial(
                "GitHub workflow run returned an empty attempt-specific job set"
            )
        jobs = tuple(
            sorted(
                (
                    self._collect_protected_workflow_job(
                        repo,
                        request,
                        review,
                        workflow,
                        run,
                        payload,
                    )
                    for payload in payloads
                ),
                key=lambda job: (job.name, job.job_id),
            )
        )
        job_ids = [job.job_id for job in jobs]
        job_names = [job.name for job in jobs]
        if len(job_ids) != len(set(job_ids)) or len(job_names) != len(set(job_names)):
            raise _ProtectedEvidencePartial(
                "GitHub workflow job evidence contained duplicates"
            )
        if set(job_names) != set(request.required_job_names) or len(job_names) != len(
            request.required_job_names
        ):
            raise _ProtectedEvidencePartial(
                "GitHub workflow jobs did not exactly match the required job set"
            )
        check_ids = [job.check.check_run_id for job in jobs]
        if len(check_ids) != len(set(check_ids)):
            raise _ProtectedEvidencePartial(
                "GitHub workflow check evidence contained duplicates"
            )
        return jobs

    def _collect_protected_workflow_job(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
        review: ProtectedReviewEvidence,
        workflow: ProtectedWorkflowMetadataEvidence,
        run: ProtectedWorkflowRunEvidence,
        payload: Any,
    ) -> ProtectedWorkflowJobEvidence:
        if not isinstance(payload, Mapping):
            raise _ProtectedEvidencePartial("GitHub workflow job was malformed")
        job_id = _positive_int(payload.get("id"))
        name = payload.get("name")
        if (
            job_id is None
            or not isinstance(name, str)
            or not name
            or _positive_int(payload.get("run_id")) != run.run_id
            or _positive_int(payload.get("run_attempt")) != run.run_attempt
            or payload.get("head_sha") != request.head_sha
            or payload.get("workflow_name") != workflow.name
            or payload.get("status") != "completed"
            or payload.get("conclusion") != "success"
        ):
            raise _ProtectedEvidencePartial(
                "GitHub workflow job did not match the exact successful attempt"
            )
        raw_steps = payload.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise _ProtectedEvidencePartial(
                "GitHub workflow job returned empty or malformed steps"
            )
        steps: list[ProtectedWorkflowStepEvidence] = []
        for raw_step in raw_steps:
            if not isinstance(raw_step, Mapping):
                raise _ProtectedEvidencePartial("GitHub workflow step was malformed")
            number = _positive_int(raw_step.get("number"))
            step_name = raw_step.get("name")
            status = raw_step.get("status")
            conclusion = raw_step.get("conclusion")
            if (
                number is None
                or not isinstance(step_name, str)
                or not step_name
                or not isinstance(status, str)
                or not status
                or not isinstance(conclusion, str)
                or not conclusion
            ):
                raise _ProtectedEvidencePartial("GitHub workflow step was malformed")
            steps.append(
                ProtectedWorkflowStepEvidence(
                    number=number,
                    name=step_name,
                    status=status,
                    conclusion=conclusion,
                )
            )
        step_numbers = [step.number for step in steps]
        step_names = [step.name for step in steps]
        if (
            len(step_numbers) != len(set(step_numbers))
            or len(step_names) != len(set(step_names))
        ):
            raise _ProtectedEvidencePartial(
                "GitHub workflow step evidence contained duplicates"
            )
        for required_name in request.required_step_names:
            required = [step for step in steps if step.name == required_name]
            if (
                len(required) != 1
                or required[0].status != "completed"
                or required[0].conclusion != "success"
            ):
                raise _ProtectedEvidencePartial(
                    "GitHub workflow required step was missing or unsuccessful"
                )
        check_run_url = payload.get("check_run_url")
        if not isinstance(check_run_url, str):
            raise _ProtectedEvidencePartial(
                "GitHub workflow job omitted its check-run URL"
            )
        parsed_check_url = urllib.parse.urlparse(check_run_url)
        expected_check_path = f"/repos/{repo}/check-runs/{job_id}"
        if (
            parsed_check_url.scheme != "https"
            or parsed_check_url.netloc != "api.github.com"
            or parsed_check_url.path != expected_check_path
            or parsed_check_url.query
            or parsed_check_url.fragment
        ):
            raise _ProtectedEvidencePartial(
                "GitHub workflow job exposed an unexpected check-run URL"
            )
        check = self._collect_protected_workflow_check(
            repo,
            request,
            review,
            run,
            job_id=job_id,
            job_name=name,
        )
        return ProtectedWorkflowJobEvidence(
            job_id=job_id,
            name=name,
            run_id=run.run_id,
            run_attempt=run.run_attempt,
            head_sha=request.head_sha,
            status="completed",
            conclusion="success",
            steps=tuple(sorted(steps, key=lambda step: step.number)),
            check=check,
        )

    def _collect_protected_workflow_check(
        self,
        repo: str,
        request: ProtectedWorkflowEvidenceRequest,
        review: ProtectedReviewEvidence,
        run: ProtectedWorkflowRunEvidence,
        *,
        job_id: int,
        job_name: str,
    ) -> ProtectedWorkflowCheckEvidence:
        payload = self._protected_evidence_json(
            f"/repos/{repo}/check-runs/{job_id}"
        )
        if not isinstance(payload, Mapping):
            raise _ProtectedEvidencePartial("GitHub check run was malformed")
        suite = payload.get("check_suite")
        app = payload.get("app")
        app_id = app.get("id") if isinstance(app, Mapping) else None
        app_slug = app.get("slug") if isinstance(app, Mapping) else None
        if (
            _positive_int(payload.get("id")) != job_id
            or payload.get("name") != job_name
            or payload.get("head_sha") != request.head_sha
            or payload.get("status") != "completed"
            or payload.get("conclusion") != "success"
            or not isinstance(suite, Mapping)
            or _positive_int(suite.get("id")) != run.check_suite_id
            or _positive_int(app_id) != request.app_id
            or not isinstance(app_slug, str)
            or not app_slug
            or not isinstance(payload.get("details_url"), str)
            or not payload.get("details_url")
        ):
            raise _ProtectedEvidencePartial(
                "GitHub check run did not match its exact successful job"
            )
        associations = payload.get("pull_requests")
        if not isinstance(associations, list):
            raise _ProtectedEvidencePartial(
                "GitHub check run omitted pull-request associations"
            )
        matching_associations = [
            association
            for association in associations
            if self._protected_review_association_matches(
                association,
                review_id=review.review_id,
                source_branch=request.source_branch,
                head_sha=request.head_sha,
                target_branch=request.target_branch,
            )
        ]
        if associations and (
            len(associations) != 1 or len(matching_associations) != 1
        ):
            raise _ProtectedEvidencePartial(
                "GitHub check run was not uniquely bound to the merged review"
            )
        return ProtectedWorkflowCheckEvidence(
            check_run_id=job_id,
            name=job_name,
            head_sha=request.head_sha,
            status="completed",
            conclusion="success",
            check_suite_id=run.check_suite_id,
            app_id=request.app_id,
            app_slug=app_slug,
            details_url=str(payload["details_url"]),
        )

    def _graphql(self, query: str, variables: dict | None = None) -> httpx.Response:
        """POST a GraphQL query/mutation to GitHub's GraphQL endpoint.

        Used for features (notably auto-merge enablement) that GitHub
        exposes only via GraphQL, not REST.
        """
        payload: dict = {"query": query, "variables": variables or {}}
        return _get_http_client().post(
            "https://api.github.com/graphql",
            headers=self._headers(),
            json=payload,
        )

    def provider_name(self) -> str:
        return "github"

    def is_available(self) -> bool:
        try:
            r = self._api("GET", "/user")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def _list_merge_queue_pr_numbers(self, repo: str) -> set[int]:
        """Return PR numbers currently in the repo's merge queue.

        Once a PR enters the merge queue, GitHub clears its REST
        ``auto_merge`` field to null even though the queue is actively
        merging it. Without an explicit merge-queue lookup, the YOLO
        idempotency check in ``_yolo_review_actions_sync`` would treat
        the queued PR as un-enqueued and re-call ``enable_auto_merge``
        every tick. (oompah-zlz_2-btf.4)

        Cost: one GraphQL request per repo per ``list_open_reviews``
        call (not per PR). Returns an empty set on any failure or when
        the repo has no merge queue configured. The empty set is also
        the right answer for repos without merge queue, so callers can
        treat it as a no-op.
        """
        owner, sep, name = repo.partition("/")
        if not (owner and sep and name):
            return set()
        query = (
            "query($owner: String!, $name: String!) { "
            "repository(owner: $owner, name: $name) { "
            "mergeQueue { entries(first: 100) { nodes { "
            "pullRequest { number } "
            "} } } "
            "} }"
        )
        try:
            gql = self._graphql(query, {"owner": owner, "name": name})
        except httpx.HTTPError as exc:
            logger.debug(
                "GitHub merge-queue lookup failed for %s: %s", repo, exc,
            )
            return set()
        if gql.status_code != 200:
            logger.debug(
                "GitHub merge-queue lookup %s: HTTP %d", repo, gql.status_code,
            )
            return set()
        try:
            body = gql.json()
        except (json.JSONDecodeError, ValueError):
            return set()
        # Surface GraphQL-level errors at debug only — repo without merge
        # queue returns mergeQueue=null, not an error, so this path is
        # only for genuinely broken queries / permission issues.
        errors = body.get("errors") or []
        if errors:
            logger.debug(
                "GitHub merge-queue GraphQL errors for %s: %s",
                repo, errors,
            )
            return set()
        repo_obj = (body.get("data") or {}).get("repository") or {}
        queue_obj = repo_obj.get("mergeQueue") or {}
        # mergeQueue is null when the repo has no merge queue configured.
        if not queue_obj:
            return set()
        nodes = (queue_obj.get("entries") or {}).get("nodes") or []
        out: set[int] = set()
        for entry in nodes:
            if not isinstance(entry, dict):
                continue
            pr = entry.get("pullRequest") or {}
            number = pr.get("number") if isinstance(pr, dict) else None
            try:
                if number is not None:
                    out.add(int(number))
            except (TypeError, ValueError):
                continue
        return out

    def _is_pr_in_merge_queue(self, repo: str, review_id: str) -> bool:
        """Return True when the given PR is currently in the merge queue.

        Used by ``get_review`` (single-PR fetch) where pulling the entire
        merge queue would be wasteful. One GraphQL call. Returns False
        on any failure — failure modes are indistinguishable from
        "not queued" from the caller's perspective.
        """
        owner, sep, name = repo.partition("/")
        if not (owner and sep and name):
            return False
        try:
            number = int(str(review_id))
        except (TypeError, ValueError):
            return False
        query = (
            "query($owner: String!, $name: String!, $number: Int!) { "
            "repository(owner: $owner, name: $name) { "
            "pullRequest(number: $number) { isInMergeQueue } "
            "} }"
        )
        try:
            gql = self._graphql(
                query,
                {"owner": owner, "name": name, "number": number},
            )
        except httpx.HTTPError as exc:
            logger.debug(
                "GitHub isInMergeQueue lookup failed for %s#%s: %s",
                repo, review_id, exc,
            )
            return False
        if gql.status_code != 200:
            return False
        try:
            body = gql.json()
        except (json.JSONDecodeError, ValueError):
            return False
        if body.get("errors"):
            return False
        repo_obj = (body.get("data") or {}).get("repository") or {}
        pr_obj = repo_obj.get("pullRequest") or {}
        return bool(pr_obj.get("isInMergeQueue"))

    def _fetch_pr_mergeable_detail(
        self, repo: str, pr_num: str
    ) -> tuple[bool | None, str] | None:
        """Fetch a single PR's detail to read ``mergeable`` and
        ``mergeable_state``.

        The /pulls?state=open LIST endpoint never populates these
        fields — GitHub only computes them on the per-PR DETAIL endpoint
        (see oompah-zlz_2-8rb). list_open_reviews calls this helper for
        every non-draft PR that GitHub isn't already auto-merging, so
        the watchdog and YOLO conflict-agent dispatch see a real signal
        instead of always-False.

        Returns:
            (mergeable, mergeable_state_raw) on success, where
            ``mergeable`` is True/False/None (None = GitHub is still
            computing it asynchronously) and ``mergeable_state_raw`` is
            the lower-case string GitHub returns ("clean", "dirty",
            "behind", "blocked", "unknown", or "").

            None if the detail fetch failed entirely (HTTP error, JSON
            decode error, non-200). Callers should preserve their
            existing list-payload values in that case rather than
            falsely flipping ``has_conflicts`` to False.
        """
        if not pr_num:
            return None
        try:
            r = self._api("GET", f"/repos/{repo}/pulls/{pr_num}")
            if r.status_code != 200:
                return None
            payload = r.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None
        return payload.get("mergeable"), payload.get("mergeable_state") or ""

    def _fetch_actions_job(self, repo: str, job_id: str) -> dict[str, Any] | None:
        """Fetch a GitHub Actions job payload by job/check-run id."""
        if not job_id:
            return None
        try:
            r = self._api("GET", f"/repos/{repo}/actions/jobs/{job_id}")
            if r.status_code != 200:
                return None
            payload = r.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _fetch_self_hosted_runners(self, repo: str) -> list[dict[str, Any]] | None:
        """Return repository self-hosted runners visible to this token."""
        runners: list[dict[str, Any]] = []
        page = 1
        while True:
            try:
                r = self._api(
                    "GET",
                    f"/repos/{repo}/actions/runners",
                    params={"per_page": 100, "page": page},
                )
                if r.status_code != 200:
                    return None
                payload = r.json()
            except (httpx.HTTPError, json.JSONDecodeError):
                return None
            page_runners = payload.get("runners") or []
            if not isinstance(page_runners, list):
                return runners
            runners.extend(
                runner for runner in page_runners if isinstance(runner, dict)
            )
            if len(page_runners) < 100:
                return runners
            page += 1

    @staticmethod
    def _label_names(raw_labels: Any) -> set[str]:
        """Normalize GitHub runner/job labels into a lower-case set."""
        labels: set[str] = set()
        if not isinstance(raw_labels, list):
            return labels
        for raw in raw_labels:
            if isinstance(raw, dict):
                name = raw.get("name")
            else:
                name = raw
            if name is None:
                continue
            normalized = str(name).strip().lower()
            if normalized:
                labels.add(normalized)
        return labels

    @staticmethod
    def _display_label_names(raw_labels: Any) -> list[str]:
        labels: list[str] = []
        if not isinstance(raw_labels, list):
            return labels
        for raw in raw_labels:
            if isinstance(raw, dict):
                name = raw.get("name")
            else:
                name = raw
            if name is None:
                continue
            text = str(name).strip()
            if text:
                labels.append(text)
        return labels

    def _queued_self_hosted_runner_warning(
        self,
        repo: str,
        check_run: dict[str, Any],
        runners: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Warn when a queued self-hosted job has no online matching runner."""
        if str(check_run.get("status") or "").lower() != "queued":
            return None
        job = check_run
        label_names = self._label_names(job.get("labels"))
        if not label_names:
            job_id = str(job.get("id") or "")
            job_payload = self._fetch_actions_job(repo, job_id)
            if not job_payload:
                return None
            job = job_payload
            label_names = self._label_names(job.get("labels"))
        if "self-hosted" not in label_names:
            return None

        if runners is None:
            runners = self._fetch_self_hosted_runners(repo)
        if runners is None:
            return None
        matching: list[dict[str, Any]] = []
        online_matching: list[dict[str, Any]] = []
        for runner in runners:
            runner_labels = self._label_names(runner.get("labels"))
            if label_names.issubset(runner_labels):
                matching.append(runner)
                if str(runner.get("status") or "").lower() == "online":
                    online_matching.append(runner)
        if online_matching:
            return None

        labels_display = self._display_label_names(job.get("labels"))
        job_name = str(job.get("name") or check_run.get("name") or "queued job")
        job_url = str(
            job.get("html_url")
            or check_run.get("html_url")
            or check_run.get("details_url")
            or ""
        )
        if matching:
            reason = "offline"
            runner_names = [
                str(r.get("name") or "")
                for r in matching
                if str(r.get("name") or "")
            ]
            names = ", ".join(runner_names) or "matching runners"
            message = (
                f"{job_name} is queued for self-hosted runner labels "
                f"{', '.join(labels_display)}, but all matching runners "
                f"are offline: {names}."
            )
        else:
            reason = "missing"
            runner_names = []
            message = (
                f"{job_name} is queued for self-hosted runner labels "
                f"{', '.join(labels_display)}, but no repository runner "
                "has all required labels."
            )
        return {
            "type": "unavailable_runner",
            "severity": "warning",
            "reason": reason,
            "job_name": job_name,
            "job_url": job_url,
            "labels": labels_display,
            "matching_runners": runner_names,
            "message": message,
        }

    def _ci_warnings_for_check_runs(
        self, repo: str, runs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        queued = [
            run for run in runs
            if isinstance(run, dict)
            and str(run.get("status") or "").lower() == "queued"
        ]
        if not queued:
            return []
        runners: list[dict[str, Any]] | None = None
        runners_loaded = False
        warnings: list[dict[str, Any]] = []
        for run in queued:
            labels = self._label_names(run.get("labels"))
            if not labels:
                job = self._fetch_actions_job(repo, str(run.get("id") or ""))
                if not job:
                    continue
                run = {**run, **job}
                labels = self._label_names(run.get("labels"))
            if "self-hosted" not in labels:
                continue
            if not runners_loaded:
                runners = self._fetch_self_hosted_runners(repo)
                runners_loaded = True
            if runners is None:
                continue
            warning = self._queued_self_hosted_runner_warning(repo, run, runners)
            if warning:
                warnings.append(warning)
        return warnings

    def _fetch_workflow_runs_ci_status(
        self, repo: str, sha: str
    ) -> tuple[str, list[dict[str, Any]]] | None:
        """Query GitHub Actions workflow-runs API as a fallback CI status source.

        Used when ``/commits/{sha}/check-runs`` returns HTTP 403 (the Checks
        permission is not available on fine-grained PATs). The workflow-runs
        API requires only ``Actions: Read`` repository permission.

        Returns ``(status, warnings)`` where ``status`` is one of
        ``"passed"``, ``"failed"``, ``"pending"``, or ``""``  — or ``None``
        when the endpoint is also unavailable (HTTP 403, other error, or no
        workflow runs found for this SHA).

        Warnings are always empty for now (runner-availability warnings
        require check-run data).
        """
        try:
            r = self._api(
                "GET",
                f"/repos/{repo}/actions/runs",
                params={"head_sha": sha, "per_page": 100},
            )
            if r.status_code != 200:
                return None
            runs = r.json().get("workflow_runs", [])
            if not runs:
                # API is accessible but no workflow runs exist for this SHA
                # yet (e.g. very fresh commit, or repo doesn't use Actions).
                # Return ("", []) to distinguish from API-unavailable (None).
                return "", []
            conclusions = {
                run.get("conclusion")
                for run in runs
                if run.get("conclusion")
            }
            statuses = {run.get("status") for run in runs}
            if "failure" in conclusions or "timed_out" in conclusions:
                return "failed", []
            if all(s == "completed" for s in statuses) and all(
                c in ("success", "neutral", "skipped") for c in conclusions if c
            ):
                return "passed", []
            # Some runs still queued or in progress
            return "pending", []
        except (httpx.HTTPError, json.JSONDecodeError):
            return None

    def _fetch_ci_status_and_warnings(
        self,
        repo: str,
        sha: str,
        *,
        empty_check_status: str = "passed",
    ) -> tuple[str, list[dict[str, Any]]]:
        """Fetch combined CI status and operator-facing CI warnings.

        Reconciles two GitHub endpoints:

        * ``/commits/{sha}/status`` — legacy combined-status (Travis,
          CircleCI, third-party integrations, ad-hoc commit statuses).
        * ``/commits/{sha}/check-runs`` — modern GitHub Actions and
          GitHub Apps that emit check-runs.

        A repo that runs all its real CI through GitHub Actions can
        still have one or more legacy commit-status entries hanging
        around (a removed Travis hook, a misconfigured external
        validator, an old branch-protection requirement). When such a
        stale legacy entry is in state="failure", the combined-status
        rollup returns state="failure" even though every modern
        check-run is green.

        The previous short-circuit (``state == "failure" -> "failed"``)
        caused YOLO to log "auto-retrying failed CI" every poll tick
        for actually-passing PRs. Now: if the legacy verdict is
        failure but check-runs are all clean (success / neutral /
        skipped), the modern check-runs win and we return "passed".
        If check-runs cannot be inspected (HTTP error, empty payload,
        non-200), we fall back to the legacy verdict so we still flag
        actually-failing PRs. (oompah-zlz_2-c91)
        Also inspects queued GitHub Actions jobs for self-hosted runner
        labels. If GitHub is waiting for labels that have no online
        matching repository runner, the returned warning lets the UI
        say "offline/missing runner" instead of only "pending CI".

        When ``/commits/{sha}/check-runs`` returns HTTP 403 (the fine-
        grained PAT does not have ``Checks: Read`` — which GitHub's PAT
        editor may not expose), the method falls back to the GitHub
        Actions ``/actions/runs?head_sha=`` endpoint (requires only
        ``Actions: Read``). If that too is unavailable, a
        ``check_runs_forbidden`` capability warning is added so the UI
        can surface a degraded-state notice. (OOMPAH-210)
        """
        try:
            r = self._api("GET", f"/repos/{repo}/commits/{sha}/status")
            if r.status_code != 200:
                return "", []
            payload = r.json()
            state = payload.get("state", "")
            total = payload.get("total_count", 0)
            # Only trust the combined-status verdict when at least one legacy
            # commit-status was reported. Repos that use GitHub Actions only
            # return state="pending" with total_count=0, which would otherwise
            # mask all-green check-runs.
            legacy_failure = False
            legacy_pending = False
            if total > 0:
                if state == "success":
                    return "passed", []
                if state == "failure" or state == "error":
                    # Don't short-circuit. The legacy entry may be stale
                    # while modern check-runs are all green. Fall through
                    # to the check-runs endpoint and let it override only
                    # if it has a clean verdict.
                    legacy_failure = True
                elif state == "pending":
                    legacy_pending = True
            # Also check check-runs (GitHub Actions use this instead of status)
            cr = self._api("GET", f"/repos/{repo}/commits/{sha}/check-runs",
                           params={"per_page": 100})
            if cr.status_code == 200:
                runs = cr.json().get("check_runs", [])
                warnings = self._ci_warnings_for_check_runs(repo, runs)
                if legacy_pending:
                    return "pending", warnings
                if runs:
                    conclusions = {r.get("conclusion") or r.get("status", "") for r in runs}
                    if "failure" in conclusions or "timed_out" in conclusions:
                        return "failed", warnings
                    if all(c in ("success", "neutral", "skipped") for c in conclusions if c):
                        # All modern check-runs are clean. If we got
                        # here from a legacy "failure" verdict, the
                        # legacy commit-status entry is stale; trust
                        # the modern check-runs instead.
                        return "passed", warnings
                    return "pending", warnings
                # Both CI APIs were read successfully and neither reports a
                # check for this exact commit. Direct callers retain the
                # historical no-CI verdict. list_open_reviews requests the
                # internal empty-set signal so it can apply a bounded,
                # head-SHA-aware registration grace period. (OOMPAH-449)
                if legacy_failure:
                    return "failed", warnings
                return empty_check_status, warnings
            elif cr.status_code == 403:
                # The token lacks Checks access (common with fine-grained PATs
                # that were not granted the Checks permission). Fall back to
                # the Actions workflow-runs API which only needs Actions: Read.
                logger.warning(
                    "GitHub check-runs returned 403 for %s/%s — falling back "
                    "to workflow-runs API. Grant Actions: Read to your PAT for "
                    "CI observation.",
                    repo, sha[:7],
                )
                wf_result = self._fetch_workflow_runs_ci_status(repo, sha)
                if wf_result is not None:
                    wf_status, wf_warnings = wf_result
                    if legacy_pending:
                        return "pending", wf_warnings
                    if legacy_failure and not wf_status:
                        return "failed", wf_warnings
                    if wf_status:
                        return wf_status, wf_warnings
                    # wf_status == "" (no workflow runs found) — fall through
                    # to the established unknown/degraded verdict. Unlike a
                    # successful empty check-runs response, a 403 means we
                    # cannot positively establish that this SHA has no checks.
                else:
                    # Neither check-runs nor workflow-runs are accessible.
                    # Surface a degraded-capability warning so the UI can
                    # inform the operator.
                    forbidden_warning: dict[str, Any] = {
                        "type": "check_runs_forbidden",
                        "message": (
                            "CI check results are unavailable: HTTP 403 from "
                            "check-runs and workflow-runs APIs. Grant "
                            "Actions: Read to your fine-grained PAT so oompah "
                            "can observe CI status."
                        ),
                    }
                    if legacy_pending:
                        return "pending", [forbidden_warning]
                    if legacy_failure:
                        return "failed", [forbidden_warning]
                    return "", [forbidden_warning]
            # No usable check-runs response. If legacy reported failure,
            # honor it — there's no modern signal to override it.
            if legacy_failure:
                return "failed", []
        except (httpx.HTTPError, json.JSONDecodeError):
            pass
        return "", []

    def _fetch_ci_status(self, repo: str, sha: str) -> str:
        """Fetch combined CI status for a commit SHA."""
        status, _warnings = self._fetch_ci_status_and_warnings(repo, sha)
        return status

    @classmethod
    def _ci_status_for_empty_review_head(
        cls,
        repo: str,
        review_id: str,
        head_sha: str,
    ) -> str:
        """Classify an exact PR head with a successful empty CI response.

        The first empty observation starts a bounded registration window.
        Repeated empty responses remain pending until the window expires, at
        which point the exact SHA is positively classified as no-CI. A head
        change always replaces the observation and starts a new window.
        """
        key = (repo, review_id)
        now = time.monotonic()
        with cls._ci_head_observations_lock:
            observation = cls._ci_head_observations.get(key)
            if observation is None or observation[0] != head_sha:
                cls._ci_head_observations[key] = (head_sha, now)
                first_observed = now
            else:
                first_observed = observation[1]

        elapsed = max(0.0, now - first_observed)
        if elapsed < cls._CI_REGISTRATION_GRACE_SECONDS:
            logger.debug(
                "GitHub CI: empty check set for %s PR #%s head %s "
                "(observed %.1fs/%.1fs) — waiting for checks to register",
                repo,
                review_id,
                head_sha[:7],
                elapsed,
                cls._CI_REGISTRATION_GRACE_SECONDS,
            )
            return "pending"
        logger.debug(
            "GitHub CI: PR %s#%s head %s remained check-free for %.1fs "
            "— classifying this SHA as no-CI",
            repo,
            review_id,
            head_sha[:7],
            elapsed,
        )
        return "passed"

    def list_open_reviews(self, repo: str) -> list[ReviewRequest]:
        self.last_open_reviews_fetch_ok = False
        try:
            r = self._api("GET", f"/repos/{repo}/pulls", params={
                "state": "open",
                "per_page": 100,
            })
            if r.status_code != 200:
                logger.warning("GitHub list_open_reviews %s: HTTP %d", repo, r.status_code)
                return []
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.warning("GitHub list_open_reviews failed for %s: %s", repo, exc)
            return []
        self.last_open_reviews_fetch_ok = True

        # Batch-fetch CI status for all PRs (reuses HTTP connection pool)
        sha_map: dict[str, str] = {}
        for pr in data:
            sha = pr.get("head", {}).get("sha", "")
            if sha:
                sha_map[str(pr.get("number", ""))] = sha
        ci_statuses: dict[str, str] = {}
        ci_warnings: dict[str, list[dict[str, Any]]] = {}
        for pr_num, sha in sha_map.items():
            status, warnings = self._fetch_ci_status_and_warnings(
                repo,
                sha,
                empty_check_status=self._EMPTY_CHECK_SET,
            )
            if status == self._EMPTY_CHECK_SET:
                status = self._ci_status_for_empty_review_head(
                    repo,
                    pr_num,
                    sha,
                )
            ci_statuses[pr_num] = status
            ci_warnings[pr_num] = warnings

        # Single GraphQL call to learn which PRs are currently in the
        # merge queue. Once a PR enters the queue, GitHub clears its
        # REST ``auto_merge`` field even though the queue is actively
        # merging it — without this lookup the YOLO idempotency check
        # would treat queued PRs as un-enqueued. (oompah-zlz_2-btf.4)
        # Skip the call when the page returned no PRs at all (no PRs
        # ⇒ none can be queued).
        merge_queue_prs: set[int] = (
            self._list_merge_queue_pr_numbers(repo) if data else set()
        )

        results = []
        # Track PR numbers seen in this LIST response so we can evict
        # cache entries for PRs that were closed/merged since last tick
        # (oompah-zlz_2-aza).
        seen_pr_nums: set[str] = set()
        for pr in data:
            author = pr.get("user", {})
            author_login = author.get("login", "") if isinstance(author, dict) else str(author)

            labels = [l.get("name", "") for l in (pr.get("labels") or [])]
            reviewers = [r.get("login", "") for r in (pr.get("requested_reviewers") or [])
                         if isinstance(r, dict)]

            # mergeable/mergeable_state are NEVER populated on the
            # /pulls?state=open LIST endpoint — GitHub only fills them
            # on per-PR DETAIL fetches. We read them defensively here in
            # case GitHub ever changes that, but treat them as absent
            # by default. The real values are filled below via
            # _fetch_pr_mergeable_detail. (oompah-zlz_2-8rb)
            mergeable = pr.get("mergeable")
            merge_state_raw = pr.get("mergeable_state") or ""
            merge_state = merge_state_raw.upper()
            has_conflicts = mergeable is False
            rebase_needed = merge_state == "BEHIND" or has_conflicts

            # Auto-merge state — set when GitHub will merge this PR
            # automatically once it's ready. Two distinct paths populate
            # this:
            #   * ``auto_merge`` non-null → the PR has the auto-merge
            #     feature turned on (still pre-queue).
            #   * PR number appears in the repo's merge queue → GitHub
            #     has already taken over and will merge it; the
            #     ``auto_merge`` field is cleared once the queue takes
            #     over, so we must consult the merge queue separately.
            # Without the merge-queue arm, YOLO would re-call
            # ``enable_auto_merge`` every tick for every queued PR.
            auto_merge_obj = pr.get("auto_merge")
            auto_merge_enabled = bool(
                auto_merge_obj
                and isinstance(auto_merge_obj, dict)
                and auto_merge_obj.get("enabled_by")
            )

            pr_num = str(pr.get("number", ""))
            if pr_num:
                seen_pr_nums.add(pr_num)
            try:
                pr_num_int = int(pr.get("number") or 0)
            except (TypeError, ValueError):
                pr_num_int = 0
            if pr_num_int and pr_num_int in merge_queue_prs:
                auto_merge_enabled = True

            # Per-PR DETAIL fetch to populate mergeable / mergeable_state.
            # The LIST endpoint omits these fields, so without this
            # call has_conflicts is silently always False and the
            # YOLO loop never dispatches a merge-conflict agent for
            # genuinely DIRTY PRs. Skip drafts (we don't act on them).
            #
            # We DO fetch detail for auto-merge / merge-queued PRs even
            # though GitHub is "handling" them: an enqueued PR can go
            # DIRTY after another PR lands first (overlapping files),
            # and the queue will then sit forever waiting for manual
            # conflict resolution. Without this fetch, has_conflicts
            # stays False and we never file a merge-conflict task.
            # See oompah-zlz_2-l81 (regression of oompah-zlz_2-8rb).
            #
            # Cost amortisation (oompah-zlz_2-aza): we cache the
            # DETAIL result keyed on (repo, pr_num) and invalidate it
            # whenever GitHub's cheap LIST endpoint reports a new
            # ``head.sha`` or ``updated_at`` for the PR. Both fields
            # change exactly when mergeable_state can change (new
            # commit, base bump, queue transition, label/check flip),
            # so a steady-state poll with no PR changes performs
            # **zero** DETAIL fetches per tick. First tick after a PR
            # push pays one DETAIL fetch (cache miss).
            pr_draft = bool(pr.get("draft", False))
            if pr_num and not pr_draft:
                list_head_sha = pr.get("head", {}).get("sha", "") or ""
                list_updated_at = pr.get("updated_at", "") or ""
                cache_key = (repo, pr_num)
                cached_detail: tuple[bool | None, str] | None = None
                with self._pr_detail_cache_lock:
                    cached = self._pr_detail_cache.get(cache_key)
                # TTL fallback (oompah-zlz_2-1of): even when the
                # (head_sha, updated_at) key matches, force a re-fetch
                # if the cache entry is older than
                # ``_PR_DETAIL_CACHE_TTL_SECONDS``. GitHub recomputes
                # mergeable_state asynchronously when the BASE branch
                # moves and does NOT always bump the PR's ``updated_at``
                # — without a TTL, an enqueued auto-merge PR can stay
                # cached as ``mergeable_state='clean'`` indefinitely
                # while GitHub's true state has flipped to DIRTY.
                ttl = self._PR_DETAIL_CACHE_TTL_SECONDS
                now_monotonic = time.monotonic()
                if (
                    cached is not None
                    and cached[0] == list_head_sha
                    and cached[1] == list_updated_at
                    and (now_monotonic - cached[4]) <= ttl
                ):
                    cached_detail = (cached[2], cached[3])

                if cached_detail is not None:
                    detail = cached_detail
                else:
                    detail = self._fetch_pr_mergeable_detail(repo, pr_num)
                    if detail is not None:
                        # Populate cache on successful fetch only.
                        # Fetch failures fall through to LIST defaults
                        # below — caching the failure would pin
                        # has_conflicts=False until the next push.
                        #
                        # 'unknown' means GitHub hasn't finished computing
                        # mergeable_state yet (typical for fresh PRs and
                        # queue transitions). Don't cache it: head_sha
                        # and updated_at don't change while GitHub
                        # computes, so a cached 'unknown' would pin the
                        # UI to that label until the next push. Re-fetch
                        # next tick — typically resolves in 1-2 polls.
                        if (detail[1] or "").lower() != "unknown":
                            with self._pr_detail_cache_lock:
                                self._pr_detail_cache[cache_key] = (
                                    list_head_sha,
                                    list_updated_at,
                                    detail[0],
                                    detail[1] or "",
                                    time.monotonic(),
                                )

                if detail is not None:
                    detail_mergeable, detail_state_raw = detail
                    detail_state = (detail_state_raw or "").upper()
                    # Preserve the list-payload state only when the
                    # detail call returned an empty string (rare; would
                    # mean GitHub itself reported no state). When detail
                    # gives us a real value, trust it.
                    if detail_state_raw:
                        merge_state_raw = detail_state_raw
                    # ``mergeable`` may be ``None`` if GitHub hasn't
                    # finished computing it yet — leave the default
                    # has_conflicts=False in that case rather than
                    # flapping every tick.
                    has_conflicts = detail_mergeable is False
                    rebase_needed = detail_state == "BEHIND" or has_conflicts

            results.append(ReviewRequest(
                id=pr_num,
                title=pr.get("title", ""),
                url=pr.get("html_url", ""),
                author=author_login,
                state="open",
                source_branch=pr.get("head", {}).get("ref", ""),
                target_branch=pr.get("base", {}).get("ref", ""),
                created_at=pr.get("created_at", ""),
                updated_at=pr.get("updated_at", ""),
                description=_truncate(pr.get("body", "") or "", 500),
                labels=labels,
                draft=pr.get("draft", False),
                reviewers=reviewers,
                ci_status=ci_statuses.get(pr_num, ""),
                ci_warnings=ci_warnings.get(pr_num, []),
                additions=pr.get("additions", 0),
                deletions=pr.get("deletions", 0),
                needs_rebase=rebase_needed,
                has_conflicts=has_conflicts,
                auto_merge_enabled=auto_merge_enabled,
                mergeable_state=merge_state_raw,
                head_sha=str(pr.get("head", {}).get("sha", "") or ""),
                base_sha=str(pr.get("base", {}).get("sha", "") or ""),
                source_repository=str(
                    (pr.get("head", {}).get("repo") or {}).get("full_name", "")
                    or ""
                ),
                target_repository=str(
                    (pr.get("base", {}).get("repo") or {}).get("full_name", "")
                    or ""
                ),
            ))

        # Evict cache entries for PRs in this repo that were not in
        # the LIST response (closed, merged, or moved out of "open").
        # Per-repo eviction — leaves entries for other repos alone.
        # (oompah-zlz_2-aza)
        with self._pr_detail_cache_lock:
            stale = [
                key for key in self._pr_detail_cache
                if key[0] == repo and key[1] not in seen_pr_nums
            ]
            for key in stale:
                self._pr_detail_cache.pop(key, None)
        with self._ci_head_observations_lock:
            stale_ci = [
                key for key in self._ci_head_observations
                if key[0] == repo and key[1] not in seen_pr_nums
            ]
            for key in stale_ci:
                self._ci_head_observations.pop(key, None)

        return results

    def list_merged_branches(self, repo: str) -> set[str]:
        return {
            review.source_branch
            for review in self.list_merged_reviews(repo)
            if review.source_branch
        }

    def list_merged_reviews(self, repo: str) -> list[ReviewRequest]:
        try:
            r = self._api("GET", f"/repos/{repo}/pulls", params={
                "state": "closed",
                "per_page": 100,
                "sort": "updated",
                "direction": "desc",
            })
            if r.status_code != 200:
                logger.debug("GitHub list_merged_reviews %s: HTTP %d", repo, r.status_code)
                return []
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug("GitHub list_merged_reviews failed for %s: %s", repo, exc)
            return []

        reviews: list[ReviewRequest] = []
        for pr in data:
            if not pr.get("merged_at"):
                continue
            head_ref = pr.get("head", {}).get("ref", "")
            if not head_ref:
                continue
            author = pr.get("user", {})
            author_login = (
                author.get("login", "") if isinstance(author, dict) else str(author)
            )
            labels = [
                lbl.get("name", "")
                for lbl in pr.get("labels", []) or []
                if isinstance(lbl, dict)
            ]
            reviews.append(ReviewRequest(
                id=str(pr.get("number", "")),
                title=pr.get("title", ""),
                url=pr.get("html_url", ""),
                author=author_login,
                state="merged",
                source_branch=head_ref,
                target_branch=pr.get("base", {}).get("ref", ""),
                created_at=pr.get("created_at", ""),
                updated_at=pr.get("updated_at", ""),
                description=_truncate(pr.get("body", "") or "", 500),
                labels=labels,
                draft=pr.get("draft", False),
            ))
        return reviews

    def observe_branch_landing(
        self,
        repo: str,
        source_branch: str,
        target_branch: str,
    ) -> bool | None:
        """Return a tri-state observation for one exact GitHub PR route."""

        source = str(source_branch or "").strip()
        target = str(target_branch or "").strip()
        if not repo or not source or not target:
            return None
        owner = repo.split("/", 1)[0] if "/" in repo else ""
        head_param = f"{owner}:{source}" if owner else source
        try:
            response = self._api(
                "GET",
                f"/repos/{repo}/pulls",
                params={
                    "state": "closed",
                    "head": head_param,
                    "base": target,
                    "per_page": 100,
                    "sort": "updated",
                    "direction": "desc",
                },
            )
            if response.status_code != 200:
                logger.debug(
                    "GitHub observe_branch_landing %s %s -> %s: HTTP %d",
                    repo,
                    source,
                    target,
                    response.status_code,
                )
                return None
            data = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug(
                "GitHub observe_branch_landing failed for %s %s -> %s: %s",
                repo,
                source,
                target,
                exc,
            )
            return None
        if not isinstance(data, list):
            return None
        for pr in data:
            if not isinstance(pr, Mapping):
                return None
            head = pr.get("head")
            base = pr.get("base")
            if not isinstance(head, Mapping) or not isinstance(base, Mapping):
                return None
            if (
                bool(pr.get("merged_at"))
                and str(head.get("ref") or "").strip() == source
                and str(base.get("ref") or "").strip() == target
            ):
                return True
        return False


    def find_pr_for_branch(
        self, repo: str, branch_name: str,
    ) -> ReviewRequest | None:
        """Find the most recent PR whose head ref matches ``branch_name``.

        Uses GitHub's pulls list endpoint with the ``head`` filter
        (which requires ``user:branch`` format) to scope the search.
        Returns the most recently updated PR, with ``state`` normalised
        to ``"merged"`` when ``merged_at`` is set.
        """
        if not branch_name:
            return None
        # ``head=user:branch`` form is required. Owner is the first
        # segment of ``repo`` (e.g. ``owner/name``).
        owner = repo.split("/", 1)[0] if "/" in repo else ""
        head_param = f"{owner}:{branch_name}" if owner else branch_name
        try:
            r = self._api(
                "GET",
                f"/repos/{repo}/pulls",
                params={
                    "state": "all",
                    "head": head_param,
                    "per_page": 50,
                    "sort": "updated",
                    "direction": "desc",
                },
            )
            if r.status_code != 200:
                logger.debug(
                    "GitHub find_pr_for_branch %s/%s: HTTP %d",
                    repo, branch_name, r.status_code,
                )
                return None
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug(
                "GitHub find_pr_for_branch failed for %s/%s: %s",
                repo, branch_name, exc,
            )
            return None
        if not data:
            return None
        pr = data[0]
        author = pr.get("user", {})
        author_login = (
            author.get("login", "") if isinstance(author, dict) else str(author)
        )
        if pr.get("merged_at"):
            state = "merged"
        elif pr.get("state") == "closed":
            state = "closed"
        else:
            state = "open"
        return ReviewRequest(
            id=str(pr.get("number", "")),
            title=pr.get("title", ""),
            url=pr.get("html_url", ""),
            author=author_login,
            state=state,
            source_branch=pr.get("head", {}).get("ref", ""),
            target_branch=pr.get("base", {}).get("ref", ""),
            created_at=pr.get("created_at", ""),
            updated_at=pr.get("updated_at", ""),
            description=_truncate(pr.get("body", "") or "", 500),
            labels=[l.get("name", "") for l in (pr.get("labels") or [])],
            draft=pr.get("draft", False),
            head_sha=str(pr.get("head", {}).get("sha", "") or ""),
            base_sha=str(pr.get("base", {}).get("sha", "") or ""),
            source_repository=str(
                (pr.get("head", {}).get("repo") or {}).get("full_name", "")
                or ""
            ),
            target_repository=str(
                (pr.get("base", {}).get("repo") or {}).get("full_name", "")
                or ""
            ),
        )

    def get_review(self, repo: str, review_id: str) -> ReviewRequest | None:
        self.last_review_fetch_ok = False
        try:
            r = self._api("GET", f"/repos/{repo}/pulls/{review_id}")
            if r.status_code == 404:
                self.last_review_fetch_ok = True
                return None
            if r.status_code != 200:
                return None
            pr = r.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None
        self.last_review_fetch_ok = True

        author = pr.get("user", {})
        author_login = author.get("login", "") if isinstance(author, dict) else str(author)

        if pr.get("merged_at"):
            state = "merged"
        elif pr.get("state") == "closed":
            state = "closed"
        else:
            state = "open"

        merge_state_raw = pr.get("mergeable_state") or ""
        # Two paths can mark a PR as auto-merge-enabled:
        #   1. ``auto_merge`` non-null — the auto-merge feature is on
        #      (still pre-queue).
        #   2. The PR is in the repo's merge queue — GitHub clears
        #      ``auto_merge`` once the queue takes over, so we have
        #      to ask GraphQL directly. (oompah-zlz_2-btf.4)
        # Skip the second call when path 1 is already true to keep
        # ``get_review`` cheap for the common case.
        auto_merge_obj = pr.get("auto_merge")
        auto_merge_enabled = bool(
            auto_merge_obj
            and isinstance(auto_merge_obj, dict)
            and auto_merge_obj.get("enabled_by")
        )
        if not auto_merge_enabled:
            review_id_str = str(pr.get("number", ""))
            if review_id_str and self._is_pr_in_merge_queue(repo, review_id_str):
                auto_merge_enabled = True

        return ReviewRequest(
            id=str(pr.get("number", "")),
            title=pr.get("title", ""),
            url=pr.get("html_url", ""),
            author=author_login,
            state=state,
            source_branch=pr.get("head", {}).get("ref", ""),
            target_branch=pr.get("base", {}).get("ref", ""),
            created_at=pr.get("created_at", ""),
            updated_at=pr.get("updated_at", ""),
            description=_truncate(pr.get("body", "") or "", 500),
            labels=[l.get("name", "") for l in (pr.get("labels") or [])],
            draft=pr.get("draft", False),
            additions=pr.get("additions", 0),
            deletions=pr.get("deletions", 0),
            auto_merge_enabled=auto_merge_enabled,
            mergeable_state=merge_state_raw,
            head_sha=str(pr.get("head", {}).get("sha", "") or ""),
            base_sha=str(pr.get("base", {}).get("sha", "") or ""),
            source_repository=str(
                (pr.get("head", {}).get("repo") or {}).get("full_name", "")
                or ""
            ),
            target_repository=str(
                (pr.get("base", {}).get("repo") or {}).get("full_name", "")
                or ""
            ),
        )

    def create_review(
        self, repo: str, title: str, source_branch: str,
        target_branch: str = "main", description: str = "",
    ) -> ReviewRequest | None:
        try:
            r = self._api("POST", f"/repos/{repo}/pulls", json={
                "title": title,
                "head": source_branch,
                "base": target_branch,
                "body": description,
            })
            if r.status_code in (200, 201):
                pr = r.json()
                pr_number = str(pr.get("number", ""))
                return self.get_review(repo, pr_number)
            # GitHub returns 422 when a PR already exists for this branch.
            # Look up and return the existing open PR so the orchestrator
            # can mark the task In Review instead of failing with
            # "forge provider returned no review".
            if r.status_code == 422:
                body_text = r.text.lower()
                if "already exists" in body_text or "pull request already" in body_text:
                    logger.info(
                        "PR already exists for %s:%s — returning existing review",
                        repo,
                        source_branch,
                    )
                    existing = self.find_pr_for_branch(repo, source_branch)
                    if existing and existing.state == "open":
                        return existing
            logger.warning("GitHub create_review failed: HTTP %d %s",
                           r.status_code, r.text[:200])
            return None
        except httpx.HTTPError as exc:
            logger.warning("GitHub create_review failed: %s", exc)
            return None

    def rebase_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        try:
            r = self._api("PUT", f"/repos/{repo}/pulls/{review_id}/update-branch",
                          json={"update_method": "rebase"})
            if r.status_code in (200, 202):
                return True, "Rebase initiated successfully"
            body = r.text[:300]
            if "merge conflict" in body.lower() or "cannot be rebased" in body.lower():
                return False, "Rebase failed: merge conflicts require manual resolution"
            return False, f"Rebase failed: HTTP {r.status_code} {body}"
        except httpx.HTTPError as exc:
            return False, f"Rebase failed: {exc}"

    def merge_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        try:
            r = self._api("PUT", f"/repos/{repo}/pulls/{review_id}/merge",
                          json={"merge_method": "merge"})
            if r.status_code == 200:
                # Delete source branch (post-merge cleanup) — but never a
                # protected/long-lived branch (release/*, main, ...), even if
                # it was this PR's head.
                pr = self._api("GET", f"/repos/{repo}/pulls/{review_id}")
                if pr.status_code == 200:
                    branch = pr.json().get("head", {}).get("ref", "")
                    if branch and not _is_protected_branch(branch):
                        self._api("DELETE", f"/repos/{repo}/git/refs/heads/{branch}")
                    elif branch:
                        logger.info(
                            "Skipping post-merge deletion of protected branch "
                            "%s in %s", branch, repo,
                        )
                return True, "PR merged successfully"
            return False, f"Merge failed: HTTP {r.status_code} {r.text[:300]}"
        except httpx.HTTPError as exc:
            return False, f"Merge failed: {exc}"

    def merge_review_exact(
        self,
        repo: str,
        review_id: str,
        expected_head_sha: str,
    ) -> tuple[bool, str]:
        """Use GitHub's merge ``sha`` precondition as the final head CAS."""

        try:
            pr = self._api("GET", f"/repos/{repo}/pulls/{review_id}")
            if pr.status_code != 200:
                return False, f"Merge failed: HTTP {pr.status_code} {pr.text[:300]}"
            pr_body = pr.json()
            head = pr_body.get("head") or {}
            branch = str(head.get("ref") or "").strip()
            source_repo = str(
                (head.get("repo") or {}).get("full_name") or ""
            ).strip()
            r = self._api(
                "PUT",
                f"/repos/{repo}/pulls/{review_id}/merge",
                json={
                    "merge_method": "merge",
                    "sha": str(expected_head_sha or "").strip().lower(),
                },
            )
            if r.status_code != 200:
                return False, f"Merge failed: HTTP {r.status_code} {r.text[:300]}"
            # Delete only an in-repository source that still names the merged
            # generation.  A post-merge push must never be removed under the
            # authority of this older exact-head operation.
            if (
                branch
                and source_repo.casefold() == repo.casefold()
                and not _is_protected_branch(branch)
            ):
                current = self.get_branch_head_sha(repo, branch)
                if current == str(expected_head_sha or "").strip().lower():
                    self._api("DELETE", f"/repos/{repo}/git/refs/heads/{branch}")
            elif branch and _is_protected_branch(branch):
                logger.info(
                    "Skipping post-merge deletion of protected branch %s in %s",
                    branch,
                    repo,
                )
            return True, "PR merged successfully"
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            return False, f"Merge failed: {exc}"

    def close_review(
        self,
        repo: str,
        review_id: str,
        comment: str = "",
    ) -> tuple[bool, str]:
        try:
            if comment:
                comment_resp = self._api(
                    "POST",
                    f"/repos/{repo}/issues/{review_id}/comments",
                    json={"body": comment},
                )
                if comment_resp.status_code not in (200, 201):
                    logger.debug(
                        "GitHub close_review comment %s#%s: HTTP %d %s",
                        repo,
                        review_id,
                        comment_resp.status_code,
                        comment_resp.text[:200],
                    )
            r = self._api(
                "PATCH",
                f"/repos/{repo}/pulls/{review_id}",
                json={"state": "closed"},
            )
            if r.status_code == 200:
                return True, "PR closed successfully"
            return False, f"Close failed: HTTP {r.status_code} {r.text[:300]}"
        except httpx.HTTPError as exc:
            return False, f"Close failed: {exc}"

    def needs_rebase(self, repo: str, review_id: str) -> bool:
        try:
            r = self._api("GET", f"/repos/{repo}/pulls/{review_id}")
            if r.status_code != 200:
                return False
            pr = r.json()
            mergeable = pr.get("mergeable")
            merge_state = (pr.get("mergeable_state") or "").upper()
            return merge_state == "BEHIND" or mergeable is False
        except (httpx.HTTPError, json.JSONDecodeError):
            return False

    def enable_auto_merge(self, repo: str, review_id: str) -> tuple[bool, str]:
        """Enable auto-merge on a GitHub PR (enqueue mode).

        GitHub's auto-merge feature is exposed **only via GraphQL** —
        there is no REST endpoint for it. The previous implementation
        POSTed to ``/repos/{repo}/pulls/{N}/auto-merge`` and got an
        unconditional HTTP 404 because that path does not exist (see
        task oompah-zlz_2-d9v). This implementation:

        1. Looks up the PR's GraphQL ``node_id`` via REST.
        2. Calls the ``enablePullRequestAutoMerge`` GraphQL mutation.

        Repo prerequisite: the target repo must have
        ``allow_auto_merge=true`` set; otherwise GitHub returns
        ``Pull request Auto merge is not allowed for this repository``
        and this method reports that distinctly so operators can flip
        the repo flag.
        """
        # --- Step 1: fetch the PR to get its GraphQL node_id ---
        try:
            pr_resp = self._api("GET", f"/repos/{repo}/pulls/{review_id}")
        except httpx.HTTPError as exc:
            return False, f"Failed to enable auto-merge: PR lookup error: {exc}"
        if pr_resp.status_code != 200:
            return False, (
                f"Failed to enable auto-merge: PR lookup HTTP "
                f"{pr_resp.status_code} {pr_resp.text[:200]}"
            )
        try:
            pr_body = pr_resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return False, f"Failed to enable auto-merge: PR lookup JSON error: {exc}"
        node_id = pr_body.get("node_id")
        if not node_id:
            return False, "Failed to enable auto-merge: PR response missing node_id"

        # --- Step 2: enablePullRequestAutoMerge GraphQL mutation ---
        mutation = (
            "mutation($pullRequestId: ID!, $mergeMethod: PullRequestMergeMethod!) { "
            "enablePullRequestAutoMerge(input: {pullRequestId: $pullRequestId, "
            "mergeMethod: $mergeMethod}) { "
            "pullRequest { autoMergeRequest { enabledAt } } "
            "} "
            "}"
        )
        try:
            gql = self._graphql(
                mutation,
                {"pullRequestId": node_id, "mergeMethod": "SQUASH"},
            )
        except httpx.HTTPError as exc:
            return False, f"Failed to enable auto-merge: GraphQL error: {exc}"
        if gql.status_code != 200:
            return False, (
                f"Failed to enable auto-merge: GraphQL HTTP "
                f"{gql.status_code} {gql.text[:200]}"
            )
        try:
            body = gql.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return False, f"Failed to enable auto-merge: GraphQL JSON error: {exc}"

        errors = body.get("errors") or []
        if errors:
            msg = "; ".join(str(e.get("message", "")) for e in errors).strip("; ")
            low = msg.lower()
            # Repo missing allow_auto_merge=true.
            if "auto merge is not allowed" in low or "auto-merge is not allowed" in low:
                return False, (
                    f"Auto-merge not allowed by repo (set allow_auto_merge=true on "
                    f"{repo}): {msg}"
                )
            # PR is already mergeable — auto-merge can't attach to it.
            if "clean status" in low:
                return False, f"Auto-merge rejected (PR already mergeable): {msg}"
            return False, f"Failed to enable auto-merge: {msg}"
        return True, "Auto-merge enabled on PR"

    def get_review_files(self, repo: str, review_id: str) -> list[str]:
        """Return file paths changed by a GitHub PR via REST /pulls/{n}/files."""
        try:
            r = self._api("GET", f"/repos/{repo}/pulls/{review_id}/files")
            if r.status_code != 200:
                logger.debug(
                    "GitHub get_review_files %s#%s: HTTP %d",
                    repo, review_id, r.status_code,
                )
                return []
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug(
                "GitHub get_review_files failed for %s#%s: %s",
                repo, review_id, exc,
            )
            return []
        return [f.get("filename", "") for f in data if f.get("filename")]

    def add_review_label(self, repo: str, review_id: str, label: str) -> None:
        """Add a label to a GitHub PR via REST /issues/{n}/labels."""
        try:
            r = self._api(
                "POST", f"/repos/{repo}/issues/{review_id}/labels",
                json={"labels": [label]},
            )
            if r.status_code not in (200, 201):
                logger.warning(
                    "GitHub add_review_label %s#%s '%s': HTTP %d %s",
                    repo, review_id, label, r.status_code, r.text[:200],
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "GitHub add_review_label failed for %s#%s '%s': %s",
                repo, review_id, label, exc,
            )

    def remove_review_label(self, repo: str, review_id: str, label: str) -> None:
        """Remove a label from a GitHub PR via REST /issues/{n}/labels/{name}."""
        try:
            encoded = urllib.parse.quote(label, safe="")
            r = self._api(
                "DELETE",
                f"/repos/{repo}/issues/{review_id}/labels/{encoded}",
            )
            # GitHub returns 200 on success, 404 if the label wasn't present.
            if r.status_code not in (200, 404):
                logger.warning(
                    "GitHub remove_review_label %s#%s '%s': HTTP %d %s",
                    repo, review_id, label, r.status_code, r.text[:200],
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "GitHub remove_review_label failed for %s#%s '%s': %s",
                repo, review_id, label, exc,
            )

    def get_pr_commits(self, repo: str, review_id: str) -> list[str]:
        """Return the commit SHAs included in a GitHub pull request.

        Uses ``GET /repos/{repo}/pulls/{pr}/commits`` (max 250 commits per
        GitHub API documentation — sufficient for any normal PR; large
        squash-heavy PRs are handled by GitHub presenting a single commit).

        Returns commits in chronological order (oldest first).  Empty list
        on HTTP error, non-200 status, or JSON decode failure.

        Args:
            repo: ``"owner/name"`` slug.
            review_id: PR number as a string.

        Returns:
            List of full-length commit SHAs, oldest first.
        """
        try:
            r = self._api(
                "GET",
                f"/repos/{repo}/pulls/{review_id}/commits",
                params={"per_page": 250},
            )
            if r.status_code != 200:
                logger.debug(
                    "GitHub get_pr_commits %s#%s: HTTP %d",
                    repo, review_id, r.status_code,
                )
                return []
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug(
                "GitHub get_pr_commits failed for %s#%s: %s",
                repo, review_id, exc,
            )
            return []
        return [
            c["sha"]
            for c in data
            if isinstance(c, dict) and c.get("sha")
        ]

    def get_branch_head_sha(self, repo: str, branch: str) -> str | None:
        """Return the HEAD commit SHA for *branch* via GitHub refs API.

        Uses ``GET /repos/{repo}/git/refs/heads/{branch}`` to fetch the
        branch tip SHA.  Returns ``None`` on any error or when the branch
        does not exist (HTTP 404).

        Args:
            repo: ``"owner/name"`` slug.
            branch: Branch name (without ``refs/heads/`` prefix).

        Returns:
            Full 40-character commit SHA, or ``None``.
        """
        try:
            r = self._api("GET", f"/repos/{repo}/git/refs/heads/{branch}")
            if r.status_code != 200:
                logger.debug(
                    "GitHub get_branch_head_sha %s/%s: HTTP %d",
                    repo, branch, r.status_code,
                )
                return None
            data = r.json()
            # Response may be a list (when a prefix matches multiple refs) or
            # a single object.  Normalise to a list.
            if isinstance(data, dict):
                data = [data]
            for item in data:
                ref = item.get("ref", "")
                if ref == f"refs/heads/{branch}":
                    sha = item.get("object", {}).get("sha", "")
                    return sha if sha else None
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug(
                "GitHub get_branch_head_sha failed for %s/%s: %s",
                repo, branch, exc,
            )
        return None

    def get_ci_status_for_sha(self, repo: str, sha: str) -> CIStatus:
        """Return the CI status for a specific commit SHA.

        Delegates to :meth:`_fetch_ci_status`.  Returns one of
        ``"passed"``, ``"failed"``, ``"pending"``, or ``"unknown"``
        when CI data is unavailable.

        Args:
            repo: ``"owner/name"`` slug.
            sha: Full 40-character commit SHA.

        Returns:
            A forge-neutral :class:`CIStatus` value.
        """
        try:
            return normalize_ci_status(self._fetch_ci_status(repo, sha))
        except Exception:  # noqa: BLE001
            return CIStatus.UNKNOWN


class GitLabProvider(SCMProvider):
    """GitLab implementation using the REST API via httpx."""

    def __init__(self, hostname: str = "gitlab.com", access_token: str | None = None):
        self._hostname = hostname
        # When an explicit token is provided (e.g. from project config), skip
        # the env/CLI fallback so per-project auth wins over the global default.
        self._token: str | None = access_token
        register_secret(access_token)
        self._token_resolved = bool(access_token)
        self.last_open_reviews_fetch_ok = True
        self.last_review_fetch_ok = True

    def _headers(self) -> dict[str, str]:
        if not self._token_resolved:
            self._token = _resolve_gitlab_token(self._hostname)
            self._token_resolved = True
        h: dict[str, str] = {}
        if self._token:
            h["PRIVATE-TOKEN"] = self._token
        return h

    def _api_url(self) -> str:
        return f"https://{self._hostname}/api/v4"

    def _api(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self._api_url()}{path}"
        return _get_http_client().request(method, url, headers=self._headers(), **kwargs)

    def _project_path(self, repo: str) -> str:
        """URL-encode the project path for GitLab API."""
        return urllib.parse.quote(repo, safe="")

    def provider_name(self) -> str:
        return "gitlab"

    @staticmethod
    def _same_project_source_repository(
        repo: str,
        review: Mapping[str, Any],
    ) -> str:
        """Return ``repo`` only for positive same-project identity evidence."""

        source_project_id = review.get("source_project_id")
        target_project_id = review.get("target_project_id")
        if (
            source_project_id is None
            or target_project_id is None
            or not str(source_project_id).strip()
            or not str(target_project_id).strip()
        ):
            return ""
        return repo if source_project_id == target_project_id else ""

    def is_available(self) -> bool:
        try:
            r = self._api("GET", "/user")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def _hydrate_open_review_identity(
        self,
        repo: str,
        encoded_repo: str,
        review: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Return list evidence with one complete immutable MR identity.

        GitLab's merge-request list endpoint may omit ``diff_refs`` even for
        open merge requests.  The detail endpoint is the authority for those
        immutable fields.  Never manufacture a repository identity or let a
        partial detail response weaken the list observation.
        """

        head_sha = str(
            review.get("sha")
            or (review.get("diff_refs") or {}).get("head_sha")
            or ""
        )
        base_sha = str((review.get("diff_refs") or {}).get("base_sha") or "")
        if _is_full_git_sha(head_sha) and _is_full_git_sha(base_sha):
            return dict(review)

        review_id = str(review.get("iid") or "").strip()
        if not review_id:
            return None
        try:
            response = self._api(
                "GET",
                f"/projects/{encoded_repo}/merge_requests/{review_id}",
            )
            if response.status_code != 200:
                logger.warning(
                    "GitLab open review identity %s!%s: HTTP %d",
                    repo,
                    review_id,
                    response.status_code,
                )
                return None
            detail = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.warning(
                "GitLab open review identity failed for %s!%s: %s",
                repo,
                review_id,
                exc,
            )
            return None
        if not isinstance(detail, Mapping) or str(detail.get("iid") or "") != review_id:
            return None

        hydrated = dict(review)
        hydrated.update(detail)
        head_sha = str(
            hydrated.get("sha")
            or (hydrated.get("diff_refs") or {}).get("head_sha")
            or ""
        )
        base_sha = str(
            (hydrated.get("diff_refs") or {}).get("base_sha") or ""
        )
        if not _is_full_git_sha(head_sha) or not _is_full_git_sha(base_sha):
            return None
        return hydrated

    def _active_merge_train_entries(
        self, repo: str
    ) -> dict[str, Mapping[str, Any]]:
        """Return active GitLab merge-train entries keyed by MR IID."""

        encoded = self._project_path(repo)
        try:
            response = self._api(
                "GET",
                f"/projects/{encoded}/merge_trains",
                params={"scope": "active", "per_page": 100},
            )
            if response.status_code != 200:
                logger.warning(
                    "GitLab merge-train observation %s: HTTP %d",
                    repo,
                    response.status_code,
                )
                return {}
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 - optional observation
            logger.warning("GitLab merge-train observation failed for %s: %s", repo, exc)
            return {}
        if not isinstance(payload, list):
            return {}
        entries: dict[str, Mapping[str, Any]] = {}
        for raw in payload:
            if not isinstance(raw, Mapping):
                return {}
            merge_request = raw.get("merge_request")
            if not isinstance(merge_request, Mapping):
                return {}
            review_id = str(merge_request.get("iid") or "").strip()
            if not review_id:
                return {}
            entries[review_id] = raw
        return entries

    def _merge_train_entry(
        self, repo: str, review_id: str
    ) -> Mapping[str, Any] | None:
        """Return one active train entry, or ``None`` when unavailable/absent."""

        encoded = self._project_path(repo)
        try:
            response = self._api(
                "GET",
                f"/projects/{encoded}/merge_trains/merge_requests/{review_id}",
            )
            if response.status_code != 200:
                return None
            payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None
        if not isinstance(payload, Mapping):
            return None
        merge_request = payload.get("merge_request")
        if (
            not isinstance(merge_request, Mapping)
            or str(merge_request.get("iid") or "").strip() != str(review_id)
        ):
            return None
        return payload

    def list_open_reviews(self, repo: str) -> list[ReviewRequest]:
        self.last_open_reviews_fetch_ok = False
        encoded = self._project_path(repo)
        try:
            r = self._api("GET", f"/projects/{encoded}/merge_requests", params={
                "state": "opened",
                "per_page": 100,
                "include_diverged_commits_count": True,
                "with_merge_status_recheck": True,
            })
            if r.status_code != 200:
                logger.warning("GitLab list_open_reviews %s: HTTP %d", repo, r.status_code)
                return []
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.warning("GitLab list_open_reviews failed for %s: %s", repo, exc)
            return []
        train_entries = self._active_merge_train_entries(repo)
        self.last_open_reviews_fetch_ok = True

        results = []
        for listed_mr in data:
            if not isinstance(listed_mr, Mapping):
                self.last_open_reviews_fetch_ok = False
                return []
            mr = self._hydrate_open_review_identity(repo, encoded, listed_mr)
            if mr is None:
                # An incomplete immutable identity is an unavailable provider
                # observation, not proof of a changed review generation.
                self.last_open_reviews_fetch_ok = False
                return []
            author = mr.get("author", {})
            author_name = author.get("username", author.get("name", "")) if isinstance(author, dict) else str(author)

            labels = mr.get("labels") or []
            reviewers = []
            for rv in (mr.get("reviewers") or []):
                if isinstance(rv, dict):
                    reviewers.append(rv.get("username", rv.get("name", "")))

            # GitLab's merge-request list response may omit ``head_pipeline``
            # even though an exact-head pipeline exists.  Treat the embedded
            # object as a fast path, then fall back to the immutable head SHA
            # through the provider's pipeline contract.  An unavailable or
            # empty observation remains UNKNOWN and therefore retryable.
            ci_status = ""
            ci_warnings: list[CapabilityWarning] = []
            pipeline = mr.get("head_pipeline") or {}
            if pipeline:
                ps = pipeline.get("status", "").lower()
                if ps == "success":
                    ci_status = "passed"
                elif ps in ("failed", "canceled"):
                    ci_status = "failed"
                elif ps in ("running", "pending", "created"):
                    ci_status = "pending"
            head_sha = str(
                mr.get("sha")
                or (mr.get("diff_refs") or {}).get("head_sha")
                or ""
            )
            if not ci_status and head_sha:
                ci_status, ci_warnings = self._fetch_ci_status_and_warnings(
                    repo, head_sha
                )

            detailed_merge_status = str(
                mr.get("detailed_merge_status") or ""
            ).strip().lower()
            has_conflicts = bool(mr.get("has_conflicts", False)) or (
                detailed_merge_status == "conflict"
            )
            rebase_needed = has_conflicts or (mr.get("diverged_commits_count") or 0) > 0
            review_id = str(mr.get("iid", mr.get("id", "")))
            train_entry = train_entries.get(review_id)
            train_status = str(
                (train_entry or {}).get("status") or ""
            ).strip().lower()
            auto_merge_enabled = train_entry is not None
            if auto_merge_enabled:
                detailed_merge_status = f"merge_train:{train_status or 'active'}"

            results.append(ReviewRequest(
                id=review_id,
                title=mr.get("title", ""),
                url=mr.get("web_url", ""),
                author=author_name,
                state="open",
                source_branch=mr.get("source_branch", ""),
                target_branch=mr.get("target_branch", ""),
                created_at=mr.get("created_at", ""),
                updated_at=mr.get("updated_at", ""),
                description=_truncate(mr.get("description", "") or "", 500),
                labels=labels,
                draft=mr.get("draft", False) or mr.get("work_in_progress", False),
                reviewers=reviewers,
                ci_status=ci_status,
                ci_warnings=ci_warnings,
                additions=mr.get("changes_count", 0) if isinstance(mr.get("changes_count"), int) else 0,
                deletions=0,
                needs_rebase=rebase_needed,
                has_conflicts=has_conflicts,
                auto_merge_enabled=auto_merge_enabled,
                mergeable_state=detailed_merge_status,
                head_sha=head_sha,
                base_sha=str((mr.get("diff_refs") or {}).get("base_sha") or ""),
                source_repository=self._same_project_source_repository(repo, mr),
                target_repository=repo,
            ))
        return results

    def list_merged_branches(self, repo: str) -> set[str]:
        return {
            review.source_branch
            for review in self.list_merged_reviews(repo)
            if review.source_branch
        }

    def list_merged_reviews(self, repo: str) -> list[ReviewRequest]:
        encoded = self._project_path(repo)
        try:
            r = self._api("GET", f"/projects/{encoded}/merge_requests", params={
                "state": "merged",
                "per_page": 100,
                "order_by": "updated_at",
                "sort": "desc",
            })
            if r.status_code != 200:
                logger.debug("GitLab list_merged_reviews %s: HTTP %d", repo, r.status_code)
                return []
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug("GitLab list_merged_reviews failed for %s: %s", repo, exc)
            return []

        reviews: list[ReviewRequest] = []
        for mr in data:
            source_branch = mr.get("source_branch", "")
            if not source_branch:
                continue
            author = mr.get("author", {})
            author_name = (
                author.get("username", author.get("name", ""))
                if isinstance(author, dict)
                else str(author)
            )
            labels_raw = mr.get("labels", []) or []
            labels = labels_raw if isinstance(labels_raw, list) else []
            reviews.append(ReviewRequest(
                id=str(mr.get("iid", mr.get("id", ""))),
                title=mr.get("title", ""),
                url=mr.get("web_url", ""),
                author=author_name,
                state="merged",
                source_branch=source_branch,
                target_branch=mr.get("target_branch", ""),
                created_at=mr.get("created_at", ""),
                updated_at=mr.get("updated_at", ""),
                description=_truncate(mr.get("description", "") or "", 500),
                labels=labels,
                draft=mr.get("draft", False) or mr.get("work_in_progress", False),
            ))
        return reviews

    def observe_branch_landing(
        self,
        repo: str,
        source_branch: str,
        target_branch: str,
    ) -> bool | None:
        """Return a tri-state observation for one exact GitLab MR route."""

        source = str(source_branch or "").strip()
        target = str(target_branch or "").strip()
        if not repo or not source or not target:
            return None
        encoded = self._project_path(repo)
        try:
            response = self._api(
                "GET",
                f"/projects/{encoded}/merge_requests",
                params={
                    "state": "merged",
                    "source_branch": source,
                    "target_branch": target,
                    "per_page": 100,
                    "order_by": "updated_at",
                    "sort": "desc",
                },
            )
            if response.status_code != 200:
                logger.debug(
                    "GitLab observe_branch_landing %s %s -> %s: HTTP %d",
                    repo,
                    source,
                    target,
                    response.status_code,
                )
                return None
            data = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug(
                "GitLab observe_branch_landing failed for %s %s -> %s: %s",
                repo,
                source,
                target,
                exc,
            )
            return None
        if not isinstance(data, list):
            return None
        for mr in data:
            if not isinstance(mr, Mapping):
                return None
            raw_state = mr.get("state")
            raw_source = mr.get("source_branch")
            raw_target = mr.get("target_branch")
            if (
                not isinstance(raw_state, str)
                or not isinstance(raw_source, str)
                or not raw_source.strip()
                or not isinstance(raw_target, str)
                or not raw_target.strip()
            ):
                return None
            if (
                raw_state.lower() == "merged"
                and raw_source.strip() == source
                and raw_target.strip() == target
            ):
                return True
        return False

    def find_pr_for_branch(
        self, repo: str, branch_name: str,
    ) -> ReviewRequest | None:
        """Find the most recent MR whose source branch matches.

        GitLab's MR list supports filtering by ``source_branch``. We
        ask for ``state=all`` and sort newest-first so the first hit
        is the latest record for the branch (whether open, merged, or
        closed without merge).
        """
        if not branch_name:
            return None
        encoded = self._project_path(repo)
        try:
            r = self._api(
                "GET",
                f"/projects/{encoded}/merge_requests",
                params={
                    "state": "all",
                    "source_branch": branch_name,
                    "per_page": 50,
                    "order_by": "updated_at",
                    "sort": "desc",
                },
            )
            if r.status_code != 200:
                logger.debug(
                    "GitLab find_pr_for_branch %s/%s: HTTP %d",
                    repo, branch_name, r.status_code,
                )
                return None
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug(
                "GitLab find_pr_for_branch failed for %s/%s: %s",
                repo, branch_name, exc,
            )
            return None
        if not data:
            return None
        mr = data[0]
        if not isinstance(mr, Mapping):
            return None
        raw_state = (mr.get("state") or "").lower()
        if raw_state == "merged":
            state = "merged"
        elif raw_state == "closed":
            state = "closed"
        else:
            state = "open"
            # The list endpoint commonly omits ``diff_refs.base_sha``.  The
            # standalone delivery authority requires both immutable head and
            # base generations before it may adopt an existing open review,
            # so hydrate from the exact MR detail endpoint just as
            # ``list_open_reviews`` does.  If detail is temporarily
            # unavailable, retain the partial list observation: callers then
            # fail closed on incomplete identity instead of attempting to
            # create a competing open review.
            hydrated = self._hydrate_open_review_identity(repo, encoded, mr)
            if hydrated is not None:
                mr = hydrated
        author = mr.get("author", {})
        author_name = (
            author.get("username", author.get("name", ""))
            if isinstance(author, dict)
            else str(author)
        )
        return ReviewRequest(
            id=str(mr.get("iid", mr.get("id", ""))),
            title=mr.get("title", ""),
            url=mr.get("web_url", ""),
            author=author_name,
            state=state,
            source_branch=mr.get("source_branch", ""),
            target_branch=mr.get("target_branch", ""),
            created_at=mr.get("created_at", ""),
            updated_at=mr.get("updated_at", ""),
            description=_truncate(mr.get("description", "") or "", 500),
            labels=mr.get("labels") or [],
            draft=mr.get("draft", False) or mr.get("work_in_progress", False),
            needs_rebase=bool(mr.get("has_conflicts", False))
            or (mr.get("diverged_commits_count") or 0) > 0,
            has_conflicts=bool(mr.get("has_conflicts", False)),
            head_sha=str(
                mr.get("sha")
                or (mr.get("diff_refs") or {}).get("head_sha")
                or ""
            ),
            base_sha=str((mr.get("diff_refs") or {}).get("base_sha") or ""),
            source_repository=self._same_project_source_repository(repo, mr),
            target_repository=repo,
        )

    def get_review(self, repo: str, review_id: str) -> ReviewRequest | None:
        encoded = self._project_path(repo)
        self.last_review_fetch_ok = False
        try:
            r = self._api("GET", f"/projects/{encoded}/merge_requests/{review_id}")
            if r.status_code == 404:
                self.last_review_fetch_ok = True
                return None
            if r.status_code != 200:
                return None
            mr = r.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None
        train_entry = self._merge_train_entry(repo, review_id)
        self.last_review_fetch_ok = True

        author = mr.get("author", {})
        author_name = author.get("username", author.get("name", "")) if isinstance(author, dict) else str(author)

        raw_state = str(mr.get("state", "") or "").lower()
        if raw_state == "merged":
            state = "merged"
        elif raw_state == "closed":
            state = "closed"
        else:
            state = "open"

        return ReviewRequest(
            id=str(mr.get("iid", mr.get("id", ""))),
            title=mr.get("title", ""),
            url=mr.get("web_url", ""),
            author=author_name,
            state=state,
            source_branch=mr.get("source_branch", ""),
            target_branch=mr.get("target_branch", ""),
            created_at=mr.get("created_at", ""),
            updated_at=mr.get("updated_at", ""),
            description=_truncate(mr.get("description", "") or "", 500),
            labels=mr.get("labels") or [],
            draft=mr.get("draft", False) or mr.get("work_in_progress", False),
            needs_rebase=bool(mr.get("has_conflicts", False))
            or str(mr.get("detailed_merge_status") or "").strip().lower()
            == "conflict"
            or (mr.get("diverged_commits_count") or 0) > 0,
            has_conflicts=bool(mr.get("has_conflicts", False))
            or str(mr.get("detailed_merge_status") or "").strip().lower()
            == "conflict",
            auto_merge_enabled=train_entry is not None,
            mergeable_state=(
                f"merge_train:{str(train_entry.get('status') or 'active').lower()}"
                if train_entry is not None
                else str(mr.get("detailed_merge_status") or "")
            ),
            head_sha=str(
                mr.get("sha")
                or (mr.get("diff_refs") or {}).get("head_sha")
                or ""
            ),
            base_sha=str((mr.get("diff_refs") or {}).get("base_sha") or ""),
            source_repository=self._same_project_source_repository(repo, mr),
            target_repository=repo,
        )

    def create_review(
        self, repo: str, title: str, source_branch: str,
        target_branch: str = "main", description: str = "",
    ) -> ReviewRequest | None:
        encoded = self._project_path(repo)
        try:
            r = self._api("POST", f"/projects/{encoded}/merge_requests", json={
                "title": title,
                "source_branch": source_branch,
                "target_branch": target_branch,
                "description": description,
            })
            if r.status_code not in (200, 201):
                logger.warning("GitLab create_review failed: HTTP %d %s",
                               r.status_code, r.text[:200])
                return None
            mr = r.json()
            mr_id = str(mr.get("iid", mr.get("id", "")))
            return self.get_review(repo, mr_id)
        except httpx.HTTPError as exc:
            logger.warning("GitLab create_review failed: %s", exc)
            return None

    def rebase_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        encoded = self._project_path(repo)
        try:
            r = self._api("PUT", f"/projects/{encoded}/merge_requests/{review_id}/rebase")
            if r.status_code in (200, 202):
                return True, "Rebase initiated successfully"
            body = r.text[:300]
            if "conflict" in body.lower():
                return False, "Rebase failed: merge conflicts require manual resolution"
            return False, f"Rebase failed: HTTP {r.status_code} {body}"
        except httpx.HTTPError as exc:
            return False, f"Rebase failed: {exc}"

    def merge_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        encoded = self._project_path(repo)
        try:
            # Never auto-remove a protected/long-lived source branch
            # (release/*, main, ...) — check before requesting removal.
            remove_source = True
            mr = self._api("GET", f"/projects/{encoded}/merge_requests/{review_id}")
            if mr.status_code == 200:
                source_branch = mr.json().get("source_branch", "")
                if _is_protected_branch(source_branch):
                    remove_source = False
                    logger.info(
                        "Skipping post-merge deletion of protected branch "
                        "%s in %s", source_branch, repo,
                    )
            r = self._api("PUT", f"/projects/{encoded}/merge_requests/{review_id}/merge",
                          json={
                              "should_remove_source_branch": remove_source,
                          })
            if r.status_code == 200:
                return True, "MR merged successfully"
            return False, f"Merge failed: HTTP {r.status_code} {r.text[:300]}"
        except httpx.HTTPError as exc:
            return False, f"Merge failed: {exc}"

    def merge_review_exact(
        self,
        repo: str,
        review_id: str,
        expected_head_sha: str,
    ) -> tuple[bool, str]:
        """Use GitLab's merge ``sha`` precondition as the final head CAS."""

        encoded = self._project_path(repo)
        try:
            mr = self._api(
                "GET",
                f"/projects/{encoded}/merge_requests/{review_id}",
            )
            if mr.status_code != 200:
                return False, f"Merge failed: HTTP {mr.status_code}"
            source_branch = mr.json().get("source_branch", "")
            remove_source = not _is_protected_branch(source_branch)
            r = self._api(
                "PUT",
                f"/projects/{encoded}/merge_requests/{review_id}/merge",
                json={
                    "should_remove_source_branch": remove_source,
                    "sha": str(expected_head_sha or "").strip().lower(),
                },
            )
            if r.status_code == 200:
                return True, "MR merged successfully"
            return False, f"Merge failed: HTTP {r.status_code} {r.text[:300]}"
        except httpx.HTTPError as exc:
            return False, f"Merge failed: {exc}"

    def close_review(
        self,
        repo: str,
        review_id: str,
        comment: str = "",
    ) -> tuple[bool, str]:
        encoded = self._project_path(repo)
        try:
            if comment:
                note_resp = self._api(
                    "POST",
                    f"/projects/{encoded}/merge_requests/{review_id}/notes",
                    json={"body": comment},
                )
                if note_resp.status_code not in (200, 201):
                    logger.debug(
                        "GitLab close_review note %s#%s: HTTP %d %s",
                        repo,
                        review_id,
                        note_resp.status_code,
                        note_resp.text[:200],
                    )
            r = self._api(
                "PUT",
                f"/projects/{encoded}/merge_requests/{review_id}",
                json={"state_event": "close"},
            )
            if r.status_code == 200:
                return True, "MR closed successfully"
            return False, f"Close failed: HTTP {r.status_code} {r.text[:300]}"
        except httpx.HTTPError as exc:
            return False, f"Close failed: {exc}"

    def needs_rebase(self, repo: str, review_id: str) -> bool:
        encoded = self._project_path(repo)
        try:
            r = self._api("GET", f"/projects/{encoded}/merge_requests/{review_id}")
            if r.status_code != 200:
                return False
            mr = r.json()
            if mr.get("has_conflicts", False):
                return True
            if (mr.get("diverged_commits_count") or 0) > 0:
                return True
            return False
        except (httpx.HTTPError, json.JSONDecodeError):
            return False

    def enable_auto_merge_exact(
        self,
        repo: str,
        review_id: str,
        expected_head_sha: str,
    ) -> tuple[bool, str]:
        """Add an exact GitLab MR head to the configured merge train."""

        expected = str(expected_head_sha or "").strip().lower()
        if not _is_full_git_sha(expected):
            return False, "Merge-train enqueue requires an exact head SHA"
        encoded = self._project_path(repo)
        try:
            r = self._api(
                "POST",
                f"/projects/{encoded}/merge_trains/merge_requests/{review_id}",
                json={"auto_merge": True, "sha": expected},
            )
            if r.status_code in (200, 201, 202):
                return True, "MR accepted by GitLab merge train"
            if r.status_code == 404:
                return False, (
                    "Merge-train enqueue unavailable: enable GitLab merge trains "
                    f"for {repo} and verify MR {review_id} exists"
                )
            if r.status_code in (401, 403):
                return False, (
                    "Merge-train enqueue rejected: approvals, permissions, or "
                    f"policy are not satisfied — {r.text[:300]}"
                )
            return False, (
                f"Merge-train enqueue failed: HTTP {r.status_code} {r.text[:300]}"
            )
        except httpx.HTTPError as exc:
            return False, f"Merge-train enqueue failed: {exc}"

    def enable_auto_merge(self, repo: str, review_id: str) -> tuple[bool, str]:
        """Legacy GitLab auto-merge compatibility path.

        Production review delivery uses :meth:`enable_auto_merge_exact`; this
        method remains for older embedders until they migrate to exact-head
        authority.
        """

        encoded = self._project_path(repo)
        try:
            response = self._api(
                "PUT",
                f"/projects/{encoded}/merge_requests/{review_id}/merge",
                json={"merge_when_pipeline_succeeds": True},
            )
            if response.status_code == 200:
                return True, "Auto-merge enabled: will merge when pipeline succeeds"
            if response.status_code in (401, 403):
                return False, (
                    "Auto-merge rejected: approvals or policy not satisfied — "
                    f"{response.text[:300]}"
                )
            if response.status_code == 405:
                return False, f"Auto-merge not allowed: {response.text[:300]}"
            return False, (
                f"Auto-merge failed: HTTP {response.status_code} "
                f"{response.text[:300]}"
            )
        except httpx.HTTPError as exc:
            return False, f"Auto-merge failed: {exc}"

    def get_review_files(self, repo: str, review_id: str) -> list[str]:
        """Return file paths changed by a GitLab MR via
        /projects/:id/merge_requests/:iid/changes.
        """
        encoded = self._project_path(repo)
        try:
            r = self._api(
                "GET", f"/projects/{encoded}/merge_requests/{review_id}/changes"
            )
            if r.status_code != 200:
                logger.debug(
                    "GitLab get_review_files %s#%s: HTTP %d",
                    repo, review_id, r.status_code,
                )
                return []
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug(
                "GitLab get_review_files failed for %s#%s: %s",
                repo, review_id, exc,
            )
            return []
        # GitLab /changes returns {"changes": [{"old_path": ..., "new_path": ...}, ...]}.
        changes = data.get("changes", [])
        paths: list[str] = []
        for c in changes:
            if not isinstance(c, dict):
                continue
            # Prefer new_path (handles renames); fall back to old_path.
            new_path = c.get("new_path") or c.get("old_path") or ""
            if new_path:
                paths.append(new_path)
        return paths

    def add_review_label(self, repo: str, review_id: str, label: str) -> None:
        """Add a label to a GitLab MR via PATCH /projects/:id/merge_requests/:iid.

        GitLab's MR label API uses a PATCH on the full MR resource with
        the ``labels`` parameter set to the *entire* desired label set.
        To add a single label without clobbering existing ones, we first
        fetch the current labels, append the new label, and PATCH the
        complete set back.
        """
        encoded = self._project_path(repo)
        try:
            # Fetch current labels so we don't clobber existing ones.
            r = self._api("GET", f"/projects/{encoded}/merge_requests/{review_id}")
            if r.status_code != 200:
                logger.warning(
                    "GitLab add_review_label %s#%s '%s': "
                    "cannot fetch MR to read existing labels: HTTP %d",
                    repo, review_id, label, r.status_code,
                )
                return
            mr = r.json()
            existing_labels: list[str] = mr.get("labels") or []
            if label not in existing_labels:
                existing_labels.append(label)
            r2 = self._api(
                "PUT", f"/projects/{encoded}/merge_requests/{review_id}",
                json={"labels": ",".join(existing_labels)},
            )
            if r2.status_code != 200:
                logger.warning(
                    "GitLab add_review_label %s#%s '%s': HTTP %d %s",
                    repo, review_id, label, r2.status_code, r2.text[:200],
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "GitLab add_review_label failed for %s#%s '%s': %s",
                repo, review_id, label, exc,
            )

    def remove_review_label(self, repo: str, review_id: str, label: str) -> None:
        """Remove a label from a GitLab MR via PATCH /projects/:id/merge_requests/:iid.

        Like add_review_label, this fetches the current labels first,
        removes the target label, and PATCHes the complete set back.
        """
        encoded = self._project_path(repo)
        try:
            # Fetch current labels so we don't clobber existing ones.
            r = self._api("GET", f"/projects/{encoded}/merge_requests/{review_id}")
            if r.status_code != 200:
                logger.warning(
                    "GitLab remove_review_label %s#%s '%s': "
                    "cannot fetch MR to read existing labels: HTTP %d",
                    repo, review_id, label, r.status_code,
                )
                return
            mr = r.json()
            existing_labels: list[str] = mr.get("labels") or []
            if label in existing_labels:
                existing_labels.remove(label)
            r2 = self._api(
                "PUT", f"/projects/{encoded}/merge_requests/{review_id}",
                json={"labels": ",".join(existing_labels)},
            )
            if r2.status_code != 200:
                logger.warning(
                    "GitLab remove_review_label %s#%s '%s': HTTP %d %s",
                    repo, review_id, label, r2.status_code, r2.text[:200],
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "GitLab remove_review_label failed for %s#%s '%s': %s",
                repo, review_id, label, exc,
            )

    def get_pr_commits(self, repo: str, review_id: str) -> list[str]:
        """Return the commit SHAs included in a GitLab merge request.

        Uses ``GET /projects/:id/merge_requests/:iid/commits`` (paginated
        at 100 per page).  Returns commits in reverse-chronological order
        as GitLab delivers them, then reverses to oldest-first to match the
        GitHub behaviour.

        Args:
            repo: GitLab project path or numeric ID.
            review_id: MR IID as a string.

        Returns:
            List of full-length commit SHAs, oldest first.  Empty on error.
        """
        encoded = self._project_path(repo)
        try:
            r = self._api(
                "GET",
                f"/projects/{encoded}/merge_requests/{review_id}/commits",
                params={"per_page": 100},
            )
            if r.status_code != 200:
                logger.debug(
                    "GitLab get_pr_commits %s#%s: HTTP %d",
                    repo, review_id, r.status_code,
                )
                return []
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug(
                "GitLab get_pr_commits failed for %s#%s: %s",
                repo, review_id, exc,
            )
            return []
        shas = [
            c["id"]
            for c in data
            if isinstance(c, dict) and c.get("id")
        ]
        # GitLab returns newest-first; reverse to oldest-first.
        shas.reverse()
        return shas

    def get_branch_head_sha(self, repo: str, branch: str) -> str | None:
        """Return the HEAD commit SHA for *branch* via GitLab branches API.

        Uses ``GET /projects/:id/repository/branches/:branch`` to fetch the
        branch tip SHA from the ``commit.id`` field.  Returns ``None`` on any
        error, a 404, or a malformed response.

        Args:
            repo: GitLab project path (e.g. ``"group/sub/project"``).
            branch: Branch name (without ``refs/heads/`` prefix).

        Returns:
            Full commit SHA string, or ``None``.
        """
        encoded_repo = self._project_path(repo)
        encoded_branch = urllib.parse.quote(branch, safe="")
        try:
            r = self._api(
                "GET",
                f"/projects/{encoded_repo}/repository/branches/{encoded_branch}",
            )
            if r.status_code != 200:
                logger.debug(
                    "GitLab get_branch_head_sha %s/%s: HTTP %d",
                    repo, branch, r.status_code,
                )
                return None
            data = r.json()
            sha = data.get("commit", {}).get("id", "")
            return sha if sha else None
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug(
                "GitLab get_branch_head_sha failed for %s/%s: %s",
                repo, branch, exc,
            )
            return None

    @staticmethod
    def _normalize_gitlab_status(status: str) -> str:
        """Map a GitLab pipeline/job status string to a forge-neutral contract string.

        Returns one of ``"passed"``, ``"failed"``, ``"pending"``, or ``""``
        (for unknown/unrecognised states).
        """
        s = (status or "").lower()
        if s in ("success", "skipped"):
            return "passed"
        if s in ("failed", "canceled"):
            return "failed"
        if s in ("running", "pending", "created", "waiting_for_resource",
                 "preparing", "scheduled"):
            return "pending"
        return ""

    def _fetch_ci_status_and_warnings(
        self, repo: str, sha: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Fetch CI status and bounded capability warnings from GitLab pipelines.

        Calls ``GET /projects/:id/pipelines?sha=:sha`` then fetches jobs for
        each pipeline to produce a single aggregated forge-neutral verdict.

        Aggregation priority: ``failed`` > ``pending`` > ``passed``.  An empty
        pipeline list yields an empty status (mapped to ``unknown`` by callers).

        Capability failures (HTTP 403, 429, or non-list payloads) are returned
        as structured warnings rather than silent ``unknown`` so the UI can
        surface a degraded-state notice.

        Args:
            repo: GitLab project path.
            sha: Full commit SHA.

        Returns:
            ``(status_string, warnings)`` where *status_string* is one of
            ``"passed"``, ``"failed"``, ``"pending"``, or ``""`` (unknown),
            and *warnings* is a list of ``CapabilityWarning``-shaped dicts
            capped at 10 entries.
        """
        encoded = self._project_path(repo)
        try:
            r = self._api(
                "GET",
                f"/projects/{encoded}/pipelines",
                params={"sha": sha, "per_page": 100},
            )
        except httpx.HTTPError as exc:
            logger.debug("GitLab _fetch_ci_status_and_warnings %s/%s: %s", repo, sha[:7], exc)
            return "", []

        if r.status_code == 403:
            return "", [{
                "type": "gitlab_ci_forbidden",
                "message": (
                    "CI check results are unavailable: HTTP 403 from GitLab "
                    "pipelines API. Grant CI access to your token so oompah "
                    "can observe CI status."
                ),
            }]
        if r.status_code == 429:
            return "", [{
                "type": "gitlab_ci_rate_limited",
                "message": (
                    "CI check results are unavailable: HTTP 429 rate limit "
                    "from GitLab pipelines API. Retry later."
                ),
            }]
        if r.status_code != 200:
            return "", []

        try:
            pipelines = r.json()
        except (json.JSONDecodeError, ValueError):
            return "", [{
                "type": "gitlab_ci_malformed_response",
                "message": "CI response from GitLab pipelines could not be parsed.",
            }]

        if not isinstance(pipelines, list):
            return "", [{
                "type": "gitlab_ci_malformed_response",
                "message": "CI response from GitLab pipelines was not a list.",
            }]

        if not pipelines:
            return "", []

        failed_jobs: list[dict[str, Any]] = []
        has_pending = False
        has_passed = False

        for pipeline in pipelines:
            pipeline_id = str(pipeline.get("id", ""))
            pipeline_url = pipeline.get("web_url", "")
            pipeline_status = pipeline.get("status", "")

            # Fetch individual jobs so stale pipeline-level rollups can be
            # overridden by the live job statuses.
            jobs: list | None = None
            try:
                jobs_r = self._api(
                    "GET",
                    f"/projects/{encoded}/pipelines/{pipeline_id}/jobs",
                )
                if jobs_r.status_code == 200:
                    try:
                        parsed = jobs_r.json()
                        if isinstance(parsed, list):
                            jobs = parsed
                    except (json.JSONDecodeError, ValueError):
                        pass
            except httpx.HTTPError:
                pass

            if jobs:
                for job in jobs:
                    normalized = self._normalize_gitlab_status(job.get("status", ""))
                    if normalized == "failed":
                        failed_jobs.append({
                            "job_url": job.get("web_url", ""),
                            "pipeline_url": pipeline_url,
                        })
                    elif normalized == "pending":
                        has_pending = True
                    elif normalized == "passed":
                        has_passed = True
            else:
                # No job-level data available; fall back to pipeline status.
                normalized = self._normalize_gitlab_status(pipeline_status)
                if normalized == "failed":
                    failed_jobs.append({"job_url": "", "pipeline_url": pipeline_url})
                elif normalized == "pending":
                    has_pending = True
                elif normalized == "passed":
                    has_passed = True

        if failed_jobs:
            # Sort deterministically by job URL (then pipeline URL) so warning
            # order is stable across multiple runs.
            failed_jobs.sort(key=lambda w: (w.get("job_url", ""), w.get("pipeline_url", "")))
            return "failed", failed_jobs[:10]
        if has_pending:
            return "pending", []
        if has_passed:
            return "passed", []
        return "", []

    def get_ci_status_for_sha(self, repo: str, sha: str) -> CIStatus:
        """Return the CI status for a specific commit SHA on GitLab.

        Delegates to :meth:`_fetch_ci_status_and_warnings` and normalises the
        raw status string to a :class:`CIStatus` enum member.  Returns
        ``CIStatus.UNKNOWN`` when CI data is unavailable or an error occurs.

        Args:
            repo: GitLab project path (e.g. ``"group/project"``).
            sha: Full commit SHA.

        Returns:
            A forge-neutral :class:`CIStatus` value.
        """
        try:
            status, _warnings = self._fetch_ci_status_and_warnings(repo, sha)
            return normalize_ci_status(status)
        except Exception:  # noqa: BLE001
            return CIStatus.UNKNOWN


# -- Helpers --

def _truncate(s: str, max_len: int) -> str:
    if not s:
        return ""
    if len(s) <= max_len:
        return s
    return s[:max_len - 3] + "..."


def detect_provider(
    repo_url: str, access_token: str | None = None,
) -> SCMProvider | None:
    """Detect the SCM provider from a repository URL.

    Returns a GitHubProvider or GitLabProvider instance, or None if
    the URL doesn't match a known pattern. When ``access_token`` is set,
    the provider uses it instead of resolving from env vars or the
    gh/glab CLI.
    """
    url_lower = repo_url.lower()
    if "github.com" in url_lower:
        return GitHubProvider(access_token=access_token)
    if "gitlab" in url_lower:
        # Extract hostname for non-default GitLab instances
        hostname = "gitlab.com"
        if "://" in repo_url:
            hostname = repo_url.split("://", 1)[1].split("/", 1)[0]
        elif repo_url.startswith("git@"):
            hostname = repo_url.split("@", 1)[1].split(":", 1)[0]
        return GitLabProvider(hostname=hostname, access_token=access_token)
    return None


def extract_repo_slug(repo_url: str) -> str:
    """Extract owner/repo slug from a git URL.

    Examples:
        https://github.com/org/repo.git -> org/repo
        git@github.com:org/repo.git     -> org/repo
        https://gitlab.com/group/project.git -> group/project
    """
    url = repo_url.strip()

    # SSH format: git@host:org/repo.git
    if url.startswith("git@"):
        _, path = url.split(":", 1)
        path = path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return path

    # HTTPS format
    # Strip protocol
    for prefix in ("https://", "http://"):
        if url.lower().startswith(prefix):
            url = url[len(prefix):]
            break

    # Strip host
    parts = url.split("/", 1)
    if len(parts) < 2:
        return url
    path = parts[1].rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path


def get_all_open_reviews(projects: list) -> list[dict]:
    """Fetch open reviews across all projects.

    Args:
        projects: List of Project objects with repo_url attribute.

    Returns:
        List of dicts with project info and review data.
    """
    results = []
    for project in projects:
        provider = detect_provider(
            project.repo_url, access_token=getattr(project, "access_token", None),
        )
        if not provider:
            logger.debug("No SCM provider detected for %s", project.repo_url)
            continue

        slug = extract_repo_slug(project.repo_url)
        try:
            reviews = provider.list_open_reviews(slug)
        except Exception as exc:
            logger.warning("Failed to fetch reviews for %s: %s", project.name, exc)
            continue

        # Surface project.yolo so the /reviews UI can hide the manual
        # "Resolve Conflicts" button on YOLO-enabled projects (where YOLO
        # already retries provider.rebase_review then falls back to
        # notifying the task — making the click redundant). See
        # oompah-zlz_2-zvf2.
        project_yolo = bool(getattr(project, "yolo", False))
        for review in reviews:
            results.append({
                "project_id": project.id,
                "project_name": project.name,
                "project_yolo": project_yolo,
                "provider": provider.provider_name(),
                "review": review.to_dict(),
            })

    return results
