"""Source control management abstraction.

Provides a unified interface over GitHub and GitLab for operations like
listing pull/merge requests. Implementations use CLI tools (gh, glab)
for auth and API access.
"""

from __future__ import annotations

import json
import logging
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


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
        """Check if the CLI tool is installed and authenticated."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g. 'github', 'gitlab')."""
        ...


class GitHubProvider(SCMProvider):
    """GitHub implementation using the `gh` CLI."""

    def provider_name(self) -> str:
        return "github"

    def is_available(self) -> bool:
        try:
            r = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def list_open_reviews(self, repo: str) -> list[ReviewRequest]:
        try:
            r = subprocess.run(
                [
                    "gh", "pr", "list",
                    "--repo", repo,
                    "--state", "open",
                    "--json", "number,title,url,author,headRefName,baseRefName,"
                              "createdAt,updatedAt,body,labels,isDraft,"
                              "reviewRequests,additions,deletions,statusCheckRollup,"
                              "mergeStateStatus,mergeable",
                    "--limit", "100",
                ],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                logger.warning("gh pr list failed for %s: %s", repo, r.stderr.strip()[:200])
                return []
            data = json.loads(r.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            logger.warning("GitHub list_open_reviews failed for %s: %s", repo, exc)
            return []

        results = []
        for pr in data:
            # Extract CI status from statusCheckRollup
            ci_status = ""
            checks = pr.get("statusCheckRollup") or []
            if checks:
                states = {c.get("conclusion") or c.get("state", "") for c in checks}
                if "FAILURE" in states or "failure" in states:
                    ci_status = "failed"
                elif all(s in ("SUCCESS", "success", "NEUTRAL", "neutral", "SKIPPED", "skipped") for s in states if s):
                    ci_status = "passed"
                else:
                    ci_status = "pending"

            author = pr.get("author", {})
            author_login = author.get("login", "") if isinstance(author, dict) else str(author)

            labels = [l.get("name", "") for l in (pr.get("labels") or [])]
            reviewers = [r.get("login", "") for r in (pr.get("reviewRequests") or [])
                         if isinstance(r, dict)]

            # Detect if rebase is needed or has conflicts
            merge_state = pr.get("mergeStateStatus", "").upper()
            mergeable = pr.get("mergeable", "")
            has_conflicts = mergeable == "CONFLICTING"
            rebase_needed = merge_state == "BEHIND" or has_conflicts

            results.append(ReviewRequest(
                id=str(pr.get("number", "")),
                title=pr.get("title", ""),
                url=pr.get("url", ""),
                author=author_login,
                state="open",
                source_branch=pr.get("headRefName", ""),
                target_branch=pr.get("baseRefName", ""),
                created_at=pr.get("createdAt", ""),
                updated_at=pr.get("updatedAt", ""),
                description=_truncate(pr.get("body", ""), 500),
                labels=labels,
                draft=pr.get("isDraft", False),
                reviewers=reviewers,
                ci_status=ci_status,
                additions=pr.get("additions", 0),
                deletions=pr.get("deletions", 0),
                needs_rebase=rebase_needed,
                has_conflicts=has_conflicts,
            ))
        return results

    def list_merged_branches(self, repo: str) -> set[str]:
        try:
            r = subprocess.run(
                [
                    "gh", "pr", "list",
                    "--repo", repo,
                    "--state", "merged",
                    "--json", "headRefName",
                    "--limit", "100",
                ],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                logger.debug("gh pr list --state merged failed for %s: %s", repo, r.stderr.strip()[:200])
                return set()
            data = json.loads(r.stdout)
            return {pr.get("headRefName", "") for pr in data if pr.get("headRefName")}
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            logger.debug("GitHub list_merged_branches failed for %s: %s", repo, exc)
            return set()

    def get_review(self, repo: str, review_id: str) -> ReviewRequest | None:
        try:
            r = subprocess.run(
                [
                    "gh", "pr", "view", review_id,
                    "--repo", repo,
                    "--json", "number,title,url,author,headRefName,baseRefName,"
                              "createdAt,updatedAt,body,labels,isDraft,"
                              "reviewRequests,additions,deletions",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                return None
            pr = json.loads(r.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return None

        author = pr.get("author", {})
        author_login = author.get("login", "") if isinstance(author, dict) else str(author)

        return ReviewRequest(
            id=str(pr.get("number", "")),
            title=pr.get("title", ""),
            url=pr.get("url", ""),
            author=author_login,
            state="open",
            source_branch=pr.get("headRefName", ""),
            target_branch=pr.get("baseRefName", ""),
            created_at=pr.get("createdAt", ""),
            updated_at=pr.get("updatedAt", ""),
            description=_truncate(pr.get("body", ""), 500),
            labels=[l.get("name", "") for l in (pr.get("labels") or [])],
            draft=pr.get("isDraft", False),
            additions=pr.get("additions", 0),
            deletions=pr.get("deletions", 0),
        )

    def create_review(
        self, repo: str, title: str, source_branch: str,
        target_branch: str = "main", description: str = "",
    ) -> ReviewRequest | None:
        cmd = [
            "gh", "pr", "create",
            "--repo", repo,
            "--title", title,
            "--head", source_branch,
            "--base", target_branch,
            "--body", description,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                logger.warning("gh pr create failed: %s", r.stderr.strip()[:200])
                return None
            # gh pr create outputs the URL
            url = r.stdout.strip()
            # Fetch the created PR to return full data
            pr_number = url.rstrip("/").rsplit("/", 1)[-1]
            return self.get_review(repo, pr_number)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("GitHub create_review failed: %s", exc)
            return None


    def rebase_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        # gh doesn't have a direct rebase command, but has update-branch
        # which merges or rebases the target into the PR branch.
        # For a true rebase, we use the GitHub API directly via gh api.
        try:
            # GitHub's "update branch" API with rebase
            r = subprocess.run(
                [
                    "gh", "api",
                    f"repos/{repo}/pulls/{review_id}/update-branch",
                    "--method", "PUT",
                    "--field", "update_method=rebase",
                ],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return True, "Rebase initiated successfully"
            stderr = r.stderr.strip()[:300]
            # If rebase fails due to conflicts, report clearly
            if "merge conflict" in stderr.lower() or "cannot be rebased" in stderr.lower():
                return False, "Rebase failed: merge conflicts require manual resolution"
            return False, f"Rebase failed: {stderr}"
        except FileNotFoundError:
            return False, "gh CLI not found"
        except subprocess.TimeoutExpired:
            return False, "Rebase timed out"

    def merge_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        try:
            r = subprocess.run(
                ["gh", "pr", "merge", review_id, "--repo", repo,
                 "--squash", "--delete-branch"],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return True, "PR merged successfully"
            return False, f"Merge failed: {r.stderr.strip()[:300]}"
        except FileNotFoundError:
            return False, "gh CLI not found"
        except subprocess.TimeoutExpired:
            return False, "Merge timed out"

    def needs_rebase(self, repo: str, review_id: str) -> bool:
        try:
            r = subprocess.run(
                [
                    "gh", "pr", "view", review_id,
                    "--repo", repo,
                    "--json", "mergeStateStatus,mergeable",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                return False
            data = json.loads(r.stdout)
            merge_state = data.get("mergeStateStatus", "").upper()
            mergeable = data.get("mergeable", "")
            return merge_state == "BEHIND" or mergeable == "CONFLICTING"
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return False


class GitLabProvider(SCMProvider):
    """GitLab implementation using the `glab` CLI."""

    def __init__(self, hostname: str = "gitlab.com"):
        self._hostname = hostname

    def provider_name(self) -> str:
        return "gitlab"

    def _glab_repo_arg(self, repo: str) -> str:
        """Return the fully-qualified repo arg for glab (hostname/owner/project)."""
        if "/" in repo and not repo.startswith(self._hostname):
            return f"{self._hostname}/{repo}"
        return repo

    def is_available(self) -> bool:
        try:
            r = subprocess.run(
                ["glab", "auth", "status", "--hostname", self._hostname],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def list_open_reviews(self, repo: str) -> list[ReviewRequest]:
        try:
            r = subprocess.run(
                [
                    "glab", "mr", "list",
                    "--repo", self._glab_repo_arg(repo),
                    "--output", "json",
                    "--per-page", "100",
                ],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                logger.warning("glab mr list failed for %s: %s", repo, r.stderr.strip()[:200])
                return []
            data = json.loads(r.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
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

            # CI status from head_pipeline — glab mr list often returns None,
            # so fall back to glab mr view for individual MR pipeline data
            ci_status = ""
            pipeline = mr.get("head_pipeline") or {}
            if not pipeline:
                # Enrich with glab mr view which includes pipeline info
                mr_id = str(mr.get("iid", mr.get("id", "")))
                try:
                    vr = subprocess.run(
                        ["glab", "mr", "view", mr_id,
                         "--repo", self._glab_repo_arg(repo),
                         "--output", "json"],
                        capture_output=True, text=True, timeout=15,
                    )
                    if vr.returncode == 0:
                        detail = json.loads(vr.stdout)
                        pipeline = detail.get("head_pipeline") or {}
                except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
                    pass
            if pipeline:
                ps = pipeline.get("status", "").lower()
                if ps == "success":
                    ci_status = "passed"
                elif ps in ("failed", "canceled"):
                    ci_status = "failed"
                elif ps in ("running", "pending", "created"):
                    ci_status = "pending"

            # Detect if rebase is needed or has conflicts
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
                description=_truncate(mr.get("description", ""), 500),
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
        try:
            r = subprocess.run(
                [
                    "glab", "mr", "list",
                    "--repo", self._glab_repo_arg(repo),
                    "--state", "merged",
                    "--output", "json",
                    "--per-page", "100",
                ],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                logger.debug("glab mr list --state merged failed for %s: %s", repo, r.stderr.strip()[:200])
                return set()
            data = json.loads(r.stdout)
            return {mr.get("source_branch", "") for mr in data if mr.get("source_branch")}
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            logger.debug("GitLab list_merged_branches failed for %s: %s", repo, exc)
            return set()

    def get_review(self, repo: str, review_id: str) -> ReviewRequest | None:
        try:
            r = subprocess.run(
                [
                    "glab", "mr", "view", review_id,
                    "--repo", self._glab_repo_arg(repo),
                    "--output", "json",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                return None
            mr = json.loads(r.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
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
            description=_truncate(mr.get("description", ""), 500),
            labels=mr.get("labels") or [],
            draft=mr.get("draft", False) or mr.get("work_in_progress", False),
        )

    def create_review(
        self, repo: str, title: str, source_branch: str,
        target_branch: str = "main", description: str = "",
    ) -> ReviewRequest | None:
        cmd = [
            "glab", "mr", "create",
            "--repo", self._glab_repo_arg(repo),
            "--title", title,
            "--source-branch", source_branch,
            "--target-branch", target_branch,
            "--description", description,
            "--yes",
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                logger.warning("glab mr create failed: %s", r.stderr.strip()[:200])
                return None
            # Parse MR URL from output
            for line in r.stdout.strip().splitlines():
                if "http" in line:
                    url = line.strip()
                    mr_id = url.rstrip("/").rsplit("/", 1)[-1]
                    return self.get_review(repo, mr_id)
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("GitLab create_review failed: %s", exc)
            return None

    def rebase_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        try:
            # glab mr rebase triggers a server-side rebase on GitLab
            r = subprocess.run(
                ["glab", "mr", "rebase", review_id, "--repo", self._glab_repo_arg(repo)],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0:
                return True, "Rebase initiated successfully"
            stderr = r.stderr.strip()[:300]
            if "conflict" in stderr.lower():
                return False, "Rebase failed: merge conflicts require manual resolution"
            return False, f"Rebase failed: {stderr}"
        except FileNotFoundError:
            return False, "glab CLI not found"
        except subprocess.TimeoutExpired:
            return False, "Rebase timed out"

    def merge_review(self, repo: str, review_id: str) -> tuple[bool, str]:
        try:
            r = subprocess.run(
                ["glab", "mr", "merge", review_id, "--repo", self._glab_repo_arg(repo),
                 "--squash", "--remove-source-branch", "--yes"],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return True, "MR merged successfully"
            return False, f"Merge failed: {r.stderr.strip()[:300]}"
        except FileNotFoundError:
            return False, "glab CLI not found"
        except subprocess.TimeoutExpired:
            return False, "Merge timed out"

    def needs_rebase(self, repo: str, review_id: str) -> bool:
        try:
            r = subprocess.run(
                ["glab", "mr", "view", review_id, "--repo", self._glab_repo_arg(repo), "--output", "json"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                return False
            mr = json.loads(r.stdout)
            # GitLab uses "has_conflicts" and "diverged_commits_count"
            if mr.get("has_conflicts", False):
                return True
            if (mr.get("diverged_commits_count") or 0) > 0:
                return True
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return False


# -- Helpers --

def _truncate(s: str, max_len: int) -> str:
    if not s:
        return ""
    if len(s) <= max_len:
        return s
    return s[:max_len - 3] + "..."


def detect_provider(repo_url: str) -> SCMProvider | None:
    """Detect the SCM provider from a repository URL.

    Returns a GitHubProvider or GitLabProvider instance, or None if
    the URL doesn't match a known pattern.
    """
    url_lower = repo_url.lower()
    if "github.com" in url_lower:
        return GitHubProvider()
    if "gitlab" in url_lower:
        # Extract hostname for non-default GitLab instances
        hostname = "gitlab.com"
        if "://" in repo_url:
            hostname = repo_url.split("://", 1)[1].split("/", 1)[0]
        elif repo_url.startswith("git@"):
            hostname = repo_url.split("@", 1)[1].split(":", 1)[0]
        return GitLabProvider(hostname=hostname)
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
        provider = detect_provider(project.repo_url)
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
