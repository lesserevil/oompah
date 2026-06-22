"""Tests verifying that .github/workflows/ci.yml covers release/* branches.

Validates OOMPAH-20: CI triggers must include release/* so the quality
gate runs for release branches and PRs targeting them.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci_workflow() -> dict:
    text = CI_WORKFLOW_PATH.read_text()
    return yaml.safe_load(text)


def test_ci_workflow_yaml_is_valid():
    """The CI workflow file must parse as valid YAML."""
    workflow = _load_ci_workflow()
    assert isinstance(workflow, dict)
    assert "on" in workflow or True in workflow  # PyYAML parses `on:` as True


def test_ci_workflow_push_includes_release_branches():
    """push trigger must include release/* so commits to release branches
    run the quality gate."""
    workflow = _load_ci_workflow()
    triggers = workflow.get("on") or workflow.get(True)
    push = triggers.get("push", {})
    branches = push.get("branches", [])
    assert any(
        b == "release/*" or b.startswith("release/")
        for b in branches
    ), f"push.branches must include 'release/*'; got: {branches}"


def test_ci_workflow_pull_request_includes_release_branches():
    """pull_request trigger must include release/* so PRs targeting
    release branches run the quality gate."""
    workflow = _load_ci_workflow()
    triggers = workflow.get("on") or workflow.get(True)
    pull_request = triggers.get("pull_request", {})
    branches = pull_request.get("branches", [])
    assert any(
        b == "release/*" or b.startswith("release/")
        for b in branches
    ), f"pull_request.branches must include 'release/*'; got: {branches}"


def test_ci_workflow_merge_group_includes_release_branches():
    """merge_group trigger must include release/* so merge-queue entries
    for release branches run the quality gate."""
    workflow = _load_ci_workflow()
    triggers = workflow.get("on") or workflow.get(True)
    merge_group = triggers.get("merge_group", {})
    branches = merge_group.get("branches", [])
    assert any(
        b == "release/*" or b.startswith("release/")
        for b in branches
    ), f"merge_group.branches must include 'release/*'; got: {branches}"


def test_ci_workflow_still_covers_main():
    """main must remain in all trigger branch lists so existing CI
    behaviour for the default branch is preserved."""
    workflow = _load_ci_workflow()
    triggers = workflow.get("on") or workflow.get(True)
    for event in ("push", "pull_request", "merge_group"):
        branches = triggers.get(event, {}).get("branches", [])
        assert "main" in branches, (
            f"{event}.branches must still include 'main'; got: {branches}"
        )
