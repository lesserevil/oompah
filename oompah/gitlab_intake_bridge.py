"""Bridge GitLab customer intake into native oompah Markdown tasks.

Native Markdown remains the authoritative tracker. This module only imports
external GitLab issues/comments into native tasks and mirrors internal status
changes back to the originating GitLab issue as comments/closure.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from oompah.gitlab_tracker import GitLabIssueTracker
from oompah.archived_audit_requests import (
    cancel_pending_archived_audit,
    request_archived_audit,
)
from oompah.intake_comments import (
    ValidatorResult as IntakeCommentResult,
    compute_fingerprint,
    post_intake_comment_if_needed,
)
from oompah.issue_validator import validate_issue
from oompah.models import Issue, Project
from oompah.provenance import (
    ContentSource,
    ProvenanceComponent,
    make_provenance,
    wrap_untrusted,
)
from oompah.statuses import (
    ARCHIVED,
    IN_VALIDATION,
    MERGED,
    PROPOSED,
    canonicalize_status,
    status_key,
)
from oompah.tracker import TrackerAuthError, TrackerError
from oompah.task_transition_service import TransitionAuthority
from oompah.webhooks import WebhookEvent

logger = logging.getLogger(__name__)

EXTERNAL_GITLAB_METADATA_KEY = "oompah.external.gitlab"
INTAKE_COMMENT_METADATA_KEY = "oompah.intake_comment"
_TERMINAL_CLOSE_KEYS = {status_key(MERGED), status_key(ARCHIVED)}
_NATIVE_TRACKER_KINDS = {"oompah_md", "oompah.md", "oompah"}


def _orchestrator_status_transition(
    orch: Any,
    tracker: Any,
    project_id: str,
) -> Callable[..., object]:
    """Bind native intake reconciliation to the durable transition service."""

    def transition(issue: Issue, status: str, **fields: object) -> object:
        operation = getattr(orch, "_transition_issue_status", None)
        if not callable(operation):
            raise RuntimeError("Task transition service is unavailable")
        if not issue.project_id:
            issue.project_id = project_id
        return operation(
            issue,
            status,
            project_id=project_id,
            tracker=tracker,
            actor=str(fields.get("actor") or "gitlab-intake"),
            authority=TransitionAuthority.SYSTEM,
            reason_code=str(fields["reason_code"]),
            authorized_recovery=bool(fields.get("authorized_recovery", False)),
        )

    return transition


def project_uses_gitlab_issue_intake(project: Project | None) -> bool:
    """Return true when *project* imports GitLab issues into native tasks."""
    if project is None:
        return False
    kind = str(getattr(project, "tracker_kind", "") or "").strip().lower()
    return kind in _NATIVE_TRACKER_KINDS and bool(
        getattr(project, "github_issue_intake_enabled", False)
    ) and str(getattr(project, "forge_kind", "")).strip().lower() == "gitlab"


def gitlab_issue_intake_repo_slug(project: Project) -> str | None:
    """Return the GitLab intake repository path for *project*, if configured."""
    owner = str(getattr(project, "tracker_owner", None) or "").strip()
    repo = str(getattr(project, "tracker_repo", None) or "").strip()
    if owner and repo:
        return f"{owner}/{repo}"
    return None


def event_matches_gitlab_issue_intake(project: Project, event: WebhookEvent) -> bool:
    """Return true when a webhook event belongs to this project's intake repo."""
    if not project_uses_gitlab_issue_intake(project):
        return False
    wanted = gitlab_issue_intake_repo_slug(project)
    return bool(wanted and event.repo_slug.lower() == wanted.lower())


def _gitlab_tracker_for_project(
    project: Project,
    active_states: list[str],
    terminal_states: list[str],
) -> GitLabIssueTracker | None:
    slug = gitlab_issue_intake_repo_slug(project)
    if not slug or "/" not in slug:
        return None
    token = getattr(project, "access_token", None)
    forge_base_url = str(getattr(project, "forge_base_url", "") or "").strip()
    if not forge_base_url:
        forge_base_url = "https://gitlab.com"
    return GitLabIssueTracker(
        project=slug,
        token=token,
        base_url=forge_base_url,
        active_states=active_states,
        terminal_states=terminal_states,
        status_label_authorized_logins=getattr(
            project,
            "status_label_authorized_logins",
            [],
        ),
    )


def _external_identifier(namespace: str, project: str, number: str | int) -> str:
    return f"{namespace}/{project}#{number}"


def _external_identifier_for_project(
    project: Project,
    number: str | int | None,
) -> str | None:
    if number in (None, ""):
        return None
    slug = gitlab_issue_intake_repo_slug(project)
    if not slug or "/" not in slug:
        return None
    return slug + f"#{number}"


def _issue_url(namespace: str, project: str, number: str | int, base_url: str = "https://gitlab.com") -> str:
    return f"{base_url}/{namespace}/{project}/-/issues/{number}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_external_metadata(native_tracker: Any, identifier: str) -> dict[str, Any]:
    try:
        metadata = native_tracker.get_metadata(identifier)
    except Exception:
        return {}
    raw = metadata.get(EXTERNAL_GITLAB_METADATA_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def _set_external_metadata(
    native_tracker: Any,
    identifier: str,
    metadata: dict[str, Any],
) -> None:
    native_tracker.set_metadata_field(
        identifier,
        EXTERNAL_GITLAB_METADATA_KEY,
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
        logger.debug("gitlab_intake: failed to scan native issues: %s", exc)
        return None, {}

    for issue in issues or []:
        metadata = _get_external_metadata(native_tracker, issue.identifier)
        if str(metadata.get("id") or "").strip().lower() == external_id.lower():
            return issue, metadata

    # Valid-task scan found nothing. Check the import index for a prior import
    # whose task file may have become corrupt or unreadable.
    find_fn = getattr(native_tracker, "find_imported_task_id_for_external", None)
    if callable(find_fn):
        known_task_id = find_fn(external_id)
        if known_task_id:
            # The import index says this external issue was already imported.
            # Determine whether the task file is corrupt (vs. cleanly deleted).
            list_corrupt_fn = getattr(native_tracker, "list_corrupt_stubs", None)
            if callable(list_corrupt_fn):
                corrupt_stems = {stub["stem"].lower() for stub in list_corrupt_fn()}
                if known_task_id.lower() in corrupt_stems:
                    logger.warning(
                        "gitlab_intake: external issue %s was previously imported as "
                        "native task %s but that task file is corrupt/unreadable. "
                        "Blocking reimport to prevent a duplicate task. "
                        "Restore or repair the file to resume: "
                        "`git show HEAD:.oompah/tasks/*/%s.md` "
                        "or delete it to allow a fresh import.",
                        external_id, known_task_id, known_task_id,
                    )
                    return None, {"_blocked_reimport": True, "_known_task_id": known_task_id}
            # Import index has an entry but file is not in corrupt stubs — it may
            # have been cleanly deleted. Allow reimport so the task can be
            # recreated (the operator intentionally removed it).
            logger.debug(
                "gitlab_intake: import index entry %s→%s found but task file is "
                "absent (not in corrupt stubs); allowing reimport.",
                external_id, known_task_id,
            )

    return None, {}


def _native_status_is_merged_or_archived(status: str | None) -> bool:
    return status_key(canonicalize_status(status)) in _TERMINAL_CLOSE_KEYS


def _gitlab_issue_is_closed(gitlab_issue: Issue) -> bool:
    raw_state = status_key(gitlab_issue.state)
    return raw_state == "closed" or getattr(gitlab_issue, "closed_at", None) is not None


def _metadata_last_gitlab_state(metadata: dict[str, Any]) -> str:
    return str(metadata.get("last_gitlab_state") or "").strip().lower()


def _write_external_metadata_if_changed(
    native_tracker: Any,
    identifier: str,
    original: dict[str, Any],
    updated: dict[str, Any],
) -> None:
    if updated != original:
        _set_external_metadata(native_tracker, identifier, updated)


def _external_metadata_from_issue(gitlab_issue: Issue) -> dict[str, Any]:
    namespace = str(gitlab_issue.tracker_owner or "").strip()
    project = str(gitlab_issue.tracker_repo or "").strip()
    number = str(gitlab_issue.issue_number or "").strip()
    external_id = (
        _external_identifier(namespace, project, number)
        if namespace and project and number
        else gitlab_issue.identifier
    )
    return {
        "id": external_id,
        "namespace": namespace or None,
        "project": project or None,
        "number": number or None,
        "url": gitlab_issue.provider_url or (
            _issue_url(namespace, project, number) if namespace and project and number else None
        ),
        "requestor_login": gitlab_issue.requestor_login,
        "imported_comment_ids": [],
        "last_synced_status": PROPOSED,
        "last_synced_at": _now_iso(),
    }


_H1_H2_RE = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)


def _demote_h1_h2_headings(body: str) -> str:
    """Demote H1 and H2 Markdown headings in *body* to H3."""
    def _replace(m: re.Match) -> str:
        hashes = m.group(1)
        text = m.group(2)
        demoted = "#" * max(3, len(hashes))
        return f"{demoted} {text}"

    return _H1_H2_RE.sub(_replace, body)


def _native_description_for_gitlab_issue(gitlab_issue: Issue) -> str:
    """Build the description stored in the native task for a GitLab intake issue."""
    lines: list[str] = []
    if gitlab_issue.description:
        demoted = _demote_h1_h2_headings(gitlab_issue.description.strip())
        lines.append(demoted)
        lines.append("")
    lines.append("## External GitLab Issue")
    if gitlab_issue.provider_url:
        lines.append(f"- URL: {gitlab_issue.provider_url}")
    if gitlab_issue.requestor_login:
        lines.append(f"- Requestor: @{gitlab_issue.requestor_login}")
    lines.append(f"- Reference: {gitlab_issue.identifier}")
    return "\n".join(lines).strip()


def ensure_native_issue_for_gitlab_issue(
    native_tracker: Any,
    gitlab_tracker: Any,
    gitlab_issue: Issue,
    *,
    post_import_comment: bool = True,
    status_transition: Callable[..., object] | None = None,
) -> Issue | None:
    """Create or update the native Proposed task corresponding to a GitLab issue."""
    external_id = gitlab_issue.identifier

    existing, metadata = _find_native_issue_for_external(native_tracker, external_id)
    if existing is not None:
        return _reconcile_native_status_from_gitlab_issue(
            native_tracker,
            gitlab_issue,
            existing,
            metadata,
            status_transition=status_transition,
        )

    # A corrupt task file was found for this external issue — do not create a
    # duplicate. The operator must repair or remove the corrupt file first.
    if metadata.get("_blocked_reimport"):
        return None

    if _gitlab_issue_is_closed(gitlab_issue):
        return None

    # Forward issue type, priority, parent, and user-facing labels from the
    # parsed GitLab issue so the native task carries the same metadata as one
    # created via the polling path. The "external:gitlab" label is always
    # added to identify the task as GitLab-intake-derived.
    issue_type = (gitlab_issue.issue_type or "task") or "task"
    gitlab_user_labels = [
        lbl for lbl in (gitlab_issue.labels or []) if lbl != "external:gitlab"
    ]
    native_labels = ["external:gitlab"] + gitlab_user_labels

    created = native_tracker.create_issue(
        gitlab_issue.title,
        issue_type=issue_type,
        description=_native_description_for_gitlab_issue(gitlab_issue),
        priority=gitlab_issue.priority,
        initial_status=PROPOSED,
        labels=native_labels,
        parent=gitlab_issue.parent_id or None,
    )
    metadata = _external_metadata_from_issue(gitlab_issue)
    _set_external_metadata(native_tracker, created.identifier, metadata)
    created = native_tracker.fetch_issue_detail(created.identifier) or created

    # Record the import in the index so a future file-corruption event cannot
    # cause a duplicate reimport of the same external GitLab issue.
    record_fn = getattr(native_tracker, "record_external_import", None)
    if callable(record_fn):
        try:
            record_fn(external_id, created.identifier)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "gitlab_intake: failed to record import index entry %s→%s: %s",
                external_id, created.identifier, exc,
            )

    if post_import_comment:
        try:
            gitlab_tracker.add_comment(
                external_id,
                (
                    f"Imported into oompah as `{created.identifier}` and queued "
                    f"for intake validation in `{PROPOSED}`."
                ),
                author="oompah",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "gitlab_intake: failed to post import comment on %s: %s",
                external_id,
                exc,
            )
    return created


def _gitlab_issue_ready_for_native_import(
    gitlab_tracker: Any,
    gitlab_issue: Issue,
) -> bool:
    """Validate a GitLab intake issue before creating native work."""
    result = validate_issue(
        title=gitlab_issue.title,
        description=gitlab_issue.description,
        issue_type=gitlab_issue.issue_type,
        labels=gitlab_issue.labels,
    )
    if result.ready:
        return True

    requestor = str(gitlab_issue.requestor_login or "").strip()
    comment_result = IntakeCommentResult.from_validation_result(result)
    fingerprint = compute_fingerprint(comment_result, requestor)
    try:
        external_id = gitlab_issue.identifier
        metadata = gitlab_tracker.get_metadata(external_id)
    except Exception:
        metadata = {}
    existing = metadata.get(INTAKE_COMMENT_METADATA_KEY)
    if isinstance(existing, dict) and existing.get("fingerprint") == fingerprint:
        return False

    post_intake_comment_if_needed(
        gitlab_tracker,
        external_id,
        comment_result,
        requestor,
        issue_updated_at=getattr(gitlab_issue, "updated_at", None),
        author="oompah",
    )
    return False


def _is_oompah_comment(author: str | None, body: str | None) -> bool:
    author_key = str(author or "").strip().lower()
    text = str(body or "").strip().lower()
    return author_key == "oompah" or text.startswith("**oompah**:")


def import_gitlab_comment_to_native(
    native_tracker: Any,
    internal_identifier: str,
    metadata: dict[str, Any],
    *,
    comment_id: str | int | None,
    author: str | None,
    body: str | None,
) -> bool:
    """Copy a GitLab comment to the native task once, unless oompah wrote it."""
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

    comment_author = str(author or "gitlab").strip() or "gitlab"
    native_tracker.add_comment(internal_identifier, text, author=comment_author)
    if comment_key:
        metadata = dict(metadata)
        imported.add(comment_key)
        metadata["imported_comment_ids"] = sorted(imported)
        _set_external_metadata(native_tracker, internal_identifier, metadata)
    return True


def _fetch_gitlab_issue(
    gitlab_tracker: Any,
    external_identifier: str,
    fallback: Issue | None = None,
) -> Issue | None:
    try:
        fetched = gitlab_tracker.fetch_issue_detail(external_identifier)
        if fetched is not None:
            return fetched
    except Exception as exc:  # noqa: BLE001
        logger.debug("gitlab_intake: failed to fetch %s: %s", external_identifier, exc)
    return fallback


def _copy_existing_gitlab_comments(
    native_tracker: Any,
    gitlab_tracker: Any,
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
        comments = gitlab_tracker.fetch_comments(external_id)
    except Exception:
        return 0
    for comment in comments or []:
        if not isinstance(comment, dict):
            continue
        metadata = _get_external_metadata(native_tracker, internal_issue.identifier)
        if import_gitlab_comment_to_native(
            native_tracker,
            internal_issue.identifier,
            metadata,
            comment_id=comment.get("id") or comment.get("node_id"),
            author=comment.get("author") or comment.get("username"),
            body=comment.get("text") or comment.get("body"),
        ):
            copied += 1
    return copied


def _reconcile_native_status_from_gitlab_issue(
    native_tracker: Any,
    gitlab_issue: Issue,
    existing: Issue | None = None,
    metadata: dict[str, Any] | None = None,
    *,
    project_id: str | None = None,
    project_store: object | None = None,
    status_transition: Callable[..., object] | None = None,
) -> Issue | None:
    """Apply GitLab open/closed state to an already-imported native task."""
    external_id = gitlab_issue.identifier

    if existing is None or metadata is None:
        existing, metadata = _find_native_issue_for_external(native_tracker, external_id)
    if existing is None:
        return None

    metadata = dict(metadata or {})
    original_metadata = dict(metadata)
    current_status = canonicalize_status(existing.state)
    gitlab_closed = _gitlab_issue_is_closed(gitlab_issue)

    if gitlab_closed:
        metadata["last_gitlab_state"] = "closed"
        if not _native_status_is_merged_or_archived(current_status):
            disposition_reason = (
                "External GitLab intake retirement "
                f"(source={external_id}, external_state=closed)"
            )
            request_archived_audit(
                existing,
                native_tracker,
                project_id,
                disposition_reason,
                project_store=project_store,
                trigger_source="gitlab_intake",
            )
            metadata["external_closed_at"] = _now_iso()
            existing = native_tracker.fetch_issue_detail(existing.identifier) or existing
            current_status = canonicalize_status(existing.state)
            metadata["last_synced_status"] = current_status
            metadata["last_synced_at"] = _now_iso()
        _write_external_metadata_if_changed(
            native_tracker,
            existing.identifier,
            original_metadata,
            metadata,
        )
        return existing

    was_closed_by_gitlab = (
        _metadata_last_gitlab_state(metadata) == "closed"
        or bool(metadata.get("external_closed_at"))
    )
    if current_status == ARCHIVED and was_closed_by_gitlab:
        transition = status_transition or getattr(
            native_tracker, "transition_issue_status", None
        )
        if not callable(transition):
            raise RuntimeError("Task transition service is unavailable")
        transition(
            existing,
            PROPOSED,
            actor="gitlab-intake",
            reason_code="intake.external_issue_reopened",
            authorized_recovery=True,
        )
        metadata["last_gitlab_state"] = "open"
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

    if current_status == IN_VALIDATION and was_closed_by_gitlab:
        cancelled, previous_state = cancel_pending_archived_audit(
            existing,
            native_tracker,
            project_id,
            "external GitLab issue reopened before retirement completed; restoring prior state.",
            project_store=project_store,
        )
        if cancelled:
            restored_status = previous_state or PROPOSED
            transition = status_transition or getattr(
                native_tracker, "transition_issue_status", None
            )
            if not callable(transition):
                raise RuntimeError("Task transition service is unavailable")
            transition(
                existing,
                restored_status,
                actor="gitlab-intake",
                reason_code="intake.external_retirement_cancelled",
                authorized_recovery=True,
            )
            metadata["last_gitlab_state"] = "open"
            metadata["external_reopened_at"] = _now_iso()
            metadata["last_synced_status"] = restored_status
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


def poll_gitlab_issue_intake_project(orch: Any, project: Project) -> int:
    """Import currently-open GitLab issues for a native-intake project."""
    if getattr(project, "paused", False):
        return 0
    if not project_uses_gitlab_issue_intake(project):
        return 0
    try:
        native_tracker = orch._tracker_for_project(project.id)
        gitlab_tracker = _gitlab_tracker_for_project(
            project,
            list(getattr(orch.config, "tracker_active_states", [])),
            list(getattr(orch.config, "tracker_terminal_states", [])),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("gitlab_intake: poll setup failed for %s: %s", project.name, exc)
        return 0
    if gitlab_tracker is None:
        return 0
    status_transition = _orchestrator_status_transition(
        orch, native_tracker, str(project.id)
    )
    imported = 0
    try:
        gitlab_issues = gitlab_tracker.fetch_all_issues()
    except TrackerAuthError as exc:
        slug = gitlab_issue_intake_repo_slug(project) or "unknown/repo"
        logger.warning(
            "gitlab_intake: authentication failed for project %r fetching %s — "
            "set project access_token or configure GITLAB_TOKEN with "
            "read access to %s: %s",
            project.name,
            slug,
            slug,
            exc,
        )
        raise
    except Exception as exc:  # noqa: BLE001
        logger.debug("gitlab_intake: poll fetch failed for %s: %s", project.name, exc)
        return 0
    for gitlab_issue in gitlab_issues:
        try:
            if _gitlab_issue_is_closed(gitlab_issue):
                _reconcile_native_status_from_gitlab_issue(
                    native_tracker,
                    gitlab_issue,
                    project_id=project.id,
                    project_store=getattr(orch, "project_store", None),
                    status_transition=status_transition,
                )
                continue

            external_id = gitlab_issue.identifier
            existing, metadata = _find_native_issue_for_external(
                native_tracker,
                external_id,
            )
            if existing is not None:
                internal = _reconcile_native_status_from_gitlab_issue(
                    native_tracker,
                    gitlab_issue,
                    existing,
                    metadata,
                    project_id=project.id,
                    project_store=getattr(orch, "project_store", None),
                    status_transition=status_transition,
                ) or existing
                _copy_existing_gitlab_comments(native_tracker, gitlab_tracker, internal)
                continue

            _reconcile_native_status_from_gitlab_issue(
                native_tracker,
                gitlab_issue,
                project_id=project.id,
                project_store=getattr(orch, "project_store", None),
                status_transition=status_transition,
            )
            if not _gitlab_issue_ready_for_native_import(gitlab_tracker, gitlab_issue):
                continue
            created = ensure_native_issue_for_gitlab_issue(
                native_tracker,
                gitlab_tracker,
                gitlab_issue,
                post_import_comment=True,
                status_transition=status_transition,
            )
            if created is not None:
                imported += 1
            _copy_existing_gitlab_comments(native_tracker, gitlab_tracker, created)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "gitlab_intake: failed to import %s for %s: %s",
                gitlab_issue.identifier,
                project.name,
                exc,
            )
    return imported


def sync_gitlab_issue_intake_statuses_for_project(
    orch: Any,
    project: Project,
) -> dict[str, int]:
    """Reflect internal native-task status changes back to GitLab."""
    metrics = {"scanned": 0, "commented": 0, "closed": 0, "errors": 0}
    if getattr(project, "paused", False):
        return metrics
    if not project_uses_gitlab_issue_intake(project):
        return metrics
    try:
        native_tracker = orch._tracker_for_project(project.id)
        gitlab_tracker = _gitlab_tracker_for_project(
            project,
            list(getattr(orch.config, "tracker_active_states", [])),
            list(getattr(orch.config, "tracker_terminal_states", [])),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("gitlab_intake: status sync setup failed for %s: %s", project.name, exc)
        return metrics
    if gitlab_tracker is None:
        return metrics

    fetch_all = getattr(native_tracker, "fetch_all_issues_enriched", None)
    if not callable(fetch_all):
        fetch_all = getattr(native_tracker, "fetch_all_issues", None)
    if not callable(fetch_all):
        return metrics

    try:
        issues = fetch_all()
    except Exception as exc:  # noqa: BLE001
        logger.debug("gitlab_intake: failed to fetch native issues for status sync: %s", exc)
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
            gitlab_tracker.add_comment(
                external_id,
                f"Oompah task `{issue.identifier}` is now `{current_status}`.",
                author="oompah",
            )
            metrics["commented"] += 1
            if status_key(current_status) in _TERMINAL_CLOSE_KEYS:
                gitlab_tracker.update_issue(external_id, status=current_status)
                metrics["closed"] += 1
            metadata["last_synced_status"] = current_status
            metadata["last_synced_at"] = _now_iso()
            _set_external_metadata(native_tracker, issue.identifier, metadata)
        except Exception as exc:  # noqa: BLE001
            metrics["errors"] += 1
            logger.debug(
                "gitlab_intake: failed to sync %s -> %s: %s",
                issue.identifier,
                external_id,
                exc,
            )
    return metrics
