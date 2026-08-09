"""Fail-closed projection of project-owner terminal delivery provenance."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from oompah.integration import ACCEPTED_SUBMISSION_STATES
from oompah.label_auth import is_authorized_status_actor
from oompah.models import Issue
from oompah.statuses import DONE, canonicalize_status
from oompah.terminal_audit import (
    AuditRevisionBinding,
    OverrideRecord,
    TargetState,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadata
from oompah.transition_gate import is_project_owner

_OVERRIDE_RECORDS_KEY = "oompah.terminal_override_records"
_REVISION_RE = re.compile(r"^[0-9a-f]{40,64}$")


@dataclass(frozen=True, slots=True)
class OwnerDeliveryProvenance:
    """One exact owner-authorized delivery assertion safe for workflow facts."""

    project_id: str
    task_id: str
    source: str
    target: str
    revision: str
    override_id: str
    evidence_fingerprint: str
    selected_ref: str
    authorized_by: str
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": 1,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "source": self.source,
            "target": self.target,
            "revision": self.revision,
            "override_id": self.override_id,
            "evidence_fingerprint": self.evidence_fingerprint,
            "selected_ref": self.selected_ref,
            "authorized_by": self.authorized_by,
        }
        if self.created_at is not None:
            value["created_at"] = self.created_at
        return value


def _field(record: object, name: str) -> object:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


def _accepted_identity(
    issue: Issue,
    *,
    project_id: str,
    integration_queue: Any | None,
) -> tuple[str, str, str] | None:
    """Return the same exact integrated source/target generation used by delivery."""

    integration = getattr(issue, "integration", None)
    integration_state = str(_field(integration, "state") or "").strip().lower()
    if integration_state in ACCEPTED_SUBMISSION_STATES:
        source = str(_field(integration, "task_branch") or "").strip()
        revision = (
            str(
                _field(integration, "integrated_sha")
                or _field(integration, "head_sha")
                or ""
            )
            .strip()
            .lower()
        )
        target = str(_field(integration, "base_branch") or "").strip()
        if source and target and _REVISION_RE.fullmatch(revision):
            return source, target, revision

    get_row = getattr(integration_queue, "get", None)
    if not callable(get_row):
        return None
    try:
        row = get_row(project_id, issue.identifier)
    except Exception:  # noqa: BLE001 - durable evidence boundary
        return None
    if row is None or str(_field(row, "state") or "").strip().lower() != "integrated":
        return None
    if str(_field(row, "project_id") or "").strip() != project_id:
        return None
    if str(_field(row, "task_id") or "").strip() != issue.identifier:
        return None
    parent_id = str(getattr(issue, "parent_id", None) or "").strip()
    row_parent = str(_field(row, "epic_id") or "").strip()
    if parent_id and row_parent != parent_id:
        return None
    source = str(_field(row, "task_branch") or "").strip()
    revision = (
        str(_field(row, "integrated_sha") or _field(row, "head_sha") or "")
        .strip()
        .lower()
    )
    target = str(_field(row, "base_branch") or "").strip()
    if source and target and _REVISION_RE.fullmatch(revision):
        return source, target, revision
    return None


def _bound_override(
    raw: Mapping[str, Any],
    *,
    document: TerminalAuditMetadata,
) -> tuple[OverrideRecord, AuditRevisionBinding] | None:
    try:
        record = OverrideRecord.from_dict(raw)
    except (TypeError, ValueError):
        return None
    if record.selected_ref is not None and record.selected_sha is not None:
        return record, AuditRevisionBinding(record.selected_ref, record.selected_sha)
    matching_audit = next(
        (
            audit
            for audit in reversed(document.pending_chain)
            if audit.project_id == record.project_id
            and audit.task_id == record.task_id
            and audit.target_state is record.target_state
            and audit.evidence_fingerprint == record.evidence_fingerprint
            and audit.selected_ref is not None
            and audit.selected_sha is not None
        ),
        None,
    )
    if matching_audit is None:
        return None
    return record, AuditRevisionBinding(
        matching_audit.selected_ref or "",
        matching_audit.selected_sha or "",
    )


def collect_owner_delivery_provenance(
    issue: Issue,
    document: TerminalAuditMetadata,
    *,
    project_id: str,
    project: Any,
    integration_queue: Any | None = None,
) -> OwnerDeliveryProvenance | None:
    """Return current exact owner delivery evidence, never prose/status inference.

    The newest applied Done override is authoritative for this projection.  If
    that row is malformed, unbound, unauthorized, or names an older accepted
    revision, older history cannot be resurrected to bless the current task.
    """

    if canonicalize_status(issue.state) != DONE:
        return None
    raw_records = document.unknown_fields.get(_OVERRIDE_RECORDS_KEY, [])
    if not isinstance(raw_records, list):
        return None
    current_raw = next(
        (
            raw
            for raw in reversed(raw_records)
            if isinstance(raw, Mapping)
            and raw.get("project_id") == project_id
            and raw.get("task_id") == issue.identifier
        ),
        None,
    )
    if (
        current_raw is None
        or current_raw.get("target_state") != TargetState.DONE.value
        or current_raw.get("applied", True) is False
        or current_raw.get("lifecycle_reconciled", False)
    ):
        return None
    bound = _bound_override(current_raw, document=document)
    if bound is None:
        return None
    record, binding = bound
    try:
        current_fingerprint = compute_issue_evidence_fingerprint(issue, project_id)
    except (TypeError, ValueError):
        return None
    if current_fingerprint != record.evidence_fingerprint:
        return None
    actor = record.authorized_by.identity
    if not (
        is_authorized_status_actor(actor, project) and is_project_owner(actor, project)
    ):
        return None
    identity = _accepted_identity(
        issue,
        project_id=project_id,
        integration_queue=integration_queue,
    )
    if identity is None:
        return None
    source, target, revision = identity
    if binding.selected_sha != revision:
        return None
    return OwnerDeliveryProvenance(
        project_id=project_id,
        task_id=issue.identifier,
        source=source,
        target=target,
        revision=revision,
        override_id=record.override_id,
        evidence_fingerprint=record.evidence_fingerprint.digest,
        selected_ref=binding.selected_ref,
        authorized_by=actor,
        created_at=record.created_at,
    )


__all__ = [
    "OwnerDeliveryProvenance",
    "collect_owner_delivery_provenance",
]
