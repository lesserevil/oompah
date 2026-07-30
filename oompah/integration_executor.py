"""Git executor for one leased private-task integration submission."""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import ContextManager

from oompah.quality_gate import BranchQualityGate, QualityGateResult


@dataclass(frozen=True)
class IntegrationExecutionResult:
    status: str
    message: str
    expected_epic_sha: str | None = None
    rebased_task_sha: str | None = None
    integrated_sha: str | None = None
    quality: QualityGateResult | None = None

    @property
    def integrated(self) -> bool:
        return self.status == "integrated"


def _git(
    repo_path: str,
    *args: str,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", repo_path, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _sha(repo_path: str, ref: str) -> str | None:
    result = _git(repo_path, "rev-parse", "--verify", ref, timeout=15)
    return result.stdout.strip() if result.returncode == 0 else None


def execute_integration(
    *,
    project_lock: ContextManager[object],
    epic_worktree: str,
    task_worktree: str,
    epic_branch: str,
    task_branch: str,
    submitted_head_sha: str,
    quality_gate: BranchQualityGate,
    quality_command: str,
    repo_identity: str,
) -> IntegrationExecutionResult:
    """Rebase, test, and compare-and-swap one task onto an epic branch."""

    expected_epic_sha: str | None = None
    rebased_sha: str | None = None
    try:
        with project_lock:
            for worktree in (epic_worktree, task_worktree):
                fetched = _git(worktree, "fetch", "--prune", "origin")
                if fetched.returncode != 0:
                    return IntegrationExecutionResult(
                        status="error",
                        message=f"git fetch failed: {fetched.stderr.strip()[:1000]}",
                    )
            remote_task_sha = _sha(task_worktree, f"origin/{task_branch}")
            if remote_task_sha is None:
                return IntegrationExecutionResult(
                    status="missing_head",
                    message=f"remote task branch {task_branch} does not exist",
                )
            if remote_task_sha != submitted_head_sha:
                return IntegrationExecutionResult(
                    status="stale_head",
                    message=(
                        f"submitted head {submitted_head_sha} no longer matches "
                        f"origin/{task_branch} at {remote_task_sha}"
                    ),
                    rebased_task_sha=remote_task_sha,
                )
            expected_epic_sha = _sha(epic_worktree, f"origin/{epic_branch}")
            if expected_epic_sha is None:
                return IntegrationExecutionResult(
                    status="missing_epic",
                    message=f"remote epic branch {epic_branch} does not exist",
                )
            checkout = _git(task_worktree, "checkout", task_branch)
            reset_task = _git(
                task_worktree,
                "reset",
                "--hard",
                f"origin/{task_branch}",
            )
            if checkout.returncode != 0 or reset_task.returncode != 0:
                return IntegrationExecutionResult(
                    status="error",
                    message=(
                        checkout.stderr.strip() or reset_task.stderr.strip()
                    )[:1000],
                    expected_epic_sha=expected_epic_sha,
                )
            rebased = _git(task_worktree, "rebase", expected_epic_sha, timeout=600)
            if rebased.returncode != 0:
                _git(task_worktree, "rebase", "--abort")
                return IntegrationExecutionResult(
                    status="conflict",
                    message=(
                        "Rebase onto the latest epic head conflicted: "
                        + rebased.stderr.strip()[-2000:]
                    ),
                    expected_epic_sha=expected_epic_sha,
                )
            rebased_sha = _sha(task_worktree, "HEAD")
            if rebased_sha is None:
                return IntegrationExecutionResult(
                    status="error",
                    message="could not resolve rebased task head",
                    expected_epic_sha=expected_epic_sha,
                )
            pushed_task = _git(
                task_worktree,
                "push",
                f"--force-with-lease=refs/heads/{task_branch}:{submitted_head_sha}",
                "origin",
                f"HEAD:refs/heads/{task_branch}",
            )
            if pushed_task.returncode != 0:
                return IntegrationExecutionResult(
                    status="task_push_race",
                    message=(
                        "task branch changed while rebasing: "
                        + pushed_task.stderr.strip()[-1000:]
                    ),
                    expected_epic_sha=expected_epic_sha,
                    rebased_task_sha=rebased_sha,
                )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return IntegrationExecutionResult(
            status="error",
            message=f"integration preparation failed: {exc}",
            expected_epic_sha=expected_epic_sha,
            rebased_task_sha=rebased_sha,
        )

    quality = quality_gate.run(
        repo_path=task_worktree,
        repo_identity=repo_identity,
        target_branch=epic_branch,
        work_branch=task_branch,
        command=quality_command,
    )
    if not quality.passed:
        if quality.status == "interrupted":
            return IntegrationExecutionResult(
                status="interrupted",
                message="Combined-tree quality gate interrupted by service shutdown",
                expected_epic_sha=expected_epic_sha,
                rebased_task_sha=rebased_sha,
                quality=quality,
            )
        return IntegrationExecutionResult(
            status="ci_failure",
            message=(
                f"Combined-tree quality gate {quality.status}: "
                f"{quality.output_tail[-4000:]}"
            ),
            expected_epic_sha=expected_epic_sha,
            rebased_task_sha=rebased_sha,
            quality=quality,
        )

    try:
        with project_lock:
            fetched = _git(epic_worktree, "fetch", "origin", epic_branch)
            if fetched.returncode != 0:
                return IntegrationExecutionResult(
                    status="error",
                    message=fetched.stderr.strip()[-1000:],
                    expected_epic_sha=expected_epic_sha,
                    rebased_task_sha=rebased_sha,
                    quality=quality,
                )
            current_remote = _sha(epic_worktree, f"origin/{epic_branch}")
            if current_remote != expected_epic_sha:
                return IntegrationExecutionResult(
                    status="epic_head_race",
                    message=(
                        f"epic head advanced from {expected_epic_sha} "
                        f"to {current_remote}; retrying on the new head"
                    ),
                    expected_epic_sha=expected_epic_sha,
                    rebased_task_sha=rebased_sha,
                    quality=quality,
                )
            checkout = _git(epic_worktree, "checkout", epic_branch)
            reset_epic = _git(
                epic_worktree,
                "reset",
                "--hard",
                f"origin/{epic_branch}",
            )
            merge = _git(epic_worktree, "merge", "--ff-only", rebased_sha or "")
            if (
                checkout.returncode != 0
                or reset_epic.returncode != 0
                or merge.returncode != 0
            ):
                _git(epic_worktree, "reset", "--hard", f"origin/{epic_branch}")
                return IntegrationExecutionResult(
                    status="epic_head_race",
                    message=(
                        checkout.stderr.strip()
                        or reset_epic.stderr.strip()
                        or merge.stderr.strip()
                    )[-1000:],
                    expected_epic_sha=expected_epic_sha,
                    rebased_task_sha=rebased_sha,
                    quality=quality,
                )
            integrated_sha = _sha(epic_worktree, "HEAD")
            pushed_epic = _git(
                epic_worktree,
                "push",
                f"--force-with-lease=refs/heads/{epic_branch}:{expected_epic_sha}",
                "origin",
                f"HEAD:refs/heads/{epic_branch}",
            )
            if pushed_epic.returncode != 0:
                _git(epic_worktree, "fetch", "origin", epic_branch)
                _git(epic_worktree, "reset", "--hard", f"origin/{epic_branch}")
                return IntegrationExecutionResult(
                    status="epic_head_race",
                    message=(
                        "epic compare-and-swap push failed: "
                        + pushed_epic.stderr.strip()[-1000:]
                    ),
                    expected_epic_sha=expected_epic_sha,
                    rebased_task_sha=rebased_sha,
                    quality=quality,
                )
            return IntegrationExecutionResult(
                status="integrated",
                message="private task head integrated into the tested epic branch",
                expected_epic_sha=expected_epic_sha,
                rebased_task_sha=rebased_sha,
                integrated_sha=integrated_sha,
                quality=quality,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return IntegrationExecutionResult(
            status="error",
            message=f"epic compare-and-swap failed: {exc}",
            expected_epic_sha=expected_epic_sha,
            rebased_task_sha=rebased_sha,
            quality=quality,
        )
