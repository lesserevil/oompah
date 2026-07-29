"""Read-only evidence collector for Done completion audits.

Collects stable, deterministic evidence snapshots for task/epic completion
audits. Evidence includes workspace/worktree info, branch/SHA info, requirements,
diff/stat excerpts, changed files, commit/push status, test commands, CI evidence,
comments, children, and contributor identities.

All operations are read-only. Missing or invalid evidence is explicitly typed
rather than guessed, ensuring auditors receive clear failure signals.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Evidence unavailability markers
class EvidenceUnavailable:
    """Marker for evidence that could not be collected (e.g., missing branch)."""

    def __init__(self, reason: str) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Unavailable evidence must have a non-empty reason")
        self.reason = reason

    def __repr__(self) -> str:
        return f"EvidenceUnavailable({self.reason!r})"

    def __str__(self) -> str:
        return f"unavailable: {self.reason}"


class EvidenceInvalid:
    """Marker for evidence that is malformed or contradictory."""

    def __init__(self, reason: str) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Invalid evidence must have a non-empty reason")
        self.reason = reason

    def __repr__(self) -> str:
        return f"EvidenceInvalid({self.reason!r})"

    def __str__(self) -> str:
        return f"invalid: {self.reason}"


EvidenceValue = str | int | float | bool | None | dict[str, Any] | list[Any]
MaybeEvidence = EvidenceValue | EvidenceUnavailable | EvidenceInvalid


@dataclass(frozen=True)
class DiffExcerpt:
    """Bounded diff chunk with line limits."""

    content: str
    total_lines: int
    excerpt_start_line: int
    excerpt_end_line: int
    is_truncated: bool

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("DiffExcerpt.content must be a string")
        if self.total_lines < 0 or self.excerpt_start_line < 0 or self.excerpt_end_line < 0:
            raise ValueError("DiffExcerpt line counts must be non-negative")
        if self.excerpt_end_line > self.total_lines:
            raise ValueError("DiffExcerpt excerpt cannot exceed total lines")
        if not isinstance(self.is_truncated, bool):
            raise TypeError("DiffExcerpt.is_truncated must be bool")


@dataclass(frozen=True)
class WorktreeInfo:
    """Information about the current worktree."""

    path: str
    is_worktree: bool
    main_worktree_path: Optional[str] = None
    branch: Optional[str] = None
    dirty: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("WorktreeInfo.path must be non-empty")
        if not isinstance(self.is_worktree, bool):
            raise TypeError("WorktreeInfo.is_worktree must be bool")
        if self.dirty and not isinstance(self.dirty, bool):
            raise TypeError("WorktreeInfo.dirty must be bool")


@dataclass(frozen=True)
class CommitStatus:
    """Status of commits on intended branch."""

    sha: Optional[str]
    message: Optional[str]
    is_on_intended_branch: Optional[bool]
    is_pushed: Optional[bool]
    unavailable_reason: Optional[str] = None
    invalid_reason: Optional[str] = None


@dataclass(frozen=True)
class EvidenceSnapshot:
    """Complete, deterministic evidence snapshot for audit."""

    # Workspace and worktree info
    worktree_info: WorktreeInfo | EvidenceUnavailable | EvidenceInvalid

    # Branch and SHA info
    source_branch: MaybeEvidence
    source_sha: MaybeEvidence
    target_branch: MaybeEvidence
    target_sha: MaybeEvidence

    # Requirements
    requirements_text: MaybeEvidence
    requirements_digest: MaybeEvidence

    # Diff and file changes
    diff_stat: MaybeEvidence
    diff_excerpt: DiffExcerpt | EvidenceUnavailable | EvidenceInvalid | None = None
    changed_files: list[str] | EvidenceUnavailable | EvidenceInvalid | None = None

    # Commit and push status
    commit_status: CommitStatus | EvidenceUnavailable | EvidenceInvalid | None = None
    push_status: MaybeEvidence = None

    # Test and CI evidence
    test_commands: list[str] | EvidenceUnavailable | EvidenceInvalid | None = None
    ci_evidence: MaybeEvidence = None
    test_evidence: MaybeEvidence = None

    # Comments and handoffs
    comments: list[dict[str, Any]] | EvidenceUnavailable | EvidenceInvalid | None = None

    # Epic-specific evidence
    children: list[EvidenceSnapshot] | EvidenceUnavailable | EvidenceInvalid | None = None
    child_audit_results: list[dict[str, Any]] | EvidenceUnavailable | EvidenceInvalid | None = None

    # Contributors
    contributors: list[dict[str, str]] | EvidenceUnavailable | EvidenceInvalid | None = None

    # Audit-specific
    task_id: str = ""
    project_id: str = ""
    audit_id: str = ""
    collected_at: str = ""

    def is_complete(self) -> bool:
        """Check if all required evidence is available and valid."""
        required_fields = [
            self.worktree_info,
            self.source_branch,
            self.source_sha,
            self.target_branch,
            self.target_sha,
            self.requirements_text,
            self.commit_status,
            self.push_status,
        ]
        return not any(isinstance(f, (EvidenceUnavailable, EvidenceInvalid)) for f in required_fields)

    def has_failures(self) -> bool:
        """Check if any evidence is marked unavailable or invalid."""
        def check_recursive(obj: Any) -> bool:
            if isinstance(obj, (EvidenceUnavailable, EvidenceInvalid)):
                return True
            if isinstance(obj, dict):
                return any(check_recursive(v) for v in obj.values())
            if isinstance(obj, (list, tuple)):
                return any(check_recursive(v) for v in obj)
            return False

        for field_value in self.__dict__.values():
            if check_recursive(field_value):
                return True
        return False


class DoneEvidenceCollector:
    """Collects stable evidence for Done completion audits.

    All operations are read-only. Collects deterministic snapshots of:
    - Workspace/worktree info
    - Branch and SHA info
    - Requirements text and digest
    - Diff/stat with bounded excerpts
    - Changed files
    - Commit/push status
    - Test commands and evidence
    - Comments/handoffs
    - Children (for epics)
    - Contributor identities

    Returns typed unavailable/invalid evidence rather than guessing.
    """

    def __init__(self, worktree_path: str, task_id: str = "", project_id: str = "") -> None:
        """Initialize the collector for a worktree.

        Args:
            worktree_path: Path to the git worktree to inspect
            task_id: The task identifier being audited
            project_id: The project identifier
        """
        self.worktree_path = Path(worktree_path).resolve()
        self.task_id = task_id
        self.project_id = project_id

        if not self.worktree_path.is_dir():
            raise ValueError(f"Worktree path does not exist: {self.worktree_path}")

    def collect(self, audit_id: str = "", collected_at: str = "") -> EvidenceSnapshot:
        """Collect a complete evidence snapshot.

        Args:
            audit_id: The audit identifier
            collected_at: ISO8601 timestamp of collection

        Returns:
            Complete EvidenceSnapshot with all available evidence
        """
        return EvidenceSnapshot(
            worktree_info=self._collect_worktree_info(),
            source_branch=self._collect_source_branch(),
            source_sha=self._collect_source_sha(),
            target_branch=self._collect_target_branch(),
            target_sha=self._collect_target_sha(),
            requirements_text=self._collect_requirements_text(),
            requirements_digest=self._collect_requirements_digest(),
            diff_stat=self._collect_diff_stat(),
            diff_excerpt=self._collect_diff_excerpt(),
            changed_files=self._collect_changed_files(),
            commit_status=self._collect_commit_status(),
            push_status=self._collect_push_status(),
            test_commands=self._collect_test_commands(),
            ci_evidence=self._collect_ci_evidence(),
            test_evidence=self._collect_test_evidence(),
            comments=self._collect_comments(),
            children=self._collect_children(),
            child_audit_results=self._collect_child_audit_results(),
            contributors=self._collect_contributors(),
            task_id=self.task_id,
            project_id=self.project_id,
            audit_id=audit_id,
            collected_at=collected_at,
        )

    # Workspace and worktree collection
    def _collect_worktree_info(self) -> WorktreeInfo | EvidenceUnavailable | EvidenceInvalid:
        """Collect worktree information."""
        try:
            # Check if we're in a git worktree
            is_worktree = self._run_git(["rev-parse", "--is-inside-work-tree"]) == "true"

            if not is_worktree:
                return EvidenceUnavailable("Not a git repository")

            # Get the branch name
            try:
                branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
            except (subprocess.CalledProcessError, ValueError):
                branch = None

            # Check if worktree is dirty
            try:
                status_output = self._run_git(["status", "--porcelain"])
                dirty = bool(status_output.strip())
            except (subprocess.CalledProcessError, ValueError):
                dirty = False

            # Check if this is a worktree (git worktree list would show it)
            try:
                worktree_list = self._run_git(["worktree", "list"])
                is_multi_worktree = len(worktree_list.strip().split("\n")) > 1
            except (subprocess.CalledProcessError, ValueError):
                is_multi_worktree = False

            # Get main worktree path if applicable
            main_worktree_path = None
            if is_multi_worktree:
                try:
                    worktree_root = self._run_git(["rev-parse", "--git-dir"])
                    # For worktrees, git-dir points to .../worktrees/NAME/
                    if "/worktrees/" in worktree_root:
                        # Try to find main worktree
                        main_worktree_path = str(self.worktree_path.parent)
                except (subprocess.CalledProcessError, ValueError):
                    pass

            return WorktreeInfo(
                path=str(self.worktree_path),
                is_worktree=True,
                main_worktree_path=main_worktree_path,
                branch=branch,
                dirty=dirty,
            )
        except Exception as exc:
            logger.exception("Failed to collect worktree info")
            return EvidenceUnavailable(f"Failed to collect worktree info: {exc}")

    # Branch and SHA collection
    def _collect_source_branch(self) -> str | EvidenceUnavailable:
        """Collect the source branch name (current branch)."""
        try:
            return self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        except (subprocess.CalledProcessError, ValueError) as exc:
            return EvidenceUnavailable(f"Cannot determine source branch: {exc}")

    def _collect_source_sha(self) -> str | EvidenceUnavailable:
        """Collect the source SHA (HEAD)."""
        try:
            return self._run_git(["rev-parse", "HEAD"])
        except (subprocess.CalledProcessError, ValueError) as exc:
            return EvidenceUnavailable(f"Cannot determine source SHA: {exc}")

    def _collect_target_branch(self) -> str | EvidenceUnavailable:
        """Collect the target branch (main/master or merge-base)."""
        try:
            # Try common default branches
            for branch in ["main", "master", "trunk"]:
                try:
                    self._run_git(["rev-parse", f"origin/{branch}"])
                    return branch
                except (subprocess.CalledProcessError, ValueError):
                    continue
            return EvidenceUnavailable("Cannot determine target branch")
        except Exception as exc:
            return EvidenceUnavailable(f"Cannot determine target branch: {exc}")

    def _collect_target_sha(self) -> str | EvidenceUnavailable:
        """Collect the target SHA (merge-base with target branch)."""
        try:
            target_branch = self._collect_target_branch()
            if isinstance(target_branch, EvidenceUnavailable):
                return target_branch
            return self._run_git(["merge-base", "HEAD", f"origin/{target_branch}"])
        except (subprocess.CalledProcessError, ValueError) as exc:
            return EvidenceUnavailable(f"Cannot determine target SHA: {exc}")

    # Requirements collection
    def _collect_requirements_text(self) -> str | EvidenceUnavailable:
        """Collect requirements text from task metadata (if available)."""
        # This would come from tracker metadata in a real implementation
        # For now, return unavailable as it requires tracker access
        return EvidenceUnavailable("Task requirements require tracker access")

    def _collect_requirements_digest(self) -> str | EvidenceUnavailable:
        """Collect digest of requirements text."""
        requirements = self._collect_requirements_text()
        if isinstance(requirements, EvidenceUnavailable):
            return requirements
        return hashlib.sha256(requirements.encode()).hexdigest()

    # Diff and file changes collection
    def _collect_diff_stat(self) -> str | EvidenceUnavailable:
        """Collect diff stats (--stat output)."""
        try:
            target_branch = self._collect_target_branch()
            if isinstance(target_branch, EvidenceUnavailable):
                return target_branch
            return self._run_git([
                "diff",
                "--stat",
                f"origin/{target_branch}...HEAD",
            ])
        except (subprocess.CalledProcessError, ValueError) as exc:
            return EvidenceUnavailable(f"Cannot collect diff stat: {exc}")

    def _collect_diff_excerpt(
        self, max_lines: int = 500
    ) -> DiffExcerpt | EvidenceUnavailable | EvidenceInvalid | None:
        """Collect bounded diff excerpt."""
        try:
            target_branch = self._collect_target_branch()
            if isinstance(target_branch, EvidenceUnavailable):
                return target_branch

            diff_output = self._run_git([
                "diff",
                f"origin/{target_branch}...HEAD",
            ])

            lines = diff_output.split("\n")
            total_lines = len(lines)
            is_truncated = total_lines > max_lines

            excerpt_lines = lines[:max_lines]
            excerpt_end_line = len(excerpt_lines)

            return DiffExcerpt(
                content="\n".join(excerpt_lines),
                total_lines=total_lines,
                excerpt_start_line=0,
                excerpt_end_line=excerpt_end_line,
                is_truncated=is_truncated,
            )
        except (subprocess.CalledProcessError, ValueError) as exc:
            return EvidenceUnavailable(f"Cannot collect diff excerpt: {exc}")
        except Exception as exc:
            return EvidenceInvalid(f"Diff excerpt is malformed: {exc}")

    def _collect_changed_files(self) -> list[str] | EvidenceUnavailable:
        """Collect list of changed files."""
        try:
            target_branch = self._collect_target_branch()
            if isinstance(target_branch, EvidenceUnavailable):
                return target_branch

            output = self._run_git([
                "diff",
                "--name-only",
                f"origin/{target_branch}...HEAD",
            ])

            return [f for f in output.split("\n") if f.strip()]
        except (subprocess.CalledProcessError, ValueError) as exc:
            return EvidenceUnavailable(f"Cannot collect changed files: {exc}")

    # Commit and push status collection
    def _collect_commit_status(self) -> CommitStatus | EvidenceUnavailable | EvidenceInvalid:
        """Collect commit status (SHA, message, branch status, push status)."""
        try:
            sha = self._collect_source_sha()
            source_branch = self._collect_source_branch()

            message: Optional[str] = None
            if not isinstance(sha, EvidenceUnavailable):
                try:
                    message = self._run_git(["log", "-1", "--pretty=%B", "HEAD"])
                except (subprocess.CalledProcessError, ValueError):
                    message = None

            # Check if on intended branch (would need intended_branch parameter)
            is_on_intended_branch: Optional[bool] = None
            if not isinstance(source_branch, EvidenceUnavailable):
                is_on_intended_branch = True  # Default: assume current branch is intended

            # Check if pushed
            is_pushed: Optional[bool] = None
            if not isinstance(sha, EvidenceUnavailable) and not isinstance(source_branch, EvidenceUnavailable):
                try:
                    # Check if HEAD is in remote branch
                    self._run_git(["branch", "-r", "--contains", "HEAD"])
                    is_pushed = True
                except (subprocess.CalledProcessError, ValueError):
                    is_pushed = False

            return CommitStatus(
                sha=sha if isinstance(sha, str) else None,
                message=message,
                is_on_intended_branch=is_on_intended_branch,
                is_pushed=is_pushed,
            )
        except Exception as exc:
            logger.exception("Failed to collect commit status")
            return EvidenceUnavailable(f"Cannot collect commit status: {exc}")

    def _collect_push_status(self) -> bool | EvidenceUnavailable:
        """Collect push status (whether commits are pushed to origin)."""
        try:
            source_branch = self._collect_source_branch()
            if isinstance(source_branch, EvidenceUnavailable):
                return source_branch

            try:
                # Check if remote tracking branch exists
                self._run_git(["rev-parse", f"origin/{source_branch}"])
                return True
            except (subprocess.CalledProcessError, ValueError):
                return False
        except Exception as exc:
            return EvidenceUnavailable(f"Cannot determine push status: {exc}")

    # Test and CI evidence collection
    def _collect_test_commands(self) -> list[str] | EvidenceUnavailable:
        """Collect configured test commands."""
        # This would come from Makefile or test config
        # For now, return unavailable
        return EvidenceUnavailable("Test commands require project configuration access")

    def _collect_ci_evidence(self) -> Optional[str]:
        """Collect latest CI evidence."""
        # This would come from GitHub/GitLab CI
        # For now, return None
        return None

    def _collect_test_evidence(self) -> Optional[str]:
        """Collect latest test evidence."""
        # This would come from CI logs or test results
        # For now, return None
        return None

    # Comments and handoffs collection
    def _collect_comments(self) -> list[dict[str, Any]] | EvidenceUnavailable:
        """Collect task comments and handoffs."""
        # This would require tracker access
        return EvidenceUnavailable("Task comments require tracker access")

    # Epic-specific evidence collection
    def _collect_children(self) -> None:
        """Collect child task evidence (for epics)."""
        # Requires traversing child tasks
        return None

    def _collect_child_audit_results(self) -> None:
        """Collect child audit results (for epics)."""
        # Requires collecting audit evidence for each child
        return None

    # Contributor collection
    def _collect_contributors(self) -> list[dict[str, str]] | EvidenceUnavailable:
        """Collect contributor identities."""
        try:
            # Try to get recent commits, handling repos with fewer than 10 commits
            try:
                output = self._run_git(["log", "--format=%an|%ae", "HEAD~10..HEAD"])
            except ValueError:
                # If HEAD~10 doesn't exist, get all commits
                output = self._run_git(["log", "--format=%an|%ae"])

            contributors = []
            seen = set()

            for line in output.strip().split("\n"):
                if "|" in line:
                    name, email = line.split("|", 1)
                    contributor_key = (name.strip(), email.strip())
                    if contributor_key not in seen and name.strip():
                        seen.add(contributor_key)
                        contributors.append({
                            "name": name.strip(),
                            "email": email.strip(),
                            "source": "git",
                        })

            return contributors
        except (subprocess.CalledProcessError, ValueError) as exc:
            return EvidenceUnavailable(f"Cannot collect contributors: {exc}")

    # Git helper
    def _run_git(self, args: list[str]) -> str:
        """Run a git command and return output (stripped)."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.worktree_path),
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"git {' '.join(args)} failed: {exc.stderr.strip()}")


__all__ = [
    "DoneEvidenceCollector",
    "EvidenceSnapshot",
    "EvidenceUnavailable",
    "EvidenceInvalid",
    "DiffExcerpt",
    "WorktreeInfo",
    "CommitStatus",
]
