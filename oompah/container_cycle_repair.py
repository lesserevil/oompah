"""Fail-closed execution of a detected container dependency cycle repair.

The cycle detector intentionally has no Git side effects.  This module is the
small, independently testable execution boundary used after a cycle has been
selected for automatic repair.  It only ever copies the authoritative parent
branch into a dependent container; it never chooses a sibling branch as a
merge source.

The executor is deliberately expressed in terms of remote refs and explicit
compare-and-swap pushes.  That makes a partially completed run safe to resume:
after a restart the remote refs are the durable evidence, so an already landed
parent or child step is observed as complete instead of being repeated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
import subprocess
import tempfile
from typing import Callable, Iterable, Mapping


_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


class ContainerCycleRepairError(RuntimeError):
    """Base class for safe-repair failures."""


class UnsafePrerequisite(ContainerCycleRepairError):
    """The selected prerequisite is not a safe descendant closure."""


class RefRace(ContainerCycleRepairError):
    """A compare-and-swap ref update lost a concurrent writer."""


class MergeConflict(ContainerCycleRepairError):
    """A parent-only child synchronization has conflicts."""


@dataclass(frozen=True)
class CycleRepairRow:
    """The exact private queue authority fenced for one cycle."""

    task_id: str
    container_id: str
    epic_id: str
    task_branch: str
    head_sha: str

    def to_dict(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "container_id": self.container_id,
            "epic_id": self.epic_id,
            "task_branch": self.task_branch,
            "head_sha": self.head_sha,
        }


@dataclass(frozen=True)
class ContainerCycleRepairPlan:
    """An immutable, exact repair selected by the graph analyzer."""

    key: str
    authoritative_container: str
    dependent_containers: tuple[str, ...]
    prerequisite_shas: tuple[tuple[str, str], ...]
    rows: tuple[CycleRepairRow, ...] = ()
    # A closure may contain intermediate commits that are intentionally part
    # of the selected prerequisite.  Supplying it is what lets the executor
    # reject a selected tip that smuggles in an unrelated sibling commit.
    declared_closure: tuple[str, ...] = ()

    @property
    def selected_shas(self) -> tuple[str, ...]:
        return tuple(sha for _task, sha in self.prerequisite_shas)

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "authoritative_container": self.authoritative_container,
            "dependent_containers": list(self.dependent_containers),
            "prerequisite_shas": {
                task: sha for task, sha in self.prerequisite_shas
            },
            "declared_closure": list(self.declared_closure),
            "rows": [row.to_dict() for row in self.rows],
        }


@dataclass
class ChildRepairResult:
    container_id: str
    branch: str
    expected_sha: str | None = None
    resulting_sha: str | None = None
    action: str = "pending"
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "container_id": self.container_id,
            "branch": self.branch,
            "expected_sha": self.expected_sha,
            "resulting_sha": self.resulting_sha,
            "action": self.action,
            "error": self.error,
        }


@dataclass
class ContainerCycleRepairResult:
    """Durable evidence emitted by one execution attempt."""

    status: str
    phase: str
    parent_branch: str
    parent_expected_sha: str | None = None
    parent_sha: str | None = None
    children: list[ChildRepairResult] = field(default_factory=list)
    restorable_rows: tuple[str, ...] = ()
    changed_rows: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "phase": self.phase,
            "parent_branch": self.parent_branch,
            "parent_expected_sha": self.parent_expected_sha,
            "parent_sha": self.parent_sha,
            "children": [child.to_dict() for child in self.children],
            "restorable_rows": list(self.restorable_rows),
            "changed_rows": list(self.changed_rows),
            "error": self.error,
        }


def epic_branch(container_id: str) -> str:
    """Return the canonical branch for a container identifier."""

    clean = str(container_id or "").strip()
    if not clean:
        raise ValueError("container identifier is required")
    return f"epic-{clean}"


def _validate_branch(branch: str) -> str:
    value = str(branch or "").strip()
    if not value or not _BRANCH_RE.fullmatch(value) or value.startswith("/"):
        raise ValueError(f"invalid Git branch name: {branch!r}")
    if ".." in value or "//" in value or value.endswith("/"):
        raise ValueError(f"invalid Git branch name: {branch!r}")
    return value


GitRunner = Callable[[list[str], str | None, int], subprocess.CompletedProcess[str]]
PersistCallback = Callable[[dict[str, object]], None]


class ContainerCycleRepairExecutor:
    """Execute one selected cycle repair under remote-ref CAS fences.

    ``persist`` is called after every durable ref step.  The caller stores the
    resulting evidence in its service-state journal before moving on to the
    queue/tracker phase.  Tests can inject ``run_git`` to exercise races and
    restart boundaries without a remote service.
    """

    def __init__(
        self,
        repo_path: str,
        *,
        remote: str = "origin",
        run_git: GitRunner | None = None,
        persist: PersistCallback | None = None,
        timeout: int = 60,
    ) -> None:
        self.repo_path = os.fspath(repo_path)
        self.remote = str(remote or "origin").strip() or "origin"
        self._run_git = run_git or self._subprocess_git
        self._persist = persist or (lambda _evidence: None)
        self.timeout = max(1, int(timeout))

    def _subprocess_git(
        self,
        args: list[str],
        cwd: str | None = None,
        timeout: int = 60,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self.repo_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )

    def _git(
        self,
        *args: str,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return self._run_git(list(args), cwd, timeout or self.timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return subprocess.CompletedProcess(
                ["git", *args],
                128,
                stdout="",
                stderr=str(exc),
            )

    def _output(self, *args: str, cwd: str | None = None) -> str:
        result = self._git(*args, cwd=cwd)
        if result.returncode != 0:
            raise ContainerCycleRepairError(
                f"git {' '.join(args[:2])} failed: "
                f"{(result.stderr or result.stdout or '').strip()[:1000]}"
            )
        return result.stdout.strip()

    def _remote_ref(self, branch: str) -> str:
        return f"refs/remotes/{self.remote}/{_validate_branch(branch)}"

    def _remote_branch(self, branch: str) -> str:
        return f"{self.remote}/{_validate_branch(branch)}"

    def remote_head(self, branch: str) -> str | None:
        """Return the fetched remote head for an exact branch name."""

        return self._ref_sha(self._remote_ref(branch))

    def _fetch(self) -> None:
        result = self._git("fetch", self.remote)
        if result.returncode != 0:
            raise ContainerCycleRepairError(
                "cycle repair fetch failed: "
                f"{(result.stderr or result.stdout or '').strip()[:1000]}"
            )

    def _ref_sha(self, ref: str) -> str | None:
        result = self._git("rev-parse", "--verify", ref)
        return result.stdout.strip() if result.returncode == 0 else None

    def _ancestor(self, ancestor: str, descendant: str) -> bool:
        return self._git("merge-base", "--is-ancestor", ancestor, descendant).returncode == 0

    def _commits_between(self, old_sha: str, selected_sha: str) -> set[str]:
        result = self._git("rev-list", f"{old_sha}..{selected_sha}")
        if result.returncode != 0:
            raise UnsafePrerequisite(
                f"cannot inspect prerequisite {selected_sha}: "
                f"{(result.stderr or result.stdout or '').strip()[:800]}"
            )
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}

    def validate_prerequisite_descendant(
        self,
        old_sha: str,
        selected_sha: str,
        declared_closure: Iterable[str],
    ) -> tuple[str, ...]:
        """Validate exact descendant + closure before any ref is changed."""

        old = str(old_sha or "").strip()
        selected = str(selected_sha or "").strip()
        closure = {str(sha).strip() for sha in declared_closure if str(sha).strip()}
        if not old or not selected or selected not in closure:
            raise UnsafePrerequisite(
                "selected prerequisite must be a non-empty member of its declared closure"
            )
        if not self._ancestor(old, selected):
            raise UnsafePrerequisite(
                f"selected prerequisite {selected} is not a descendant of {old}"
            )
        commits = self._commits_between(old, selected)
        # A declared closure may name tips; include every explicitly selected
        # tip, but never infer permission for an unlisted branch commit.
        if not commits.issubset(closure):
            unrelated = sorted(commits - closure)
            raise UnsafePrerequisite(
                f"selected prerequisite {selected} contains commits outside its "
                f"declared closure: {', '.join(unrelated[:8])}"
            )
        return tuple(sorted(commits))

    def _cas_push(self, branch: str, new_sha: str, expected_sha: str) -> str:
        result = self._git(
            "push",
            f"--force-with-lease=refs/heads/{_validate_branch(branch)}:{expected_sha}",
            self.remote,
            f"{new_sha}:refs/heads/{_validate_branch(branch)}",
        )
        if result.returncode == 0:
            return new_sha
        self._fetch()
        observed = self._ref_sha(self._remote_ref(branch))
        if observed == new_sha:
            return observed
        raise RefRace(
            f"compare-and-swap lost for {branch}: expected {expected_sha}, "
            f"observed {observed or '<missing'}"
        )

    def _advance_parent(
        self,
        plan: ContainerCycleRepairPlan,
        parent_branch: str,
        prior_parent_sha: str | None,
    ) -> tuple[str, str]:
        current = self._ref_sha(self._remote_ref(parent_branch))
        if not current:
            raise ContainerCycleRepairError(f"authoritative branch {parent_branch} is missing")
        expected = prior_parent_sha or current
        if prior_parent_sha and current != prior_parent_sha:
            # A prior push may have committed just before the process died. If
            # the remote already contains the selected closure, resume from it.
            if all(
                self._ancestor(sha, current) for sha in plan.selected_shas
            ):
                return expected, current
            raise RefRace(
                f"authoritative branch {parent_branch} changed from {prior_parent_sha} "
                f"to {current} before repair resumed"
            )

        closure = plan.declared_closure or plan.selected_shas
        for selected in plan.selected_shas:
            if self._ancestor(selected, current):
                continue
            self.validate_prerequisite_descendant(current, selected, closure)
            current = self._cas_push(parent_branch, selected, current)
            self._persist(
                {
                    "phase": "parent_advanced",
                    "parent_branch": parent_branch,
                    "parent_expected_sha": expected,
                    "parent_sha": current,
                }
            )
        return expected, current

    def _merge_parent_into_child(
        self,
        child_branch: str,
        child_sha: str,
        parent_branch: str,
        parent_sha: str,
    ) -> tuple[str, str]:
        if self._ancestor(parent_sha, child_sha):
            return child_sha, "already_reachable"
        if not self._ancestor(child_sha, parent_sha):
            probe = self._git("merge-tree", "--write-tree", child_sha, parent_sha)
            if probe.returncode != 0:
                raise MergeConflict(
                    f"parent-only synchronization conflicts for {child_branch}: "
                    f"{(probe.stderr or probe.stdout or '').strip()[:1000]}"
                )

        # Use an isolated detached worktree so a repair never touches an
        # operator/agent checkout.  A fast-forward needs no new object; a
        # diverged child gets one merge commit whose only second parent is the
        # authoritative parent branch.
        temp_parent = tempfile.mkdtemp(prefix="oompah-cycle-repair-")
        try:
            add = self._git("worktree", "add", "--detach", temp_parent, child_sha)
            if add.returncode != 0:
                raise ContainerCycleRepairError(
                    f"could not create isolated child repair worktree for {child_branch}: "
                    f"{(add.stderr or add.stdout or '').strip()[:800]}"
                )
            if self._ancestor(child_sha, parent_sha):
                merge = self._git("reset", "--hard", parent_sha, cwd=temp_parent)
                if merge.returncode != 0:
                    raise ContainerCycleRepairError(
                        f"could not fast-forward {child_branch}: "
                        f"{(merge.stderr or merge.stdout or '').strip()[:800]}"
                    )
                result_sha = parent_sha
                action = "fast_forward"
            else:
                merge = self._git(
                    "merge",
                    "--no-edit",
                    parent_sha,
                    cwd=temp_parent,
                )
                if merge.returncode != 0:
                    raise MergeConflict(
                        f"parent-only synchronization conflicts for {child_branch}: "
                        f"{(merge.stderr or merge.stdout or '').strip()[:1000]}"
                    )
                result_sha = self._output("rev-parse", "HEAD", cwd=temp_parent)
                action = "merge_parent"
            return result_sha, action
        finally:
            self._git("worktree", "remove", "--force", temp_parent)
            try:
                os.rmdir(temp_parent)
            except OSError:
                pass

    def execute(
        self,
        plan: ContainerCycleRepairPlan,
        *,
        prior_evidence: Mapping[str, object] | None = None,
    ) -> ContainerCycleRepairResult:
        """Run or resume a repair plan and return scoped durable evidence."""

        parent_branch = epic_branch(plan.authoritative_container)
        prior = dict(prior_evidence or {})
        result = ContainerCycleRepairResult(
            status="blocked",
            phase=str(prior.get("phase") or "planned"),
            parent_branch=parent_branch,
            parent_expected_sha=(
                str(prior["parent_expected_sha"])
                if prior.get("parent_expected_sha")
                else None
            ),
            parent_sha=(str(prior["parent_sha"]) if prior.get("parent_sha") else None),
        )
        try:
            self._fetch()
            expected, parent_sha = self._advance_parent(
                plan,
                parent_branch,
                result.parent_sha,
            )
            result.parent_expected_sha = expected
            result.parent_sha = parent_sha
            result.phase = "parent_advanced"
            self._persist(result.to_dict())

            conflict_containers: set[str] = set()
            for container_id in plan.dependent_containers:
                branch = epic_branch(container_id)
                observed_child_sha = self._ref_sha(self._remote_ref(branch))
                child = ChildRepairResult(
                    container_id=container_id,
                    branch=branch,
                    # The remote ref is the durable CAS authority.  A
                    # persisted expected SHA is retained in the journal for
                    # evidence, but never overrides a newer ref observed
                    # after a restart.
                    expected_sha=observed_child_sha,
                )
                if not child.expected_sha:
                    child.action = "missing"
                    child.error = f"dependent branch {branch} is missing"
                    conflict_containers.add(container_id)
                    result.children.append(child)
                    continue
                try:
                    if self._ancestor(parent_sha, child.expected_sha):
                        child.resulting_sha = child.expected_sha
                        child.action = "already_reachable"
                    else:
                        child.resulting_sha, child.action = self._merge_parent_into_child(
                            branch,
                            child.expected_sha,
                            parent_branch,
                            parent_sha,
                        )
                        child.resulting_sha = self._cas_push(
                            branch,
                            child.resulting_sha,
                            child.expected_sha,
                        )
                    self._persist(
                        {
                            "phase": "child_synchronized",
                            "parent_sha": parent_sha,
                            "child": child.to_dict(),
                        }
                    )
                except MergeConflict as exc:
                    child.action = "conflict"
                    child.error = str(exc)
                    conflict_containers.add(container_id)
                except RefRace as exc:
                    child.action = "ref_race"
                    child.error = str(exc)
                    conflict_containers.add(container_id)
                except ContainerCycleRepairError as exc:
                    child.action = "error"
                    child.error = str(exc)
                    conflict_containers.add(container_id)
                result.children.append(child)

            result.phase = "children_synchronized"
            affected = {
                child.container_id
                for child in result.children
                if child.action in {"already_reachable", "fast_forward", "merge_parent"}
            }
            result.restorable_rows = tuple(
                row.task_id for row in plan.rows if row.container_id in affected
            )
            result.changed_rows = tuple(
                row.task_id for row in plan.rows if row.container_id in conflict_containers
            )
            if conflict_containers:
                result.status = "partial"
                result.error = (
                    "container repair conflicts: "
                    + ", ".join(sorted(conflict_containers))
                )
                self._persist(result.to_dict())
                return result
            result.status = "ready_for_queue_restore"
            self._persist(result.to_dict())
            return result
        except ContainerCycleRepairError as exc:
            result.status = "blocked"
            result.error = str(exc)
            self._persist(result.to_dict())
            return result

    def prove_reachability(
        self,
        plan: ContainerCycleRepairPlan,
        result: ContainerCycleRepairResult,
    ) -> bool:
        """Prove every selected SHA reaches every synchronized child ref."""

        if not result.parent_sha:
            return False
        targets = [result.parent_sha]
        targets.extend(
            child.resulting_sha
            for child in result.children
            if child.resulting_sha and child.action in {
                "already_reachable",
                "fast_forward",
                "merge_parent",
            }
        )
        for target in targets:
            if not all(self._ancestor(sha, target) for sha in plan.selected_shas):
                return False
        return True


__all__ = [
    "ChildRepairResult",
    "ContainerCycleRepairError",
    "ContainerCycleRepairExecutor",
    "ContainerCycleRepairPlan",
    "ContainerCycleRepairResult",
    "CycleRepairRow",
    "MergeConflict",
    "RefRace",
    "UnsafePrerequisite",
    "epic_branch",
]
