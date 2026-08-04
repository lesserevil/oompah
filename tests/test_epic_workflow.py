"""Epic rollup facts, target-relative decisions, and durable job coverage."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from oompah.epic_workflow import EpicFactCollector, EpicWorkflowController
from oompah.models import Issue
from oompah.statuses import DONE, IN_PROGRESS, OPEN
from oompah.workflow_contract import TaskDisposition
from oompah.workflow_facts import GitLandingCollector, LandingRequest, LandingState
from oompah.workflow_jobs import WorkflowJobState, WorkflowJobStore


class Tracker:
    def __init__(self, issues: list[Issue]) -> None:
        self.issues = {item.identifier: item for item in issues}

    def fetch_issue_detail(self, identifier: str):
        return self.issues.get(identifier)

    def fetch_children(self, identifier: str):
        return [item for item in self.issues.values() if item.parent_id == identifier]


def issue(
    identifier: str,
    *,
    state: str,
    issue_type: str = "task",
    parent_id: str | None = None,
    work_branch: str | None = None,
    project_id: str = "project-1",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="epic workflow fixture",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id=project_id,
        work_branch=work_branch,
    )


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Epic Workflow",
            "GIT_AUTHOR_EMAIL": "epic@example.invalid",
            "GIT_COMMITTER_NAME": "Epic Workflow",
            "GIT_COMMITTER_EMAIL": "epic@example.invalid",
        },
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def make_git_fixture(repo: Path) -> None:
    git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-m", "base")
    git(repo, "checkout", "-b", "leaf")
    (repo / "leaf.txt").write_text("leaf\n")
    git(repo, "add", "leaf.txt")
    git(repo, "commit", "-m", "leaf")
    git(repo, "checkout", "main")
    git(repo, "checkout", "-b", "epic-MID")
    git(repo, "cherry-pick", "leaf")
    git(repo, "checkout", "main")
    git(repo, "checkout", "-b", "epic-TOP")
    git(repo, "cherry-pick", "epic-MID")
    git(repo, "checkout", "main")


def test_nested_rollups_use_immediate_landing_without_parent_status_cycle(tmp_path):
    make_git_fixture(tmp_path)
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    mid = issue("MID", state=OPEN, issue_type="epic", parent_id="TOP")
    leaf = issue(
        "LEAF", state=DONE, parent_id="MID", work_branch="leaf"
    )
    tracker = Tracker([top, mid, leaf])
    collector = EpicFactCollector(
        project_id="project-1",
        tracker=tracker,
        repo_path=str(tmp_path),
    )
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(collector=collector, store=store)

    batch, scheduled = controller.reconcile([top, mid])

    decisions = {item.task.identifier: item.decision for item in batch.tasks}
    assert decisions["MID"].disposition is TaskDisposition.RUNNABLE
    assert decisions["MID"].reason_code == "rollup.children_complete"
    # MID is intentionally still Open. TOP is eligible from MID's landing on
    # epic-TOP, not from a status that TOP would have derived from MID.
    assert decisions["TOP"].disposition is TaskDisposition.RUNNABLE
    assert decisions["TOP"].durable_jobs == ("rollup_review_creation",)
    assert scheduled.jobs_created == 2
    assert all(
        job.state is WorkflowJobState.QUEUED for job in store.list_jobs(limit=10)
    )
    store.close()


def test_deleted_source_ref_preserves_durable_landing_fact(tmp_path):
    make_git_fixture(tmp_path)
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    mid = issue("MID", state=IN_PROGRESS, issue_type="epic", parent_id="TOP")
    leaf = issue("LEAF", state=DONE, parent_id="MID", work_branch="leaf")
    tracker = Tracker([top, mid, leaf])
    first = EpicFactCollector(
        project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
    ).collect("MID")
    durable = next(
        item
        for item in first.landings
        if item.source == "leaf" and item.target == "epic-MID"
    )
    assert durable.state is LandingState.LANDED
    assert durable.durable

    git(tmp_path, "branch", "-D", "leaf")
    second = EpicFactCollector(
        project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
    ).collect(
        "MID",
        prior_landings={(durable.source, durable.target): durable},
    )
    preserved = next(
        item
        for item in second.landings
        if item.source == "leaf" and item.target == "epic-MID"
    )
    assert preserved.state is LandingState.LANDED
    assert preserved.durable
    assert preserved.evidence_revision == durable.evidence_revision


def test_rebased_source_is_proven_by_patch_equivalence(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-m", "base")
    git(repo, "checkout", "-b", "source")
    (repo / "change.txt").write_text("same patch\n")
    git(repo, "add", "change.txt")
    git(repo, "commit", "-m", "source change")
    git(repo, "checkout", "main")
    git(repo, "checkout", "-b", "target")
    git(repo, "cherry-pick", "source")
    git(repo, "checkout", "source")
    git(repo, "reset", "--hard", "HEAD~1")
    (repo / "change.txt").write_text("same patch\n")
    git(repo, "add", "change.txt")
    git(repo, "commit", "-m", "rebased source change")

    fact = GitLandingCollector(repo, project_id="project-1").collect(
        # The branch is not an ancestor of target, but its patch is identical.
        LandingRequest("source", "target")
    )

    assert fact.state is LandingState.LANDED
    assert fact.proof["kind"] == "patch_id"
    assert fact.durable
