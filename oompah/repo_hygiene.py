"""Repository hygiene health thresholds and categorization."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class WorktreeCategory(str, Enum):
    """Categorization of worktrees by their retention rationale."""

    ACTIVE = "active"  # Currently running agent
    DIRTY = "dirty"  # Has uncommitted changes or unsynced commits
    UNMERGED = "unmerged"  # Terminal state but unmerged work
    TERMINAL_PROTECTED = "terminal_protected"  # Terminal state, merged, kept for audit
    SHARED_OWNER = "shared_owner"  # Shared or non-project-owned worktree
    SAFELY_PRUNABLE = "safely_prunable"  # Terminal, merged, no retention reason


class BranchCategory(str, Enum):
    """Categorization of branches by their retention rationale."""

    ACTIVE = "active"  # Referenced by active worktree
    DIRTY = "dirty"  # Has unpushed commits
    UNMERGED = "unmerged"  # Not merged to default branch
    TERMINAL_PROTECTED = "terminal_protected"  # Merged but kept for audit
    SHARED_OWNER = "shared_owner"  # Non-project-owned branch
    SAFELY_PRUNABLE = "safely_prunable"  # Merged, no retention reason


@dataclass
class WorktreeInventory:
    """Inventory of worktrees by category."""

    active: int = 0
    dirty: int = 0
    unmerged: int = 0
    terminal_protected: int = 0
    shared_owner: int = 0
    safely_prunable: int = 0

    def total(self) -> int:
        """Return total worktree count."""
        return (
            self.active
            + self.dirty
            + self.unmerged
            + self.terminal_protected
            + self.shared_owner
            + self.safely_prunable
        )

    def healthy_retained(self) -> int:
        """Return count of retained worktrees with justification."""
        return (
            self.active
            + self.dirty
            + self.unmerged
            + self.terminal_protected
            + self.shared_owner
        )

    def to_dict(self) -> dict[str, Any]:
        """Return as dictionary."""
        return asdict(self)


@dataclass
class BranchInventory:
    """Inventory of branches by category (local and remote)."""

    active: int = 0
    dirty: int = 0
    unmerged: int = 0
    terminal_protected: int = 0
    shared_owner: int = 0
    safely_prunable: int = 0

    def total(self) -> int:
        """Return total branch count."""
        return (
            self.active
            + self.dirty
            + self.unmerged
            + self.terminal_protected
            + self.shared_owner
            + self.safely_prunable
        )

    def healthy_retained(self) -> int:
        """Return count of retained branches with justification."""
        return (
            self.active
            + self.dirty
            + self.unmerged
            + self.terminal_protected
            + self.shared_owner
        )

    def to_dict(self) -> dict[str, Any]:
        """Return as dictionary."""
        return asdict(self)


@dataclass
class OverdueArtifact:
    """Track an artifact that exceeded its safe-to-prune age threshold."""

    artifact_type: str  # "worktree" or "branch"
    identifier: str  # worktree path or branch name
    category: str  # WorktreeCategory or BranchCategory value
    age_seconds: int  # Time since terminal state
    threshold_seconds: int  # Configured age threshold for safe pruning
    project_id: str | None = None
    task_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return as dictionary."""
        return asdict(self)


@dataclass
class RepoHygieneHealth:
    """Overall repository hygiene health status."""

    # Inventory counts
    worktrees: WorktreeInventory = field(default_factory=WorktreeInventory)
    branches_local: BranchInventory = field(default_factory=BranchInventory)
    branches_remote: BranchInventory = field(default_factory=BranchInventory)

    # Overdue safely-prunable artifacts requiring action
    overdue_artifacts: list[OverdueArtifact] = field(default_factory=list)

    # Cleanup errors from last run
    cleanup_errors: list[str] = field(default_factory=list)

    # Health status
    is_healthy: bool = True
    last_evaluated_at: float = 0.0

    # Summary for alerts
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return as dictionary, suitable for JSON serialization."""
        return {
            "worktrees": self.worktrees.to_dict(),
            "branches_local": self.branches_local.to_dict(),
            "branches_remote": self.branches_remote.to_dict(),
            "overdue_artifacts": [a.to_dict() for a in self.overdue_artifacts],
            "cleanup_errors": self.cleanup_errors,
            "is_healthy": self.is_healthy,
            "last_evaluated_at": self.last_evaluated_at,
            "summary": self.summary,
        }


class HealthThresholds:
    """Configuration for repository hygiene health thresholds."""

    def __init__(
        self,
        *,
        safely_prunable_age_seconds: int = 604800,  # 7 days
        safely_prunable_count_warning: int = 10,
        safely_prunable_count_critical: int = 50,
        cleanup_error_threshold: int = 3,  # Alert after 3 consecutive errors
    ):
        """Initialize thresholds.

        Args:
            safely_prunable_age_seconds: Seconds before a safely-prunable artifact
                is considered overdue for cleanup. Default: 7 days (604800s).
            safely_prunable_count_warning: Count threshold for warning alerts.
            safely_prunable_count_critical: Count threshold for critical alerts.
            cleanup_error_threshold: Number of consecutive cleanup errors before alert.
        """
        self.safely_prunable_age_seconds = safely_prunable_age_seconds
        self.safely_prunable_count_warning = safely_prunable_count_warning
        self.safely_prunable_count_critical = safely_prunable_count_critical
        self.cleanup_error_threshold = cleanup_error_threshold

    def evaluate_health(
        self,
        health: RepoHygieneHealth,
    ) -> tuple[bool, str]:
        """Evaluate whether health meets thresholds.

        Returns:
            (is_healthy, summary_message)
        """
        issues = []

        # Check for overdue artifacts
        if health.overdue_artifacts:
            issue = (
                f"{len(health.overdue_artifacts)} safely-prunable "
                f"{'artifact' if len(health.overdue_artifacts) == 1 else 'artifacts'} "
                f"overdue for cleanup"
            )
            issues.append(issue)

        # Check safely-prunable counts
        total_safely_prunable = (
            health.worktrees.safely_prunable + health.branches_local.safely_prunable
        )
        if total_safely_prunable >= self.safely_prunable_count_critical:
            issue = (
                f"{total_safely_prunable} safely-prunable artifacts "
                f"exceeds critical threshold ({self.safely_prunable_count_critical})"
            )
            issues.append(issue)
        elif total_safely_prunable >= self.safely_prunable_count_warning:
            issue = (
                f"{total_safely_prunable} safely-prunable artifacts "
                f"exceeds warning threshold ({self.safely_prunable_count_warning})"
            )
            issues.append(issue)

        # Check for cleanup errors
        if health.cleanup_errors:
            issues.append(f"{len(health.cleanup_errors)} recent cleanup errors")

        if issues:
            summary = "Repository hygiene issues: " + "; ".join(issues)
            return False, summary

        # Healthy if no issues and all retained artifacts have justification
        total_worktrees = health.worktrees.total()
        total_branches = health.branches_local.total() + health.branches_remote.total()

        if total_worktrees == 0 and total_branches == 0:
            summary = "Repository hygiene healthy: no worktrees or branches"
            return True, summary

        healthy_worktrees = health.worktrees.healthy_retained()
        healthy_branches = (
            health.branches_local.healthy_retained()
            + health.branches_remote.healthy_retained()
        )

        if (
            total_worktrees > 0
            and healthy_worktrees != total_worktrees
        ):
            summary = (
                f"Repository hygiene healthy: "
                f"{healthy_worktrees}/{total_worktrees} retained worktrees have justification"
            )
        else:
            summary = "Repository hygiene healthy"

        return True, summary
