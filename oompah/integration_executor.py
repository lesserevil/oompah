"""Git executor for one leased private-task integration submission."""

from __future__ import annotations

from dataclasses import dataclass
from contextvars import ContextVar
from functools import wraps
import os
import subprocess
from typing import Callable, ContextManager, ParamSpec, TypeVar

from oompah.git_credentials import (
    git_authentication_failure,
    git_credential_environment,
    redact_git_output,
)
from oompah.git_noninteractive import NONINTERACTIVE_GIT_ENV
from oompah.quality_gate import (
    BranchQualityGate,
    QualityGateOwner,
    QualityGateResult,
)
from oompah.projects import ProjectError, generated_worktree_helpers_in_revision


@dataclass(frozen=True)
class IntegrationExecutionResult:
    status: str
    message: str
    expected_epic_sha: str | None = None
    rebased_task_sha: str | None = None
    integrated_sha: str | None = None
    quality: QualityGateResult | None = None

    @property
    def failing_step(self) -> str:
        """Return the concrete integration step represented by this result."""

        return {
            "generated_helper": "submitted-head generated-helper validation",
            "wrong_worktree": "worktree branch validation",
            "dirty_worktree": "worktree cleanliness validation",
            "missing_head": "task branch validation",
            "stale_head": "submitted-head validation",
            "worktree_recovery": "worktree head validation",
            "missing_epic": "epic branch validation",
            "conflict": "task rebase",
            "epic_head_race": "epic compare-and-swap",
            "epic_merge_failure": "epic merge",
            "task_push_race": "task branch compare-and-swap",
            "ci_failure": "combined-tree quality gate",
            "needs_rebase": "combined-tree quality gate",
            "interrupted": "combined-tree quality gate",
        }.get(self.status, "integration preparation")

    @property
    def integrated(self) -> bool:
        return self.status == "integrated"


@dataclass(frozen=True)
class IntegrationCandidateAuthority:
    """Gate authority rebound to the exact post-rebase candidate head."""

    generation: str | None
    owner: QualityGateOwner | None
    is_current: Callable[[], bool] | None


def _make_git_env() -> dict[str, str]:
    """Return a subprocess environment with noninteractive overrides applied.

    Merges NONINTERACTIVE_GIT_ENV into the current process environment so
    that no interactive editor or terminal prompt can block a git subprocess.
    """
    env = dict(os.environ)
    env.update(NONINTERACTIVE_GIT_ENV)
    return env


_PROJECT_CREDENTIALS: ContextVar[tuple[str | None, str] | None] = ContextVar(
    "integration_project_credentials", default=None
)
_P = ParamSpec("_P")
_R = TypeVar("_R")


def _with_project_credentials(function: Callable[_P, _R]) -> Callable[_P, _R]:
    """Scope every Git subprocess in one integration attempt to its project."""

    @wraps(function)
    def wrapped(
        *args: _P.args,
        access_token: str | None = None,
        forge_kind: str = "github",
        **kwargs: _P.kwargs,
    ) -> _R:
        marker = _PROJECT_CREDENTIALS.set((access_token, forge_kind))
        try:
            return function(*args, **kwargs)
        finally:
            _PROJECT_CREDENTIALS.reset(marker)

    return wrapped


def _git(
    repo_path: str,
    *args: str,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    access_token, forge_kind = _PROJECT_CREDENTIALS.get() or (None, "github")
    with git_credential_environment(
        forge_kind=forge_kind,
        access_token=access_token,
        base_env=_make_git_env(),
    ) as env:
        result = subprocess.run(
            ["git", "-C", repo_path, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    result.stdout = redact_git_output(result.stdout, (access_token or "",))
    result.stderr = redact_git_output(result.stderr, (access_token or "",))
    return result


def _git_failure_message(
    operation: str,
    result: subprocess.CompletedProcess[str],
) -> tuple[str, str | None]:
    """Return a safe diagnostic and optional credential classification."""
    access_token, forge_kind = _PROJECT_CREDENTIALS.get() or (None, "github")
    output = result.stderr.strip() or result.stdout.strip()
    auth_message = git_authentication_failure(
        forge_kind=forge_kind,
        access_token=access_token,
        output=output,
        operation=operation,
    )
    if auth_message is not None:
        return (
            auth_message,
            "authentication_failed" if str(access_token or "").strip() else "credential_missing",
        )
    return redact_git_output(output[:2000], (access_token or "",)), None


def _sha(repo_path: str, ref: str) -> str | None:
    result = _git(repo_path, "rev-parse", "--verify", ref, timeout=15)
    return result.stdout.strip() if result.returncode == 0 else None


def _current_branch(repo_path: str) -> str | None:
    result = _git(repo_path, "branch", "--show-current", timeout=15)
    return result.stdout.strip() if result.returncode == 0 else None


def _dirty_worktree(repo_path: str) -> str | None:
    """Return task-owned porcelain changes before any destructive git step."""

    result = _git(
        repo_path,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        timeout=30,
    )
    if result.returncode != 0:
        return "git status failed: " + result.stderr.strip()[:1000]
    dirty = [
        line
        for line in result.stdout.splitlines()
        if line and not line[3:].strip().startswith(".oompah-no-hooks/")
        and line[3:].strip() != ".oompah-no-hooks"
    ]
    return "\n".join(dirty) if dirty else None


@_with_project_credentials
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
    retry_forced: bool = False,
    commit_allowed: Callable[[], bool] | None = None,
    gate_generation: str | None = None,
    gate_owner: QualityGateOwner | None = None,
    canonicalize_candidate: Callable[
        [str, str], IntegrationCandidateAuthority
    ]
    | None = None,
) -> IntegrationExecutionResult:
    """Rebase, test, and compare-and-swap one task onto an epic branch."""

    expected_epic_sha: str | None = None
    rebased_sha: str | None = None

    def _authority_failure(stage: str) -> IntegrationExecutionResult | None:
        if commit_allowed is None:
            return None
        try:
            allowed = commit_allowed()
        except Exception as exc:  # fail closed when tracker authority is unknown
            return IntegrationExecutionResult(
                status="authority_unavailable",
                message=(
                    f"could not verify integration authority {stage}: {exc}"
                ),
                expected_epic_sha=expected_epic_sha,
                rebased_task_sha=rebased_sha,
            )
        if allowed:
            return None
        return IntegrationExecutionResult(
            status="cancelled",
            message=f"integration authority was withdrawn {stage}",
            expected_epic_sha=expected_epic_sha,
            rebased_task_sha=rebased_sha,
        )

    try:
        with project_lock:
            authority_failure = _authority_failure("before preparation")
            if authority_failure is not None:
                return authority_failure
            current_task_branch = _current_branch(task_worktree)
            if current_task_branch != task_branch:
                return IntegrationExecutionResult(
                    status="wrong_worktree",
                    message=(
                        "task worktree is on "
                        f"{current_task_branch or 'a detached HEAD'}, not "
                        f"queued branch {task_branch}; refusing to reset it"
                    ),
                )
            current_epic_branch = _current_branch(epic_worktree)
            if current_epic_branch != epic_branch:
                return IntegrationExecutionResult(
                    status="wrong_worktree",
                    message=(
                        "epic worktree is on "
                        f"{current_epic_branch or 'a detached HEAD'}, not "
                        f"expected branch {epic_branch}; refusing to reset it"
                    ),
                )
            for worktree in (epic_worktree, task_worktree):
                fetched = _git(worktree, "fetch", "--prune", "origin")
                if fetched.returncode != 0:
                    message, auth_status = _git_failure_message(
                        "integration fetch", fetched
                    )
                    return IntegrationExecutionResult(
                        status=auth_status or "error",
                        message=f"git fetch failed: {message}",
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
            try:
                generated_helpers = generated_worktree_helpers_in_revision(
                    task_worktree,
                    remote_task_sha,
                )
            except ProjectError as exc:
                return IntegrationExecutionResult(
                    status="error",
                    message=f"generated-helper validation failed: {exc}",
                )
            if generated_helpers:
                rendered_helpers = ", ".join(
                    f"`{path}`" for path in generated_helpers[:20]
                )
                suffix = (
                    " and more"
                    if len(generated_helpers) > 20
                    else ""
                )
                return IntegrationExecutionResult(
                    status="generated_helper",
                    message=(
                        "submitted task head tracks Oompah-generated worktree "
                        f"helper(s): {rendered_helpers}{suffix}. These paths "
                        "are non-deliverable; remove them from the task branch "
                        "with `git rm`, commit, push the new head, and submit "
                        "again. The shared epic worktree was not mutated."
                    ),
                    expected_epic_sha=expected_epic_sha,
                    rebased_task_sha=remote_task_sha,
                )
            current_task_head = _sha(task_worktree, "HEAD")
            if current_task_head != remote_task_sha:
                return IntegrationExecutionResult(
                    status="worktree_recovery",
                    message=(
                        "task worktree head "
                        f"{current_task_head or 'unknown'} differs from the "
                        f"published task head {remote_task_sha}; refusing to "
                        "reset a preserved recovery snapshot"
                    ),
                    rebased_task_sha=remote_task_sha,
                )
            for worktree, label in (
                (task_worktree, "task"),
                (epic_worktree, "epic"),
            ):
                dirty = _dirty_worktree(worktree)
                if dirty:
                    return IntegrationExecutionResult(
                        status="dirty_worktree",
                        message=(
                            f"{label} worktree has uncommitted task-owned "
                            f"changes; refusing to reset it: {dirty[:1000]}"
                        ),
                        expected_epic_sha=expected_epic_sha,
                    )
            expected_epic_sha = _sha(epic_worktree, f"origin/{epic_branch}")
            if expected_epic_sha is None:
                return IntegrationExecutionResult(
                    status="missing_epic",
                    message=f"remote epic branch {epic_branch} does not exist",
                )
            current_epic_head = _sha(epic_worktree, "HEAD")
            if current_epic_head != expected_epic_sha:
                return IntegrationExecutionResult(
                    status="worktree_recovery",
                    message=(
                        "epic worktree head "
                        f"{current_epic_head or 'unknown'} differs from the "
                        f"published epic head {expected_epic_sha}; refusing "
                        "to reset a preserved recovery snapshot"
                    ),
                    expected_epic_sha=expected_epic_sha,
                )
            checkout = _git(task_worktree, "checkout", task_branch)
            if checkout.returncode != 0:
                return IntegrationExecutionResult(
                    status="error",
                    message=checkout.stderr.strip()[:1000],
                    expected_epic_sha=expected_epic_sha,
                )
            reset_task = _git(
                task_worktree,
                "reset",
                "--hard",
                f"origin/{task_branch}",
            )
            if reset_task.returncode != 0:
                return IntegrationExecutionResult(
                    status="error",
                    message=reset_task.stderr.strip()[:1000],
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
            authority_failure = _authority_failure("before task branch update")
            if authority_failure is not None:
                return authority_failure
            pushed_task = _git(
                task_worktree,
                "push",
                f"--force-with-lease=refs/heads/{task_branch}:{submitted_head_sha}",
                "origin",
                f"HEAD:refs/heads/{task_branch}",
            )
            if pushed_task.returncode != 0:
                message, auth_status = _git_failure_message(
                    "task branch push", pushed_task
                )
                return IntegrationExecutionResult(
                    status=auth_status or "task_push_race",
                    message=(
                        message
                        if auth_status
                        else "task branch changed while rebasing: " + message
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

    if rebased_sha is None or expected_epic_sha is None:
        return IntegrationExecutionResult(
            status="error",
            message="integration candidate was not resolved",
            expected_epic_sha=expected_epic_sha,
            rebased_task_sha=rebased_sha,
        )

    if canonicalize_candidate is not None:
        try:
            candidate_authority = canonicalize_candidate(
                rebased_sha,
                expected_epic_sha,
            )
        except Exception as exc:  # fail closed before launching the gate
            return IntegrationExecutionResult(
                status="authority_unavailable",
                message=f"could not canonicalize integration candidate: {exc}",
                expected_epic_sha=expected_epic_sha,
                rebased_task_sha=rebased_sha,
            )
        gate_generation = candidate_authority.generation
        gate_owner = candidate_authority.owner
        commit_allowed = candidate_authority.is_current
        authority_failure = _authority_failure("before quality gate")
        if authority_failure is not None:
            return authority_failure

    quality = quality_gate.run(
        repo_path=task_worktree,
        repo_identity=repo_identity,
        target_branch=epic_branch,
        work_branch=task_branch,
        command=quality_command,
        retry_forced=retry_forced,
        expected_head_sha=rebased_sha,
        generation=gate_generation,
        owner=gate_owner,
        is_current=commit_allowed,
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
        if quality.status == "needs_rebase":
            return IntegrationExecutionResult(
                status="needs_rebase",
                message=(
                    "Combined-tree quality gate was refused because the task "
                    "branch does not contain the deployed lifecycle safety "
                    f"contract: {quality.output_tail[-4000:]}"
                ),
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
            authority_failure = _authority_failure("before epic commit")
            if authority_failure is not None:
                return authority_failure
            fetched = _git(epic_worktree, "fetch", "origin", epic_branch)
            if fetched.returncode != 0:
                message, auth_status = _git_failure_message(
                    "epic branch verification fetch", fetched
                )
                return IntegrationExecutionResult(
                    status=auth_status or "error",
                    message=message,
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
            current_epic_head = _sha(epic_worktree, "HEAD")
            if current_epic_head != expected_epic_sha:
                return IntegrationExecutionResult(
                    status="worktree_recovery",
                    message=(
                        "epic worktree changed during the quality gate; "
                        "refusing to reset preserved task-owned work"
                    ),
                    expected_epic_sha=expected_epic_sha,
                    rebased_task_sha=rebased_sha,
                    quality=quality,
                )
            dirty = _dirty_worktree(epic_worktree)
            if dirty:
                return IntegrationExecutionResult(
                    status="dirty_worktree",
                    message=(
                        "epic worktree has uncommitted task-owned changes "
                        "after the quality gate; refusing to reset it: "
                        f"{dirty[:1000]}"
                    ),
                    expected_epic_sha=expected_epic_sha,
                    rebased_task_sha=rebased_sha,
                    quality=quality,
                )
            checkout = _git(epic_worktree, "checkout", epic_branch)
            if checkout.returncode != 0:
                return IntegrationExecutionResult(
                    status="error",
                    message=f"epic checkout failed: {checkout.stderr.strip()[:1000]}",
                    expected_epic_sha=expected_epic_sha,
                    rebased_task_sha=rebased_sha,
                    quality=quality,
                )
            reset_epic = _git(
                epic_worktree,
                "reset",
                "--hard",
                f"origin/{epic_branch}",
            )
            if reset_epic.returncode != 0:
                return IntegrationExecutionResult(
                    status="error",
                    message=f"epic reset failed: {reset_epic.stderr.strip()[:1000]}",
                    expected_epic_sha=expected_epic_sha,
                    rebased_task_sha=rebased_sha,
                    quality=quality,
                )
            merge = _git(epic_worktree, "merge", "--ff-only", rebased_sha or "")
            if merge.returncode != 0:
                _git(epic_worktree, "reset", "--hard", f"origin/{epic_branch}")
                return IntegrationExecutionResult(
                    status="epic_merge_failure",
                    message=f"epic merge failed: {merge.stderr.strip()[:1000]}",
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
                message, auth_status = _git_failure_message(
                    "epic branch push", pushed_epic
                )
                _git(epic_worktree, "fetch", "origin", epic_branch)
                _git(epic_worktree, "reset", "--hard", f"origin/{epic_branch}")
                return IntegrationExecutionResult(
                    status=auth_status or "epic_head_race",
                    message=(
                        message
                        if auth_status
                        else "epic compare-and-swap push failed: " + message
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
