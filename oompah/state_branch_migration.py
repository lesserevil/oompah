"""State-branch migration engine for existing oompah-managed projects (OOMPAH-259).

Provides an explicit, operator-driven migration path for projects whose
``.oompah/`` task tree currently lives on the default branch (``main``).
Migration is split into three stages as defined in plans/state-branch-design.md
§ 6:

  Stage A – Bootstrap orphan state branch; enable shadow writes to BOTH
             the state branch (primary) and the default branch (shadow).
             This allows zero-data-loss rollback during the soak window.

  Stage B – Disable shadow writes; the tracker now reads and writes
             exclusively from the state branch.  Task files on the default
             branch become a snapshot for rollback only.

  Stage C – (optional, operator-initiated) Delete ``.oompah/tasks/`` from
             the default branch.  This is the only irreversible step.

Rollback is supported from Stage A and Stage B (see ``rollback_migration``).

Design reference: plans/state-branch-design.md § 6, § 7
Operator guide:   docs/state-branch-migration.md
"""

from __future__ import annotations

import logging
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

TASKS_DIR = ".oompah/tasks"

_VALID_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ValidationCheck:
    """Result of a single pre-migration validation check."""
    name: str
    passed: bool
    message: str = ""


@dataclass
class ValidationResult:
    """Aggregate result of all pre-migration validation checks."""
    checks: list[ValidationCheck] = field(default_factory=list)
    all_passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "message": c.message}
                for c in self.checks
            ],
        }


@dataclass
class MigrationResult:
    """Result of a migration stage operation."""
    stage: str             # "A", "B", "C", "rollback", or ""
    ok: bool = False
    already_done: bool = False
    message: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "ok": self.ok,
            "already_done": self.already_done,
            "message": self.message,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Internal git helpers
# ---------------------------------------------------------------------------


def _git(
    args: list[str],
    *,
    cwd: str | Path,
    check: bool = False,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Run a git command in *cwd*; never raise on non-zero exit."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _git_check(
    args: list[str],
    *,
    cwd: str | Path,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Run a git command; raise RuntimeError on non-zero exit."""
    r = _git(args, cwd=cwd, timeout=timeout)
    if r.returncode != 0:
        err = r.stderr.strip() or r.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)}: {err}")
    return r


def _branch_exists_local(repo: Path, branch: str) -> bool:
    return _git(["rev-parse", "--verify", branch], cwd=repo).returncode == 0


def _branch_exists_remote(repo: Path, branch: str) -> bool:
    return (
        _git(
            ["rev-parse", "--verify", f"refs/remotes/origin/{branch}"],
            cwd=repo,
        ).returncode
        == 0
    )


def _has_remote(repo: Path, name: str = "origin") -> bool:
    return _git(["remote", "get-url", name], cwd=repo).returncode == 0


def _current_branch(repo: Path) -> str | None:
    r = _git(["symbolic-ref", "--short", "HEAD"], cwd=repo)
    return r.stdout.strip() if r.returncode == 0 else None


def _task_files_valid_yaml(tasks_dir: Path) -> tuple[int, list[str]]:
    """Validate YAML front matter of all task files.

    Returns (valid_count, list_of_error_messages).
    """
    errors: list[str] = []
    count = 0
    if not tasks_dir.is_dir():
        return 0, []
    for md_file in tasks_dir.rglob("*.md"):
        count += 1
        text = md_file.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---\n"):
            errors.append(f"{md_file.relative_to(tasks_dir.parent.parent)}: missing YAML front matter")
            continue
        end = text.find("\n---", 4)
        if end < 0:
            errors.append(f"{md_file.relative_to(tasks_dir.parent.parent)}: unclosed YAML front matter")
            continue
        try:
            yaml.load(text[4:end], Loader=_VALID_YAML_LOADER)  # noqa: S506
        except yaml.YAMLError as exc:
            errors.append(
                f"{md_file.relative_to(tasks_dir.parent.parent)}: invalid YAML: {exc}"
            )
    return count, errors


def _check_no_duplicate_task_ids(tasks_dir: Path) -> list[str]:
    """Return list of error messages for duplicate task IDs."""
    seen: dict[str, Path] = {}
    errors: list[str] = []
    if not tasks_dir.is_dir():
        return errors
    for md_file in tasks_dir.rglob("*.md"):
        text = md_file.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---", 4)
        if end < 0:
            continue
        try:
            meta = yaml.load(text[4:end], Loader=_VALID_YAML_LOADER) or {}  # noqa: S506
        except yaml.YAMLError:
            continue
        task_id = str(meta.get("id") or md_file.stem).upper()
        if task_id in seen:
            errors.append(
                f"Duplicate task ID {task_id!r}: "
                f"{md_file} vs {seen[task_id]}"
            )
        else:
            seen[task_id] = md_file
    return errors


# ---------------------------------------------------------------------------
# Pre-migration validation (design § 6.1)
# ---------------------------------------------------------------------------


def validate_state_branch(
    repo_path: str | Path,
    project_id: str,
    *,
    default_branch: str = "main",
) -> ValidationResult:
    """Run all pre-migration validation checks for a project.

    Parameters
    ----------
    repo_path:
        Absolute path to the managed git checkout (the project's ``repo_path``).
    project_id:
        The project's stable ID (e.g. ``"proj-14849f1b"``).  Used to compute
        the state branch name.
    default_branch:
        The project's default code branch.  Default ``"main"``.

    Returns
    -------
    ValidationResult
        Contains per-check results and an aggregate ``all_passed`` flag.
    """
    repo = Path(repo_path)
    branch_name = f"oompah/state/{project_id}"
    checks: list[ValidationCheck] = []

    # 1 — Default branch is clean
    status = _git(["status", "--porcelain"], cwd=repo)
    if status.returncode != 0:
        checks.append(ValidationCheck(
            "default branch is clean",
            False,
            f"git status failed: {status.stderr.strip() or status.stdout.strip()}",
        ))
    else:
        dirty_lines = [
            ln for ln in status.stdout.splitlines()
            if not ln.startswith("??")
        ]
        if dirty_lines:
            checks.append(ValidationCheck(
                "default branch is clean",
                False,
                f"Managed checkout has {len(dirty_lines)} uncommitted file(s). "
                "Run `make restart` to trigger the service's automatic repo-heal pass.",
            ))
        else:
            checks.append(ValidationCheck("default branch is clean", True))

    # 2 — Default branch up-to-date
    has_remote = _has_remote(repo)
    if has_remote:
        fetch = _git(["fetch", "origin", default_branch], cwd=repo, timeout=30)
        if fetch.returncode != 0:
            checks.append(ValidationCheck(
                "default branch up-to-date",
                False,
                f"Cannot fetch from origin: {fetch.stderr.strip() or fetch.stdout.strip()}",
            ))
        else:
            behind = _git(
                ["log", "HEAD..origin/" + default_branch, "--oneline"],
                cwd=repo,
            )
            behind_count = len(behind.stdout.strip().splitlines()) if behind.returncode == 0 else 0
            if behind_count > 0:
                checks.append(ValidationCheck(
                    "default branch up-to-date",
                    False,
                    f"Local {default_branch!r} is {behind_count} commit(s) behind origin. "
                    f"Run: git -C <checkout> pull --ff-only origin {default_branch}",
                ))
            else:
                checks.append(ValidationCheck("default branch up-to-date", True))
    else:
        checks.append(ValidationCheck(
            "default branch up-to-date",
            True,
            "No remote configured — skipping remote sync check.",
        ))

    # 3 — No conflicting state branch (or existing is recent)
    local_ok = _branch_exists_local(repo, branch_name)
    remote_ok = has_remote and _branch_exists_remote(repo, branch_name)
    if local_ok or remote_ok:
        checks.append(ValidationCheck(
            "no conflicting state branch",
            True,
            f"State branch {branch_name!r} already exists — "
            "migration will reuse it (idempotent).",
        ))
    else:
        checks.append(ValidationCheck("no conflicting state branch", True))

    # 4 — Service account can push (dry-run)
    if has_remote:
        push_target = (
            f"HEAD:{branch_name}" if (local_ok or remote_ok) else
            f"HEAD:{branch_name}"
        )
        dry_run = _git(
            ["push", "--dry-run", "origin", push_target],
            cwd=repo,
            timeout=30,
        )
        if dry_run.returncode != 0:
            err = dry_run.stderr.strip() or dry_run.stdout.strip()
            checks.append(ValidationCheck(
                "service account can push",
                False,
                f"git push --dry-run failed: {err}. "
                "Verify that GITHUB_TOKEN has write access to this repository.",
            ))
        else:
            checks.append(ValidationCheck("service account can push", True))

        # 5 — Branch protection check (look for 403 in dry-run output)
        if dry_run.returncode != 0 and ("403" in err or "protected" in err.lower()):
            checks.append(ValidationCheck(
                "branch protection allows push",
                False,
                "Branch protection is blocking direct push to the state branch. "
                "Add a protection rule for 'oompah/state/*' that allows the "
                "service account to push directly (no PR required). "
                "See docs/state-branch-migration.md § Step 2.",
            ))
        else:
            checks.append(ValidationCheck(
                "branch protection allows push",
                True,
                "" if dry_run.returncode == 0 else
                "Push dry-run failed but not due to branch protection — "
                "check the error above.",
            ))
    else:
        checks.append(ValidationCheck(
            "service account can push",
            True,
            "No remote configured — skipping push dry-run.",
        ))
        checks.append(ValidationCheck(
            "branch protection allows push",
            True,
            "No remote configured — skipping branch protection check.",
        ))

    # 6 — Task files have valid YAML front matter
    tasks_dir = repo / TASKS_DIR
    task_count, yaml_errors = _task_files_valid_yaml(tasks_dir)
    if yaml_errors:
        checks.append(ValidationCheck(
            "task files have valid YAML",
            False,
            f"{task_count} task(s) checked; {len(yaml_errors)} corrupt: "
            + "; ".join(yaml_errors[:3])
            + ("..." if len(yaml_errors) > 3 else ""),
        ))
    else:
        checks.append(ValidationCheck(
            "task files have valid YAML",
            True,
            f"{task_count} task(s) checked, 0 corrupt.",
        ))

    # 7 — No duplicate task IDs
    dup_errors = _check_no_duplicate_task_ids(tasks_dir)
    if dup_errors:
        checks.append(ValidationCheck(
            "no duplicate task IDs",
            False,
            "; ".join(dup_errors),
        ))
    else:
        checks.append(ValidationCheck("no duplicate task IDs", True))

    all_passed = all(c.passed for c in checks)
    return ValidationResult(checks=checks, all_passed=all_passed)


# ---------------------------------------------------------------------------
# Stage A migration
# ---------------------------------------------------------------------------


def migrate_stage_a(
    repo_path: str | Path,
    project_id: str,
    *,
    default_branch: str = "main",
    push: bool = True,
) -> MigrationResult:
    """Stage A: Bootstrap the state branch and enable shadow writes.

    Creates an orphan state branch seeded from the current task state on the
    default branch, then pushes it to origin.  Returns a result object; never
    raises.  Idempotent — safe to call multiple times.

    Parameters
    ----------
    repo_path:
        Absolute path to the managed git checkout.
    project_id:
        Project stable ID (used to compute branch name).
    default_branch:
        The project's default code branch.  Default ``"main"``.
    push:
        Whether to push the state branch to origin.  Set to ``False`` in
        test environments without a remote.

    After this call succeeds, the caller must update the project config:
    - ``state_branch_enabled = True``
    - ``state_branch_shadow_write = True``
    - ``state_branch_migration_stage = "A"``
    """
    from oompah.project_bootstrap import initialize_state_branch  # avoid circular

    repo = Path(repo_path)
    stage = "A"

    try:
        # Initialise (or reuse) the state branch.
        result = initialize_state_branch(
            repo,
            project_id,
            default_branch=default_branch,
            push=push,
        )
        if result.error:
            return MigrationResult(
                stage=stage,
                ok=False,
                error=f"State branch bootstrap failed: {result.error}",
            )

        already_done = result.already_existed
        msg = (
            f"State branch {result.branch_name!r} already existed — reusing."
            if already_done
            else f"State branch {result.branch_name!r} created (commit {result.commit_sha[:8]})."
        )
        logger.info("Stage A migration: %s", msg)

        return MigrationResult(
            stage=stage,
            ok=True,
            already_done=already_done,
            message=msg,
        )
    except Exception as exc:
        logger.exception("Stage A migration failed for project %s", project_id)
        return MigrationResult(stage=stage, ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# Stage B migration
# ---------------------------------------------------------------------------


def migrate_stage_b(
    repo_path: str | Path,
    project_id: str,
    *,
    default_branch: str = "main",
) -> MigrationResult:
    """Stage B: Disable shadow writes; state branch becomes the sole write target.

    Verifies that the state branch exists and is healthy before returning.  The
    default branch's ``.oompah/tasks/`` files are left in place as a rollback
    snapshot — they are NOT deleted here.

    After this call, the caller must update the project config:
    - ``state_branch_shadow_write = False``
    - ``state_branch_migration_stage = "B"``

    Stage A must have been completed before calling this.
    """
    repo = Path(repo_path)
    branch_name = f"oompah/state/{project_id}"
    stage = "B"

    try:
        local_ok = _branch_exists_local(repo, branch_name)
        remote_ok = _has_remote(repo) and _branch_exists_remote(repo, branch_name)

        if not local_ok and not remote_ok:
            return MigrationResult(
                stage=stage,
                ok=False,
                error=(
                    f"State branch {branch_name!r} does not exist. "
                    "Complete Stage A first."
                ),
            )

        # Sync from remote to ensure state branch is up-to-date.
        if _has_remote(repo):
            fetch = _git(["fetch", "origin", branch_name], cwd=repo, timeout=30)
            if fetch.returncode != 0:
                logger.warning(
                    "Stage B: fetch of %r failed (non-fatal): %s",
                    branch_name,
                    fetch.stderr.strip(),
                )

        msg = (
            f"State branch {branch_name!r} validated. "
            "Shadow writes will be disabled; "
            f"task files on {default_branch!r} are preserved as a rollback snapshot."
        )
        logger.info("Stage B migration: %s", msg)
        return MigrationResult(stage=stage, ok=True, message=msg)

    except Exception as exc:
        logger.exception("Stage B migration failed for project %s", project_id)
        return MigrationResult(stage=stage, ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# Stage C migration (optional)
# ---------------------------------------------------------------------------


def migrate_stage_c(
    repo_path: str | Path,
    project_id: str,
    *,
    default_branch: str = "main",
    push: bool = True,
) -> MigrationResult:
    """Stage C (optional): Remove ``.oompah/tasks/`` from the default branch.

    This is the only **irreversible** migration step.  Only call this after
    the recommended 30-day soak window post-Stage B, when you are confident
    that rollback is not required.

    After Stage C the default branch no longer carries any task state; recovery
    from this point requires restoring from the state branch.
    """
    repo = Path(repo_path)
    stage = "C"

    try:
        # Ensure we are on the default branch.
        cur = _current_branch(repo)
        if cur != default_branch:
            return MigrationResult(
                stage=stage,
                ok=False,
                error=(
                    f"Stage C requires the checkout to be on {default_branch!r}; "
                    f"currently on {cur!r}. Switch branches and retry."
                ),
            )

        tasks_dir = repo / TASKS_DIR
        if not tasks_dir.exists():
            return MigrationResult(
                stage=stage,
                ok=True,
                already_done=True,
                message=f"{TASKS_DIR} is already absent from {default_branch!r}.",
            )

        # Sync from origin before modifying.
        if _has_remote(repo):
            _git(["fetch", "origin", default_branch], cwd=repo, timeout=30)
            _git(
                ["merge", "--ff-only", f"origin/{default_branch}"],
                cwd=repo,
            )

        # Remove the task tree from the default branch.
        rm_result = _git(["rm", "-r", TASKS_DIR], cwd=repo)
        if rm_result.returncode != 0:
            return MigrationResult(
                stage=stage,
                ok=False,
                error=(
                    f"git rm -r {TASKS_DIR} failed: "
                    f"{rm_result.stderr.strip() or rm_result.stdout.strip()}"
                ),
            )

        _git_check(
            [
                "commit",
                "-m",
                (
                    f"Remove migrated oompah task state from {default_branch}\n\n"
                    "Stage C migration: task state is now exclusively on the "
                    f"state branch (oompah/state/{project_id}). "
                    "See docs/state-branch-migration.md.\n\n"
                    "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
                    "Co-authored-by: oompah <lesserevil@users.noreply.github.com>\n"
                ),
            ],
            cwd=repo,
        )

        if push and _has_remote(repo):
            _git_check(
                ["push", "origin", f"HEAD:{default_branch}"],
                cwd=repo,
                timeout=60,
            )

        msg = (
            f"Removed {TASKS_DIR} from {default_branch!r} "
            "(Stage C complete). This step is irreversible without "
            "restoring from the state branch."
        )
        logger.info("Stage C migration complete for project %s: %s", project_id, msg)
        return MigrationResult(stage=stage, ok=True, message=msg)

    except Exception as exc:
        logger.exception("Stage C migration failed for project %s", project_id)
        return MigrationResult(stage=stage, ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback_migration(
    repo_path: str | Path,
    project_id: str,
    *,
    default_branch: str = "main",
    current_stage: str = "",
    push: bool = True,
) -> MigrationResult:
    """Roll back a state-branch migration to legacy default-branch mode.

    Supports rollback from Stage A and Stage B.  Stage C rollback is also
    supported (restores task files from the state branch).

    After a successful rollback the caller must update the project config:
    - ``state_branch_enabled = False``
    - ``state_branch_shadow_write = False``
    - ``state_branch_migration_stage = ""``

    Parameters
    ----------
    repo_path:
        Absolute path to the managed git checkout.
    project_id:
        The project's stable ID.
    default_branch:
        The project's default code branch.  Default ``"main"``.
    current_stage:
        The stage the project is currently at (``"A"``, ``"B"``, or ``""``).
        Used to choose the correct recovery path.
    push:
        Whether to push the restored default branch to origin.
    """
    repo = Path(repo_path)
    branch_name = f"oompah/state/{project_id}"

    try:
        if current_stage == "A":
            # Stage A rollback: shadow writes kept default branch in sync.
            # No git operations needed — just update the project config.
            return MigrationResult(
                stage="rollback",
                ok=True,
                message=(
                    "Rolled back from Stage A. "
                    "Default branch is in sync (shadow writes preserved all mutations). "
                    "Update project config: state_branch_enabled=False, "
                    "state_branch_shadow_write=False, state_branch_migration_stage=''."
                ),
            )

        # Stage B or C rollback: need to restore task files from the state branch.
        # 1. Ensure the state branch is available.
        local_ok = _branch_exists_local(repo, branch_name)
        remote_ok = _has_remote(repo) and _branch_exists_remote(repo, branch_name)
        if not local_ok and not remote_ok:
            return MigrationResult(
                stage="rollback",
                ok=False,
                error=(
                    f"Cannot rollback: state branch {branch_name!r} does not exist "
                    "locally or at origin. Manual recovery required."
                ),
            )

        # 2. Ensure the main checkout is on the default branch.
        cur = _current_branch(repo)
        if cur != default_branch:
            _git_check(["checkout", default_branch], cwd=repo)

        # 3. Sync default branch from origin.
        if _has_remote(repo):
            _git(["fetch", "origin", default_branch], cwd=repo, timeout=30)
            ff = _git(
                ["merge", "--ff-only", f"origin/{default_branch}"],
                cwd=repo,
            )
            if ff.returncode != 0:
                logger.warning(
                    "Rollback: merge --ff-only failed, attempting rebase: %s",
                    ff.stderr.strip(),
                )
                _git_check(
                    ["rebase", "--autostash", f"origin/{default_branch}"],
                    cwd=repo,
                )

        # 4. Also fetch the state branch.
        if _has_remote(repo) and remote_ok:
            _git(["fetch", "origin", branch_name], cwd=repo, timeout=30)

        # 5. Restore .oompah/ from state branch HEAD into the main checkout.
        checkout_result = _git(
            ["checkout", branch_name, "--", ".oompah/"],
            cwd=repo,
        )
        if checkout_result.returncode != 0:
            return MigrationResult(
                stage="rollback",
                ok=False,
                error=(
                    f"Cannot restore .oompah/ from {branch_name!r}: "
                    f"{checkout_result.stderr.strip() or checkout_result.stdout.strip()}"
                ),
            )

        # 6. Stage and commit.
        _git(["add", ".oompah/"], cwd=repo)
        diff = _git(
            ["diff", "--cached", "--quiet", "--", ".oompah/"],
            cwd=repo,
        )
        if diff.returncode != 0:
            _git_check(
                [
                    "commit",
                    "-m",
                    (
                        f"Restore oompah task state from state branch\n\n"
                        f"Rollback from Stage {current_stage or 'B/C'} migration. "
                        f"Task files restored from {branch_name}. "
                        "state_branch_enabled will be set to False. "
                        "See docs/state-branch-migration.md.\n\n"
                        "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
                        "Co-authored-by: oompah <lesserevil@users.noreply.github.com>\n"
                    ),
                ],
                cwd=repo,
            )

        # 7. Push to origin.
        if push and _has_remote(repo):
            _git_check(
                ["push", "origin", f"HEAD:{default_branch}"],
                cwd=repo,
                timeout=60,
            )

        msg = (
            f"Rolled back from Stage {current_stage or 'B/C'}: "
            f"task files restored from {branch_name!r} onto {default_branch!r}. "
            "The state branch is preserved. "
            "Update project config: state_branch_enabled=False, "
            "state_branch_shadow_write=False, state_branch_migration_stage=''."
        )
        logger.info("Rollback complete for project %s: %s", project_id, msg)
        return MigrationResult(stage="rollback", ok=True, message=msg)

    except Exception as exc:
        logger.exception("Rollback failed for project %s", project_id)
        return MigrationResult(stage="rollback", ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# Status helper
# ---------------------------------------------------------------------------


def get_migration_status(
    repo_path: str | Path,
    project_id: str,
    *,
    default_branch: str = "main",
) -> dict[str, Any]:
    """Return the current migration status for a project.

    Used by ``oompah admin state-branch-status`` and the API endpoint.
    """
    repo = Path(repo_path)
    branch_name = f"oompah/state/{project_id}"
    local_ok = _branch_exists_local(repo, branch_name)
    remote_ok = _has_remote(repo) and _branch_exists_remote(repo, branch_name)

    last_commit: str | None = None
    if local_ok:
        r = _git(["log", "-1", "--format=%H %ai", branch_name], cwd=repo)
        if r.returncode == 0:
            last_commit = r.stdout.strip()

    tasks_on_default = (repo / TASKS_DIR).is_dir()

    return {
        "branch_name": branch_name,
        "branch_exists_local": local_ok,
        "branch_exists_remote": remote_ok,
        "tasks_on_default_branch": tasks_on_default,
        "last_state_branch_commit": last_commit,
    }
