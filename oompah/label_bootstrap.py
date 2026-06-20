"""Bootstrap required GitHub labels and validate managed-project tracker config."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from oompah.models import Project

logger = logging.getLogger(__name__)

LabelDefinition = tuple[str, str, str]

PROPOSED_STATUS = "Proposed"
_STATUS_LABEL_PREFIX = "oompah:status:"
_GITHUB_TRACKER_KINDS = frozenset({"github_issues", "github-issues"})

_STATUS_LABEL_COLORS: dict[str, str] = {
    "Proposed": "fbca04",
    "Backlog": "ededed",
    "Open": "0075ca",
    "In Progress": "e4e669",
    "Needs Answer": "d876e3",
    "Needs Human": "d876e3",
    "Needs CI Fix": "ee0701",
    "Needs Rebase": "ee0701",
    "In Review": "0e8a16",
    "Decomposed": "bfd4f2",
    "Duplicate Candidate": "fef2c0",
    "Done": "cfd3d7",
    "Merged": "6f42c1",
    "Archived": "ededed",
}


def _status_slug(status: str) -> str:
    return status.strip().lower().replace(" ", "-")


def _status_label(status: str) -> LabelDefinition:
    color = _STATUS_LABEL_COLORS.get(status, "ededed")
    return (
        f"{_STATUS_LABEL_PREFIX}{_status_slug(status)}",
        color,
        f"oompah task status: {status}",
    )


def _required_status_labels() -> tuple[LabelDefinition, ...]:
    from oompah.statuses import CANONICAL_STATUSES

    statuses: list[str] = [PROPOSED_STATUS]
    seen = {_status_slug(PROPOSED_STATUS)}
    for status in CANONICAL_STATUSES:
        slug = _status_slug(status)
        if slug in seen:
            continue
        seen.add(slug)
        statuses.append(status)
    return tuple(_status_label(status) for status in statuses)


REQUIRED_LABELS: tuple[LabelDefinition, ...] = _required_status_labels()
REQUIRED_LABEL_NAMES: tuple[str, ...] = tuple(name for name, _, _ in REQUIRED_LABELS)

INTAKE_REQUIRED_LABELS: frozenset[str] = frozenset({
    "oompah:status:proposed",
    "oompah:status:backlog",
    "oompah:status:archived",
})


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class LabelBootstrapResult:
    """Per-project outcome of :func:`bootstrap_project_labels`.

    Attributes
    ----------
    project_id:
        oompah project identifier (e.g. ``"proj-14849f1b"``).
    project_name:
        Human-readable project name.
    owner:
        GitHub owner (org or user) of the tracker repository.
    repo:
        GitHub repository name of the tracker.
    created:
        Label names that were newly created during this run.
    already_exists:
        Label names that were already present (idempotent skip).
    failed:
        Pairs of ``(label_name, reason_string)`` for labels that could not be
        created.
    config_errors:
        Validation errors that prevent a reliable GitHub label bootstrap.
    config_warnings:
        Non-blocking configuration findings surfaced to operators.
    """

    project_id: str
    project_name: str
    owner: str
    repo: str
    created: list[str] = field(default_factory=list)
    already_exists: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    config_errors: list[str] = field(default_factory=list)
    config_warnings: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """``True`` when no labels failed and no config errors were found."""
        return not self.failed and not self.config_errors

    @property
    def needs_alert(self) -> bool:
        """``True`` when the result should be surfaced to operators."""
        return bool(self.failed or self.config_errors or self.config_warnings)

    @property
    def has_permission_error(self) -> bool:
        """``True`` when at least one failure looks like a permission issue."""
        for _, reason in self.failed:
            lower = reason.lower()
            if (
                "authentication failed" in lower
                or "access forbidden" in lower
                or "403" in lower
                or "401" in lower
                or "permission" in lower
            ):
                return True
        return False

    def status_summary(self) -> str:
        """One-line summary suitable for a log line."""
        if self.config_errors:
            return "config errors: " + "; ".join(self.config_errors)
        parts: list[str] = []
        if self.created:
            parts.append(f"created {len(self.created)}: {', '.join(self.created)}")
        if self.already_exists:
            parts.append(f"{len(self.already_exists)} already present")
        if self.failed:
            failed_names = [name for name, _ in self.failed]
            parts.append(f"failed {len(self.failed)}: {', '.join(failed_names)}")
        if self.config_warnings:
            parts.append("warnings: " + "; ".join(self.config_warnings))
        return "; ".join(parts) if parts else "ok (nothing to do)"

    def alert_message(self) -> str:
        """Human-readable actionable message for a dashboard alert.

        Includes the repo slug and the names of labels that failed so an
        operator knows exactly what to fix.
        """
        repo_slug = _repo_slug(self.owner, self.repo, self.project_name, self.project_id)
        if self.config_errors:
            return (
                f"Label bootstrap skipped for {repo_slug}: "
                + "; ".join(self.config_errors)
            )
        if self.failed:
            failed_names = [name for name, _ in self.failed]
            label_list = _format_names(failed_names)
            reasons = "; ".join(
                f"{name}: {reason}" for name, reason in self.failed[:3]
            )
            if len(self.failed) > 3:
                reasons += f" (and {len(self.failed) - 3} more)"
            return (
                f"Cannot create required GitHub labels in {repo_slug}: {label_list}. "
                f"Errors: {reasons}. "
                "Grant the oompah GitHub credential write access to repository "
                "labels/issues, or create the listed labels manually, then restart."
            )
        if self.config_warnings:
            return (
                f"GitHub label bootstrap completed for {repo_slug}, but project "
                "config needs review: " + "; ".join(self.config_warnings)
            )
        return f"Label bootstrap ok for {repo_slug}"


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def _is_github_tracker_kind(kind: str | None) -> bool:
    return str(kind or "").strip().lower() in _GITHUB_TRACKER_KINDS


def validate_project_config(project: "Project") -> list[str]:
    """Validate minimum required configuration for a GitHub-backed project.

    Returns a list of human-readable error strings.  An empty list means
    the configuration is valid.

    Empty ``status_label_authorized_logins`` is valid: the configured
    ``tracker_owner`` and oompah bot login are implicitly authorized.

    Parameters
    ----------
    project:
        A :class:`~oompah.models.Project` instance.

    Returns
    -------
    list[str]
        Validation error strings (empty means valid).
    """
    errors: list[str] = []
    tracker_kind = getattr(project, "tracker_kind", None)
    if not _is_github_tracker_kind(tracker_kind):
        errors.append(
            f"tracker_kind is {tracker_kind!r}; expected 'github_issues'"
        )
    tracker_owner = getattr(project, "tracker_owner", None)
    if not tracker_owner or not str(tracker_owner).strip():
        errors.append("tracker_owner is missing or empty")
    tracker_repo = getattr(project, "tracker_repo", None)
    if not tracker_repo or not str(tracker_repo).strip():
        errors.append("tracker_repo is missing or empty")

    authorized = getattr(project, "status_label_authorized_logins", [])
    if authorized is None:
        authorized = []
    if not isinstance(authorized, list):
        errors.append("status_label_authorized_logins must be a list of GitHub logins")
    else:
        seen: set[str] = set()
        for idx, login in enumerate(authorized):
            if not isinstance(login, str) or not login.strip():
                errors.append(
                    f"status_label_authorized_logins[{idx}] must be a non-empty string"
                )
                continue
            key = login.strip().lower()
            if key in seen:
                errors.append(
                    f"status_label_authorized_logins contains duplicate login {login!r}"
                )
            seen.add(key)

    return errors


def validate_project_config_warnings(project: "Project") -> list[str]:
    """Return non-blocking GitHub tracker configuration findings."""
    return []


# ---------------------------------------------------------------------------
# Core bootstrap logic
# ---------------------------------------------------------------------------


def bootstrap_project_labels(
    owner: str,
    repo: str,
    client: Any,
    labels: Sequence[LabelDefinition] = REQUIRED_LABELS,
    *,
    project_id: str = "",
    project_name: str = "",
) -> LabelBootstrapResult:
    """Create any missing required labels in a GitHub repository.

    Fetches the existing repository labels first, then POSTs only the labels
    that are not already present.  This makes the function safe to call
    repeatedly (idempotent).

    Parameters
    ----------
    owner:
        GitHub owner (org or user login).
    repo:
        Repository name.
    client:
        A :class:`~oompah.github_tracker.GitHubClient` instance (or any
        object with ``request_paginated(path)`` and ``post(path, json=...)``
        methods).
    labels:
        Sequence of ``(name, color_hex, description)`` tuples to ensure exist.
        Defaults to :data:`REQUIRED_LABELS`.
    project_id:
        Optional oompah project ID for the result object.
    project_name:
        Optional project name for the result object.

    Returns
    -------
    LabelBootstrapResult
        Detailed per-label outcome.  Never raises — all errors are captured
        in the result.
    """
    from oompah.tracker import TrackerError, TrackerTimeoutError

    result = LabelBootstrapResult(
        project_id=project_id,
        project_name=project_name,
        owner=owner,
        repo=repo,
    )

    # ------------------------------------------------------------------
    # 1. Fetch existing labels (paginated)
    # ------------------------------------------------------------------
    try:
        raw_labels = client.request_paginated(
            f"/repos/{owner}/{repo}/labels",
            params={"per_page": 100},
        )
    except (TrackerError, TrackerTimeoutError) as exc:
        msg = str(exc)
        for name, _, _ in labels:
            result.failed.append((name, f"Cannot list repository labels: {msg}"))
        logger.warning(
            "label_bootstrap: cannot list labels for %s/%s: %s",
            owner, repo, exc,
        )
        return result

    existing_names_by_lower: dict[str, str] = {
        str(lbl["name"]).lower(): str(lbl["name"])
        for lbl in raw_labels
        if isinstance(lbl, dict) and lbl.get("name")
    }
    logger.debug(
        "label_bootstrap: %s/%s has %d existing labels",
        owner, repo, len(existing_names_by_lower),
    )

    # ------------------------------------------------------------------
    # 2. Create missing labels
    # ------------------------------------------------------------------
    for name, color, description in labels:
        existing_name = existing_names_by_lower.get(name.lower())
        if existing_name:
            result.already_exists.append(existing_name)
            logger.debug(
                "label_bootstrap: %s/%s — %r already exists, skipping",
                owner, repo, name,
            )
            continue

        try:
            client.post(
                f"/repos/{owner}/{repo}/labels",
                json={"name": name, "color": color, "description": description},
            )
            result.created.append(name)
            existing_names_by_lower[name.lower()] = name
            logger.info(
                "label_bootstrap: created label %r in %s/%s",
                name, owner, repo,
            )
        except (TrackerError, TrackerTimeoutError) as exc:
            exc_str = str(exc)
            # A 422 means the label was created between our list and our
            # create calls (race condition) — treat as idempotent success.
            if "422" in exc_str:
                result.already_exists.append(name)
                existing_names_by_lower[name.lower()] = name
                logger.debug(
                    "label_bootstrap: %s/%s — %r created concurrently (422)",
                    owner, repo, name,
                )
            else:
                result.failed.append((name, exc_str))
                logger.warning(
                    "label_bootstrap: failed to create %r in %s/%s: %s",
                    name, owner, repo, exc,
                )

    return result


# ---------------------------------------------------------------------------
# Bulk bootstrap (startup entry point)
# ---------------------------------------------------------------------------


def ensure_github_labels(
    projects: "list[Project]",
    labels: Sequence[LabelDefinition] = REQUIRED_LABELS,
    *,
    client_factory: Callable[["Project"], Any] | None = None,
) -> "dict[str, LabelBootstrapResult]":
    """Bootstrap required labels for every GitHub-backed managed project.

    Filters *projects* to those with ``tracker_kind == "github_issues"``
    and ``tracker_owner`` / ``tracker_repo`` set, then calls
    :func:`bootstrap_project_labels` for each one.

    Called at startup from :func:`oompah.bootstrap.setup_services` so that
    newly-added managed projects and fresh installs always have the labels
    they need.

    Parameters
    ----------
    projects:
        All managed projects (may be an empty list — the function is a
        no-op in that case).
    labels:
        Label definitions to ensure.  Defaults to :data:`REQUIRED_LABELS`.

    Returns
    -------
    dict[str, LabelBootstrapResult]
        Mapping of ``project_id → LabelBootstrapResult``.  Never raises.
    """
    results: dict[str, LabelBootstrapResult] = {}

    for project in projects:
        pid = getattr(project, "id", "") or ""
        pname = getattr(project, "name", pid) or pid
        tracker_kind = getattr(project, "tracker_kind", None)

        # Only bootstrap GitHub-backed projects.
        if not _is_github_tracker_kind(tracker_kind):
            continue

        config_errors = validate_project_config(project)
        config_warnings = validate_project_config_warnings(project)
        if config_errors:
            result = LabelBootstrapResult(
                project_id=pid,
                project_name=pname,
                owner=getattr(project, "tracker_owner", "") or "",
                repo=getattr(project, "tracker_repo", "") or "",
                config_errors=config_errors,
                config_warnings=config_warnings,
            )
            results[pid] = result
            logger.warning(
                "label_bootstrap: skipping project %s due to config errors: %s",
                pname, "; ".join(config_errors),
            )
            continue

        owner = str(project.tracker_owner).strip()
        repo = str(project.tracker_repo).strip()

        try:
            client = (
                client_factory(project)
                if client_factory is not None
                else _github_client_for_project(project)
            )
            result = bootstrap_project_labels(
                owner=owner,
                repo=repo,
                client=client,
                labels=labels,
                project_id=pid,
                project_name=pname,
            )
            result.config_warnings.extend(config_warnings)
        except Exception as exc:
            # Belt-and-suspenders: bootstrap_project_labels should never raise,
            # but guard here to avoid crashing setup_services.
            result = LabelBootstrapResult(
                project_id=pid,
                project_name=pname,
                owner=owner,
                repo=repo,
                config_errors=[f"Unexpected error: {exc}"],
            )
            logger.error(
                "label_bootstrap: unexpected error for project %s: %s",
                pname, exc,
            )

        results[pid] = result

    return results


def _github_client_for_project(project: "Project") -> Any:
    from oompah.github_tracker import GitHubAuth, GitHubClient

    access_token: str | None = getattr(project, "access_token", None)
    auth = GitHubAuth(pat=access_token) if access_token else GitHubAuth()
    return GitHubClient(auth=auth)


def build_label_bootstrap_alerts(
    results: dict[str, LabelBootstrapResult],
) -> list[dict[str, Any]]:
    """Convert bootstrap results into dashboard alert dictionaries."""
    alerts: list[dict[str, Any]] = []
    for project_id, result in results.items():
        if not result.needs_alert:
            continue
        level = "error" if result.failed or result.config_errors else "warning"
        repo_slug = _repo_slug(
            result.owner,
            result.repo,
            result.project_name,
            result.project_id or project_id,
        )
        failed_labels = [name for name, _ in result.failed]
        alerts.append(
            {
                "level": level,
                "source": f"label_bootstrap:{result.project_id or project_id}",
                "title": f"GitHub label bootstrap issue for {repo_slug}",
                "message": result.alert_message(),
                "detail": result.alert_message(),
                "project_id": result.project_id or project_id,
                "project_name": result.project_name,
                "repo": repo_slug,
                "labels": failed_labels,
                "config_errors": list(result.config_errors),
                "config_warnings": list(result.config_warnings),
            }
        )
    return alerts


def _repo_slug(owner: str, repo: str, project_name: str = "", project_id: str = "") -> str:
    owner = str(owner or "").strip()
    repo = str(repo or "").strip()
    if owner and repo:
        return f"{owner}/{repo}"
    fallback = project_name or project_id or "unknown project"
    return f"{fallback} (tracker repo not fully configured)"


def _format_names(names: Sequence[str], *, limit: int = 8) -> str:
    shown = [f"'{name}'" for name in names[:limit]]
    if len(names) > limit:
        shown.append(f"and {len(names) - limit} more")
    return ", ".join(shown)
