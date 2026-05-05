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
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

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
    additions: int = 0
    deletions: int = 0
    needs_rebase: bool = False
    has_conflicts: bool = False

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
            "additions": self.additions,
            "deletions": self.deletions,
            "needs_rebase": self.needs_rebase,
            "has_conflicts": self.has_conflicts,
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
    def is_available(self) -> bool:
        """Check if the provider is authenticated and reachable."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g. 'github', 'gitlab')."""
        ...


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


class GitHubProvider(SCMProvider):
    """GitHub implementation using the REST API via httpx."""

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

    def provider_name(self) -> str:
        return "github"

    def is_available(self) -> bool:
        try:
            r = self._api("GET", "/user")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def _fetch_ci_status(self, repo: str, sha: str) -> str:
        """Fetch combined CI status for a commit SHA."""
        try:
            r = self._api("GET", f"/repos/{repo}/commits/{sha}/status")
            if r.status_code != 200:
                return ""
            payload = r.json()
            state = payload.get("state", "")
            total = payload.get("total_count", 0)
            # Only trust the combined-status verdict when at least one legacy
            # commit-status was reported. Repos that use GitHub Actions only
            # return state="pending" with total_count=0, which would otherwise
            # mask all-green check-runs.
            if total > 0:
                if state == "success":
                    return "passed"
                if state == "failure" or state == "error":
                    return "failed"
                if state == "pending":
                    return "pending"
            # Also check check-runs (GitHub Actions use this instead of status)
            cr = self._api("GET", f"/repos/{repo}/commits/{sha}/check-runs",
                           params={"per_page": 100})
            if cr.status_code == 200:
                runs = cr.json().get("check_runs", [])
                if runs:
                    conclusions = {r.get("conclusion") or r.get("status", "") for r in runs}
                    if "failure" in conclusions or "timed_out" in conclusions:
                        return "failed"
                    if all(c in ("success", "neutral", "skipped") for c in conclusions if c):
                        return "passed"
                    return "pending"
        except (httpx.HTTPError, json.JSONDecodeError):
            pass
        return ""

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
        for pr_num, sha in sha_map.items():
            ci_statuses[pr_num] = self._fetch_ci_status(repo, sha)

        results = []
        for pr in data:
            author = pr.get("user", {})
            author_login = author.get("login", "") if isinstance(author, dict) else str(author)

            labels = [l.get("name", "") for l in (pr.get("labels") or [])]
            reviewers = [r.get("login", "") for r in (pr.get("requested_reviewers") or [])
                         if isinstance(r, dict)]

            # mergeable/merge state require individual PR fetch — use what's available
            mergeable = pr.get("mergeable")
            merge_state = (pr.get("mergeable_state") or "").upper()
            has_conflicts = mergeable is False
            rebase_needed = merge_state == "BEHIND" or has_conflicts

            pr_num = str(pr.get("number", ""))
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
                additions=pr.get("additions", 0),
                deletions=pr.get("deletions", 0),
                needs_rebase=rebase_needed,
                has_conflicts=has_conflicts,
            ))
        return results

    def list_merged_branches(self, repo: str) -> set[str]:
        try:
            r = self._api("GET", f"/repos/{repo}/pulls", params={
                "state": "closed",
                "per_page": 100,
                "sort": "updated",
                "direction": "desc",
            })
            if r.status_code != 200:
                logger.debug("GitHub list_merged_branches %s: HTTP %d", repo, r.status_code)
                return set()
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug("GitHub list_merged_branches failed for %s: %s", repo, exc)
            return set()

        return {
            pr.get("head", {}).get("ref", "")
            for pr in data
            if pr.get("merged_at") and pr.get("head", {}).get("ref")
        }

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
            if r.status_code not in (200, 201):
                logger.warning("GitHub create_review failed: HTTP %d %s",
                               r.status_code, r.text[:200])
                return None
            pr = r.json()
            pr_number = str(pr.get("number", ""))
            return self.get_review(repo, pr_number)
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
                # Delete source branch
                pr = self._api("GET", f"/repos/{repo}/pulls/{review_id}")
                if pr.status_code == 200:
                    branch = pr.json().get("head", {}).get("ref", "")
                    if branch:
                        self._api("DELETE", f"/repos/{repo}/git/refs/heads/{branch}")
                return True, "PR merged successfully"
            return False, f"Merge failed: HTTP {r.status_code} {r.text[:300]}"
        except httpx.HTTPError as exc:
            return False, f"Merge failed: {exc}"

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
        encoded = self._project_path(repo)
        try:
            r = self._api("GET", f"/projects/{encoded}/merge_requests", params={
                "state": "merged",
                "per_page": 100,
                "order_by": "updated_at",
                "sort": "desc",
            })
            if r.status_code != 200:
                logger.debug("GitLab list_merged_branches %s: HTTP %d", repo, r.status_code)
                return set()
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.debug("GitLab list_merged_branches failed for %s: %s", repo, exc)
            return set()

        return {mr.get("source_branch", "") for mr in data if mr.get("source_branch")}

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
            r = self._api("PUT", f"/projects/{encoded}/merge_requests/{review_id}/merge",
                          json={
                              "squash": True,
                              "should_remove_source_branch": True,
                          })
            if r.status_code == 200:
                return True, "MR merged successfully"
            return False, f"Merge failed: HTTP {r.status_code} {r.text[:300]}"
        except httpx.HTTPError as exc:
            return False, f"Merge failed: {exc}"

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

        for review in reviews:
            results.append({
                "project_id": project.id,
                "project_name": project.name,
                "provider": provider.provider_name(),
                "review": review.to_dict(),
            })

    return results
