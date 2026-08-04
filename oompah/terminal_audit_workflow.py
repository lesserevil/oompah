"""Durable ownership and phase transitions for terminal audits.

The terminal-audit metadata remains the authoritative evidence and attempt
history.  This module adds the missing execution ledger: one leased workflow
job owns one exact audit/evidence identity, while the coordinator remains the
only component allowed to apply a verdict to tracker state.

Provider prose, comments, prompts, and command output are deliberately not
accepted as checkpoint data.  Durable checkpoints contain only bounded,
machine-readable identities and outcome fields, which keeps a noisy auditor
from starving or corrupting finalization.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from oompah.terminal_audit import RequestState, TerminalAuditRecord
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJob,
    WorkflowJobLeaseLost,
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
)


TERMINAL_AUDIT_JOB_ACTION = "terminal_audit"
TERMINAL_AUDIT_WORKFLOW_VERSION = 1
_MAX_CHECKPOINT_TEXT = 512
_MAX_CHECKPOINT_BYTES = 4096
_SENSITIVE_RE = re.compile(
    r"(?:bearer\s+\S+|(?:api[_-]?key|authorization|password|secret|token)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)


class AuditWorkflowPhase(str, Enum):
    """Execution phase visible to workflow decisions and operators."""

    QUEUED = "queued"
    RUNNING = "running"
    FINALIZING = "finalizing"
    RETRY_WAIT = "retry_wait"
    ACTION_REQUIRED = "action_required"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class AuditWorkflowDecision:
    """A redacted durable disposition for one terminal audit."""

    project_id: str
    task_id: str
    audit_id: str
    evidence_fingerprint: str
    phase: AuditWorkflowPhase
    attempt_id: str | None = None
    retry_at: float | None = None
    action_code: str | None = None
    informational: bool = False

    def __post_init__(self) -> None:
        for name in ("project_id", "task_id", "audit_id", "evidence_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if len(self.evidence_fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in self.evidence_fingerprint
        ):
            raise ValueError("evidence_fingerprint must be a lowercase SHA-256 digest")
        object.__setattr__(self, "phase", AuditWorkflowPhase(self.phase))
        if self.attempt_id is not None and not str(self.attempt_id).strip():
            raise ValueError("attempt_id must be non-empty when present")
        if self.retry_at is not None and self.retry_at < 0:
            raise ValueError("retry_at must be non-negative")
        if self.action_code is not None and not str(self.action_code).strip():
            raise ValueError("action_code must be non-empty when present")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": TERMINAL_AUDIT_WORKFLOW_VERSION,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "audit_id": self.audit_id,
            "evidence_fingerprint": self.evidence_fingerprint,
            "phase": self.phase.value,
            "attempt_id": self.attempt_id,
            "retry_at": self.retry_at,
            "action_code": self.action_code,
            "informational": self.informational,
        }


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _required_text(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _safe_text(value: object, name: str) -> str:
    text = _SENSITIVE_RE.sub("[REDACTED]", _required_text(value, name))
    return text[:_MAX_CHECKPOINT_TEXT]


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


class TerminalAuditWorkflow:
    """Bridge terminal-audit records to leased durable workflow jobs."""

    def __init__(
        self,
        store: WorkflowJobStore,
        *,
        lease_owner: str = "terminal-audit",
        lease_seconds: float = 3600,
        max_attempts: int = 3,
        retry_delay_seconds: float = 10,
        clock: Any = _now,
    ) -> None:
        if not isinstance(store, WorkflowJobStore):
            raise TypeError("store must be a WorkflowJobStore")
        self.store = store
        self.lease_owner = _required_text(lease_owner, "lease_owner")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if isinstance(max_attempts, bool) or max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        self.lease_seconds = float(lease_seconds)
        self.max_attempts = int(max_attempts)
        self.retry_delay_seconds = float(retry_delay_seconds)
        self.clock = clock

    @staticmethod
    def generation(record: TerminalAuditRecord) -> str:
        """Return a stable generation fenced to exact audit evidence."""

        payload = {
            "version": TERMINAL_AUDIT_WORKFLOW_VERSION,
            "project_id": record.project_id,
            "task_id": record.task_id,
            "audit_id": record.audit_id,
            "target_state": record.target_state.value,
            "evidence_fingerprint": record.evidence_fingerprint.digest,
        }
        return "audit:" + hashlib.sha256(_canonical(payload).encode()).hexdigest()

    @classmethod
    def idempotency_key(cls, record: TerminalAuditRecord) -> str:
        return "terminal-audit:" + ":".join(
            (
                record.project_id,
                record.task_id,
                record.audit_id,
                record.evidence_fingerprint.digest,
            )
        )

    @classmethod
    def spec(cls, record: TerminalAuditRecord, *, max_attempts: int = 3) -> WorkflowJobSpec:
        """Build immutable work for one exact audit request."""

        if record.request_state not in (RequestState.PENDING, RequestState.IN_PROGRESS):
            raise ValueError("only pending or in-progress audits may be enqueued")
        return WorkflowJobSpec(
            project_id=record.project_id,
            task_id=record.task_id,
            generation=cls.generation(record),
            action=TERMINAL_AUDIT_JOB_ACTION,
            idempotency_key=cls.idempotency_key(record),
            phase=AuditWorkflowPhase.QUEUED.value,
            expected_evidence_revision=record.evidence_fingerprint.digest,
            max_attempts=max_attempts,
        )

    def _matching_jobs(self, record: TerminalAuditRecord) -> tuple[WorkflowJob, ...]:
        return tuple(
            job
            for job in self.store.list_jobs(
                project_id=record.project_id,
                task_id=record.task_id,
                limit=1000,
            )
            if job.action == TERMINAL_AUDIT_JOB_ACTION
            and job.generation == self.generation(record)
            and job.idempotency_key == self.idempotency_key(record)
        )

    def ensure(self, record: TerminalAuditRecord) -> WorkflowJob:
        """Persist or replay the exact audit job without reviving terminal work."""

        matches = self._matching_jobs(record)
        if matches:
            return matches[0]
        return self.store.enqueue(self.spec(record, max_attempts=self.max_attempts))

    def _decision_from_job(
        self, record: TerminalAuditRecord, job: WorkflowJob
    ) -> AuditWorkflowDecision:
        if job.state in {
            WorkflowJobState.COMPLETED,
            WorkflowJobState.SUPERSEDED,
            WorkflowJobState.CANCELLED,
        }:
            phase = AuditWorkflowPhase.COMPLETED
        elif job.state is WorkflowJobState.EXHAUSTED:
            phase = AuditWorkflowPhase.ACTION_REQUIRED
        elif job.state is WorkflowJobState.RETRY_WAIT:
            phase = AuditWorkflowPhase.RETRY_WAIT
        elif job.state is WorkflowJobState.RUNNING:
            try:
                phase = AuditWorkflowPhase(job.phase)
            except ValueError:
                phase = AuditWorkflowPhase.RUNNING
        else:
            phase = AuditWorkflowPhase.QUEUED
        checkpoint = job.checkpoint or {}
        attempt_id = checkpoint.get("attempt_id")
        action_code = checkpoint.get("action_code")
        return AuditWorkflowDecision(
            project_id=record.project_id,
            task_id=record.task_id,
            audit_id=record.audit_id,
            evidence_fingerprint=record.evidence_fingerprint.digest,
            phase=phase,
            attempt_id=str(attempt_id) if attempt_id else None,
            retry_at=job.retry_at,
            action_code=str(action_code) if action_code else None,
            informational=phase
            in {
                AuditWorkflowPhase.RUNNING,
                AuditWorkflowPhase.FINALIZING,
                AuditWorkflowPhase.RETRY_WAIT,
            },
        )

    def decision(self, record: TerminalAuditRecord) -> AuditWorkflowDecision:
        """Read the durable audit disposition, creating queued ownership if needed."""

        return self._decision_from_job(record, self.ensure(record))

    def _checkpoint_payload(
        self,
        record: TerminalAuditRecord,
        *,
        attempt_id: str | None = None,
        candidate: Any | None = None,
        action_code: str | None = None,
        verdict: str | None = None,
        failure_classification: str | None = None,
        result_idempotency: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": TERMINAL_AUDIT_WORKFLOW_VERSION,
            "audit_id": record.audit_id,
            "target_state": record.target_state.value,
            "evidence_fingerprint": record.evidence_fingerprint.digest,
        }
        if attempt_id:
            payload["attempt_id"] = _safe_text(attempt_id, "attempt_id")
        if candidate is not None:
            payload["candidate"] = {
                "provider_id": _safe_text(getattr(candidate, "provider_id", ""), "provider_id"),
                "model": _safe_text(getattr(candidate, "model", ""), "model"),
            }
        for key, value in (
            ("action_code", action_code),
            ("verdict", verdict),
            ("failure_classification", failure_classification),
            ("result_idempotency", result_idempotency),
        ):
            if value is not None:
                payload[key] = _safe_text(value, key)
        encoded = _canonical(payload).encode()
        if len(encoded) > _MAX_CHECKPOINT_BYTES:
            raise ValueError("terminal-audit checkpoint exceeds the durable size bound")
        return payload

    def start(
        self,
        record: TerminalAuditRecord,
        *,
        attempt_id: str,
        candidate: Any,
    ) -> WorkflowJob | None:
        """Claim queued ownership and checkpoint the selected candidate."""

        existing = self.ensure(record)
        if existing.state is WorkflowJobState.RUNNING:
            return existing
        claimed = self.store.claim_next(
            lease_owner=self.lease_owner,
            lease_seconds=self.lease_seconds,
            project_id=record.project_id,
            task_id=record.task_id,
            generation=self.generation(record),
            actions=(TERMINAL_AUDIT_JOB_ACTION,),
            now=self.clock(),
        )
        if claimed is None:
            return None
        return self.store.checkpoint(
            claimed.job_id,
            claimed.lease_token,
            phase=AuditWorkflowPhase.RUNNING.value,
            checkpoint=self._checkpoint_payload(
                record, attempt_id=attempt_id, candidate=candidate
            ),
            now=self.clock(),
        )

    def mark_finalizing(
        self,
        job: WorkflowJob,
        record: TerminalAuditRecord,
        *,
        verdict: str,
        failure_classification: str | None = None,
        result_idempotency: str | None = None,
    ) -> WorkflowJob:
        """Reserve the result boundary before tracker comments or status writes."""

        if job.lease_token is None:
            raise WorkflowJobLeaseLost(f"terminal-audit job has no lease: {job.job_id}")
        return self.store.checkpoint(
            job.job_id,
            job.lease_token,
            phase=AuditWorkflowPhase.FINALIZING.value,
            checkpoint=self._checkpoint_payload(
                record,
                attempt_id=(job.checkpoint or {}).get("attempt_id"),
                verdict=verdict,
                failure_classification=failure_classification,
                result_idempotency=result_idempotency,
            ),
            now=self.clock(),
        )

    def complete(
        self,
        job: WorkflowJob,
        *,
        result: Mapping[str, Any] | None = None,
    ) -> WorkflowJob:
        if job.lease_token is None:
            raise WorkflowJobLeaseLost(f"terminal-audit job has no lease: {job.job_id}")
        return self.store.complete(job.job_id, job.lease_token, result_transition=result, now=self.clock())

    def retry(
        self,
        job: WorkflowJob,
        *,
        category: WorkflowFailureCategory | str = WorkflowFailureCategory.TRANSIENT,
        reason: str = "audit transport retry scheduled",
    ) -> WorkflowJob:
        if job.lease_token is None:
            raise WorkflowJobLeaseLost(f"terminal-audit job has no lease: {job.job_id}")
        return self.store.fail(
            job.job_id,
            job.lease_token,
            category=category,
            error=_safe_text(reason, "reason"),
            retryable=True,
            retry_delay_seconds=self.retry_delay_seconds,
            phase=AuditWorkflowPhase.RETRY_WAIT.value,
            now=self.clock(),
        )

    def action_required(
        self,
        job: WorkflowJob,
        *,
        record: TerminalAuditRecord | None = None,
        action_code: str,
        reason: str,
    ) -> WorkflowJob:
        if job.lease_token is None:
            raise WorkflowJobLeaseLost(f"terminal-audit job has no lease: {job.job_id}")
        # Persist the bounded operator action before closing the lease.  The
        # human-readable reason remains in the job error field, never in the
        # structured checkpoint consumed by workflow decisions.
        record_data = job.checkpoint or {}
        if record is not None:
            record_data = {
                "audit_id": record.audit_id,
                "target_state": record.target_state.value,
                "evidence_fingerprint": record.evidence_fingerprint.digest,
            }
        checkpoint = {
            "version": TERMINAL_AUDIT_WORKFLOW_VERSION,
            "audit_id": _safe_text(record_data.get("audit_id"), "audit_id"),
            "target_state": _safe_text(record_data.get("target_state"), "target_state"),
            "evidence_fingerprint": _safe_text(
                record_data.get("evidence_fingerprint"), "evidence_fingerprint"
            ),
            "action_code": _safe_text(action_code, "action_code"),
        }
        if len(_canonical(checkpoint).encode()) > _MAX_CHECKPOINT_BYTES:
            raise ValueError("terminal-audit action checkpoint exceeds the durable size bound")
        checkpointed = self.store.checkpoint(
            job.job_id,
            job.lease_token,
            phase=AuditWorkflowPhase.ACTION_REQUIRED.value,
            checkpoint=checkpoint,
            now=self.clock(),
        )
        return self.store.fail(
            checkpointed.job_id,
            checkpointed.lease_token,
            category=WorkflowFailureCategory.POLICY,
            error=_safe_text(reason, "reason"),
            retryable=False,
            phase=AuditWorkflowPhase.ACTION_REQUIRED.value,
            now=self.clock(),
        )

    def require_action(
        self,
        record: TerminalAuditRecord,
        *,
        action_code: str,
        reason: str,
    ) -> WorkflowJob:
        """Close queued audit ownership as an explicit operator action."""

        job = self.ensure(record)
        if job.state in {
            WorkflowJobState.COMPLETED,
            WorkflowJobState.EXHAUSTED,
            WorkflowJobState.SUPERSEDED,
            WorkflowJobState.CANCELLED,
        }:
            return job
        if job.state is not WorkflowJobState.RUNNING:
            claimed = self.store.claim_next(
                lease_owner=self.lease_owner,
                lease_seconds=self.lease_seconds,
                project_id=record.project_id,
                task_id=record.task_id,
                generation=self.generation(record),
                actions=(TERMINAL_AUDIT_JOB_ACTION,),
                now=self.clock(),
            )
            if claimed is None:
                return self.ensure(record)
            job = claimed
        return self.action_required(
            job,
            record=record,
            action_code=action_code,
            reason=reason,
        )

    def recover(
        self,
        record: TerminalAuditRecord,
        *,
        active_attempt_ids: set[str] | None = None,
    ) -> AuditWorkflowDecision:
        """Requeue an owned audit after restart when no live attempt remains."""

        job = self.ensure(record)
        if job.state is WorkflowJobState.RUNNING:
            attempt_id = (job.checkpoint or {}).get("attempt_id")
            if active_attempt_ids is None or attempt_id in active_attempt_ids:
                return self._decision_from_job(record, job)
            self.store.recover_abandoned(
                lease_owner=job.lease_owner,
                phase=AuditWorkflowPhase.QUEUED.value,
                now=self.clock(),
                limit=100,
            )
            job = self.store.get(job.job_id)
        return self._decision_from_job(record, job)


DurableTerminalAuditWorkflow = TerminalAuditWorkflow
