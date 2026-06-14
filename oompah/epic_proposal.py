"""Epic and child-task proposals for oversized intake issues.

This module owns the decomposition payload for issues that the readiness
validator classifies as too large for one task.  It is intentionally
tracker-agnostic: callers pass any object implementing the tracker protocol
methods used here (metadata, comments, issue creation, and parent linking).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from oompah.intake_schema import (
    DecompositionStatus,
    IntakeReadiness,
    IntakeScopeKind,
    ValidatorResult,
    intake_to_raw,
    parse_intake_metadata,
)
from oompah.intake_comments import post_intake_comment_if_needed
from oompah.intake_promotion import promote_proposed_issue_to_backlog
from oompah.issue_validator import ScopeClassification, ValidationResult, validate_issue
from oompah.models import Issue
from oompah.statuses import DECOMPOSED, PROPOSED

logger = logging.getLogger(__name__)

EPIC_PROPOSAL_METADATA_KEY = "oompah.epic_proposal"
INTAKE_METADATA_KEY = "oompah.intake"
MAX_GENERATED_CHILDREN = 6
MIN_GENERATED_CHILDREN = 3

_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$", re.MULTILINE)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
_AC_HEADING_RE = re.compile(
    r"^#{1,6}\s+(?:acceptance criteria|success criteria|definition of done|done criteria|ac)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class EpicProposalChild:
    """One proposed child task in an epic decomposition."""

    title: str
    description: str
    issue_type: str = "task"
    priority: int | None = None

    def to_raw(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "issue_type": self.issue_type,
            "priority": self.priority,
        }

    @classmethod
    def from_raw(cls, raw: Any) -> "EpicProposalChild | None":
        if not isinstance(raw, dict):
            return None
        title = str(raw.get("title") or "").strip()
        description = str(raw.get("description") or "").strip()
        if not title or not description:
            return None
        priority_raw = raw.get("priority")
        priority: int | None
        try:
            priority = int(priority_raw) if priority_raw is not None else None
        except (TypeError, ValueError):
            priority = None
        return cls(
            title=title,
            description=description,
            issue_type=str(raw.get("issue_type") or "task").strip() or "task",
            priority=priority,
        )


@dataclass
class EpicProposal:
    """Stored decomposition proposal for one oversized source issue."""

    fingerprint: str
    source_identifier: str
    source_title: str
    source_requestor: str | None
    epic_title: str
    epic_summary: str
    children: list[EpicProposalChild] = field(default_factory=list)
    status: str = DecompositionStatus.PROPOSED.value
    epic_identifier: str | None = None
    child_identifiers: list[str] = field(default_factory=list)
    applied_fingerprint: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_raw(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "source_identifier": self.source_identifier,
            "source_title": self.source_title,
            "source_requestor": self.source_requestor,
            "epic_title": self.epic_title,
            "epic_summary": self.epic_summary,
            "children": [child.to_raw() for child in self.children],
            "status": self.status,
            "epic_identifier": self.epic_identifier,
            "child_identifiers": list(self.child_identifiers),
            "applied_fingerprint": self.applied_fingerprint,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_raw(cls, raw: Any) -> "EpicProposal | None":
        if not isinstance(raw, dict):
            return None
        children = [
            child
            for child in (EpicProposalChild.from_raw(c) for c in raw.get("children") or [])
            if child is not None
        ]
        fingerprint = str(raw.get("fingerprint") or "").strip()
        source_identifier = str(raw.get("source_identifier") or "").strip()
        epic_title = str(raw.get("epic_title") or "").strip()
        epic_summary = str(raw.get("epic_summary") or "").strip()
        if not fingerprint or not source_identifier or not epic_title or not epic_summary:
            return None
        child_identifiers_raw = raw.get("child_identifiers") or []
        if isinstance(child_identifiers_raw, str):
            child_identifiers_raw = [child_identifiers_raw]
        return cls(
            fingerprint=fingerprint,
            source_identifier=source_identifier,
            source_title=str(raw.get("source_title") or "").strip(),
            source_requestor=(
                str(raw.get("source_requestor")).strip()
                if raw.get("source_requestor") is not None
                else None
            ),
            epic_title=epic_title,
            epic_summary=epic_summary,
            children=children,
            status=str(raw.get("status") or DecompositionStatus.PROPOSED.value),
            epic_identifier=(
                str(raw.get("epic_identifier")).strip()
                if raw.get("epic_identifier") is not None
                else None
            ),
            child_identifiers=[
                str(value).strip()
                for value in child_identifiers_raw
                if str(value).strip()
            ],
            applied_fingerprint=(
                str(raw.get("applied_fingerprint")).strip()
                if raw.get("applied_fingerprint") is not None
                else None
            ),
            created_at=(
                str(raw.get("created_at")).strip()
                if raw.get("created_at") is not None
                else None
            ),
            updated_at=(
                str(raw.get("updated_at")).strip()
                if raw.get("updated_at") is not None
                else None
            ),
        )


@dataclass
class EpicProposalEnsureResult:
    """Result of ensuring a proposed decomposition exists."""

    proposal: EpicProposal
    created: bool = False
    comment_posted: bool = False
    duplicate_suppressed: bool = False


@dataclass
class EpicProposalApplyResult:
    """Result of applying an accepted decomposition proposal."""

    proposal: EpicProposal | None
    epic_identifier: str | None = None
    child_identifiers: list[str] = field(default_factory=list)
    created_epic: bool = False
    created_child_count: int = 0
    updated_child_count: int = 0
    duplicate_suppressed: bool = False
    skipped_reason: str | None = None


@dataclass
class IntakeValidationProcessResult:
    """Result of validating a Proposed issue that did not need decomposition."""

    validation: ValidationResult
    comment_posted: bool = False
    promoted: bool = False
    validation_recorded: bool = True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _truncate(value: str, limit: int) -> str:
    value = _normalize_text(value)
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)].rstrip(" ,.;:-") + "..."


def _source_ref(issue: Issue) -> str:
    if issue.url:
        return f"{issue.identifier} ({issue.url})"
    return issue.identifier


def _topic_from_title(title: str) -> str:
    topic = _normalize_text(title)
    topic = re.sub(r"^(epic|task|feature|bug|chore)\s*:\s*", "", topic, flags=re.I)
    return topic or "the requested work"


def _section_after(match: re.Match[str], description: str) -> str:
    rest = description[match.end():]
    next_heading = _HEADING_RE.search(rest)
    if next_heading:
        return rest[: next_heading.start()]
    return rest


def _clean_bullet(text: str) -> str:
    cleaned = re.sub(r"^\[[ xX]\]\s*", "", text.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -\t")


def _acceptance_items(description: str) -> list[str]:
    body = description or ""
    matches = list(_AC_HEADING_RE.finditer(body))
    sections = [_section_after(match, body) for match in matches]
    search_bodies = sections or [body]
    items: list[str] = []
    seen: set[str] = set()
    for search_body in search_bodies:
        for raw in _BULLET_RE.findall(search_body):
            item = _clean_bullet(raw)
            if len(item) < 8:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
            if len(items) >= MAX_GENERATED_CHILDREN:
                return items
    return items


def _child_title_from_item(item: str, topic: str) -> str:
    phrase = item
    phrase = re.sub(r"^(the\s+)?(system|user|agent|oompah)\s+(must|should|can|will)\s+", "", phrase, flags=re.I)
    phrase = re.sub(r"^(must|should|can|will|shall)\s+", "", phrase, flags=re.I)
    phrase = phrase.rstrip(".")
    if not phrase:
        phrase = topic
    if not re.match(r"^(add|allow|build|create|define|detect|ensure|generate|implement|preserve|prevent|record|support|update|validate)\b", phrase, re.I):
        phrase = f"Implement {phrase[0].lower()}{phrase[1:]}" if phrase else topic
    return _truncate(phrase[0].upper() + phrase[1:], 96)


def _child_description(
    *,
    source: Issue,
    requestor: str | None,
    work_summary: str,
    acceptance_item: str,
) -> str:
    lines = [
        f"Source issue: {_source_ref(source)}",
        f"Source title: {source.title}",
    ]
    if requestor:
        lines.append(f"Original requestor: @{requestor}")
    lines.extend(
        [
            "",
            "## Work",
            work_summary,
            "",
            "## Acceptance Criteria",
            f"- {acceptance_item.rstrip('.')}.",
        ]
    )
    return "\n".join(lines)


def _fallback_items(topic: str) -> list[tuple[str, str]]:
    return [
        (
            f"Define {topic} scope and implementation plan",
            "Scope boundaries, data contracts, and rollout assumptions are documented for this slice.",
        ),
        (
            f"Implement {topic} core workflow",
            "The central behavior from the source request is implemented behind the agreed interface.",
        ),
        (
            f"Add {topic} verification and regression coverage",
            "Automated tests and operator-facing verification cover the completed workflow.",
        ),
    ]


def _generate_children(source: Issue, requestor: str | None) -> list[EpicProposalChild]:
    topic = _topic_from_title(source.title)
    children: list[EpicProposalChild] = []
    for item in _acceptance_items(source.description or ""):
        title = _child_title_from_item(item, topic)
        description = _child_description(
            source=source,
            requestor=requestor,
            work_summary=f"Deliver this independently testable slice of the source request: {item.rstrip('.')}.",
            acceptance_item=item,
        )
        children.append(
            EpicProposalChild(
                title=title,
                description=description,
                priority=source.priority,
            )
        )

    existing_titles = {child.title.lower() for child in children}
    for title, acceptance in _fallback_items(topic):
        if len(children) >= MIN_GENERATED_CHILDREN:
            break
        child_title = _truncate(title, 96)
        if child_title.lower() in existing_titles:
            continue
        children.append(
            EpicProposalChild(
                title=child_title,
                description=_child_description(
                    source=source,
                    requestor=requestor,
                    work_summary=(
                        "Deliver a bounded slice of the oversized source request "
                        f"focused on {topic}."
                    ),
                    acceptance_item=acceptance,
                ),
                priority=source.priority,
            )
        )
        existing_titles.add(child_title.lower())

    return children[:MAX_GENERATED_CHILDREN]


def _proposal_fingerprint_payload(
    source: Issue,
    epic_title: str,
    epic_summary: str,
    children: list[EpicProposalChild],
) -> dict[str, Any]:
    return {
        "source_identifier": source.identifier,
        "source_title": _normalize_text(source.title),
        "source_description": _normalize_text(source.description),
        "source_issue_type": _normalize_text(source.issue_type),
        "epic_title": _normalize_text(epic_title),
        "epic_summary": _normalize_text(epic_summary),
        "children": [
            {
                "title": _normalize_text(child.title),
                "description": _normalize_text(child.description),
                "issue_type": _normalize_text(child.issue_type),
            }
            for child in children
        ],
    }


def compute_epic_proposal_fingerprint(
    source: Issue,
    epic_title: str,
    epic_summary: str,
    children: list[EpicProposalChild],
) -> str:
    """Return a stable SHA-256 fingerprint for a generated proposal."""
    payload = _proposal_fingerprint_payload(source, epic_title, epic_summary, children)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def generate_epic_proposal(
    source: Issue,
    *,
    validation_result: ValidationResult | None = None,
    requestor: str | None = None,
) -> EpicProposal:
    """Generate a deterministic epic/child-task proposal for *source*."""
    topic = _topic_from_title(source.title)
    epic_title = source.title if source.title.lower().startswith("epic:") else f"Epic: {topic}"
    epic_title = _truncate(epic_title, 120)
    epic_summary = (
        f"Decompose the oversized request from {_source_ref(source)} into "
        "independently reviewable implementation tasks while preserving the "
        "original request context."
    )
    if requestor:
        epic_summary += f" Original requestor: @{requestor}."
    if validation_result is not None and validation_result.warnings:
        epic_summary += " Validator note: " + " ".join(validation_result.warnings)
    children = _generate_children(source, requestor)
    fingerprint = compute_epic_proposal_fingerprint(
        source, epic_title, epic_summary, children
    )
    now = _now_iso()
    return EpicProposal(
        fingerprint=fingerprint,
        source_identifier=source.identifier,
        source_title=source.title,
        source_requestor=requestor,
        epic_title=epic_title,
        epic_summary=epic_summary,
        children=children,
        created_at=now,
        updated_at=now,
    )


def build_epic_proposal_comment(proposal: EpicProposal) -> str:
    """Return the Markdown comment that asks for decomposition approval."""
    actor = f"@{proposal.source_requestor}" if proposal.source_requestor else "Hi"
    child_lines = [
        f"{idx}. **{child.title}**"
        for idx, child in enumerate(proposal.children, start=1)
    ]
    child_block = "\n".join(child_lines)
    return (
        f"{actor}, this issue looks too large for one implementation task. "
        "I generated a proposed epic breakdown for review.\n\n"
        f"## Proposed Epic\n\n**{proposal.epic_title}**\n\n"
        f"{proposal.epic_summary}\n\n"
        f"## Proposed Child Tasks\n\n{child_block}\n\n"
        "Approve the breakdown with `/oompah approve`, or edit the issue if "
        "the proposed split should change.\n\n"
        f"Proposal fingerprint: `{proposal.fingerprint}`"
    )


def should_propose_epic_decomposition(
    validation_result: ValidationResult,
    issue: Issue,
) -> bool:
    """Return True when a validator result should enter decomposition."""
    return (
        validation_result.scope == ScopeClassification.EPIC_NEEDED
        and (issue.issue_type or "task").strip().lower() != "epic"
        and not issue.parent_id
    )


def _load_readiness(tracker: Any, identifier: str) -> IntakeReadiness:
    try:
        meta = tracker.get_metadata(identifier)
    except Exception as exc:  # noqa: BLE001
        logger.debug("epic_proposal: failed to read metadata for %s: %s", identifier, exc)
        return IntakeReadiness()
    return parse_intake_metadata(meta.get(INTAKE_METADATA_KEY))


def _save_readiness(tracker: Any, identifier: str, readiness: IntakeReadiness) -> None:
    tracker.set_metadata_field(identifier, INTAKE_METADATA_KEY, intake_to_raw(readiness))


def load_epic_proposal(tracker: Any, identifier: str) -> EpicProposal | None:
    """Load the stored proposal metadata for *identifier*, if present."""
    try:
        meta = tracker.get_metadata(identifier)
    except Exception as exc:  # noqa: BLE001
        logger.debug("epic_proposal: failed to read proposal metadata for %s: %s", identifier, exc)
        return None
    return EpicProposal.from_raw(meta.get(EPIC_PROPOSAL_METADATA_KEY))


def save_epic_proposal(tracker: Any, identifier: str, proposal: EpicProposal) -> None:
    """Persist *proposal* to issue metadata."""
    proposal.updated_at = _now_iso()
    if proposal.created_at is None:
        proposal.created_at = proposal.updated_at
    tracker.set_metadata_field(identifier, EPIC_PROPOSAL_METADATA_KEY, proposal.to_raw())


def _missing_field_keys(validation_result: ValidationResult) -> list[str]:
    return [
        re.sub(r"[^a-z0-9]+", "_", missing.field.strip().lower()).strip("_")
        for missing in validation_result.missing_fields
        if missing.field.strip()
    ]


def ensure_epic_proposal(
    tracker: Any,
    source: Issue,
    *,
    validation_result: ValidationResult | None = None,
    requestor: str | None = None,
    author: str = "oompah",
) -> EpicProposalEnsureResult | None:
    """Create or refresh the proposal metadata/comment for an oversized issue.

    Returns ``None`` when the issue is not classified as needing decomposition.
    Repeated calls with the same proposal fingerprint update readiness metadata
    but suppress duplicate comments.
    """
    result = validation_result or validate_issue(
        title=source.title,
        description=source.description,
        issue_type=source.issue_type,
        labels=source.labels,
    )
    if not should_propose_epic_decomposition(result, source):
        return None

    proposal = generate_epic_proposal(
        source,
        validation_result=result,
        requestor=requestor,
    )
    existing = load_epic_proposal(tracker, source.identifier)
    readiness = _load_readiness(tracker, source.identifier)
    readiness.scope = IntakeScopeKind.NEEDS_DECOMPOSITION
    readiness.proposal_fingerprint = proposal.fingerprint
    readiness.missing_fields = _missing_field_keys(result)
    readiness.last_validator_result = (
        ValidatorResult.PASS if result.ready else ValidatorResult.FAIL
    )
    readiness.last_validated_at = _now_iso()

    if existing is not None and existing.fingerprint == proposal.fingerprint:
        if readiness.decomposition_status in (
            DecompositionStatus.NOT_NEEDED,
            DecompositionStatus.PENDING,
        ):
            readiness.decomposition_status = DecompositionStatus.PROPOSED
        _save_readiness(tracker, source.identifier, readiness)
        return EpicProposalEnsureResult(
            proposal=existing,
            created=False,
            comment_posted=False,
            duplicate_suppressed=True,
        )

    readiness.decomposition_status = DecompositionStatus.PROPOSED
    save_epic_proposal(tracker, source.identifier, proposal)
    _save_readiness(tracker, source.identifier, readiness)

    comment_posted = False
    try:
        tracker.add_comment(
            source.identifier,
            build_epic_proposal_comment(proposal),
            author=author,
        )
        comment_posted = True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "epic_proposal: failed to post proposal comment on %s: %s",
            source.identifier,
            exc,
        )

    return EpicProposalEnsureResult(
        proposal=proposal,
        created=True,
        comment_posted=comment_posted,
        duplicate_suppressed=False,
    )


def _issue_exists(tracker: Any, identifier: str | None) -> bool:
    if not identifier:
        return False
    try:
        return tracker.fetch_issue_detail(identifier) is not None
    except Exception:  # noqa: BLE001
        return False


def _epic_description(proposal: EpicProposal) -> str:
    lines = [
        proposal.epic_summary,
        "",
        "## Source",
        f"- Issue: {proposal.source_identifier}",
        f"- Title: {proposal.source_title}",
    ]
    if proposal.source_requestor:
        lines.append(f"- Original requestor: @{proposal.source_requestor}")
    lines.extend(
        [
            f"- Proposal fingerprint: `{proposal.fingerprint}`",
            "",
            "## Child Tasks",
        ]
    )
    for child in proposal.children:
        lines.append(f"- {child.title}")
    return "\n".join(lines)


def _child_description_with_fingerprint(
    proposal: EpicProposal,
    child: EpicProposalChild,
) -> str:
    return (
        f"{child.description}\n\n"
        "## Decomposition\n"
        f"- Epic proposal fingerprint: `{proposal.fingerprint}`\n"
        f"- Source issue: {proposal.source_identifier}"
    )


def _all_applied_issue_ids_exist(tracker: Any, proposal: EpicProposal) -> bool:
    if proposal.applied_fingerprint != proposal.fingerprint:
        return False
    if not proposal.epic_identifier or not proposal.child_identifiers:
        return False
    if len(proposal.child_identifiers) != len(proposal.children):
        return False
    if not _issue_exists(tracker, proposal.epic_identifier):
        return False
    return all(_issue_exists(tracker, child_id) for child_id in proposal.child_identifiers)


def apply_epic_proposal(
    tracker: Any,
    source: Issue,
    *,
    require_accepted: bool = True,
    author: str = "oompah",
) -> EpicProposalApplyResult:
    """Apply an accepted proposal by creating/updating the epic and children."""
    proposal = load_epic_proposal(tracker, source.identifier)
    if proposal is None:
        return EpicProposalApplyResult(proposal=None, skipped_reason="missing_proposal")

    readiness = _load_readiness(tracker, source.identifier)
    if require_accepted and readiness.decomposition_status != DecompositionStatus.ACCEPTED:
        return EpicProposalApplyResult(
            proposal=proposal,
            skipped_reason="not_accepted",
        )

    if _all_applied_issue_ids_exist(tracker, proposal):
        return EpicProposalApplyResult(
            proposal=proposal,
            epic_identifier=proposal.epic_identifier,
            child_identifiers=list(proposal.child_identifiers),
            duplicate_suppressed=True,
        )

    created_epic = False
    epic_description = _epic_description(proposal)
    if proposal.epic_identifier and _issue_exists(tracker, proposal.epic_identifier):
        tracker.update_issue(
            proposal.epic_identifier,
            title=proposal.epic_title,
            description=epic_description,
        )
        epic_identifier = proposal.epic_identifier
    else:
        epic = tracker.create_issue(
            proposal.epic_title,
            issue_type="epic",
            description=epic_description,
            priority=source.priority,
            initial_status=PROPOSED,
        )
        epic_identifier = epic.identifier
        proposal.epic_identifier = epic_identifier
        created_epic = True

    child_ids: list[str] = []
    created_children = 0
    updated_children = 0
    existing_child_ids = list(proposal.child_identifiers)
    for idx, child in enumerate(proposal.children):
        existing_child_id = existing_child_ids[idx] if idx < len(existing_child_ids) else None
        description = _child_description_with_fingerprint(proposal, child)
        if existing_child_id and _issue_exists(tracker, existing_child_id):
            tracker.update_issue(
                existing_child_id,
                title=child.title,
                description=description,
            )
            child_identifier = existing_child_id
            updated_children += 1
        else:
            created = tracker.create_issue(
                child.title,
                issue_type=child.issue_type,
                description=description,
                priority=child.priority if child.priority is not None else source.priority,
                initial_status=PROPOSED,
                parent=epic_identifier,
            )
            child_identifier = created.identifier
            created_children += 1
        try:
            tracker.add_parent_child(child_identifier, epic_identifier)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "epic_proposal: failed to link %s under %s: %s",
                child_identifier,
                epic_identifier,
                exc,
            )
        child_ids.append(child_identifier)

    proposal.child_identifiers = child_ids
    proposal.status = DecompositionStatus.ACCEPTED.value
    proposal.applied_fingerprint = proposal.fingerprint
    save_epic_proposal(tracker, source.identifier, proposal)

    readiness.decomposition_status = DecompositionStatus.ACCEPTED
    readiness.proposal_fingerprint = proposal.fingerprint
    _save_readiness(tracker, source.identifier, readiness)

    try:
        tracker.update_issue(source.identifier, status=DECOMPOSED)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "epic_proposal: failed to mark source %s decomposed: %s",
            source.identifier,
            exc,
        )

    try:
        tracker.add_comment(
            source.identifier,
            (
                f"Applied accepted decomposition proposal `{proposal.fingerprint}`: "
                f"{epic_identifier} with {len(child_ids)} child task(s)."
            ),
            author=author,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "epic_proposal: failed to post application comment on %s: %s",
            source.identifier,
            exc,
        )

    return EpicProposalApplyResult(
        proposal=proposal,
        epic_identifier=epic_identifier,
        child_identifiers=child_ids,
        created_epic=created_epic,
        created_child_count=created_children,
        updated_child_count=updated_children,
    )


def process_epic_proposal_issue(
    tracker: Any,
    issue: Issue,
    *,
    requestor: str | None = None,
    author: str = "oompah",
    auto_promote: bool = True,
) -> EpicProposalEnsureResult | EpicProposalApplyResult | IntakeValidationProcessResult | None:
    """Run intake validation and decomposition handling for one Proposed issue."""
    validation = validate_issue(
        title=issue.title,
        description=issue.description,
        issue_type=issue.issue_type,
        labels=issue.labels,
    )
    ensured = ensure_epic_proposal(
        tracker,
        issue,
        validation_result=validation,
        requestor=requestor,
        author=author,
    )
    if ensured is None:
        requested_actor = (
            requestor
            or getattr(issue, "requestor_login", None)
            or getattr(issue, "author", None)
            or ""
        )
        comment_posted = post_intake_comment_if_needed(
            tracker,
            issue.identifier,
            validation,
            requested_actor,
            issue_updated_at=getattr(issue, "updated_at", None),
            author=author,
            post_comment=False,
        )
        promoted = False
        if validation.ready and auto_promote:
            promotion = promote_proposed_issue_to_backlog(
                tracker,
                issue.identifier,
                current_status=issue.state,
                author=author,
                post_audit_comment=False,
            )
            promoted = promotion.promoted
        return IntakeValidationProcessResult(
            validation=validation,
            comment_posted=comment_posted,
            promoted=promoted,
        )

    readiness = _load_readiness(tracker, issue.identifier)
    if readiness.decomposition_status == DecompositionStatus.ACCEPTED:
        return apply_epic_proposal(tracker, issue, require_accepted=True, author=author)
    return ensured
