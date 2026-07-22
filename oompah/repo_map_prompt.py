"""Repository-map context injection for agent startup prompts (OOMPAH-298).

This module provides :func:`build_repo_map_context`, the fail-open function
that integrates repository maps (produced by OOMPAH-296/OOMPAH-297) into
agent startup prompts.

Behaviour contract
------------------
1. Resolve the workspace HEAD SHA via ``git rev-parse HEAD``.
2. Derive the state-branch worktree path from the workspace git common
   directory (same convention as ``OompahMdTracker._state_worktree_path``).
3. Read a fresh, project-scoped artifact via :func:`~oompah.repo_map.read_repo_map`.
   If no fresh artifact exists (stale SHA, wrong project, missing file,
   schema mismatch) return ``None``.
4. Derive task-relevant seeds (symbol mentions) from the issue title,
   description, and focus-handoff comments.
5. Render a token-bounded map via
   :func:`~oompah.repo_map_ranker.render_repo_map`.
6. Wrap the result as an untrusted repository-context block with full
   provenance metadata.
7. Return a :class:`RepoMapContext` on success, or ``None`` on any failure.

**Security:** This function never executes or evaluates content from the
repository map.  All fields are treated as untrusted data and wrapped in
``<oompah:untrusted>`` delimiters before inclusion in any prompt.

**Fail-open guarantee:** A ``None`` return value means no repo map is
available for this startup.  The caller must preserve the existing prompt
unchanged.  No startup is blocked by map generation or retrieval failure.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from oompah.provenance import (
    ContentSource,
    ProvenanceComponent,
    make_provenance,
    wrap_untrusted,
)
from oompah.repo_map import read_repo_map
from oompah.repo_map_ranker import render_repo_map

if TYPE_CHECKING:
    from oompah.models import Issue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public defaults
# ---------------------------------------------------------------------------

#: Default token budget for rendered repo maps injected into startup prompts.
#: Override via ``OOMPAH_REPO_MAP_TOKEN_BUDGET`` environment variable.
DEFAULT_REPO_MAP_TOKEN_BUDGET: int = 2000

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class RepoMapContext:
    """Result returned by :func:`build_repo_map_context` on success.

    Attributes
    ----------
    text:
        The rendered, provenance-wrapped map text ready for prompt injection.
        Always begins with ``<oompah:untrusted source="repo_file">``.
    commit_sha:
        The HEAD commit SHA of the workspace checkout used to select the map.
        Available for diagnostic logging and telemetry.
    repo_identity:
        The canonical repository identity used to look up the map.
    """

    text: str
    commit_sha: str
    repo_identity: str


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_head_sha(workspace_path: str) -> str | None:
    """Return the lowercase HEAD SHA of the workspace git checkout, or None.

    Returns ``None`` on any error (not a git repository, git not on PATH,
    command timeout, etc.).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            sha = result.stdout.strip().lower()
            if sha:
                return sha
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _resolve_state_branch_dir(
    workspace_path: str,
    state_branch_name: str,
) -> Path | None:
    """Compute the state-branch worktree path from the workspace git common dir.

    Uses the same path convention as ``OompahMdTracker._state_worktree_path``:
    ``<git_common_dir>/oompah-state-worktrees/<safe_branch_name>``

    Returns ``None`` if the git common dir cannot be resolved or the worktree
    directory does not exist.

    Parameters
    ----------
    workspace_path:
        Root of the managed project git checkout.
    state_branch_name:
        Name of the oompah state branch (e.g. ``"oompah/state/proj-abc"``).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        git_common_dir = Path(result.stdout.strip())
        if not git_common_dir.is_absolute():
            git_common_dir = (Path(workspace_path) / git_common_dir).resolve()
        safe_name = state_branch_name.replace("/", "__").replace("\\", "__")
        candidate = git_common_dir / "oompah-state-worktrees" / safe_name
        if candidate.is_dir():
            return candidate
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _extract_task_mentions(
    issue: "Issue",
    comments: list[dict] | None = None,
) -> list[str]:
    """Extract likely Python symbol names from issue title, description, and comments.

    Algorithm
    ~~~~~~~~~
    1. Concatenate title, description, and comment text.
    2. Extract tokens that match ``[A-Za-z_][A-Za-z0-9_]{2,}`` (valid
       identifiers, length >= 3).
    3. Return deduplicated list preserving first-occurrence order.

    These tokens are passed as ``task_mentions`` to :func:`render_repo_map`,
    where any symbol whose exact name appears in this list receives a
    relevance boost (:data:`~oompah.repo_map_ranker.TASK_MENTION_BOOST`).

    Parameters
    ----------
    issue:
        The task being dispatched.
    comments:
        Optional issue comments (list of dicts with a ``"text"`` key).

    Returns
    -------
    list[str]
        Deduplicated list of extracted identifier tokens.
    """
    texts: list[str] = []
    if issue.title:
        texts.append(issue.title)
    if issue.description:
        texts.append(issue.description)
    for comment in (comments or []):
        raw = str(comment.get("text") or "")
        if raw:
            texts.append(raw)

    full_text = " ".join(texts)
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", full_text)

    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _token_budget_from_env() -> int:
    """Return the repo-map token budget from env, falling back to the default."""
    raw = os.environ.get("OOMPAH_REPO_MAP_TOKEN_BUDGET", "")
    if raw.strip():
        try:
            budget = int(raw.strip())
            if budget > 0:
                return budget
        except ValueError:
            pass
    return DEFAULT_REPO_MAP_TOKEN_BUDGET


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_repo_map_context(
    issue: "Issue",
    workspace_path: str,
    state_branch_name: str,
    repo_identity: str,
    token_budget: int | None = None,
    comments: list[dict] | None = None,
) -> RepoMapContext | None:
    """Build a repository-map context block for injection into agent startup prompts.

    This function is **fail-open**: any failure (missing artifact, stale SHA,
    wrong project, state-branch worktree not found, render error, git command
    failure) returns ``None`` and does not raise.  Startup is never blocked
    by map unavailability.

    The returned :class:`RepoMapContext` carries a ``text`` field already
    wrapped in ``<oompah:untrusted source="repo_file">`` delimiters with a
    full provenance header, so callers can safely append it to a startup
    prompt without additional escaping.

    Parameters
    ----------
    issue:
        The task being dispatched.  Used to derive task-relevant seeds.
    workspace_path:
        Root of the managed project git checkout (the agent's working directory).
        Must be a valid directory path inside a git repository.
    state_branch_name:
        Name of the oompah state branch for this project
        (e.g. ``"oompah/state/proj-abc"``).  Used to locate the state-branch
        worktree that holds the map artifact.
    repo_identity:
        Canonical URL or opaque identifier for the repository
        (e.g. ``"https://github.com/org/repo"``).  Must match the value used
        when the map was generated.
    token_budget:
        Maximum number of whitespace-separated tokens in the rendered map.
        Defaults to :data:`DEFAULT_REPO_MAP_TOKEN_BUDGET` (or the value of
        the ``OOMPAH_REPO_MAP_TOKEN_BUDGET`` environment variable if set).
        Must be a positive integer when supplied.
    comments:
        Optional issue comments to include in seed extraction.  Dicts must
        have a ``"text"`` key.

    Returns
    -------
    RepoMapContext or None
        A populated context block on success, ``None`` when no fresh map is
        available or on any error.
    """
    if token_budget is None:
        token_budget = _token_budget_from_env()
    try:
        return _build_repo_map_context_unsafe(
            issue=issue,
            workspace_path=workspace_path,
            state_branch_name=state_branch_name,
            repo_identity=repo_identity,
            token_budget=token_budget,
            comments=comments,
        )
    except Exception:
        logger.debug(
            "repo-map context injection skipped for %s (exception swallowed)",
            getattr(issue, "identifier", "?"),
            exc_info=True,
        )
        return None


def _build_repo_map_context_unsafe(
    *,
    issue: "Issue",
    workspace_path: str,
    state_branch_name: str,
    repo_identity: str,
    token_budget: int,
    comments: list[dict] | None,
) -> RepoMapContext | None:
    """Inner (non-fail-open) implementation; wrapped by build_repo_map_context."""

    # 1. Resolve workspace HEAD SHA.
    commit_sha = _resolve_head_sha(workspace_path)
    if not commit_sha:
        logger.debug(
            "repo-map: could not resolve HEAD SHA for workspace %s",
            workspace_path,
        )
        return None

    # 2. Find the state-branch worktree.
    state_branch_dir = _resolve_state_branch_dir(workspace_path, state_branch_name)
    if state_branch_dir is None:
        logger.debug(
            "repo-map: state-branch worktree not found for branch %r in workspace %s",
            state_branch_name,
            workspace_path,
        )
        return None

    # 3. Read a fresh, project-scoped artifact.
    #    Returns None for: stale SHA, missing file, schema mismatch, wrong project.
    repo_map = read_repo_map(
        state_branch_dir,
        repo_identity,
        commit_sha,
        require_fresh=True,
    )
    if repo_map is None:
        logger.debug(
            "repo-map: no fresh artifact for %s @ %.8s (state_dir=%s)",
            repo_identity,
            commit_sha,
            state_branch_dir,
        )
        return None

    # 4. Derive task-relevant seeds from the issue metadata.
    task_mentions = _extract_task_mentions(issue, comments)

    # 5. Render a token-bounded map.
    rendered = render_repo_map(
        repo_map,
        token_budget,
        task_mentions=task_mentions,
        seed_files=None,
    )

    # 6. Wrap as an untrusted repository-data block with provenance.
    provenance = make_provenance(
        ProvenanceComponent.PROMPT_RENDERER,
        ContentSource.REPO_FILE,
        issue_identifier=getattr(issue, "identifier", None),
    )
    wrapped = wrap_untrusted(rendered, provenance)

    logger.info(
        "repo-map context included in prompt for %s: sha=%.8s repo=%s tokens<=%d",
        getattr(issue, "identifier", "?"),
        commit_sha,
        repo_identity,
        token_budget,
    )

    return RepoMapContext(
        text=wrapped,
        commit_sha=commit_sha,
        repo_identity=repo_identity,
    )
