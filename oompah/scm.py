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
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

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
    ci_status: str = ""  # passed, failed, pending, ""
    ci_warnings: list[dict[str, Any]] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    needs_rebase: bool = False
    has_conflicts: bool = False
    # GitHub merge-queue / auto-merge state. Populated from the GitHub
    # pull-request API (``auto_merge`` and ``mergeable_state``). Both are
    # left at their defaults for GitLab — GitLab merge trains are a
    # separate feature not adopted in this rollout.
    auto_merge_enabled: bool = False
    mergeable_state: str = ""
    # True when at least one file changed by this review appears in the
    # project's top-N churn-magnet list (oompah-zlz_2-rxwe.2). Populated
    # by the orchestrator's churn-magnet check in _yolo_review_actions_sync.
    churn_magnet: bool = False
    churn_magnet_files: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

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
            "files": self.files,
            "churn_magnet": self.churn_magnet,
            "churn_magnet_files": self.churn_magnet_files,
        }


class SCMProvider(ABC):
    """Base class for source control management providers."""

    @abstractmethod
    def list_open_reviews(self, repo: str) -> list[ReviewRequest]:
        """List all open pull/merge requests for a repo.

        Args:
            repo: Repository identifier. Format depends on provider:
                  GitHub: "owner/repo"
                  GitLab: "group/project" or project ID
        """
        ...

    @abstractmethod
    def list_merged_branches(self, repo: str) -> set[str]:
        """Return source branch names of recently merged PRs/MRs."""
        ...

    @abstractmethod
    def list_merged_reviews(self, repo: str) -> list[ReviewRequest]:
        """Return recently merged PRs/MRs with source and target branches."""
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

        Used by the epic auto-close gate (oompah-zlz_2-lvcd) to verify
        a child's branch was merged before closing the parent epic.
        """
        ...

    @abstractmethod
    def get_review(self, repo: str, review_id: str) -> ReviewRequest | None:
        """Get a single pull/merge request by ID."""
        ...

    @abstractmethod
    def create_review(
        self, repo: str, title: str, source_branch: str,
        target_branch: str = "main", description: str = "",
    ) -> ReviewRequest | None:
        """Create a new pull/merge request."""
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
        """Check if a PR/MR needs a rebase (is behind target branch)."""
        ...

    @abstractmethod
    def merge_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        """Merge a pull/merge request.

        Returns:
            (success, message) tuple.
        """
        ...

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
        """Check if the provider is authenticated and reachable."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g. 'github', 'gitlab')."""
        ...

    @abstractmethod
    def get_review_files(self, repo: str, review_id: str) -> list[str]:
        """Return a list of file paths changed by the review.

        Args:
            repo: Repository identifier.
            review_id: PR/MR number.

        Returns:
            List of file paths (e.g. ``["src/foo.py", "README.md"]``).
        """
        ...

    @abstractmethod
    def add_review_label(self, repo: str, review_id: str, label: str) -> None:
        """Add a label to a pull/merge request.

        Args:
            repo: Repository identifier.
            review_id: PR/MR number.
            label: Label name to add.
        """
        ...

    @abstractmethod
    def remove_review_label(self, repo: str, review_id: str, label: str) -> None:
        """Remove a label from a pull/merge request.

        Args:
            repo: Repository identifier.
            review_id: PR/MR number.
            label: Label name to remove.
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


def _resolve_gh_token() -> str | None:
    """Resolve GitHub token from environment or gh CLI config."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        r = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _resolve_gitlab_token(hostname: str = "gitlab.com") -> str | None:
    """Resolve GitLab token from environment or glab CLI config."""
    token = os.environ.get("GITLAB_TOKEN") or os.environ.get("GITLAB_API_TOKEN")
    if token:
        return token
    try:
        r = subprocess.run(
            ["glab", "auth", "token", "--hostname", hostname],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
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

    def __init__(self, access_token: str | None = None) -> None:
        # When an explicit token is provided (e.g. from project config), skip
        # the env/CLI fallback so per-project auth wins over the global default.
        self._token: str | None = access_token
        self._token_resolved = bool(access_token)

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
        self, repo: str, sha: str
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

    def list_open_reviews(self, repo: str) -> list[ReviewRequest]:
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

        # Batch-fetch CI status for all PRs (reuses HTTP connection pool)
        sha_map: dict[str, str] = {}
        for pr in data:
            sha = pr.get("head", {}).get("sha", "")
            if sha:
                sha_map[str(pr.get("number", ""))] = sha
        ci_statuses: dict[str, str] = {}
        ci_warnings: dict[str, list[dict[str, Any]]] = {}
        for pr_num, sha in sha_map.items():
            status, warnings = self._fetch_ci_status_and_warnings(repo, sha)
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
        )

    def get_review(self, repo: str, review_id: str) -> ReviewRequest | None:
        try:
            r = self._api("GET", f"/repos/{repo}/pulls/{review_id}")
            if r.status_code != 200:
                return None
            pr = r.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None

        author = pr.get("user", {})
        author_login = author.get("login", "") if isinstance(author, dict) else str(author)

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
            state="open",
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
                          json={"merge_method": "squash"})
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


class GitLabProvider(SCMProvider):
    """GitLab implementation using the REST API via httpx."""

    def __init__(self, hostname: str = "gitlab.com", access_token: str | None = None):
        self._hostname = hostname
        # When an explicit token is provided (e.g. from project config), skip
        # the env/CLI fallback so per-project auth wins over the global default.
        self._token: str | None = access_token
        self._token_resolved = bool(access_token)

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

    def is_available(self) -> bool:
        try:
            r = self._api("GET", "/user")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def list_open_reviews(self, repo: str) -> list[ReviewRequest]:
        encoded = self._project_path(repo)
        try:
            r = self._api("GET", f"/projects/{encoded}/merge_requests", params={
                "state": "opened",
                "per_page": 100,
            })
            if r.status_code != 200:
                logger.warning("GitLab list_open_reviews %s: HTTP %d", repo, r.status_code)
                return []
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.warning("GitLab list_open_reviews failed for %s: %s", repo, exc)
            return []

        results = []
        for mr in data:
            author = mr.get("author", {})
            author_name = author.get("username", author.get("name", "")) if isinstance(author, dict) else str(author)

            labels = mr.get("labels") or []
            reviewers = []
            for rv in (mr.get("reviewers") or []):
                if isinstance(rv, dict):
                    reviewers.append(rv.get("username", rv.get("name", "")))

            # CI status from head_pipeline
            ci_status = ""
            pipeline = mr.get("head_pipeline") or {}
            if pipeline:
                ps = pipeline.get("status", "").lower()
                if ps == "success":
                    ci_status = "passed"
                elif ps in ("failed", "canceled"):
                    ci_status = "failed"
                elif ps in ("running", "pending", "created"):
                    ci_status = "pending"

            has_conflicts = mr.get("has_conflicts", False)
            rebase_needed = has_conflicts or (mr.get("diverged_commits_count") or 0) > 0

            results.append(ReviewRequest(
                id=str(mr.get("iid", mr.get("id", ""))),
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
                additions=mr.get("changes_count", 0) if isinstance(mr.get("changes_count"), int) else 0,
                deletions=0,
                needs_rebase=rebase_needed,
                has_conflicts=has_conflicts,
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
        raw_state = (mr.get("state") or "").lower()
        if raw_state == "merged":
            state = "merged"
        elif raw_state == "closed":
            state = "closed"
        else:
            state = "open"
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
        )

    def get_review(self, repo: str, review_id: str) -> ReviewRequest | None:
        encoded = self._project_path(repo)
        try:
            r = self._api("GET", f"/projects/{encoded}/merge_requests/{review_id}")
            if r.status_code != 200:
                return None
            mr = r.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None

        author = mr.get("author", {})
        author_name = author.get("username", author.get("name", "")) if isinstance(author, dict) else str(author)

        return ReviewRequest(
            id=str(mr.get("iid", mr.get("id", ""))),
            title=mr.get("title", ""),
            url=mr.get("web_url", ""),
            author=author_name,
            state="open",
            source_branch=mr.get("source_branch", ""),
            target_branch=mr.get("target_branch", ""),
            created_at=mr.get("created_at", ""),
            updated_at=mr.get("updated_at", ""),
            description=_truncate(mr.get("description", "") or "", 500),
            labels=mr.get("labels") or [],
            draft=mr.get("draft", False) or mr.get("work_in_progress", False),
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
                              "squash": True,
                              "should_remove_source_branch": remove_source,
                          })
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

    def enable_auto_merge(self, repo: str, review_id: str) -> tuple[bool, str]:
        """Enable auto-merge for a GitLab MR.

        GitLab merge trains differ from GitHub's merge queue and are not
        adopted in this rollout.  Falls back to a direct merge so that
        queue-mode projects on GitLab still make progress.
        """
        logger.debug(
            "GitLab enable_auto_merge: falling back to direct merge for %s MR #%s",
            repo, review_id,
        )
        return self.merge_review(repo, review_id)

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
