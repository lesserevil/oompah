"""Intake comment poster: deduplicated comments for issues missing information.

When a proposed issue fails readiness validation, the requestor needs one
clear, actionable message explaining what is missing.  This module owns the
"post a comment if needed" decision and the comment text generation so the
rest of oompah can call a single function without duplicating deduplication
logic.

## Deduplication strategy

A comment is suppressed when **all three** conditions hold:

1. A previous intake comment has been posted for this issue.
2. The validator result fingerprint is identical to the one recorded in the
   issue's ``oompah.intake_comment`` metadata.

When the fingerprint differs (validator result changed because the requestor
fixed some fields but not all), a new comment may be posted.

## Metadata format

The persistence record is stored in the hidden ``<!-- oompah:metadata -->``
block under the key ``intake_comment``::

    {
      "fingerprint": "<16-hex-char sha256 prefix>",
      "requested_actor": "<github login>",
      "posted_at": "<ISO-8601 UTC timestamp>",
      "issue_updated_at": "<ISO-8601 UTC timestamp or null>"
    }

All timestamps are UTC ISO-8601 strings.  ``issue_updated_at`` may be
``null`` when the caller did not supply the issue's updated-at time.

## Usage

The primary entry point is :func:`post_intake_comment_if_needed`.  Call it
after running the readiness validator::

    from oompah.intake_comments import ValidatorResult, post_intake_comment_if_needed

    result = ValidatorResult(
        is_ready=False,
        missing_fields=["acceptance_criteria", "problem_statement"],
        suggested_fixes={"acceptance_criteria": "Add a list of testable ACs."},
        scope="small_task",
    )
    posted = post_intake_comment_if_needed(
        tracker=tracker,
        identifier="lesserevil/oompah#123",
        result=result,
        requested_actor="alice",
        issue_updated_at=issue.updated_at,
    )
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from oompah.intake_schema import (
    DecompositionStatus,
    IntakeScopeKind,
    ValidatorResult as StoredValidatorResult,
    intake_to_raw,
    parse_intake_metadata,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

#: Valid scope classifications returned by the readiness validator.
SCOPE_SMALL_TASK = "small_task"
SCOPE_EPIC_NEEDED = "epic_needed"
SCOPE_DUPLICATE_CANDIDATE = "duplicate_candidate"
SCOPE_NEEDS_HUMAN_OWNER_REVIEW = "needs_human_owner_review"

#: Human-readable labels for scope values, used inside comments.
_SCOPE_LABELS: dict[str, str] = {
    SCOPE_SMALL_TASK: "implementation task",
    SCOPE_EPIC_NEEDED: "epic (requires decomposition)",
    SCOPE_DUPLICATE_CANDIDATE: "possible duplicate",
    SCOPE_NEEDS_HUMAN_OWNER_REVIEW: "needs human owner review",
}

#: Human-readable labels for missing field keys.
_FIELD_LABELS: dict[str, str] = {
    "title": "a clear, specific title",
    "problem_statement": "a clear problem statement",
    "desired_behavior": "a description of the desired behaviour",
    "acceptance_criteria": "acceptance criteria",
    "relevant_context": "relevant context or background",
    "issue_type": "issue type (bug / feature / chore / task)",
    "reproduction_steps": "reproduction steps",
    "repro_steps": "reproduction steps",
    "environment_detail": "environment / version details",
    "environment": "environment / version details",
    "expected_behavior": "expected behaviour",
    "actual_behavior": "actual behaviour",
    "success_criteria": "success criteria",
    "scope_justification": "scope justification",
    "work_description": "work description",
}

_SCOPE_TO_INTAKE_SCOPE: dict[str, IntakeScopeKind] = {
    SCOPE_SMALL_TASK: IntakeScopeKind.SMALL,
    SCOPE_EPIC_NEEDED: IntakeScopeKind.NEEDS_DECOMPOSITION,
    SCOPE_DUPLICATE_CANDIDATE: IntakeScopeKind.UNKNOWN,
    SCOPE_NEEDS_HUMAN_OWNER_REVIEW: IntakeScopeKind.UNKNOWN,
}


@dataclass
class ValidatorResult:
    """Structured result from the proposed-issue readiness validator.

    Parameters
    ----------
    is_ready:
        ``True`` when the issue passes all readiness checks and can be
        promoted to Backlog.  When ``False``, ``missing_fields`` lists the
        fields that must still be provided.
    missing_fields:
        Short field keys identifying what information is absent.  Empty
        when ``is_ready`` is ``True``.  The order is not significant;
        :func:`compute_fingerprint` normalises before hashing.
    suggested_fixes:
        Optional mapping from field key to a concrete suggestion the
        requestor can act on.  Keys that do not appear in this dict are
        described generically in the comment body.
    scope:
        Scope classification of the issue.  One of the ``SCOPE_*``
        constants in this module.  Used to tailor the comment preamble.
    """

    is_ready: bool
    missing_fields: list[str] = field(default_factory=list)
    suggested_fixes: dict[str, str] = field(default_factory=dict)
    scope: str = SCOPE_SMALL_TASK

    @classmethod
    def from_validation_result(cls, result: Any) -> "ValidatorResult":
        """Adapt ``oompah.issue_validator.ValidationResult``-like objects.

        The readiness validator returns ``ready``, ``scope`` and
        ``missing_fields`` where each missing field may be a rich object with
        ``field`` and ``suggested_fix`` attributes.  This adapter also accepts
        the simpler local shape used by unit tests and future callers.
        """
        ready = getattr(result, "is_ready", None)
        if ready is None:
            ready = getattr(result, "ready", False)

        scope = getattr(result, "scope", SCOPE_SMALL_TASK)
        scope_value = _scope_value(scope)

        missing_keys: list[str] = []
        suggested_fixes: dict[str, str] = {}
        for item in getattr(result, "missing_fields", []) or []:
            if hasattr(item, "field"):
                key = _normalise_field_key(getattr(item, "field", ""))
                suggestion = str(getattr(item, "suggested_fix", "") or "").strip()
            else:
                key = _normalise_field_key(item)
                suggestion = ""
            if not key:
                continue
            missing_keys.append(key)
            if suggestion:
                suggested_fixes[key] = suggestion

        raw_suggestions = getattr(result, "suggested_fixes", {}) or {}
        if isinstance(raw_suggestions, dict):
            for key, suggestion in raw_suggestions.items():
                normalised_key = _normalise_field_key(key)
                if normalised_key and suggestion:
                    suggested_fixes[normalised_key] = str(suggestion).strip()

        return cls(
            is_ready=bool(ready),
            missing_fields=missing_keys,
            suggested_fixes=suggested_fixes,
            scope=scope_value,
        )


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------


def compute_fingerprint(result: ValidatorResult, requested_actor: str) -> str:
    """Return a stable 16-hex-char fingerprint for a validator result.

    The fingerprint is derived from the **sorted** list of missing fields,
    the scope classification, and the requested actor.  It is stable across
    Python runs and unaffected by dict or list ordering in the caller.

    Two results are considered equivalent (same fingerprint) when they flag
    the same missing fields, the same scope, and target the same actor.
    The ``suggested_fixes`` dict does **not** contribute to the fingerprint
    because wording changes alone should not trigger a fresh comment.
    """
    key_parts = sorted(
        field
        for field in (_normalise_field_key(f) for f in result.missing_fields)
        if field
    )
    key_parts.extend([_scope_value(result.scope), _normalise_actor(requested_actor)])
    raw = "|".join(key_parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Comment text generation
# ---------------------------------------------------------------------------


def build_intake_comment(
    result: ValidatorResult,
    requested_actor: str,
    *,
    author: str = "oompah",
) -> str:
    """Generate the Markdown comment body for a readiness failure.

    The comment:

    * Addresses the requestor directly (``@{requested_actor}``).
    * Names each missing field with a concrete description.
    * Includes per-field suggestions where ``result.suggested_fixes``
      provides them.
    * Mentions the scope classification when it is not ``small_task``.

    The ``author`` parameter is accepted but **not** prepended here — the
    tracker's :meth:`add_comment` method handles the ``**{author}**: ``
    prefix so callers do not need to format it themselves.

    Returns
    -------
    str
        Markdown comment body, ready to pass to ``tracker.add_comment()``.
    """
    actor = requested_actor.strip()
    actor_mention = f"@{actor}" if actor else "Hi"

    # Scope line — only shown for non-default scopes.
    scope_key = _scope_value(result.scope)
    scope_label = _SCOPE_LABELS.get(scope_key, scope_key)
    scope_note = ""
    if scope_key and scope_key != SCOPE_SMALL_TASK:
        scope_note = (
            "\n\n> **Scope note:** This issue is classified as "
            f"*{scope_label}* and may need additional scoping discussion "
            "before it can be actioned."
        )

    if not result.missing_fields:
        return (
            f"{actor_mention}, this issue has been reviewed and appears ready "
            f"to enter the backlog.{scope_note}"
        )

    # Build the field list.
    suggestions = {
        _normalise_field_key(key): str(value).strip()
        for key, value in result.suggested_fixes.items()
        if _normalise_field_key(key) and str(value).strip()
    }
    lines: list[str] = []
    for field_key in sorted({_normalise_field_key(f) for f in result.missing_fields}):
        if not field_key:
            continue
        label = _FIELD_LABELS.get(field_key, field_key.replace("_", " "))
        suggestion = suggestions.get(field_key, "")
        if suggestion:
            lines.append(f"- **{label}** — {suggestion}")
        else:
            lines.append(f"- **{label}**")

    field_list = "\n".join(lines)

    preamble = (
        f"{actor_mention}, this issue is missing the following information "
        f"before it can enter the backlog:"
    )

    return (
        f"{preamble}\n\n{field_list}{scope_note}\n\n"
        "Please update the issue with the missing details."
    )


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

_META_KEY = "oompah.intake_comment"
_INTAKE_META_KEY = "oompah.intake"


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _dt_to_iso(dt: datetime | None) -> str | None:
    """Serialise a datetime to ISO-8601 UTC string, or None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _iso_to_dt(s: str | None) -> datetime | None:
    """Parse an ISO-8601 string to a UTC-aware datetime, or None."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _normalise_actor(actor: str) -> str:
    """Return a canonical actor login for fingerprinting."""
    return str(actor or "").strip().lower()


def _normalise_field_key(field: Any) -> str:
    """Return a canonical snake_case key for a missing validator field."""
    raw = str(field or "").strip().lower()
    if not raw:
        return ""
    return (
        raw.replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("__", "_")
    )


def _scope_value(scope: Any) -> str:
    """Return a stable string value for enum or string scope objects."""
    value = getattr(scope, "value", scope)
    return str(value or SCOPE_SMALL_TASK).strip().lower()


def _load_intake_record(tracker: Any, identifier: str) -> dict[str, Any]:
    """Return the existing intake comment record for *identifier*, or ``{}``."""
    try:
        meta = tracker.get_metadata(identifier)
    except Exception as exc:
        logger.debug(
            "intake_comments: failed to read metadata for %s: %s",
            identifier,
            exc,
        )
        return {}
    value = meta.get(_META_KEY)
    if not isinstance(value, dict):
        return {}
    return value


def _save_intake_record(
    tracker: Any,
    identifier: str,
    record: dict[str, Any],
) -> None:
    """Persist *record* as the intake comment state for *identifier*."""
    try:
        tracker.set_metadata_field(identifier, _META_KEY, record)
    except Exception as exc:
        logger.warning(
            "intake_comments: failed to save intake record for %s: %s",
            identifier,
            exc,
        )


def _scope_to_intake_scope(scope: str) -> IntakeScopeKind:
    """Map readiness-validator scope values to the persisted intake schema."""
    return _SCOPE_TO_INTAKE_SCOPE.get(_scope_value(scope), IntakeScopeKind.UNKNOWN)


def _update_intake_metadata(
    tracker: Any,
    identifier: str,
    result: ValidatorResult,
    validated_at: str,
) -> None:
    """Persist the latest failed validation into ``oompah.intake`` metadata."""
    try:
        meta = tracker.get_metadata(identifier)
    except Exception as exc:
        logger.debug(
            "intake_comments: failed to read intake metadata for %s: %s",
            identifier,
            exc,
        )
        meta = {}

    previous = parse_intake_metadata(meta.get(_INTAKE_META_KEY))
    readiness = parse_intake_metadata(meta.get(_INTAKE_META_KEY))
    readiness.missing_fields = [
        field
        for field in sorted({_normalise_field_key(f) for f in result.missing_fields})
        if field
    ]
    readiness.scope = _scope_to_intake_scope(result.scope)
    readiness.last_validator_result = (
        StoredValidatorResult.PASS if result.is_ready else StoredValidatorResult.FAIL
    )
    readiness.last_validated_at = validated_at
    if readiness.scope == IntakeScopeKind.NEEDS_DECOMPOSITION:
        readiness.decomposition_status = DecompositionStatus.PENDING
    elif readiness.decomposition_status == DecompositionStatus.PENDING:
        readiness.decomposition_status = DecompositionStatus.NOT_NEEDED

    previous_raw = intake_to_raw(previous)
    next_raw = intake_to_raw(readiness)
    previous_raw.pop("last_validated_at", None)
    next_raw.pop("last_validated_at", None)
    if previous.last_validated_at and previous_raw == next_raw:
        return

    readiness.last_validated_at = validated_at
    try:
        tracker.set_metadata_field(
            identifier,
            _INTAKE_META_KEY,
            intake_to_raw(readiness),
        )
    except Exception as exc:
        logger.warning(
            "intake_comments: failed to save intake metadata for %s: %s",
            identifier,
            exc,
        )


# ---------------------------------------------------------------------------
# Deduplication decision
# ---------------------------------------------------------------------------


def should_post_intake_comment(
    existing_record: dict[str, Any],
    fingerprint: str,
    issue_updated_at: datetime | None,
) -> bool:
    """Return ``True`` when a fresh intake comment should be posted.

    Decision table
    --------------

    ===========================  =====
    Existing record              Post?
    ===========================  =====
    None (first time)            Yes
    Same fingerprint             No
    Different fingerprint        Yes
    ===========================  =====

    Parameters
    ----------
    existing_record:
        The dict previously returned by :func:`_load_intake_record`.  Empty
        dict means no record exists.
    fingerprint:
        The fingerprint of the *current* validator result.
    issue_updated_at:
        Accepted for backward compatibility with older callers. It no longer
        affects duplicate suppression because oompah's own metadata writes and
        comments also advance GitHub's issue timestamp.
    """
    if not existing_record:
        # First time we've seen this issue — always post.
        return True

    existing_fp = existing_record.get("fingerprint", "")
    return existing_fp != fingerprint


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def post_intake_comment_if_needed(
    tracker: Any,
    identifier: str,
    result: ValidatorResult | Any,
    requested_actor: str,
    issue_updated_at: datetime | None = None,
    *,
    author: str = "oompah",
    post_comment: bool = True,
) -> bool:
    """Post an intake comment on *identifier* if deduplication allows it.

    Parameters
    ----------
    tracker:
        Any object satisfying :class:`oompah.tracker.TrackerProtocol`
        (``add_comment``, ``get_metadata``, ``set_metadata_field``).
    identifier:
        Fully-qualified issue identifier (e.g. ``lesserevil/oompah#123``).
    result:
        The validator result for the issue.  If ``result.is_ready`` is
        ``True`` and ``result.missing_fields`` is empty, no comment is
        posted (the issue needs no intake reminder).
    requested_actor:
        The GitHub login (without ``@``) of the person being asked to fill
        in the missing information — typically the issue author.
    issue_updated_at:
        The issue's ``updated_at`` datetime at the time of this call.
        Pass ``None`` when the timestamp is unavailable; deduplication will
        be conservative (duplicate suppression still active).
    author:
        Comment attribution string.  Defaults to ``"oompah"``.
    post_comment:
        When ``False``, only update intake metadata. This lets automatic
        background paths surface guidance in the UI without posting GitHub
        comments.

    Returns
    -------
    bool
        ``True`` when a comment was posted; ``False`` when suppressed.
    """
    comment_result = (
        result if isinstance(result, ValidatorResult)
        else ValidatorResult.from_validation_result(result)
    )

    validated_at = _now_iso()
    _update_intake_metadata(tracker, identifier, comment_result, validated_at)

    if comment_result.is_ready or not comment_result.missing_fields:
        # Issue is ready — nothing to request.
        logger.debug(
            "intake_comments: issue %s is ready, skipping intake comment", identifier
        )
        return False

    if not post_comment:
        logger.debug(
            "intake_comments: issue %s is missing fields; comment disabled",
            identifier,
        )
        return False

    fingerprint = compute_fingerprint(comment_result, requested_actor)
    existing = _load_intake_record(tracker, identifier)

    if not should_post_intake_comment(existing, fingerprint, issue_updated_at):
        logger.debug(
            "intake_comments: suppressing duplicate intake comment for %s "
            "(fp=%s, same as existing record)",
            identifier, fingerprint,
        )
        return False

    # Build and post the comment.
    comment_body = build_intake_comment(comment_result, requested_actor, author=author)
    try:
        tracker.add_comment(identifier, comment_body, author=author)
    except Exception as exc:
        logger.warning(
            "intake_comments: failed to post comment on %s: %s", identifier, exc
        )
        return False

    # Persist the new record so future calls can deduplicate.
    record: dict[str, Any] = {
        "fingerprint": fingerprint,
        "requested_actor": requested_actor.strip(),
        "posted_at": validated_at,
        "issue_updated_at": _dt_to_iso(issue_updated_at),
    }
    _save_intake_record(tracker, identifier, record)

    logger.info(
        "intake_comments: posted intake comment on %s (fp=%s, actor=%s, fields=%s)",
        identifier, fingerprint, requested_actor, comment_result.missing_fields,
    )
    return True
