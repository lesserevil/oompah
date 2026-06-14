"""Managed-project issue template refresh workflow.

Oompah owns a set of canonical GitHub issue templates (bug report, feature
request, question) that satisfy its intake validator.  This module lets
operators inspect whether a managed project's ``.github/ISSUE_TEMPLATE``
directory matches those canonical templates, preview exactly what would
change, and apply + commit + push the updates safely.

Design notes
------------
* Canonical templates are embedded here (not loaded from oompah's own
  ``.github/ISSUE_TEMPLATE``) so they travel with the library and are
  always available even when the oompah install is not a git checkout of
  the oompah repo.
* The apply path refuses to proceed when the managed repo has uncommitted
  changes that would be overwritten — dirty-worktree safety.
* Commit/push uses the project's configured git identity so the update is
  attributed correctly in the managed repo's history.
"""

from __future__ import annotations

import difflib
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical templates
# ---------------------------------------------------------------------------

CANONICAL_BUG_REPORT = """\
name: Bug Report
description: Report something broken in an oompah-managed project
title: "[Bug] "
labels: ["type:bug"]
body:
  - type: markdown
    attributes:
      value: |
        Bug reports must include enough detail for oompah to validate the issue before it enters the backlog.
  - type: textarea
    id: problem
    attributes:
      label: Problem
      description: What is broken, and why does it matter?
      placeholder: |
        The service appears healthy, but new Open issues do not dispatch.
    validations:
      required: true
  - type: textarea
    id: steps_to_reproduce
    attributes:
      label: Steps to Reproduce
      description: Provide numbered steps, or explain why the bug is not reliably reproducible.
      placeholder: |
        1. Start the service.
        2. Create or move an issue to Open.
        3. Observe that no agent starts.
    validations:
      required: true
  - type: textarea
    id: actual_behavior
    attributes:
      label: Actual Behavior
      description: What currently happens?
      placeholder: |
        The UI shows no alerts, but the dispatch loop has stopped ticking.
    validations:
      required: true
  - type: textarea
    id: expected_behavior
    attributes:
      label: Expected Behavior
      description: What should happen instead?
      placeholder: |
        Oompah should surface an alert and recover or restart the dispatch loop safely.
    validations:
      required: true
  - type: textarea
    id: acceptance_criteria
    attributes:
      label: Acceptance Criteria
      description: List concrete checks that prove the bug is fixed.
      placeholder: |
        - The stale loop condition is detected.
        - A regression test covers the failure.
    validations:
      required: true
  - type: textarea
    id: environment
    attributes:
      label: Environment
      description: OS, version, branch, command, runner, browser, or other relevant context.
      placeholder: |
        Ubuntu 24.04, oompah main, service on port 8090
    validations:
      required: false
  - type: textarea
    id: logs
    attributes:
      label: Logs or Screenshots
      description: Paste relevant logs, screenshots, or links.
    validations:
      required: false
"""

CANONICAL_FEATURE_REQUEST = """\
name: Feature Request
description: Request a new capability or workflow improvement
title: "[Feature] "
labels: ["type:feature"]
body:
  - type: markdown
    attributes:
      value: |
        Feature requests should describe the user problem, desired behavior, and acceptance criteria.
  - type: textarea
    id: problem
    attributes:
      label: Problem
      description: What user need, workflow gap, or limitation should this solve?
      placeholder: |
        I want to add a managed project without hand-editing multiple config files.
    validations:
      required: true
  - type: textarea
    id: desired_behavior
    attributes:
      label: Desired Behavior
      description: What should the system do after this change?
      placeholder: |
        Oompah should provide a guided project setup flow that validates repo access and tracker settings.
    validations:
      required: true
  - type: textarea
    id: acceptance_criteria
    attributes:
      label: Acceptance Criteria
      description: List concrete checks that prove the feature is complete.
      placeholder: |
        - A project can be added through the UI.
        - Invalid repo credentials show an actionable error.
        - Tests cover the setup flow.
    validations:
      required: true
  - type: textarea
    id: use_case
    attributes:
      label: Use Case
      description: Describe the specific workflow or user scenario.
      placeholder: |
        A project owner wants to onboard a repository and have new GitHub issues appear in oompah.
    validations:
      required: false
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives Considered
      description: Workarounds, prior art, or designs you considered.
    validations:
      required: false
"""

CANONICAL_QUESTION = """\
name: Question
description: Ask a question that may reveal a documentation or workflow gap
title: "[Question] "
labels: ["type:task"]
body:
  - type: markdown
    attributes:
      value: |
        Questions are tracked as tasks when answering them may require documentation, clarification, or follow-up work.
  - type: textarea
    id: problem
    attributes:
      label: Problem
      description: What are you trying to understand or accomplish?
      placeholder: |
        I am trying to understand how oompah maps GitHub issue labels to task states.
    validations:
      required: true
  - type: textarea
    id: desired_behavior
    attributes:
      label: Desired Behavior
      description: What answer, decision, or documentation outcome would resolve this?
      placeholder: |
        I need a clear explanation of the state mapping and where it is configured.
    validations:
      required: true
  - type: textarea
    id: acceptance_criteria
    attributes:
      label: Acceptance Criteria
      description: How will we know the question has been answered?
      placeholder: |
        - The answer is documented in the issue or docs.
        - Any discovered follow-up work is linked.
    validations:
      required: true
  - type: textarea
    id: docs_checked
    attributes:
      label: Documentation Checked
      description: Which docs, issues, or code paths did you already check?
      placeholder: |
        README.md, docs/github-issue-intake.md, related GitHub issues
    validations:
      required: false
"""

# Maps filename → canonical content.  config.yml is intentionally excluded:
# it may have project-specific contact links and we only manage the three
# functional templates that the intake validator depends on.
CANONICAL_TEMPLATES: dict[str, str] = {
    "bug_report.yml": CANONICAL_BUG_REPORT,
    "feature_request.yml": CANONICAL_FEATURE_REQUEST,
    "question.yml": CANONICAL_QUESTION,
}

TEMPLATE_SUBDIR = ".github/ISSUE_TEMPLATE"


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class TemplateDrift:
    """State of one issue template file relative to the canonical version."""

    filename: str
    canonical: str
    current: str | None  # None means file is absent in the managed repo
    is_current: bool
    diff: str  # Unified diff; empty when is_current is True


@dataclass
class TemplateRefreshStatus:
    """Drift status for all canonical templates in a managed project."""

    all_current: bool
    drifted: list[TemplateDrift] = field(default_factory=list)
    current: list[TemplateDrift] = field(default_factory=list)


@dataclass
class TemplateApplyResult:
    """Result of applying canonical templates to a managed repo."""

    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    commit_sha: str = ""
    pushed: bool = False
    error: str = ""


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


def _template_dir(repo_path: str | Path) -> Path:
    return Path(repo_path) / TEMPLATE_SUBDIR


def _read_current(repo_path: str | Path, filename: str) -> str | None:
    """Return the file content from the managed repo, or None if absent."""
    path = _template_dir(repo_path) / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None


def _build_drift(filename: str, canonical: str, current: str | None) -> TemplateDrift:
    """Build a TemplateDrift for one template file."""
    is_current = current == canonical
    diff = ""
    if not is_current:
        from_lines = (current or "").splitlines(keepends=True)
        to_lines = canonical.splitlines(keepends=True)
        diff = "".join(
            difflib.unified_diff(
                from_lines,
                to_lines,
                fromfile=f"a/{TEMPLATE_SUBDIR}/{filename}",
                tofile=f"b/{TEMPLATE_SUBDIR}/{filename}",
            )
        )
    return TemplateDrift(
        filename=filename,
        canonical=canonical,
        current=current,
        is_current=is_current,
        diff=diff,
    )


def check_template_drift(repo_path: str | Path) -> TemplateRefreshStatus:
    """Return a :class:`TemplateRefreshStatus` for the managed repo at *repo_path*.

    Compares each canonical template against the file currently present in
    ``<repo_path>/.github/ISSUE_TEMPLATE/``.  Missing files are reported as
    drifted (effectively an empty-string diff from nothing to the canonical
    content).
    """
    drifted: list[TemplateDrift] = []
    current: list[TemplateDrift] = []

    for filename, canonical in CANONICAL_TEMPLATES.items():
        existing = _read_current(repo_path, filename)
        drift = _build_drift(filename, canonical, existing)
        if drift.is_current:
            current.append(drift)
        else:
            drifted.append(drift)

    return TemplateRefreshStatus(
        all_current=len(drifted) == 0,
        drifted=drifted,
        current=current,
    )


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def preview_template_updates(repo_path: str | Path) -> str:
    """Return a combined unified diff previewing the pending template updates.

    Returns an empty string when all templates are already current.
    """
    status = check_template_drift(repo_path)
    if status.all_current:
        return ""
    return "\n".join(d.diff for d in status.drifted if d.diff)


# ---------------------------------------------------------------------------
# Dirty worktree detection
# ---------------------------------------------------------------------------


def _repo_is_dirty(repo_path: str | Path, paths: list[str]) -> list[str]:
    """Return the subset of *paths* (relative to repo_path) that git considers
    dirty (modified, staged, or untracked and matching the list).

    A path that does not yet exist is *not* considered dirty — it will be
    created by the apply step.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "-u"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"git status failed: {exc}") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"git status exited {result.returncode}: {result.stderr.strip()[:200]}"
        )

    dirty: set[str] = set()
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        # "XY path" — columns 0-1 are status codes, column 2 is a space.
        relative = line[3:].strip()
        dirty.add(relative)

    # Check which of the template paths are in the dirty set.
    conflicts = []
    for p in paths:
        if p in dirty:
            conflicts.append(p)
    return conflicts


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply_template_updates(
    repo_path: str | Path,
    *,
    git_user_name: str | None = None,
    git_user_email: str | None = None,
    branch: str = "main",
    commit_message: str = "chore: refresh oompah canonical issue templates",
    push: bool = True,
    dry_run: bool = False,
) -> TemplateApplyResult:
    """Write canonical templates into the managed repo and commit/push.

    Parameters
    ----------
    repo_path:
        Absolute path to the managed project's git checkout.
    git_user_name / git_user_email:
        Identity to use for the commit.  Falls back to the repo's existing
        git config when not provided.
    branch:
        Branch to commit and push to.  Must already be checked out in
        *repo_path*.
    commit_message:
        The commit message.
    push:
        When True, run ``git push`` after committing.
    dry_run:
        When True, report what would happen without writing or committing.

    Returns
    -------
    TemplateApplyResult with ``error`` set on failure.
    """
    repo_path = Path(repo_path)
    result = TemplateApplyResult()

    # --- Drift check ---
    status = check_template_drift(repo_path)
    if status.all_current:
        result.skipped = list(CANONICAL_TEMPLATES.keys())
        return result

    # Build the relative paths that will be written.
    to_write = [
        f"{TEMPLATE_SUBDIR}/{d.filename}" for d in status.drifted
    ]

    # --- Dirty worktree check ---
    # We only check the files we intend to touch.  Other uncommitted changes
    # are the operator's business.
    try:
        conflicts = _repo_is_dirty(repo_path, to_write)
    except RuntimeError as exc:
        result.error = f"dirty-worktree check failed: {exc}"
        return result

    if conflicts:
        result.error = (
            "Refused: the following files have uncommitted changes in the managed repo "
            "that would be overwritten — commit or stash them first:\n"
            + "\n".join(f"  {p}" for p in conflicts)
        )
        return result

    if dry_run:
        result.applied = to_write
        return result

    # --- Write files ---
    template_dir = _template_dir(repo_path)
    template_dir.mkdir(parents=True, exist_ok=True)

    for drift in status.drifted:
        dest = template_dir / drift.filename
        try:
            dest.write_text(drift.canonical, encoding="utf-8")
            result.applied.append(f"{TEMPLATE_SUBDIR}/{drift.filename}")
        except OSError as exc:
            result.error = f"Failed to write {drift.filename}: {exc}"
            return result

    result.skipped = [f"{TEMPLATE_SUBDIR}/{d.filename}" for d in status.current]

    # --- Git identity env ---
    env = os.environ.copy()
    if git_user_name:
        env["GIT_AUTHOR_NAME"] = git_user_name
        env["GIT_COMMITTER_NAME"] = git_user_name
    if git_user_email:
        env["GIT_AUTHOR_EMAIL"] = git_user_email
        env["GIT_COMMITTER_EMAIL"] = git_user_email

    def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

    # --- git add ---
    add = _run(["git", "add"] + result.applied)
    if add.returncode != 0:
        result.error = f"git add failed: {add.stderr.strip()[:300]}"
        return result

    # --- git commit ---
    commit = _run(["git", "commit", "-m", commit_message])
    if commit.returncode != 0:
        stderr = commit.stderr.strip()[:300]
        # "nothing to commit" is not an error — the drift check raced.
        if "nothing to commit" in commit.stdout or "nothing to commit" in stderr:
            result.applied = []
            result.skipped = list(CANONICAL_TEMPLATES.keys())
            return result
        result.error = f"git commit failed: {stderr}"
        return result

    # Extract the new commit SHA.
    sha_r = _run(["git", "rev-parse", "HEAD"])
    if sha_r.returncode == 0:
        result.commit_sha = sha_r.stdout.strip()

    # --- git push ---
    if push:
        push_r = _run(
            ["git", "push", "origin", branch],
            timeout=60,
        )
        if push_r.returncode != 0:
            result.error = f"git push failed: {push_r.stderr.strip()[:300]}"
            return result
        result.pushed = True

    return result


# ---------------------------------------------------------------------------
# Server-level helpers
# ---------------------------------------------------------------------------


def ensure_issue_templates(
    repo_path: str | Path,
    *,
    git_user_name: str | None = None,
    git_user_email: str | None = None,
    branch: str = "main",
    push: bool = True,
) -> bool:
    """Idempotently write canonical templates and commit/push if needed.

    Returns True when a commit was made, False when all templates were
    already current.  Raises RuntimeError on failure.
    """
    result = apply_template_updates(
        repo_path,
        git_user_name=git_user_name,
        git_user_email=git_user_email,
        branch=branch,
        push=push,
    )
    if result.error:
        raise RuntimeError(result.error)
    return bool(result.applied)
