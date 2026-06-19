"""Bridge GitHub customer intake into native oompah Markdown tasks.

Native Markdown remains the authoritative tracker.  This module only imports
external GitHub issues/comments into native tasks and mirrors internal status
changes back to the originating GitHub issue as comments/closure.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from oompah.github_tracker import GitHubAuth, GitHubIssueTracker
from oompah.intake_comments import (
    ValidatorResult as IntakeCommentResult,
    compute_fingerprint,
    post_intake_comment_if_needed,
)
from oompah.issue_validator import validate_issue
from oompah.models import Issue, Project
from oompah.projects import github_owner_repo_from_url
from oompah.statuses import ARCHIVED, MERGED, PROPOSED, canonicalize_status, status_key
from oompah.tracker import TrackerError
from oompah.webhooks import WebhookEvent

logger = logging.getLogger(__name__)

EXTERNAL_GITHUB_METADATA_KEY = "oompah.external.github"
INTAKE_COMMENT_METADATA_KEY = "oompah.intake_comment"
_TERMINAL_CLOSE_KEYS = {status_key(MERGED), status_key(ARCHIVED)}
_NATIVE_TRACKER_KINDS = {"oompah_md", "oompah.md", "oompah"}


def project_uses_github_issue_intake(project: Project | None) -> bool:
    """Return true when *project* imports GitHub issues into native tasks."""
    if project is None:
        return False
    kind = str(getattr(project, "tracker_kind", "") or "").strip().lower()
    return kind in _NATIVE_TRACKER_KINDS and bool(
        getattr(project, "github_issue_intake_enabled", False)
    )


def github_issue_intake_repo_slug(project: Project) -> str | None:
    """Return the GitHub intake repository slug for *project*, if configured."""
    owner = str(getattr(project, "tracker_owner", None) or "").strip()
    repo = str(getattr(project, "tracker_repo", None) or "").strip()
    if owner and repo:
        return f"{owner}/{repo}"
    owner, repo = github_owner_repo_from_url(str(getattr(project, "repo_url", "") or ""))
    if owner and repo:
        return f"{owner}/{repo}"
    return None


def event_matches_github_issue_intake(project: Project, event: WebhookEvent) -> bool:
    """Return true when a webhook event belongs to this project's intake repo."""
    if not project_uses_github_issue_intake(project):
        return False
    wanted = github_issue_intake_repo_slug(project)
    return bool(wanted and event.repo_slug.lower() == wanted.lower())


def _github_tracker_for_project(
    project: Project,
    active_states: list[str],
    terminal_states: list[str],
) -> GitHubIssueTracker | None:
    slug = github_issue_intake_repo_slug(project)
    if not slug or "/" not in slug:
        return None
    owner, repo = slug.split("/", 1)
    token = getattr(project, "access_token", None)
    auth = GitHubAuth(pat=token) if token else GitHubAuth()
    return GitHubIssueTracker(
        owner=owner,
        repo=repo,
        active_states=active_states,
        terminal_states=terminal_states,
        auth=auth,
        status_label_authorized_logins=getattr(
            project,
            "status_label_authorized_logins",
            [],
        ),
    )


def _external_identifier(owner: str, repo: str, number: str | int) -> str:
    return f"{owner}/{repo}#{number}"


def _external_identifier_for_project(
    project: Project,
    number: str | int | None,
) -> str | None:
    if number in (None, ""):
        return None
    slug = github_issue_intake_repo_slug(project)
    if not slug or "/" not in slug:
        return None
    owner, repo = slug.split("/", 1)
    return _external_identifier(owner, repo, number)


def _issue_url(owner: str, repo: str, number: str | int) -> str:
    return f"https://github.com/{owner}/{repo}/issues/{number}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_external_metadata(native_tracker: Any, identifier: str) -> dict[str, Any]:
    try:
        metadata = native_tracker.get_metadata(identifier)
    except Exception:
        return {}
    raw = metadata.get(EXTERNAL_GITHUB_METADATA_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def _set_external_metadata(
    native_tracker: Any,
    identifier: str,
    metadata: dict[str, Any],
) -> None:
    native_tracker.set_metadata_field(
        identifier,
        EXTERNAL_GITHUB_METADATA_KEY,
        dict(metadata),
    )


def _find_native_issue_for_external(
    native_tracker: Any,
    external_id: str,
) -> tuple[Issue | None, dict[str, Any]]:
    fetch_all = getattr(native_tracker, "fetch_all_issues_enriched", None)
    if not callable(fetch_all):
        fetch_all = getattr(native_tracker, "fetch_all_issues", None)
    if not callable(fetch_all):
        return None, {}
    try:
        issues = fetch_all()
    except Exception as exc:  # noqa: BLE001
        logger.debug("github_intake: failed to scan native issues: %s", exc)
        return None, {}

    for issue in issues or []:
        metadata = _get_external_metadata(native_tracker, issue.identifier)
        if str(metadata.get("id") or "").strip().lower() == external_id.lower():
            return issue, metadata
    return None, {}


def _native_status_is_merged_or_archived(status: str | None) -> bool:
    return status_key(canonicalize_status(status)) in _TERMINAL_CLOSE_KEYS


def _github_issue_is_closed(github_issue: Issue) -> bool:
    raw_state = status_key(github_issue.state)
    return raw_state == "closed" or getattr(github_issue, "closed_at", None) is not None


def _metadata_last_github_state(metadata: dict[str, Any]) -> str:
    return str(metadata.get("last_github_state") or "").strip().lower()


def _write_external_metadata_if_changed(
    native_tracker: Any,
    identifier: str,
    original: dict[str, Any],
    updated: dict[str, Any],
) -> None:
    if updated != original:
        _set_external_metadata(native_tracker, identifier, updated)


def _reconcile_native_status_from_github_issue(
    native_tracker: Any,
    github_issue: Issue,
    existing: Issue | None = None,
    metadata: dict[str, Any] | None = None,
) -> Issue | None:
    """Apply GitHub open/closed state to an already-imported native task."""
    external_id = github_issue.identifier
    if existing is None or metadata is None:
        existing, metadata = _find_native_issue_for_external(native_tracker, external_id)
    if existing is None:
        return None

    metadata = dict(metadata or {})
    original_metadata = dict(metadata)
    current_status = canonicalize_status(existing.state)
    github_closed = _github_issue_is_closed(github_issue)

    if github_closed:
        metadata["last_github_state"] = "closed"
        if not _native_status_is_merged_or_archived(current_status):
            native_tracker.update_issue(existing.identifier, status=ARCHIVED)
            current_status = ARCHIVED
            metadata["external_closed_at"] = _now_iso()
            metadata["last_synced_status"] = ARCHIVED
            metadata["last_synced_at"] = _now_iso()
            existing = native_tracker.fetch_issue_detail(existing.identifier) or existing
        _write_external_metadata_if_changed(
            native_tracker,
            existing.identifier,
            original_metadata,
            metadata,
        )
        return existing

    was_closed_by_github = (
        _metadata_last_github_state(metadata) == "closed"
        or bool(metadata.get("external_closed_at"))
    )
    if current_status == ARCHIVED and was_closed_by_github:
        native_tracker.update_issue(existing.identifier, status=PROPOSED)
        metadata["last_github_state"] = "open"
        metadata["external_reopened_at"] = _now_iso()
        metadata["last_synced_status"] = PROPOSED
        metadata["last_synced_at"] = _now_iso()
        existing = native_tracker.fetch_issue_detail(existing.identifier) or existing
        _write_external_metadata_if_changed(
            native_tracker,
            existing.identifier,
            original_metadata,
            metadata,
        )
        return existing

    return existing


def _github_issue_from_event(event: WebhookEvent, project: Project) -> Issue | None:
    issue = (event.raw or {}).get("issue") or {}
    number = event.issue_number or issue.get("number")
    external_id = _external_identifier_for_project(project, number)
    if not external_id:
        return None
    slug = github_issue_intake_repo_slug(project) or ""
    owner, repo = slug.split("/", 1)
    user = issue.get("user") if isinstance(issue.get("user"), dict) else {}
    closed_at = issue.get("closed_at")
    parsed_closed_at = None
    if closed_at:
        try:
            parsed_closed_at = datetime.fromisoformat(
                str(closed_at).replace("Z", "+00:00")
            )
        except ValueError:
            parsed_closed_at = None
    return Issue(
        id=external_id,
        identifier=external_id,
        title=str(issue.get("title") or event.title or f"GitHub issue #{number}"),
        description=str(issue.get("body") or ""),
        state=str(issue.get("state") or "open"),
        issue_type="task",
        tracker_kind="github_issues",
        tracker_owner=owner,
        tracker_repo=repo,
        issue_number=str(number),
        provider_url=str(issue.get("html_url") or _issue_url(owner, repo, number)),
        requestor_login=str(user.get("login") or event.author or "").strip() or None,
        closed_at=parsed_closed_at,
    )


def _external_metadata_from_issue(github_issue: Issue) -> dict[str, Any]:
    owner = str(github_issue.tracker_owner or "").strip()
    repo = str(github_issue.tracker_repo or "").strip()
    number = str(github_issue.issue_number or "").strip()
    external_id = (
        _external_identifier(owner, repo, number)
        if owner and repo and number
        else github_issue.identifier
    )
    return {
        "id": external_id,
        "owner": owner or None,
        "repo": repo or None,
        "number": number or None,
        "url": github_issue.provider_url or (
            _issue_url(owner, repo, number) if owner and repo and number else None
        ),
        "requestor_login": github_issue.requestor_login,
        "imported_comment_ids": [],
        "last_synced_status": PROPOSED,
        "last_synced_at": _now_iso(),
    }


def _native_description_for_github_issue(github_issue: Issue) -> str:
    lines: list[str] = []
    if github_issue.description:
        lines.append(github_issue.description.strip())
        lines.append("")
    lines.append("## External GitHub Issue")
    if github_issue.provider_url:
        lines.append(f"- URL: {github_issue.provider_url}")
    if github_issue.requestor_login:
        lines.append(f"- Requestor: @{github_issue.requestor_login}")
    lines.append(f"- Reference: {github_issue.identifier}")
    return "\n".join(lines).strip()


def ensure_native_issue_for_github_issue(
    native_tracker: Any,
    github_tracker: Any,
    github_issue: Issue,
    *,
    post_import_comment: bool = True,
) -> Issue | None:
    """Create or update the native Proposed task corresponding to a GitHub issue."""
    external_id = github_issue.identifier
    existing, metadata = _find_native_issue_for_external(native_tracker, external_id)
    if existing is not None:
        return _reconcile_native_status_from_github_issue(
            native_tracker,
            github_issue,
            existing,
            metadata,
        )

    if _github_issue_is_closed(github_issue):
        return None

    created = native_tracker.create_issue(
        github_issue.title,
        issue_type="task",
        description=_native_description_for_github_issue(github_issue),
        priority=github_issue.priority,
        initial_status=PROPOSED,
        labels=["external:github"],
    )
    metadata = _external_metadata_from_issue(github_issue)
    _set_external_metadata(native_tracker, created.identifier, metadata)
    created = native_tracker.fetch_issue_detail(created.identifier) or created

    if post_import_comment:
        try:
            github_tracker.add_comment(
                external_id,
                (
                    f"Imported into oompah as `{created.identifier}` and queued "
                    f"for intake validation in `{PROPOSED}`."
                ),
                author="oompah",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "github_intake: failed to post import comment on %s: %s",
                external_id,
                exc,
            )
    return created


def _github_issue_ready_for_native_import(
    github_tracker: Any,
    github_issue: Issue,
) -> bool:
    """Validate a GitHub intake issue before creating native work."""
    result = validate_issue(
        title=github_issue.title,
        description=github_issue.description,
        issue_type=github_issue.issue_type,
        labels=github_issue.labels,
    )
    if result.ready:
        return True

    requestor = str(github_issue.requestor_login or "").strip()
    comment_result = IntakeCommentResult.from_validation_result(result)
    fingerprint = compute_fingerprint(comment_result, requestor)
    try:
        metadata = github_tracker.get_metadata(github_issue.identifier)
    except Exception:
        metadata = {}
    existing = metadata.get(INTAKE_COMMENT_METADATA_KEY)
    if isinstance(existing, dict) and existing.get("fingerprint") == fingerprint:
        return False

    post_intake_comment_if_needed(
        github_tracker,
        github_issue.identifier,
        comment_result,
        requestor,
        issue_updated_at=getattr(github_issue, "updated_at", None),
        author="oompah",
    )
    return False


def _is_oompah_comment(author: str | None, body: str | None) -> bool:
    author_key = str(author or "").strip().lower()
    text = str(body or "").strip().lower()
    return author_key == "oompah" or text.startswith("**oompah**:")


def import_github_comment_to_native(
    native_tracker: Any,
    internal_identifier: str,
    metadata: dict[str, Any],
    *,
    comment_id: str | int | None,
    author: str | None,
    body: str | None,
) -> bool:
    """Copy a GitHub comment to the native task once, unless oompah wrote it."""
    text = str(body or "").strip()
    if not text or _is_oompah_comment(author, text):
        return False
    comment_key = str(comment_id or "").strip()
    imported = {
        str(value)
        for value in (metadata.get("imported_comment_ids") or [])
        if str(value).strip()
    }
    if comment_key and comment_key in imported:
        return False

    comment_author = str(author or "github").strip() or "github"
    native_tracker.add_comment(internal_identifier, text, author=comment_author)
    if comment_key:
        metadata = dict(metadata)
        imported.add(comment_key)
        metadata["imported_comment_ids"] = sorted(imported)
        _set_external_metadata(native_tracker, internal_identifier, metadata)
    return True


def _fetch_github_issue(
    github_tracker: Any,
    external_identifier: str,
    fallback: Issue | None = None,
) -> Issue | None:
    try:
        fetched = github_tracker.fetch_issue_detail(external_identifier)
        if fetched is not None:
            return fetched
    except Exception as exc:  # noqa: BLE001
        logger.debug("github_intake: failed to fetch %s: %s", external_identifier, exc)
    return fallback


def handle_github_issue_event_for_native_project(
    orch: Any,
    event: WebhookEvent,
    project: Project,
) -> None:
    """Handle a GitHub issue/comment webhook for native-task intake."""
    if getattr(project, "paused", False):
        return
    if not event_matches_github_issue_intake(project, event):
        return
    external_id = _external_identifier_for_project(project, event.issue_number)
    if not external_id:
        return
    try:
        native_tracker = orch._tracker_for_project(project.id)
        github_tracker = _github_tracker_for_project(
            project,
            list(getattr(orch.config, "tracker_active_states", [])),
            list(getattr(orch.config, "tracker_terminal_states", [])),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "github_intake: failed to initialize trackers for project %s: %s",
            project.name,
            exc,
        )
        return
    if github_tracker is None:
        logger.warning(
            "github_intake: project %s has no GitHub intake repository configured",
            project.name,
        )
        return

    fallback_issue = _github_issue_from_event(event, project)
    github_issue = _fetch_github_issue(github_tracker, external_id, fallback_issue)
    if github_issue is None:
        return

    if _github_issue_is_closed(github_issue):
        _reconcile_native_status_from_github_issue(native_tracker, github_issue)
        return

    _reconcile_native_status_from_github_issue(native_tracker, github_issue)

    if event.event_type == "issues" and event.action in {"opened", "edited", "reopened"}:
        if not _github_issue_ready_for_native_import(github_tracker, github_issue):
            return
        internal = ensure_native_issue_for_github_issue(
            native_tracker,
            github_tracker,
            github_issue,
        )
        _copy_existing_github_comments(native_tracker, github_tracker, internal)
        return

    if event.event_type == "issue_comment" and event.action in {"created", "edited"}:
        if not _github_issue_ready_for_native_import(github_tracker, github_issue):
            return
        internal = ensure_native_issue_for_github_issue(
            native_tracker,
            github_tracker,
            github_issue,
        )
        if internal is None:
            return
        metadata = _get_external_metadata(native_tracker, internal.identifier)
        comment = (event.raw or {}).get("comment") or {}
        author = (
            str((comment.get("user") or {}).get("login") or event.author or "").strip()
            or None
        )
        import_github_comment_to_native(
            native_tracker,
            internal.identifier,
            metadata,
            comment_id=event.comment_id or comment.get("id"),
            author=author,
            body=comment.get("body"),
        )


def poll_github_issue_intake_project(orch: Any, project: Project) -> int:
    """Import currently-open GitHub issues for a native-intake project."""
    if getattr(project, "paused", False):
        return 0
    if not project_uses_github_issue_intake(project):
        return 0
    try:
        native_tracker = orch._tracker_for_project(project.id)
        github_tracker = _github_tracker_for_project(
            project,
            list(getattr(orch.config, "tracker_active_states", [])),
            list(getattr(orch.config, "tracker_terminal_states", [])),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("github_intake: poll setup failed for %s: %s", project.name, exc)
        return 0
    if github_tracker is None:
        return 0
    imported = 0
    try:
        github_issues = github_tracker.fetch_all_issues()
    except Exception as exc:  # noqa: BLE001
        logger.debug("github_intake: poll fetch failed for %s: %s", project.name, exc)
        return 0
    for github_issue in github_issues:
        try:
            if _github_issue_is_closed(github_issue):
                _reconcile_native_status_from_github_issue(native_tracker, github_issue)
                continue

            _reconcile_native_status_from_github_issue(native_tracker, github_issue)
            if not _github_issue_ready_for_native_import(github_tracker, github_issue):
                continue
            before, _ = _find_native_issue_for_external(
                native_tracker,
                github_issue.identifier,
            )
            created = ensure_native_issue_for_github_issue(
                native_tracker,
                github_tracker,
                github_issue,
                post_import_comment=before is None,
            )
            if before is None and created is not None:
                imported += 1
            _copy_existing_github_comments(native_tracker, github_tracker, created)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "github_intake: failed to import %s for %s: %s",
                github_issue.identifier,
                project.name,
                exc,
            )
    return imported


def _copy_existing_github_comments(
    native_tracker: Any,
    github_tracker: Any,
    internal_issue: Issue | None,
) -> int:
    if internal_issue is None:
        return 0
    metadata = _get_external_metadata(native_tracker, internal_issue.identifier)
    external_id = str(metadata.get("id") or "").strip()
    if not external_id:
        return 0
    copied = 0
    try:
        comments = github_tracker.fetch_comments(external_id)
    except Exception:
        return 0
    for comment in comments or []:
        if not isinstance(comment, dict):
            continue
        metadata = _get_external_metadata(native_tracker, internal_issue.identifier)
        if import_github_comment_to_native(
            native_tracker,
            internal_issue.identifier,
            metadata,
            comment_id=comment.get("id") or comment.get("node_id"),
            author=comment.get("author"),
            body=comment.get("text") or comment.get("body"),
        ):
            copied += 1
    return copied


def sync_github_issue_intake_statuses_for_project(
    orch: Any,
    project: Project,
) -> dict[str, int]:
    """Reflect internal native-task status changes back to GitHub."""
    metrics = {"scanned": 0, "commented": 0, "closed": 0, "errors": 0}
    if getattr(project, "paused", False):
        return metrics
    if not project_uses_github_issue_intake(project):
        return metrics
    try:
        native_tracker = orch._tracker_for_project(project.id)
        github_tracker = _github_tracker_for_project(
            project,
            list(getattr(orch.config, "tracker_active_states", [])),
            list(getattr(orch.config, "tracker_terminal_states", [])),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("github_intake: status sync setup failed for %s: %s", project.name, exc)
        return metrics
    if github_tracker is None:
        return metrics

    fetch_all = getattr(native_tracker, "fetch_all_issues_enriched", None)
    if not callable(fetch_all):
        fetch_all = getattr(native_tracker, "fetch_all_issues", None)
    if not callable(fetch_all):
        return metrics

    try:
        issues = fetch_all()
    except Exception as exc:  # noqa: BLE001
        logger.debug("github_intake: failed to fetch native issues for status sync: %s", exc)
        return metrics

    for issue in issues or []:
        metadata = _get_external_metadata(native_tracker, issue.identifier)
        external_id = str(metadata.get("id") or "").strip()
        if not external_id:
            continue
        metrics["scanned"] += 1
        current_status = canonicalize_status(issue.state)
        if status_key(current_status) == status_key(metadata.get("last_synced_status")):
            continue
        try:
            github_tracker.add_comment(
                external_id,
                f"Oompah task `{issue.identifier}` is now `{current_status}`.",
                author="oompah",
            )
            metrics["commented"] += 1
            if status_key(current_status) in _TERMINAL_CLOSE_KEYS:
                github_tracker.update_issue(external_id, status=current_status)
                metrics["closed"] += 1
            metadata["last_synced_status"] = current_status
            metadata["last_synced_at"] = _now_iso()
            _set_external_metadata(native_tracker, issue.identifier, metadata)
        except Exception as exc:  # noqa: BLE001
            metrics["errors"] += 1
            logger.debug(
                "github_intake: failed to sync %s -> %s: %s",
                issue.identifier,
                external_id,
                exc,
            )
    return metrics
