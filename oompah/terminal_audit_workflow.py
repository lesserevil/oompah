"""Durable ownership and phase transitions for terminal audits.

The terminal-audit metadata remains the authoritative evidence and attempt
history.  This module adds the missing execution ledger: one leased workflow
job owns one exact project/task/target/evidence generation, while its claimed
checkpoint fences callbacks to one audit and attempt identity.  The
coordinator remains the only component allowed to apply a verdict to tracker
state.

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
    ACTIVE_JOB_STATES,
    WorkflowFailureCategory,
    WorkflowJob,
    WorkflowJobLeaseLost,
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
)


TERMINAL_AUDIT_JOB_ACTION = "terminal_audit"
TERMINAL_AUDIT_WORKFLOW_VERSION = 2
_MAX_CHECKPOINT_TEXT = 512
_MAX_CHECKPOINT_BYTES = 4096
_SENSITIVE_RE = re.compile(
    r"(?:bearer\s+\S+|(?:api[_-]?key|authorization|password|secret|token)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)

AuditAttemptIdentity = tuple[str, str, str, str]


def audit_attempt_identity(
    project_id: object,
    task_id: object,
    audit_id: object,
    attempt_id: object,
) -> AuditAttemptIdentity:
    """Return the complete identity of one live terminal-audit attempt."""

    return (
        _required_text(project_id, "project_id"),
        _required_text(task_id, "task_id"),
        _required_text(audit_id, "audit_id"),
        _required_text(attempt_id, "attempt_id"),
    )


class AuditWorkflowPhase(str, Enum):
    """Execution phase visible to workflow decisions and operators."""

    QUEUED = "queued"
    RUNNING = "running"
    FINALIZING = "finalizing"
    RETRY_WAIT = "retry_wait"
    ACTION_REQUIRED = "action_required"
    COMPLETED = "completed"


class AuditWorkflowIdentityError(RuntimeError):
    """A callback or recovery attempt did not own the exact audit lease."""


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
            character not in "0123456789abcdef"
            for character in self.evidence_fingerprint
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
        """Return the canonical target/evidence generation.

        ``audit_id`` is a callback fence chosen after a generation is
        staged; it is not part of the work itself.  Excluding it here makes
        concurrent webhook, review, and reconciliation requests converge on
        one durable owner for the same project/task/target/evidence tuple.
        """

        payload = {
            "version": TERMINAL_AUDIT_WORKFLOW_VERSION,
            "project_id": record.project_id,
            "task_id": record.task_id,
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
                record.target_state.value,
                record.evidence_fingerprint.digest,
            )
        )

    @staticmethod
    def scheduling_lane(record: TerminalAuditRecord) -> str:
        """Return the target-specific replacement lane for one task."""

        return f"terminal-audit:{record.target_state.value}"

    @classmethod
    def spec(
        cls,
        record: TerminalAuditRecord,
        *,
        max_attempts: int = 3,
        idempotency_key: str | None = None,
    ) -> WorkflowJobSpec:
        """Build immutable work for one exact audit request."""

        if record.request_state not in (RequestState.PENDING, RequestState.IN_PROGRESS):
            raise ValueError("only pending or in-progress audits may be enqueued")
        return WorkflowJobSpec(
            project_id=record.project_id,
            task_id=record.task_id,
            generation=cls.generation(record),
            action=TERMINAL_AUDIT_JOB_ACTION,
            idempotency_key=idempotency_key or cls.idempotency_key(record),
            phase=AuditWorkflowPhase.QUEUED.value,
            scheduling_lane=cls.scheduling_lane(record),
            expected_evidence_revision=record.evidence_fingerprint.digest,
            max_attempts=max_attempts,
        )

    def _matching_jobs(self, record: TerminalAuditRecord) -> tuple[WorkflowJob, ...]:
        """Return every activation of one semantic target/evidence job."""

        return tuple(
            job
            for job in self.store.list_jobs(
                project_id=record.project_id,
                task_id=record.task_id,
                generation=self.generation(record),
                actions=(TERMINAL_AUDIT_JOB_ACTION,),
                scheduling_lanes=(self.scheduling_lane(record),),
                expected_evidence_revisions=(
                    record.evidence_fingerprint.digest,
                ),
                limit=1000,
                newest_first=True,
            )
            if job.action == TERMINAL_AUDIT_JOB_ACTION
            and job.generation == self.generation(record)
            and job.scheduling_lane == self.scheduling_lane(record)
            and job.expected_evidence_revision
            == record.evidence_fingerprint.digest
        )

    def ensure(self, record: TerminalAuditRecord) -> WorkflowJob:
        """Persist or replay one canonical audit generation.

        A new evidence generation atomically replaces only older work for the
        same terminal target.  ``Done`` and ``Merged`` are separate lanes, so
        materializing the latter cannot cancel the former in an ordered audit
        chain.
        """

        semantic_jobs = self._matching_jobs(record)
        active = [job for job in semantic_jobs if job.state in ACTIVE_JOB_STATES]
        reusable = [
            job
            for job in semantic_jobs
            if job.state
            in {WorkflowJobState.COMPLETED, WorkflowJobState.EXHAUSTED}
        ]
        selected = max(active, key=lambda job: job.enqueue_sequence) if active else None
        if selected is None and reusable:
            # A later authorized rearm may have produced a newer terminal
            # decision for the same immutable evidence.  The latest durable
            # activation is authoritative; an older PASS must not mask a
            # later exhaustion (or vice versa).
            selected = max(reusable, key=lambda job: job.enqueue_sequence)
        needs_fresh_activation = selected is None and bool(semantic_jobs)
        idempotency_key = (
            selected.idempotency_key
            if selected is not None
            else (
                f"{self.idempotency_key(record)}:activation:"
                f"{record.source_generation}"
                if needs_fresh_activation
                else self.idempotency_key(record)
            )
        )
        write = self.store.enqueue_replacing_lane(
            self.spec(
                record,
                max_attempts=self.max_attempts,
                idempotency_key=idempotency_key,
            ),
            source_generation=record.source_generation,
            require_source_advance=needs_fresh_activation,
            reason="superseded by a newer terminal-audit evidence generation",
            now=self.clock(),
        )
        if not write.accepted or write.job is None:
            raise AuditWorkflowIdentityError(
                "terminal-audit source generation is stale"
            )
        return write.job

    @staticmethod
    def _validate_rearm_authorization(
        record: TerminalAuditRecord,
        prior_audit_id: str,
        authorization: Mapping[str, Any],
    ) -> None:
        """Validate the coordinator's bounded, durable owner-rearm proof."""

        if not isinstance(authorization, Mapping):
            raise AuditWorkflowIdentityError(
                "terminal-audit rearm authorization is missing"
            )
        expected: dict[str, object] = {
            "version": 1,
            "audit_id": record.audit_id,
            "superseded_audit_id": prior_audit_id,
            "project_id": record.project_id,
            "task_id": record.task_id,
            "target_state": record.target_state.value,
            "evidence_fingerprint": record.evidence_fingerprint.digest,
            "source_generation": record.source_generation,
        }
        for key, value in expected.items():
            if authorization.get(key) != value:
                raise AuditWorkflowIdentityError(
                    f"terminal-audit rearm authorization {key} does not match"
                )
        actor = authorization.get("actor")
        if not isinstance(actor, Mapping) or not str(actor.get("identity") or "").strip():
            raise AuditWorkflowIdentityError(
                "terminal-audit rearm authorization lacks owner identity"
            )
        if str(authorization.get("mode") or "") not in {
            "evidence_addendum",
            "infrastructure_recovery",
        }:
            raise AuditWorkflowIdentityError(
                "terminal-audit rearm authorization mode is invalid"
            )
        for key in ("reason", "authorized_at"):
            if not str(authorization.get(key) or "").strip():
                raise AuditWorkflowIdentityError(
                    f"terminal-audit rearm authorization lacks {key}"
                )

    def rearm(
        self,
        record: TerminalAuditRecord,
        *,
        authorization: Mapping[str, Any],
    ) -> WorkflowJob:
        """Rearm one semantic job only with coordinator-issued owner proof."""

        terminal_candidates = [
            job
            for job in self._matching_jobs(record)
            if job.state
            in {WorkflowJobState.COMPLETED, WorkflowJobState.EXHAUSTED}
        ]
        if terminal_candidates:
            terminal = max(
                terminal_candidates,
                key=lambda job: job.enqueue_sequence,
            )
            prior_audit_id = str((terminal.checkpoint or {}).get("audit_id") or "")
            if not prior_audit_id:
                raise AuditWorkflowIdentityError(
                    "terminal-audit job is not eligible for owner rearm"
                )
        else:
            prior_audit_id = str(
                authorization.get("superseded_audit_id")
                if isinstance(authorization, Mapping)
                else ""
            ).strip()
            if not prior_audit_id:
                raise AuditWorkflowIdentityError(
                    "terminal-audit rearm authorization is missing prior identity"
                )
        # Validate before ``ensure`` advances the lane or supersedes a
        # different live evidence generation.  A rejected proof must be
        # observationally read-only, including after a workflow-DB rebuild
        # where the prior terminal row is no longer present.
        self._validate_rearm_authorization(
            record,
            prior_audit_id,
            authorization,
        )

        existing = self.ensure(record)
        if existing.state in ACTIVE_JOB_STATES:
            return existing
        checkpoint_audit_id = str(
            (existing.checkpoint or {}).get("audit_id") or ""
        )
        if existing.state not in {
            WorkflowJobState.COMPLETED,
            WorkflowJobState.EXHAUSTED,
        } or not checkpoint_audit_id:
            raise AuditWorkflowIdentityError(
                "terminal-audit job is not eligible for owner rearm"
            )
        return self.store.rearm_terminal_job(
            existing.job_id,
            generation=self.generation(record),
            phase=AuditWorkflowPhase.QUEUED.value,
            reason="coordinator-authorized owner rearm",
            now=self.clock(),
        )

    def retire_resolved(
        self,
        *,
        project_id: str,
        task_id: str,
        records: tuple[TerminalAuditRecord, ...] | list[TerminalAuditRecord],
    ) -> int:
        """Retire non-finalizing jobs already resolved in tracker metadata.

        This reconciles the cross-store crash window where the coordinator
        completed an unsafe metadata-only archive but the process died before
        the workflow row could be cancelled.  Typed FINALIZING jobs remain
        owned by result replay and are never retired here.
        """

        live_by_identity = {
            (
                record.target_state.value,
                record.evidence_fingerprint.digest,
            )
            for record in records
            if record.project_id == project_id
            and record.task_id == task_id
            and record.request_state
            in {
                RequestState.PENDING,
                RequestState.IN_PROGRESS,
            }
        }
        terminal_by_identity = {
            (
                record.target_state.value,
                record.evidence_fingerprint.digest,
            )
            for record in records
            if record.project_id == project_id
            and record.task_id == task_id
            and record.request_state
            in {
                RequestState.COMPLETED,
                RequestState.SUPERSEDED,
                RequestState.CANCELLED,
            }
        } - live_by_identity
        retired = 0
        for job in self.store.list_jobs(
            project_id=project_id,
            task_id=task_id,
            states=tuple(ACTIVE_JOB_STATES),
            actions=(TERMINAL_AUDIT_JOB_ACTION,),
            limit=1000,
        ):
            if (
                job.action != TERMINAL_AUDIT_JOB_ACTION
                or job.phase == AuditWorkflowPhase.FINALIZING.value
            ):
                continue
            target = job.scheduling_lane.removeprefix("terminal-audit:")
            if (
                target,
                str(job.expected_evidence_revision or ""),
            ) not in terminal_by_identity:
                continue
            self.store.cancel(
                job.job_id,
                generation=job.generation,
                reason="tracker metadata already resolved terminal-audit generation",
                now=self.clock(),
            )
            retired += 1
        return retired

    def retire(self, record: TerminalAuditRecord, *, reason: str) -> int:
        """Cancel active work for one exact generation without taking its lease.

        This is the fail-closed boundary for synchronous preflights which
        authoritatively resolve an audit before a provider launch.  Every
        cancellation is fenced by the immutable generation; sibling targets
        and newer evidence remain untouched.
        """

        retired = 0
        for job in self._matching_jobs(record):
            if job.state not in ACTIVE_JOB_STATES:
                continue
            self.store.cancel(
                job.job_id,
                generation=self.generation(record),
                reason=_safe_text(reason, "reason"),
                now=self.clock(),
            )
            retired += 1
        return retired

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
        workflow_job_id: str | None = None,
        job_attempt: int | None = None,
        result_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": TERMINAL_AUDIT_WORKFLOW_VERSION,
            "audit_id": record.audit_id,
            "target_state": record.target_state.value,
            "evidence_fingerprint": record.evidence_fingerprint.digest,
        }
        if attempt_id:
            payload["attempt_id"] = _safe_text(attempt_id, "attempt_id")
        if workflow_job_id:
            payload["workflow_job_id"] = _safe_text(workflow_job_id, "workflow_job_id")
        if job_attempt is not None:
            if isinstance(job_attempt, bool) or int(job_attempt) < 1:
                raise ValueError("job_attempt must be a positive integer")
            payload["job_attempt"] = int(job_attempt)
        if candidate is not None:
            payload["candidate"] = {
                "provider_id": _safe_text(
                    getattr(candidate, "provider_id", ""), "provider_id"
                ),
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
        if result_payload is not None:
            payload["result"] = dict(result_payload)
        encoded = _canonical(payload).encode()
        if len(encoded) > _MAX_CHECKPOINT_BYTES:
            raise ValueError("terminal-audit checkpoint exceeds the durable size bound")
        return payload

    @staticmethod
    def _result_payload(result: Any) -> dict[str, Any]:
        """Reduce one typed result to a bounded, replayable decision.

        Provider output and tool transcripts never enter the workflow DB.
        Only the coordinator inputs needed to replay the exact typed result
        are retained; free text is redacted and bounded.
        """

        attempt_id = _required_text(getattr(result, "attempt_id", None), "attempt_id")
        target = getattr(getattr(result, "target_state", None), "value", None)
        verdict = getattr(getattr(result, "verdict", None), "value", None)
        fingerprint = getattr(
            getattr(result, "evidence_fingerprint", None), "digest", None
        )
        raw_safe_evidence = getattr(result, "safe_evidence", None) or {}
        raw_questions = tuple(getattr(result, "questions", ()) or ())
        raw_instructions = tuple(getattr(result, "instructions", ()) or ())
        raw_auditor = getattr(result, "auditor", None)
        payload: dict[str, Any] = {
            "audit_id": _safe_text(getattr(result, "audit_id", None), "audit_id"),
            "target_state": _safe_text(target, "target_state"),
            "evidence_fingerprint": _safe_text(fingerprint, "evidence_fingerprint"),
            "attempt_id": _safe_text(attempt_id, "attempt_id"),
            "verdict": _safe_text(verdict, "verdict"),
            "message": _SENSITIVE_RE.sub(
                "[REDACTED]", str(getattr(result, "message", "") or "")
            )[:_MAX_CHECKPOINT_TEXT],
        }
        classification = getattr(result, "failure_classification", None)
        if classification is not None:
            payload["failure_classification"] = _safe_text(
                getattr(classification, "value", classification),
                "failure_classification",
            )
        for field_name in ("questions", "instructions"):
            values = raw_questions if field_name == "questions" else raw_instructions
            payload[field_name] = [
                _SENSITIVE_RE.sub("[REDACTED]", str(value))[:192]
                for value in tuple(values)[:3]
            ]
        payload["safe_evidence"] = {
            _SENSITIVE_RE.sub("[REDACTED]", str(key))[:64]: _SENSITIVE_RE.sub(
                "[REDACTED]", str(value)
            )[:128]
            for key, value in list(raw_safe_evidence.items())[:4]
        }
        auditor = raw_auditor
        if auditor is not None:
            payload["auditor"] = {
                "identity": _SENSITIVE_RE.sub(
                    "[REDACTED]",
                    _required_text(
                        getattr(auditor, "identity", None), "auditor.identity"
                    ),
                )[:256],
                "source": (
                    _SENSITIVE_RE.sub(
                        "[REDACTED]", str(getattr(auditor, "source", None))
                    )[:128]
                    if getattr(auditor, "source", None)
                    else None
                ),
            }
        # Bind the digest to the exact bounded representation which recovery
        # will deserialize.  Hashing the unbounded provider payload would make
        # a redacted/truncated checkpoint unverifiable and provide no
        # corruption fence at replay time.
        payload["result_digest"] = hashlib.sha256(
            _canonical(payload).encode()
        ).hexdigest()
        return payload

    def _validate_owned_identity(
        self,
        job: WorkflowJob,
        record: TerminalAuditRecord,
        *,
        attempt_id: str,
        lease_token: str | None = None,
        allowed_phases: tuple[AuditWorkflowPhase, ...] = (AuditWorkflowPhase.RUNNING,),
    ) -> Mapping[str, Any]:
        """Validate every durable identity before accepting a callback."""

        checkpoint = job.checkpoint or {}
        expected = {
            "workflow_job_id": job.job_id,
            "audit_id": record.audit_id,
            "target_state": record.target_state.value,
            "evidence_fingerprint": record.evidence_fingerprint.digest,
            "attempt_id": attempt_id,
        }
        if job.state is not WorkflowJobState.RUNNING:
            raise AuditWorkflowIdentityError("terminal-audit job is not running")
        if job.action != TERMINAL_AUDIT_JOB_ACTION:
            raise AuditWorkflowIdentityError("terminal-audit action identity changed")
        if job.generation != self.generation(record):
            raise AuditWorkflowIdentityError("terminal-audit generation changed")
        if job.expected_evidence_revision != record.evidence_fingerprint.digest:
            raise AuditWorkflowIdentityError("terminal-audit evidence revision changed")
        if job.phase not in {phase.value for phase in allowed_phases}:
            raise AuditWorkflowIdentityError(
                "terminal-audit phase no longer accepts results"
            )
        for key, value in expected.items():
            if str(checkpoint.get(key) or "") != str(value):
                raise AuditWorkflowIdentityError(
                    f"terminal-audit checkpoint {key} does not match"
                )
        if int(checkpoint.get("job_attempt") or 0) != job.attempts:
            raise AuditWorkflowIdentityError("terminal-audit job attempt changed")
        if lease_token is not None and job.lease_token != lease_token:
            raise AuditWorkflowIdentityError("terminal-audit lease token changed")
        return checkpoint

    def start(
        self,
        record: TerminalAuditRecord,
        *,
        attempt_id: str,
        candidate: Any,
    ) -> WorkflowJob | None:
        """Claim queued ownership and checkpoint the selected candidate."""

        try:
            existing = self.ensure(record)
        except AuditWorkflowIdentityError:
            # A late metadata snapshot cannot claim after a newer source
            # generation has advanced this target lane.
            return None
        if existing.state is WorkflowJobState.RUNNING:
            # A running row belongs to the exact lease which launched it.
            # Returning that token to a later plan would let a new attempt
            # inherit arbitrary in-flight ownership.
            return None
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
                record,
                attempt_id=attempt_id,
                candidate=candidate,
                workflow_job_id=claimed.job_id,
                job_attempt=claimed.attempts,
            ),
            now=self.clock(),
        )

    def mark_finalizing(
        self,
        job: WorkflowJob,
        record: TerminalAuditRecord,
        *,
        result: Any,
        attempt_id: str,
        lease_token: str,
    ) -> WorkflowJob:
        """Reserve the result boundary before tracker comments or status writes."""

        self._validate_owned_identity(
            job,
            record,
            attempt_id=attempt_id,
            lease_token=lease_token,
        )
        result_payload = self._result_payload(result)
        if result_payload["audit_id"] != record.audit_id:
            raise AuditWorkflowIdentityError("result audit identity changed")
        if result_payload["target_state"] != record.target_state.value:
            raise AuditWorkflowIdentityError("result target identity changed")
        if result_payload["evidence_fingerprint"] != record.evidence_fingerprint.digest:
            raise AuditWorkflowIdentityError("result evidence identity changed")
        if result_payload["attempt_id"] != attempt_id:
            raise AuditWorkflowIdentityError("result attempt identity changed")
        return self.store.checkpoint(
            job.job_id,
            lease_token,
            phase=AuditWorkflowPhase.FINALIZING.value,
            checkpoint=self._checkpoint_payload(
                record,
                attempt_id=attempt_id,
                verdict=str(result_payload["verdict"]),
                failure_classification=result_payload.get("failure_classification"),
                result_idempotency=attempt_id,
                workflow_job_id=job.job_id,
                job_attempt=job.attempts,
                result_payload=result_payload,
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
        return self.store.complete(
            job.job_id, job.lease_token, result_transition=result, now=self.clock()
        )

    def cancel(self, job: WorkflowJob, *, reason: str) -> WorkflowJob:
        if job.lease_token is None:
            raise WorkflowJobLeaseLost(f"terminal-audit job has no lease: {job.job_id}")
        return self.store.cancel_owned(
            job.job_id,
            job.lease_token,
            reason=_safe_text(reason, "reason"),
            now=self.clock(),
        )

    def finalizing_jobs(
        self, *, project_id: str | None = None, limit: int = 1000
    ) -> tuple[WorkflowJob, ...]:
        """Return bounded result checkpoints which still need acknowledgement."""

        return tuple(
            self.store.list_jobs(
                project_id=project_id,
                states=(WorkflowJobState.RUNNING,),
                actions=(TERMINAL_AUDIT_JOB_ACTION,),
                phases=(AuditWorkflowPhase.FINALIZING.value,),
                limit=limit,
            )
        )

    def reclaim_finalizing(
        self,
        job: WorkflowJob,
        record: TerminalAuditRecord,
        *,
        active_attempt_identities: set[AuditAttemptIdentity],
    ) -> WorkflowJob | None:
        """Take over one exact abandoned finalization after restart."""

        checkpoint = job.checkpoint or {}
        attempt_id = _required_text(checkpoint.get("attempt_id"), "attempt_id")
        retry_at = checkpoint.get("finalization_retry_at")
        if retry_at is not None and float(retry_at) > self.clock():
            return None
        self._validate_owned_identity(
            job,
            record,
            attempt_id=attempt_id,
            allowed_phases=(AuditWorkflowPhase.FINALIZING,),
        )
        if audit_attempt_identity(
            job.project_id,
            job.task_id,
            checkpoint.get("audit_id"),
            attempt_id,
        ) in active_attempt_identities:
            return None
        if job.lease_token is None:
            raise WorkflowJobLeaseLost(f"terminal-audit job has no lease: {job.job_id}")
        return self.store.reclaim_abandoned(
            job.job_id,
            job.lease_token,
            lease_owner=self.lease_owner,
            lease_seconds=self.lease_seconds,
            expected_phase=AuditWorkflowPhase.FINALIZING.value,
            now=self.clock(),
        )

    def defer_finalizing(self, job: WorkflowJob) -> WorkflowJob:
        """Back off a coordinator transport failure without losing its result."""

        if job.lease_token is None:
            raise WorkflowJobLeaseLost(f"terminal-audit job has no lease: {job.job_id}")
        checkpoint = dict(job.to_dict().get("checkpoint") or {})
        failures = int(checkpoint.get("finalization_failures") or 0) + 1
        if failures >= self.max_attempts:
            return self.action_required(
                job,
                action_code="finalization_transport_exhausted",
                reason=(
                    "terminal-audit result finalization exhausted its bounded "
                    "transport retry budget"
                ),
            )
        checkpoint["finalization_failures"] = failures
        checkpoint["finalization_retry_at"] = self.clock() + max(
            self.retry_delay_seconds,
            1.0,
        )
        if len(_canonical(checkpoint).encode()) > _MAX_CHECKPOINT_BYTES:
            raise ValueError("terminal-audit checkpoint exceeds the durable size bound")
        return self.store.checkpoint(
            job.job_id,
            job.lease_token,
            phase=AuditWorkflowPhase.FINALIZING.value,
            checkpoint=checkpoint,
            now=self.clock(),
        )

    def requeue_unreplayable_finalizing(
        self,
        job: WorkflowJob,
        *,
        active_attempt_identities: set[AuditAttemptIdentity],
    ) -> WorkflowJob | None:
        """Bound recovery for a pre-cutover finalizing checkpoint.

        Older rows did not retain the complete typed result and therefore
        cannot be safely replayed.  They still carry the exact audit,
        evidence and attempt identities; rotate only that lease and schedule
        one fresh auditor attempt instead of leaving the row permanently
        finalizing or recovering every job owned by the process.
        """

        checkpoint = job.checkpoint or {}
        attempt_id = _required_text(checkpoint.get("attempt_id"), "attempt_id")
        if audit_attempt_identity(
            job.project_id,
            job.task_id,
            checkpoint.get("audit_id"),
            attempt_id,
        ) in active_attempt_identities:
            return None
        if (
            job.action != TERMINAL_AUDIT_JOB_ACTION
            or job.state is not WorkflowJobState.RUNNING
            or job.phase != AuditWorkflowPhase.FINALIZING.value
            or checkpoint.get("evidence_fingerprint") != job.expected_evidence_revision
            or job.lease_token is None
        ):
            raise AuditWorkflowIdentityError(
                "legacy finalizing checkpoint identity does not match"
            )
        reclaimed = self.store.reclaim_abandoned(
            job.job_id,
            job.lease_token,
            lease_owner=self.lease_owner,
            lease_seconds=self.lease_seconds,
            expected_phase=AuditWorkflowPhase.FINALIZING.value,
            now=self.clock(),
        )
        return self.retry(
            reclaimed,
            category=WorkflowFailureCategory.ABANDONED,
            reason="pre-cutover finalizing result requires a fresh exact attempt",
        )

    def quarantine_finalizing(
        self,
        job: WorkflowJob,
        *,
        active_attempt_identities: set[AuditAttemptIdentity],
        reason: str,
    ) -> WorkflowJob | None:
        """Terminalize one corrupt abandoned result without blocking siblings."""

        checkpoint = job.checkpoint or {}
        raw_audit_id = str(checkpoint.get("audit_id") or "").strip()
        raw_attempt_id = str(checkpoint.get("attempt_id") or "").strip()
        if raw_audit_id and raw_attempt_id and audit_attempt_identity(
            job.project_id,
            job.task_id,
            raw_audit_id,
            raw_attempt_id,
        ) in active_attempt_identities:
            return None
        if (
            job.action != TERMINAL_AUDIT_JOB_ACTION
            or job.state is not WorkflowJobState.RUNNING
            or job.phase != AuditWorkflowPhase.FINALIZING.value
            or job.lease_token is None
        ):
            raise AuditWorkflowIdentityError(
                "corrupt finalizing job identity does not match"
            )
        reclaimed = self.store.reclaim_abandoned(
            job.job_id,
            job.lease_token,
            lease_owner=self.lease_owner,
            lease_seconds=self.lease_seconds,
            expected_phase=AuditWorkflowPhase.FINALIZING.value,
            now=self.clock(),
        )
        return self.action_required(
            reclaimed,
            action_code="corrupt_finalization_checkpoint",
            reason=reason,
        )

    @staticmethod
    def finalizing_result_payload(job: WorkflowJob) -> Mapping[str, Any]:
        # Jobs freeze nested JSON values on read.  Digest verification and the
        # coordinator replay contract both require an ordinary JSON mapping.
        checkpoint = job.to_dict().get("checkpoint") or {}
        result = checkpoint.get("result")
        if not isinstance(result, Mapping):
            raise AuditWorkflowIdentityError("finalizing result checkpoint is missing")
        for key in (
            "audit_id",
            "target_state",
            "evidence_fingerprint",
            "attempt_id",
            "verdict",
        ):
            if not str(result.get(key) or "").strip():
                raise AuditWorkflowIdentityError(
                    f"finalizing result checkpoint lacks {key}"
                )
        for key in (
            "audit_id",
            "target_state",
            "evidence_fingerprint",
            "attempt_id",
        ):
            if str(result.get(key) or "") != str(checkpoint.get(key) or ""):
                raise AuditWorkflowIdentityError(
                    f"finalizing result checkpoint {key} does not match owner"
                )
        supplied_digest = str(result.get("result_digest") or "")
        if len(supplied_digest) != 64 or any(
            character not in "0123456789abcdef" for character in supplied_digest
        ):
            raise AuditWorkflowIdentityError(
                "finalizing result checkpoint lacks a valid digest"
            )
        digest_payload = dict(result)
        digest_payload.pop("result_digest", None)
        expected_digest = hashlib.sha256(
            _canonical(digest_payload).encode()
        ).hexdigest()
        if supplied_digest != expected_digest:
            raise AuditWorkflowIdentityError(
                "finalizing result checkpoint digest does not match"
            )
        return dict(result)

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
        # WorkflowJob freezes nested JSON as mapping proxies.  Work from its
        # public serialized form so a preserved typed result remains JSON
        # serializable when the ACTION_REQUIRED checkpoint is written.
        record_data = job.to_dict().get("checkpoint") or {}
        if record is not None:
            record_data = {
                "audit_id": record.audit_id,
                "target_state": record.target_state.value,
                "evidence_fingerprint": record.evidence_fingerprint.digest,
            }
        fallback_target = job.scheduling_lane.removeprefix("terminal-audit:")
        checkpoint = {
            "version": TERMINAL_AUDIT_WORKFLOW_VERSION,
            "audit_id": _safe_text(
                record_data.get("audit_id") or f"workflow-job:{job.job_id}",
                "audit_id",
            ),
            "target_state": _safe_text(
                record_data.get("target_state") or fallback_target,
                "target_state",
            ),
            "evidence_fingerprint": _safe_text(
                record_data.get("evidence_fingerprint")
                or job.expected_evidence_revision,
                "evidence_fingerprint",
            ),
            "action_code": _safe_text(action_code, "action_code"),
        }
        # An exhausted/corrupt finalizer still has to project one exact
        # retryable attempt into tracker metadata.  Preserve the bounded owner
        # identity when it is available so ACTION_REQUIRED recovery can finish
        # that attempt instead of manufacturing an unrelated no-auditor row.
        for key in (
            "attempt_id",
            "workflow_job_id",
            "job_attempt",
            "result_idempotency",
            "verdict",
            "failure_classification",
        ):
            value = record_data.get(key)
            if value is not None:
                checkpoint[key] = value
        result_data = record_data.get("result")
        if isinstance(result_data, Mapping):
            checkpoint["result"] = dict(result_data)
        if len(_canonical(checkpoint).encode()) > _MAX_CHECKPOINT_BYTES:
            raise ValueError(
                "terminal-audit action checkpoint exceeds the durable size bound"
            )
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
        if job.state is WorkflowJobState.RUNNING:
            # Candidate selection lost to an already-launched exact attempt.
            # It does not own that lease and cannot turn live work into an
            # operator action.
            return job
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
        active_attempt_identities: set[AuditAttemptIdentity] | None = None,
    ) -> AuditWorkflowDecision:
        """Requeue an owned audit after restart when no live attempt remains."""

        job = self.ensure(record)
        if job.state is WorkflowJobState.RUNNING:
            attempt_id = (job.checkpoint or {}).get("attempt_id")
            active_identity = (
                audit_attempt_identity(
                    job.project_id,
                    job.task_id,
                    (job.checkpoint or {}).get("audit_id"),
                    attempt_id,
                )
                if attempt_id and (job.checkpoint or {}).get("audit_id")
                else None
            )
            if (
                active_attempt_identities is None
                or active_identity in active_attempt_identities
            ):
                return self._decision_from_job(record, job)
            if job.phase == AuditWorkflowPhase.FINALIZING.value:
                # A typed result is already durable.  The replay lane takes
                # over this exact lease and applies it; never reset it into a
                # fresh provider attempt.
                return self._decision_from_job(record, job)
            if job.lease_token is None:
                raise WorkflowJobLeaseLost(
                    f"terminal-audit job has no lease: {job.job_id}"
                )
            self.store.reclaim_abandoned(
                job.job_id,
                job.lease_token,
                lease_owner=self.lease_owner,
                lease_seconds=self.lease_seconds,
                expected_phase=AuditWorkflowPhase.RUNNING.value,
                now=self.clock(),
            )
            current = self.store.get(job.job_id)
            self.retry(
                current,
                category=WorkflowFailureCategory.ABANDONED,
                reason="exact auditor attempt was abandoned during restart",
            )
            job = self.store.get(job.job_id)
        return self._decision_from_job(record, job)


DurableTerminalAuditWorkflow = TerminalAuditWorkflow
