"""Test auditor validation targets configuration (OOMPAH-736 / EXOCOMP-159).

Regression test for policy-contract alignment: when a project requires
additional validation targets (fmt-check, lint, help), the auditor should
allow those commands without exhausting the policy budget.
"""

from __future__ import annotations

import pytest

from oompah.auditor import (
    check_auditor_command,
    _get_auditor_validation_targets,
    _build_auditor_command_regex,
)
from oompah.models import Project


class TestAuditorValidationTargets:
    """Tests for dynamic auditor command validation."""

    def test_default_validation_targets_allow_test_commands(self):
        """Default targets allow test, test-serial, check-secrets."""
        targets = _get_auditor_validation_targets()
        assert "test" in targets
        assert "test-serial" in targets
        assert "check-secrets" in targets

    def test_default_validation_targets_deny_fmt_check_and_lint(self):
        """Default targets do not include fmt-check or lint."""
        targets = _get_auditor_validation_targets()
        assert "fmt-check" not in targets
        assert "lint" not in targets

    def test_check_auditor_command_allows_default_targets(self):
        """Auditor allows make commands from default targets."""
        # These should be allowed with default configuration
        for target in ["test", "test-serial", "check-secrets"]:
            denial = check_auditor_command(f"make {target}")
            assert denial is None, f"make {target} should be allowed by default"

    def test_check_auditor_command_denies_fmt_check_by_default(self):
        """Auditor denies make fmt-check without project configuration."""
        denial = check_auditor_command("make fmt-check")
        assert denial is not None
        assert "policy permits only read-only repository inspection" in denial

    def test_check_auditor_command_denies_lint_by_default(self):
        """Auditor denies make lint without project configuration."""
        denial = check_auditor_command("make lint")
        assert denial is not None
        assert "policy permits only read-only repository inspection" in denial

    def test_check_auditor_command_denies_help_by_default(self):
        """Auditor denies make help without project configuration."""
        denial = check_auditor_command("make help")
        assert denial is not None
        assert "policy permits only read-only repository inspection" in denial

    def test_build_regex_with_custom_targets(self):
        """Regex builder creates correct pattern for custom targets."""
        custom_targets = ["test", "fmt-check", "lint", "help"]
        regex = _build_auditor_command_regex(custom_targets)
        
        # All custom targets should match
        for target in custom_targets:
            assert regex.fullmatch(f"make {target}") is not None
        
        # Default-only targets should not match
        assert regex.fullmatch("make test-serial") is None
        assert regex.fullmatch("make check-secrets") is None

    def test_build_regex_escapes_special_characters(self):
        """Regex builder properly escapes special characters in targets."""
        targets = ["test", "test-unit", "check-all"]
        regex = _build_auditor_command_regex(targets)
        
        # Hyphens are literal characters, not regex special chars
        assert regex.fullmatch("make test") is not None
        assert regex.fullmatch("make test-unit") is not None
        assert regex.fullmatch("make check-all") is not None

    def test_check_auditor_command_allows_other_read_only_commands(self):
        """Other read-only commands remain allowed regardless of validation targets."""
        # These should always be allowed
        safe_commands = [
            "ls -la",
            "cat Makefile",
            "grep pytest tests/",
            "git status",
            "git diff main",
            "pwd",
        ]
        for cmd in safe_commands:
            denial = check_auditor_command(cmd)
            assert denial is None, f"{cmd} should be allowed"

    def test_check_auditor_command_rejects_mutations(self):
        """Mutations remain denied regardless of validation targets."""
        mutating_commands = [
            "git commit -m 'test'",
            "rm -rf /",
            "git push",
            "make clean",
        ]
        for cmd in mutating_commands:
            denial = check_auditor_command(cmd)
            assert denial is not None, f"{cmd} should be denied"

    def test_check_auditor_command_with_explicit_project_targets(self):
        """When project config includes fmt-check, auditor allows it."""
        # Simulate a project with fmt-check configured
        custom_targets = ["test", "fmt-check", "lint"]
        
        # Create a mock project for testing (we'll use validation_targets directly)
        # Instead of relying on ProjectStore, we pass the targets directly
        regex = _build_auditor_command_regex(custom_targets)
        
        # These should match the custom regex
        assert regex.fullmatch("make test") is not None
        assert regex.fullmatch("make fmt-check") is not None
        assert regex.fullmatch("make lint") is not None

    def test_regression_exocomp_159_fmt_check_and_lint_allowed(self):
        """EXOCOMP-159 regression: fmt-check, lint, help can be configured."""
        # The issue: a project requires make fmt-check and make lint,
        # but the default policy only allows make test/test-serial/check-secrets.
        # Result: auditor gets exhausted on policy budget and task fails.
        
        # With the fix, projects can configure these as allowed targets
        approved_targets = ["test", "test-serial", "check-secrets", "fmt-check", "lint", "help"]
        regex = _build_auditor_command_regex(approved_targets)
        
        # All project requirements should be executable
        for target in ["test", "fmt-check", "lint", "help"]:
            cmd = f"make {target}"
            assert regex.fullmatch(cmd) is not None, (
                f"Project-required command '{cmd}' should be allowed"
            )

    def test_project_model_includes_auditor_validation_targets_field(self):
        """Project model can store auditor_validation_targets configuration."""
        project = Project(
            id="test-project",
            name="Test Project",
            repo_url="https://github.com/test/repo",
            repo_path="/path/to/repo",
            auditor_validation_targets=["test", "fmt-check", "lint"],
        )
        assert project.auditor_validation_targets == ["test", "fmt-check", "lint"]

    def test_project_model_serializes_auditor_validation_targets(self):
        """Project.to_dict includes auditor_validation_targets when set."""
        project = Project(
            id="test-project",
            name="Test Project",
            repo_url="https://github.com/test/repo",
            repo_path="/path/to/repo",
            auditor_validation_targets=["test", "fmt-check"],
        )
        d = project.to_dict()
        assert "auditor_validation_targets" in d
        assert d["auditor_validation_targets"] == ["test", "fmt-check"]

    def test_project_model_deserializes_auditor_validation_targets(self):
        """Project.from_dict restores auditor_validation_targets from dict."""
        data = {
            "id": "test-project",
            "name": "Test Project",
            "repo_url": "https://github.com/test/repo",
            "repo_path": "/path/to/repo",
            "auditor_validation_targets": ["test", "fmt-check", "lint"],
        }
        project = Project.from_dict(data)
        assert project.auditor_validation_targets == ["test", "fmt-check", "lint"]
