"""Tests for repository hygiene health thresholds and categorization."""

from __future__ import annotations

import unittest

from oompah.repo_hygiene import (
    BranchCategory,
    BranchInventory,
    HealthThresholds,
    OverdueArtifact,
    RepoHygieneHealth,
    WorktreeCategory,
    WorktreeInventory,
)


class TestWorktreeInventory(unittest.TestCase):
    """Test WorktreeInventory class."""

    def test_init_defaults(self) -> None:
        """Test initialization with default values."""
        inv = WorktreeInventory()
        self.assertEqual(inv.active, 0)
        self.assertEqual(inv.dirty, 0)
        self.assertEqual(inv.unmerged, 0)
        self.assertEqual(inv.terminal_protected, 0)
        self.assertEqual(inv.shared_owner, 0)
        self.assertEqual(inv.safely_prunable, 0)

    def test_total(self) -> None:
        """Test total count calculation."""
        inv = WorktreeInventory(
            active=1, dirty=2, unmerged=3, terminal_protected=4, shared_owner=5, safely_prunable=6
        )
        self.assertEqual(inv.total(), 21)

    def test_healthy_retained(self) -> None:
        """Test healthy retained count calculation."""
        inv = WorktreeInventory(
            active=1, dirty=2, unmerged=3, terminal_protected=4, shared_owner=5, safely_prunable=6
        )
        # All except safely_prunable
        self.assertEqual(inv.healthy_retained(), 15)

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        inv = WorktreeInventory(active=5, dirty=2)
        d = inv.to_dict()
        self.assertEqual(d["active"], 5)
        self.assertEqual(d["dirty"], 2)
        self.assertEqual(d["safely_prunable"], 0)


class TestBranchInventory(unittest.TestCase):
    """Test BranchInventory class."""

    def test_init_defaults(self) -> None:
        """Test initialization with default values."""
        inv = BranchInventory()
        self.assertEqual(inv.active, 0)
        self.assertEqual(inv.dirty, 0)
        self.assertEqual(inv.unmerged, 0)
        self.assertEqual(inv.terminal_protected, 0)
        self.assertEqual(inv.shared_owner, 0)
        self.assertEqual(inv.safely_prunable, 0)

    def test_total(self) -> None:
        """Test total count calculation."""
        inv = BranchInventory(
            active=1, dirty=2, unmerged=3, terminal_protected=4, shared_owner=5, safely_prunable=6
        )
        self.assertEqual(inv.total(), 21)

    def test_healthy_retained(self) -> None:
        """Test healthy retained count calculation."""
        inv = BranchInventory(
            active=1, dirty=2, unmerged=3, terminal_protected=4, shared_owner=5, safely_prunable=6
        )
        # All except safely_prunable
        self.assertEqual(inv.healthy_retained(), 15)


class TestOverdueArtifact(unittest.TestCase):
    """Test OverdueArtifact class."""

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        artifact = OverdueArtifact(
            artifact_type="worktree",
            identifier="/path/to/worktree",
            category=WorktreeCategory.SAFELY_PRUNABLE.value,
            age_seconds=864000,  # 10 days
            threshold_seconds=604800,  # 7 days
            project_id="proj-123",
            task_id="OOMPAH-100",
        )
        d = artifact.to_dict()
        self.assertEqual(d["artifact_type"], "worktree")
        self.assertEqual(d["age_seconds"], 864000)
        self.assertIsNotNone(d["project_id"])


class TestRepoHygieneHealth(unittest.TestCase):
    """Test RepoHygieneHealth class."""

    def test_init_defaults(self) -> None:
        """Test initialization with default values."""
        health = RepoHygieneHealth()
        self.assertIsInstance(health.worktrees, WorktreeInventory)
        self.assertIsInstance(health.branches_local, BranchInventory)
        self.assertIsInstance(health.branches_remote, BranchInventory)
        self.assertEqual(len(health.overdue_artifacts), 0)
        self.assertEqual(len(health.cleanup_errors), 0)
        self.assertTrue(health.is_healthy)

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        health = RepoHygieneHealth(
            is_healthy=True,
            summary="All healthy",
        )
        d = health.to_dict()
        self.assertEqual(d["summary"], "All healthy")
        self.assertTrue(d["is_healthy"])
        self.assertIn("worktrees", d)
        self.assertIn("overdue_artifacts", d)


class TestHealthThresholds(unittest.TestCase):
    """Test HealthThresholds class."""

    def test_init_defaults(self) -> None:
        """Test initialization with default values."""
        thresholds = HealthThresholds()
        self.assertEqual(thresholds.safely_prunable_age_seconds, 7 * 24 * 60 * 60)
        self.assertEqual(thresholds.safely_prunable_count_warning, 10)
        self.assertEqual(thresholds.safely_prunable_count_critical, 50)
        self.assertEqual(thresholds.cleanup_error_threshold, 3)

    def test_init_custom(self) -> None:
        """Test initialization with custom values."""
        thresholds = HealthThresholds(
            safely_prunable_age_seconds=1000,
            safely_prunable_count_warning=5,
            safely_prunable_count_critical=20,
            cleanup_error_threshold=2,
        )
        self.assertEqual(thresholds.safely_prunable_age_seconds, 1000)
        self.assertEqual(thresholds.safely_prunable_count_warning, 5)
        self.assertEqual(thresholds.safely_prunable_count_critical, 20)
        self.assertEqual(thresholds.cleanup_error_threshold, 2)

    def test_evaluate_health_empty_healthy(self) -> None:
        """Test health evaluation when empty (no artifacts)."""
        thresholds = HealthThresholds()
        health = RepoHygieneHealth()
        is_healthy, summary = thresholds.evaluate_health(health)
        self.assertTrue(is_healthy)
        self.assertIn("healthy", summary.lower())
        self.assertEqual(health.is_healthy, is_healthy)

    def test_evaluate_health_with_overdue_artifacts(self) -> None:
        """Test health evaluation with overdue artifacts."""
        thresholds = HealthThresholds()
        health = RepoHygieneHealth(
            overdue_artifacts=[
                OverdueArtifact(
                    artifact_type="worktree",
                    identifier="/path/to/worktree",
                    category=WorktreeCategory.SAFELY_PRUNABLE.value,
                    age_seconds=864000,
                    threshold_seconds=604800,
                )
            ]
        )
        is_healthy, summary = thresholds.evaluate_health(health)
        self.assertFalse(is_healthy)
        self.assertIn("overdue", summary.lower())

    def test_evaluate_health_with_warning_count(self) -> None:
        """Test health evaluation when safely-prunable count hits warning."""
        thresholds = HealthThresholds(safely_prunable_count_warning=5)
        health = RepoHygieneHealth(
            worktrees=WorktreeInventory(safely_prunable=5)
        )
        is_healthy, summary = thresholds.evaluate_health(health)
        self.assertFalse(is_healthy)
        self.assertIn("warning threshold", summary.lower())

    def test_evaluate_health_with_critical_count(self) -> None:
        """Test health evaluation when safely-prunable count hits critical."""
        thresholds = HealthThresholds(safely_prunable_count_critical=10)
        health = RepoHygieneHealth(
            worktrees=WorktreeInventory(safely_prunable=10)
        )
        is_healthy, summary = thresholds.evaluate_health(health)
        self.assertFalse(is_healthy)
        self.assertIn("critical threshold", summary.lower())

    def test_evaluate_health_with_cleanup_errors(self) -> None:
        """Test health evaluation with cleanup errors."""
        thresholds = HealthThresholds()
        health = RepoHygieneHealth(
            cleanup_errors=["Error 1", "Error 2", "Error 3"]
        )
        is_healthy, summary = thresholds.evaluate_health(health)
        self.assertFalse(is_healthy)
        self.assertIn("cleanup error", summary.lower())

    def test_evaluate_health_healthy_with_retention_justification(self) -> None:
        """Test health evaluation when artifacts have retention justification."""
        thresholds = HealthThresholds()
        health = RepoHygieneHealth(
            worktrees=WorktreeInventory(active=2, dirty=1, unmerged=3, safely_prunable=0)
        )
        is_healthy, summary = thresholds.evaluate_health(health)
        self.assertTrue(is_healthy)
        self.assertIn("healthy", summary.lower())

    def test_evaluate_health_mixed_scenarios(self) -> None:
        """Test health evaluation with multiple factors."""
        thresholds = HealthThresholds(
            safely_prunable_count_warning=3,
            safely_prunable_count_critical=10,
        )
        health = RepoHygieneHealth(
            worktrees=WorktreeInventory(
                active=2,
                safely_prunable=5,  # Hits warning but not critical
            ),
            overdue_artifacts=[
                OverdueArtifact(
                    artifact_type="worktree",
                    identifier="/path",
                    category=WorktreeCategory.SAFELY_PRUNABLE.value,
                    age_seconds=800000,
                    threshold_seconds=604800,
                )
            ],
        )
        is_healthy, summary = thresholds.evaluate_health(health)
        self.assertFalse(is_healthy)
        # Should mention overdue (first priority)
        self.assertIn("overdue", summary.lower())


if __name__ == "__main__":
    unittest.main()
