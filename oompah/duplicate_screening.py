"""Revision-aware state for model-backed duplicate screening.

The inexpensive similarity pass in :mod:`oompah.orchestrator` is deliberately
heuristic.  This module records the stronger, model-backed qualification that
must complete before an ordinary Open task is dispatched for implementation.

Records live in tracker metadata so they survive service restarts and work
with every tracker adapter.  A pass is valid only for the exact normalized
task fingerprint and detector version that produced it.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable

from oompah.models import Issue
from oompah.statuses import OPEN, canonicalize_status

METADATA_KEY = "oompah.duplicate_screening"
SCHEMA_VERSION = 1
DETECTOR_VERSION = "duplicate-detector-v1"
DEFAULT_CLAIM_TTL_SECONDS = 30 * 60

_SPACE_RE = re.compile(r"\s+")
_TRANSIENT_LABEL_PREFIXES = (
    "focus-complete:",
    "needs:",
    "oompah:",
    "epic:",
    "duplicate-preflight:",
)
_TRANSIENT_LABELS = {
    "asking_question",
    "ci-fix",
    "decomposed",
    "duplicate-candidate",
    "human-only",
    "merge-conflict",
}


class ScreeningState(str, Enum):
    """Operator-visible duplicate-screening qualification state."""

    UNCHECKED = "unchecked"
    RUNNING = "running"
    CHECKED = "checked"
    STALE = "stale"


class ScreeningVerdict(str, Enum):
    """Validated outcome of a model-backed duplicate-screening run."""

    NO_DUPLICATE = "no_duplicate"
    DUPLICATE_CANDIDATE = "duplicate_candidate"
    INCONCLUSIVE = "inconclusive"


def _normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return _SPACE_RE.sub(" ", text).strip().casefold()


def _relevant_labels(labels: Iterable[str]) -> list[str]:
    normalized: set[str] = set()
    for raw in labels:
        label = _normalize_text(raw)
        if not label:
            continue
        if label in _TRANSIENT_LABELS:
            continue
        if any(label.startswith(prefix) for prefix in _TRANSIENT_LABEL_PREFIXES):
            continue
        normalized.add(label)
    return sorted(normalized)


def compute_task_fingerprint(issue: Issue) -> str:
    """Return a stable SHA-256 fingerprint of duplicate-relevant task input.

    Tracker state, priority, timestamps, comments, and Oompah-owned transient
    labels are intentionally excluded.  Writing screening metadata or agent
    telemetry therefore cannot make its own result stale.
    """

    dependencies = sorted(
        {
            _normalize_text(blocker.identifier or blocker.id)
            for blocker in (issue.blocked_by or [])
            if _normalize_text(blocker.identifier or blocker.id)
        }
    )
    payload = {
        "title": _normalize_text(issue.title),
        "description": _normalize_text(issue.description),
        "project_id": _normalize_text(issue.project_id),
        "issue_type": _normalize_text(issue.issue_type),
        "parent_id": _normalize_text(issue.parent_id),
        "dependencies": dependencies,
        "labels": _relevant_labels(issue.labels or []),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class DuplicateScreeningRecord:
    """JSON-compatible persisted record for one task revision."""

    task_fingerprint: str
    detector_version: str
    verdict: ScreeningVerdict = ScreeningVerdict.INCONCLUSIVE
    checked_at: datetime | None = None
    matched_identifiers: tuple[str, ...] = ()
    evidence: str = ""
    claim_id: str | None = None
    claim_owner: str | None = None
    claimed_at: datetime | None = None
    claim_expires_at: datetime | None = None
    retry_count: int = 0
    retry_after: datetime | None = None
    schema_version: int = SCHEMA_VERSION

    @property
    def is_running(self) -> bool:
        return bool(self.claim_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_fingerprint": self.task_fingerprint,
            "detector_version": self.detector_version,
            "verdict": self.verdict.value,
            "checked_at": _iso(self.checked_at),
            "matched_identifiers": list(self.matched_identifiers),
            "evidence": self.evidence,
            "claim_id": self.claim_id,
            "claim_owner": self.claim_owner,
            "claimed_at": _iso(self.claimed_at),
            "claim_expires_at": _iso(self.claim_expires_at),
            "retry_count": max(int(self.retry_count), 0),
            "retry_after": _iso(self.retry_after),
        }

    @classmethod
    def from_raw(cls, raw: object) -> DuplicateScreeningRecord | None:
        """Parse metadata conservatively; malformed/future records fail closed."""

        if not isinstance(raw, dict):
            return None
        try:
            schema_version = int(raw.get("schema_version", 0))
        except (TypeError, ValueError):
            return None
        if schema_version != SCHEMA_VERSION:
            return None
        fingerprint = str(raw.get("task_fingerprint") or "").strip()
        detector_version = str(raw.get("detector_version") or "").strip()
        if not fingerprint or not detector_version:
            return None
        try:
            verdict = ScreeningVerdict(
                str(raw.get("verdict") or ScreeningVerdict.INCONCLUSIVE.value)
            )
        except ValueError:
            return None
        matches_raw = raw.get("matched_identifiers") or []
        if not isinstance(matches_raw, (list, tuple)):
            return None
        try:
            retry_count = max(int(raw.get("retry_count", 0) or 0), 0)
        except (TypeError, ValueError):
            retry_count = 0
        return cls(
            schema_version=schema_version,
            task_fingerprint=fingerprint,
            detector_version=detector_version,
            verdict=verdict,
            checked_at=_parse_datetime(raw.get("checked_at")),
            matched_identifiers=tuple(
                str(value).strip()
                for value in matches_raw
                if str(value).strip()
            ),
            evidence=str(raw.get("evidence") or "").strip(),
            claim_id=str(raw.get("claim_id") or "").strip() or None,
            claim_owner=str(raw.get("claim_owner") or "").strip() or None,
            claimed_at=_parse_datetime(raw.get("claimed_at")),
            claim_expires_at=_parse_datetime(raw.get("claim_expires_at")),
            retry_count=retry_count,
            retry_after=_parse_datetime(raw.get("retry_after")),
        )


@dataclass(frozen=True)
class ScreeningAssessment:
    """Current qualification state derived from a task and stored record."""

    state: ScreeningState
    reason: str
    record: DuplicateScreeningRecord | None = None

    @property
    def implementation_eligible(self) -> bool:
        return (
            self.state == ScreeningState.CHECKED
            and self.record is not None
            and self.record.verdict == ScreeningVerdict.NO_DUPLICATE
        )

    def to_public_dict(self) -> dict[str, Any]:
        record = self.record
        return {
            "state": self.state.value,
            "reason": self.reason,
            "checked_at": _iso(record.checked_at) if record else None,
            "detector_version": record.detector_version if record else None,
            "verdict": record.verdict.value if record else None,
            "matched_identifiers": list(record.matched_identifiers) if record else [],
            "claim_started_at": _iso(record.claimed_at) if record else None,
            "claim_expires_at": _iso(record.claim_expires_at) if record else None,
        }


def raw_record_for_issue(issue: Issue) -> object:
    return getattr(issue, "duplicate_screening", None)


def set_issue_record(
    issue: Issue, record: DuplicateScreeningRecord | dict[str, Any] | None
) -> None:
    if isinstance(record, DuplicateScreeningRecord):
        issue.duplicate_screening = record.to_dict()
    else:
        issue.duplicate_screening = record


def assess_screening(
    issue: Issue,
    *,
    detector_version: str = DETECTOR_VERSION,
    now: datetime | None = None,
) -> ScreeningAssessment:
    """Classify the current screening evidence for *issue*."""

    now = now or datetime.now(timezone.utc)
    raw = raw_record_for_issue(issue)
    record = DuplicateScreeningRecord.from_raw(raw)
    if record is None:
        legacy = any(
            str(label).strip().casefold() == "focus-complete:duplicate_detector"
            for label in (issue.labels or [])
        )
        if legacy:
            return ScreeningAssessment(
                ScreeningState.STALE,
                "legacy duplicate-screening label has no revision fingerprint",
            )
        if raw not in (None, {}):
            return ScreeningAssessment(
                ScreeningState.STALE,
                "duplicate-screening metadata is malformed or from an unsupported version",
            )
        return ScreeningAssessment(
            ScreeningState.UNCHECKED,
            "no model-backed duplicate-screening result",
        )

    fingerprint = compute_task_fingerprint(issue)
    if record.task_fingerprint != fingerprint:
        return ScreeningAssessment(
            ScreeningState.STALE,
            "task content changed after duplicate screening",
            record,
        )
    if record.detector_version != detector_version:
        return ScreeningAssessment(
            ScreeningState.STALE,
            "duplicate detector version changed",
            record,
        )
    if record.is_running:
        if record.claim_expires_at is None or record.claim_expires_at <= now:
            return ScreeningAssessment(
                ScreeningState.STALE,
                "duplicate-screening claim expired",
                record,
            )
        return ScreeningAssessment(
            ScreeningState.RUNNING,
            "model-backed duplicate screening is running",
            record,
        )
    if record.retry_after is not None and record.retry_after > now:
        return ScreeningAssessment(
            ScreeningState.STALE,
            "duplicate-screening retry is in backoff",
            record,
        )
    if record.checked_at is not None and record.verdict in {
        ScreeningVerdict.NO_DUPLICATE,
        ScreeningVerdict.DUPLICATE_CANDIDATE,
    }:
        return ScreeningAssessment(
            ScreeningState.CHECKED,
            "model-backed duplicate screening completed",
            record,
        )
    return ScreeningAssessment(
        ScreeningState.UNCHECKED,
        "no conclusive model-backed duplicate-screening result",
        record,
    )


def eligible_for_model_screening(issue: Issue) -> bool:
    """Return whether this task participates in Open-task preflight."""

    return (
        canonicalize_status(issue.state) == OPEN
        and (issue.issue_type or "task").strip().casefold() != "epic"
    )


def load_record(tracker: Any, issue: Issue) -> DuplicateScreeningRecord | None:
    """Load a record through the generic tracker metadata API."""

    metadata = tracker.get_metadata(issue.identifier) or {}
    raw = metadata.get(METADATA_KEY)
    set_issue_record(issue, raw if isinstance(raw, dict) else raw)
    return DuplicateScreeningRecord.from_raw(raw)


def save_record(
    tracker: Any,
    issue: Issue,
    record: DuplicateScreeningRecord,
) -> None:
    """Persist *record* without overwriting unrelated tracker metadata."""

    payload = record.to_dict()
    tracker.set_metadata_field(issue.identifier, METADATA_KEY, payload)
    set_issue_record(issue, payload)


def new_claim_record(
    issue: Issue,
    *,
    owner: str,
    detector_version: str = DETECTOR_VERSION,
    now: datetime | None = None,
    ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
    retry_count: int = 0,
) -> DuplicateScreeningRecord:
    """Build a running record for a newly admitted preflight."""

    now = now or datetime.now(timezone.utc)
    ttl = max(int(ttl_seconds), 1)
    return DuplicateScreeningRecord(
        task_fingerprint=compute_task_fingerprint(issue),
        detector_version=detector_version,
        claim_id=str(uuid.uuid4()),
        claim_owner=owner,
        claimed_at=now,
        claim_expires_at=now + timedelta(seconds=ttl),
        retry_count=max(int(retry_count), 0),
    )


def complete_claim_record(
    record: DuplicateScreeningRecord,
    *,
    verdict: ScreeningVerdict,
    matched_identifiers: Iterable[str] = (),
    evidence: str = "",
    now: datetime | None = None,
) -> DuplicateScreeningRecord:
    """Return a conclusive record with claim fields cleared."""

    now = now or datetime.now(timezone.utc)
    return DuplicateScreeningRecord(
        task_fingerprint=record.task_fingerprint,
        detector_version=record.detector_version,
        verdict=verdict,
        checked_at=now,
        matched_identifiers=tuple(
            dict.fromkeys(
                str(identifier).strip()
                for identifier in matched_identifiers
                if str(identifier).strip()
            )
        ),
        evidence=str(evidence or "").strip(),
        retry_count=record.retry_count,
    )


def inconclusive_record(
    record: DuplicateScreeningRecord,
    *,
    retry_count: int,
    retry_after: datetime,
    evidence: str = "",
) -> DuplicateScreeningRecord:
    """Clear a failed claim and retain bounded retry/backoff state."""

    return DuplicateScreeningRecord(
        task_fingerprint=record.task_fingerprint,
        detector_version=record.detector_version,
        verdict=ScreeningVerdict.INCONCLUSIVE,
        evidence=str(evidence or "").strip(),
        retry_count=max(int(retry_count), 0),
        retry_after=retry_after,
    )
