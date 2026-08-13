"""Production effects for the durable implementation workflow.

The implementation controller owns lifecycle decisions; this adapter is the
single production bridge to the existing worker launcher, owner-claim store,
duplicate-screening service, and integration queue.  Every effect is scoped to
one project/task/generation and leaves an immutable SQLite receipt.  The
receipt is deliberately separate from the worker checkpoint: after a process
dies between applying an effect and checkpointing it, ``inspect`` can recover
the exact disposition without repeating the mutation.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import sqlite3
import threading
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

from oompah.authority_lock import acquire_bounded_task_lock
from oompah.duplicate_screening import (
    DETECTOR_VERSION as DUPLICATE_DETECTOR_VERSION,
    ScreeningState,
    assess_screening,
)
from oompah.implementation_workflow import (
    IMPLEMENTATION_ACTIONS,
    ImplementationAction,
    ImplementationDisposition,
    ImplementationExecutionResult,
    ImplementationOwnershipSource,
    ImplementationState,
    ImplementationWorkflowHandler,
)
from oompah.integration import accepted_submission_branch
from oompah.statuses import (
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    IN_VALIDATION,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
    OPEN,
    READY_TO_INTEGRATE,
    canonicalize_status,
    is_terminal_status,
)
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionIntent,
    TransitionOutcome,
    issue_authority_version,
    issue_exact_head,
)
from oompah.workflow_jobs import WorkflowFailureCategory, WorkflowJob, WorkflowJobState
from oompah.workflow_worker import (
    RevalidationResult,
    VerificationResult,
    WorkflowActionError,
    WorkflowActionSuperseded,
    WorkflowJobContext,
)


_HEAD_RE = re.compile(r"^[0-9a-f]{40,64}$")


def _text(value: object | None) -> str:
    return str(value or "").strip()


def _iso_from_epoch(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


class ImplementationReceiptStore:
    """Immutable, project-scoped receipts for applied implementation effects."""

    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS implementation_receipts (
                    project_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    generation TEXT NOT NULL,
                    action TEXT NOT NULL,
                    expected_evidence_revision TEXT,
                    expected_head_sha TEXT,
                    disposition_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, task_id, generation, action)
                )
                """
            )
            columns = {
                str(row["name"])
                for row in self._conn.execute(
                    "PRAGMA table_info(implementation_receipts)"
                ).fetchall()
            }
            if "expected_evidence_revision" not in columns:
                self._conn.execute(
                    "ALTER TABLE implementation_receipts "
                    "ADD COLUMN expected_evidence_revision TEXT"
                )
            self._conn.commit()

    @staticmethod
    def _key(context: WorkflowJobContext) -> tuple[str, str, str, str]:
        job = context.job
        return job.project_id, job.task_id, job.generation, job.action

    def get(self, context: WorkflowJobContext) -> ImplementationDisposition | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT expected_evidence_revision, expected_head_sha,
                       disposition_json
                  FROM implementation_receipts
                 WHERE project_id = ? AND task_id = ?
                   AND generation = ? AND action = ?
                """,
                self._key(context),
            ).fetchone()
        if row is None:
            return None
        if (
            _text(row["expected_evidence_revision"])
            != _text(context.job.expected_evidence_revision)
            or _text(row["expected_head_sha"])
            != _text(context.job.expected_head_sha)
        ):
            raise WorkflowActionError(
                "implementation receipt evidence fence disagrees with the job",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )
        try:
            raw = json.loads(str(row["disposition_json"]))
            disposition = ImplementationDisposition.from_dict(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise WorkflowActionError(
                "implementation receipt is corrupt",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            ) from exc
        return disposition if disposition.matches(context.job, allow_incomplete=True) else None

    def record(
        self,
        context: WorkflowJobContext,
        disposition: ImplementationDisposition,
    ) -> ImplementationDisposition:
        if not disposition.matches(context.job, allow_incomplete=True):
            raise WorkflowActionError(
                "implementation receipt does not match its exact job",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )
        encoded = json.dumps(
            disposition.to_dict(), sort_keys=True, separators=(",", ":")
        )
        key = self._key(context)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT expected_evidence_revision, expected_head_sha,
                           disposition_json
                      FROM implementation_receipts
                     WHERE project_id = ? AND task_id = ?
                       AND generation = ? AND action = ?
                    """,
                    key,
                ).fetchone()
                if row is None:
                    self._conn.execute(
                        """
                        INSERT INTO implementation_receipts(
                            project_id, task_id, generation, action,
                            expected_evidence_revision, expected_head_sha,
                            disposition_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            *key,
                            context.job.expected_evidence_revision,
                            context.job.expected_head_sha,
                            encoded,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                elif (
                    _text(row["expected_evidence_revision"])
                    != _text(context.job.expected_evidence_revision)
                    or _text(row["expected_head_sha"])
                    != _text(context.job.expected_head_sha)
                    or str(row["disposition_json"]) != encoded
                ):
                    raise WorkflowActionError(
                        "implementation receipt identity was reused for a different effect",
                        category=WorkflowFailureCategory.PERMANENT,
                        retryable=False,
                    )
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise
        return disposition

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class OrchestratorImplementationEffects:
    """One-task production mutations used by the implementation backend."""

    def __init__(
        self,
        orchestrator: Any,
        *,
        project_id: str,
        tracker: Any | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.project_id = _text(project_id)
        if not self.project_id:
            raise ValueError("project_id is required")
        store_path = getattr(orchestrator.workflow_job_store, "path", "")
        state_dir = os.path.dirname(os.path.abspath(store_path))
        self._receipt_path = os.path.join(
            state_dir, "implementation_receipts.sqlite3"
        )
        self._bound_tracker = tracker
        self._mutations: dict[str, asyncio.Task[ImplementationDisposition]] = {}

    def _mutation_finished(
        self,
        key: str,
        mutation: asyncio.Task[ImplementationDisposition],
    ) -> None:
        """Retire one exact shielded mutation after its real completion."""

        if self._mutations.get(key) is mutation:
            self._mutations.pop(key, None)
        if not mutation.cancelled():
            # The worker-facing awaiter may have been cancelled by a timeout.
            # Consume a detached mutation failure without changing what any
            # concurrent waiter observes from the same task.
            mutation.exception()

    @property
    def pending_mutation_count(self) -> int:
        """Return shielded effects which still own external/store access."""

        return sum(not mutation.done() for mutation in self._mutations.values())

    async def drain_mutations(self, *, timeout_seconds: float | None = None) -> bool:
        """Wait for already-started shielded mutations without cancelling them."""

        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        pending = tuple(
            mutation for mutation in self._mutations.values() if not mutation.done()
        )
        if not pending:
            return True
        waiter = asyncio.gather(*pending, return_exceptions=True)
        try:
            if timeout_seconds is None:
                await waiter
            else:
                await asyncio.wait_for(asyncio.shield(waiter), timeout_seconds)
        except TimeoutError:
            return False
        return True

    async def prepare_quarantine_recycle(self, job: WorkflowJob) -> None:
        """Transfer one fenced mutation from loop drain to process restart.

        The workflow ledger must already contain the exact quarantined token
        and recycle marker before this is called.  Cancelling the asyncio task
        does not pretend to terminate a synchronous adapter thread; it only
        prevents safe-stop from waiting forever on an in-memory wrapper.  The
        running quarantine continues to block replacements until the process
        boundary removes the old thread and startup recovers that exact owner.
        """

        current = self.orchestrator.workflow_job_store.get(job.job_id)
        marker = (current.checkpoint or {}).get("quarantine_recycle")
        if not (
            current.state is WorkflowJobState.RUNNING
            and current.phase == "quarantined"
            and current.lease_owner == job.lease_owner
            and current.lease_token == job.lease_token
            and isinstance(marker, Mapping)
            and _text(marker.get("lease_owner")) == _text(current.lease_owner)
            and _text(marker.get("lease_token")) == _text(current.lease_token)
        ):
            raise WorkflowActionError(
                "implementation recycle lacks an exact durable quarantine marker",
                category=WorkflowFailureCategory.PERMANENT,
                retryable=False,
            )
        mutation = self._mutations.get(job.idempotency_key)
        if mutation is None or mutation.done():
            return
        mutation.cancel()
        await asyncio.gather(mutation, return_exceptions=True)

    @property
    def receipts(self) -> ImplementationReceiptStore:
        """Open the effect ledger lazily so shadow construction is zero-write."""

        shared = getattr(self.orchestrator, "_implementation_receipt_store", None)
        if shared is None:
            shared = ImplementationReceiptStore(self._receipt_path)
            self.orchestrator._implementation_receipt_store = shared
        return shared

    def _tracker(self) -> Any:
        if self._bound_tracker is not None:
            return self._bound_tracker
        return self.orchestrator._tracker_for_project(self.project_id)

    def _issue(self, task_id: str) -> Any:
        issue = self._tracker().fetch_issue_detail(task_id)
        if issue is None:
            raise WorkflowActionError(
                f"implementation task {task_id} is unavailable",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )
        issue_project = _text(getattr(issue, "project_id", None))
        if issue_project and issue_project != self.project_id:
            raise WorkflowActionError(
                "implementation effect crossed its project binding",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        issue.project_id = self.project_id
        return issue

    def _running(self, issue: Any, generation: str) -> Any | None:
        entry = self._project_running(issue)
        if entry is None:
            return None
        if _text(getattr(entry, "authority_generation", None)) != generation:
            return None
        return entry

    def _project_running(self, issue: Any) -> Any | None:
        """Return only a live runtime proven to belong to this project/task."""

        entry = self.orchestrator._current_running_entry(issue.id)
        if entry is None:
            return None
        entry_issue = getattr(entry, "issue", None)
        if _text(getattr(entry_issue, "project_id", None)) != self.project_id:
            return None
        if _text(getattr(entry_issue, "identifier", None)) != _text(
            getattr(issue, "identifier", None)
        ):
            return None
        return entry

    def _active_exact_direct_owner_claim(self, issue: Any) -> Any | None:
        """Return only current direct-owner authority for this bound task.

        Recovery jobs are derived from an earlier fact cut which may lose a
        race to a direct-owner claim. Read the claim under the same project
        write lock used by claim grant/release so the captured claim id cannot
        be an ABA mixture. The caller may use that immutable id as the
        replacement generation, but must not persist a recovery receipt for a
        lease which can later expire or be released.
        """

        project_store = getattr(self.orchestrator, "project_store", None)
        lock_factory = getattr(project_store, "project_write_lock", None)
        project_lock = (
            lock_factory(self.project_id)
            if callable(lock_factory)
            else contextlib.nullcontext()
        )
        with project_lock:
            claim = self.orchestrator._owner_claim_for_issue(
                issue.id,
                self.project_id,
            )
            now = datetime.now(timezone.utc).timestamp()
            if (
                claim is None
                or _text(getattr(claim, "issue_id", None)) != _text(issue.id)
                or _text(getattr(claim, "project_id", None)) != self.project_id
                or not _text(getattr(claim, "claim_id", None))
                or not _text(getattr(claim, "owner_login", None))
                or bool(getattr(claim, "retirement_pending", False))
                or float(getattr(claim, "expires_at", 0) or 0) <= now
                or canonicalize_status(issue.state) == IN_VALIDATION
                or is_terminal_status(issue.state)
            ):
                return None
            return claim

    def _supersede_recovery_for_direct_owner(
        self,
        issue: Any,
        context: WorkflowJobContext,
    ) -> None:
        """Fence stale recovery when an exact direct-owner generation won."""

        if (
            ImplementationAction(context.job.action)
            is not ImplementationAction.RECOVERY
        ):
            return
        claim = self._active_exact_direct_owner_claim(issue)
        if claim is None:
            return
        raise WorkflowActionSuperseded(
            "implementation recovery was replaced by an active direct-owner claim",
            replacement_generation=f"direct-owner:{claim.claim_id}",
        )

    def _assert_job_current(self, context: WorkflowJobContext) -> None:
        """Fence a multi-step effect after an awaited retirement boundary."""

        if context.job.state is not WorkflowJobState.RUNNING:
            return
        current = self.orchestrator.workflow_job_store.get(context.job.job_id)
        if (
            current.state is not WorkflowJobState.RUNNING
            or current.lease_token != context.job.lease_token
        ):
            raise WorkflowActionError(
                "implementation authority changed during the external effect",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )

    async def _fence_dispatched_generation(
        self, issue: Any, context: WorkflowJobContext
    ) -> None:
        """Retire an exact launch if its durable job lost authority mid-start."""

        try:
            self._assert_job_current(context)
        except WorkflowActionError:
            if self._running(issue, context.job.generation) is not None:
                self.orchestrator._cancel_retry_for_issue(
                    issue_id=issue.id,
                    identifier=issue.identifier,
                    project_id=self.project_id,
                    reason="implementation job was superseded during dispatch",
                    schedule_termination=False,
                )
                await self.orchestrator._terminate_running(
                    issue.id, cleanup_workspace=False
                )
            raise

    @asynccontextmanager
    async def _dispatch_lane(self):
        """Serialize durable admission with the scheduler capacity gate."""

        lock = getattr(self.orchestrator, "_dispatch_lane_lock", None)
        if lock is None:
            yield
            return
        async with lock:
            yield

    @asynccontextmanager
    async def _issue_authority_lane(self, issue: Any):
        """Serialize owner-claim mutation with accepted submission capture."""

        lock_factory = getattr(self.orchestrator, "issue_transition_lock", None)
        lock = lock_factory(issue.id) if callable(lock_factory) else None
        if lock is None or not callable(getattr(lock, "acquire", None)):
            yield
            return
        control_timeout = max(
            float(
                getattr(
                    getattr(self.orchestrator, "config", None),
                    "terminal_control_lock_timeout_seconds",
                    5.0,
                )
            ),
            0.1,
        )
        # The pre-provider evidence fence releases within one control interval;
        # a second interval lets this durable retry win naturally after that
        # retirement without approaching the workflow call's outer deadline.
        timeout_seconds = control_timeout * 2.0
        acquired = await acquire_bounded_task_lock(
            lock,
            timeout_seconds=timeout_seconds,
        )
        if acquired is None:
            yield
            return
        if not acquired:
            raise WorkflowActionError(
                "direct-owner claim is waiting for bounded task authority "
                f"(issue_id={issue.id}, waited={timeout_seconds:g}s)",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        try:
            yield
        finally:
            lock.release()

    async def _admit_dispatch(
        self,
        issue: Any,
        *,
        duplicate_preflight: bool = False,
        durable_recovery: bool = False,
    ) -> None:
        fresh = await asyncio.to_thread(self._issue, issue.identifier)
        integration = getattr(fresh, "integration", None)
        integration_state = _text(getattr(integration, "state", None)).lower()
        accepted_branch = accepted_submission_branch(fresh)
        if (
            canonicalize_status(fresh.state)
            in {OPEN, IN_PROGRESS, NEEDS_CI_FIX, NEEDS_REBASE}
            and integration_state in {"ready", "queued", "integrating"}
            and accepted_branch
        ):
            accepted_head = _text(getattr(integration, "head_sha", None))
            raise WorkflowActionSuperseded(
                "accepted submission replaced implementation dispatch",
                replacement_generation=(
                    f"accepted-submission:{accepted_head}"
                    if accepted_head
                    else f"accepted-submission:{accepted_branch}"
                ),
            )
        admitted = await asyncio.to_thread(
            self.orchestrator._should_dispatch,
            fresh,
            duplicate_preflight=duplicate_preflight,
            durable_recovery=durable_recovery,
            suppress_lifecycle_writes=True,
        )
        if admitted:
            return
        reason = "dispatch policy is not currently admitting this task"
        reject_streak = getattr(
            getattr(self.orchestrator, "state", None), "reject_streak", {}
        )
        rejected = (
            reject_streak.get(issue.id)
            if isinstance(reject_streak, dict)
            else None
        )
        if rejected:
            reason = f"{reason}: {rejected[0]}"
        raise WorkflowActionError(
            reason,
            category=WorkflowFailureCategory.TRANSIENT,
            retryable=True,
        )

    @staticmethod
    def _source(action: ImplementationAction) -> ImplementationOwnershipSource:
        if action is ImplementationAction.DIRECT_OWNER_CLAIM:
            return ImplementationOwnershipSource.DIRECT_OWNER
        if action is ImplementationAction.DUPLICATE_SCREENING:
            return ImplementationOwnershipSource.DUPLICATE_INVESTIGATOR
        if action is ImplementationAction.RECOVERY:
            return ImplementationOwnershipSource.RECOVERY
        return ImplementationOwnershipSource.AGENT

    @staticmethod
    def _state(action: ImplementationAction) -> ImplementationState:
        return {
            ImplementationAction.START: ImplementationState.ACTIVE,
            ImplementationAction.DIRECT_OWNER_CLAIM: ImplementationState.ACTIVE,
            ImplementationAction.DUPLICATE_SCREENING: ImplementationState.ACTIVE,
            ImplementationAction.FOCUS_HANDOFF: ImplementationState.HANDED_OFF,
            ImplementationAction.WORKER_EXIT: ImplementationState.COMPLETED,
            ImplementationAction.VALIDATION_SUBMISSION: ImplementationState.SUBMITTED,
            ImplementationAction.AUTHORITY_REVOCATION: ImplementationState.REVOKED,
            ImplementationAction.RETRY: ImplementationState.RETRY_WAIT,
            ImplementationAction.RECOVERY: ImplementationState.ACTIVE,
        }[action]

    def _disposition(
        self,
        context: WorkflowJobContext,
        *,
        issue: Any,
        owner_id: str | None = None,
        assignment_id: str | None = None,
        run_id: str | None = None,
        lease_expires_at: str | None = None,
    ) -> ImplementationDisposition:
        action = ImplementationAction(context.job.action)
        payload = context.job.payload or {}
        state = self._state(action)
        if state in {
            ImplementationState.ACTIVE,
            ImplementationState.HANDED_OFF,
        }:
            owner_id = _text(owner_id or payload.get("owner_id")) or (
                f"workflow:{context.job.generation}"
            )
            lease_expires_at = _text(
                lease_expires_at or payload.get("lease_expires_at")
            ) or (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        exact_head = _text(context.job.expected_head_sha) or _text(
            payload.get("head_sha") or issue_exact_head(issue)
        )

        return ImplementationDisposition(
            project_id=self.project_id,
            task_id=context.job.task_id,
            generation=context.job.generation,
            action=action,
            state=state,
            ownership_source=self._source(action),
            owner_id=_text(owner_id or payload.get("owner_id")) or None,
            assignment_id=_text(assignment_id or payload.get("assignment_id")) or None,
            run_id=_text(run_id or payload.get("run_id")) or None,
            focus=_text(payload.get("focus")) or None,
            work_branch=_text(
                payload.get("work_branch")
                or getattr(issue, "work_branch", None)
                or getattr(issue, "branch_name", None)
            )
            or None,
            head_sha=exact_head or None,
            lease_expires_at=lease_expires_at,
            retry_at=_text(payload.get("retry_at")) or None,
            incomplete_sessions=int(payload.get("incomplete_sessions") or 0),
        )

    @staticmethod
    def _entry_lease(entry: Any) -> str:
        started_at = getattr(entry, "started_at", None)
        if isinstance(started_at, datetime):
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            expires_at = started_at.astimezone(timezone.utc) + timedelta(hours=1)
            return expires_at.isoformat()
        return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    def _derive(self, context: WorkflowJobContext) -> ImplementationDisposition | None:
        """Recover effects observable outside the receipt transaction."""

        action = ImplementationAction(context.job.action)
        issue = self._issue(context.job.task_id)
        payload = context.job.payload or {}
        if action in {
            ImplementationAction.START,
            ImplementationAction.RECOVERY,
            ImplementationAction.FOCUS_HANDOFF,
        }:
            entry = self._running(issue, context.job.generation)
            if entry is None:
                self._supersede_recovery_for_direct_owner(issue, context)
                return None
            return self._disposition(
                context,
                issue=issue,
                owner_id=(
                    _text(payload.get("owner_id"))
                    or _text(getattr(entry, "run_id", None))
                ),
                assignment_id=_text(getattr(entry, "assignment_id", None)),
                run_id=_text(getattr(entry, "run_id", None)),
                lease_expires_at=(
                    None
                    if action is ImplementationAction.FOCUS_HANDOFF
                    else _text(payload.get("lease_expires_at"))
                    or self._entry_lease(entry)
                ),
            )
        if action is ImplementationAction.DIRECT_OWNER_CLAIM:
            claim = self.orchestrator._owner_claim_for_issue(issue.id, self.project_id)
            if claim is None or claim.expires_at <= datetime.now(timezone.utc).timestamp():
                return None
            if _text(payload.get("owner_id")) and claim.owner_login != _text(
                payload.get("owner_id")
            ):
                return None
            if _text(payload.get("claim_id")) and claim.claim_id != _text(
                payload.get("claim_id")
            ):
                return None
            return self._disposition(
                context,
                issue=issue,
                owner_id=claim.owner_login,
                lease_expires_at=_iso_from_epoch(claim.expires_at),
            )
        if action is ImplementationAction.AUTHORITY_REVOCATION:
            claim = self.orchestrator._owner_claim_for_issue(
                issue.id, self.project_id
            )
            direct_owner_only = (
                _text(payload.get("authority_kind")) == "direct_owner"
                or "claim_id" in payload
            )
            if direct_owner_only:
                expected_claim_id = _text(payload.get("claim_id"))
                if claim is None or _text(claim.claim_id) != expected_claim_id:
                    return self._disposition(context, issue=issue)
                return None
            if self._project_running(issue) is not None:
                return None
            if claim is not None:
                return None
            return self._disposition(context, issue=issue)
        if action is ImplementationAction.DUPLICATE_SCREENING:
            assessment = assess_screening(
                issue, detector_version=DUPLICATE_DETECTOR_VERSION
            )
            entry = self._running(issue, context.job.generation)
            completed_open_preflight = bool(
                canonicalize_status(issue.state) == OPEN
                and assessment.state is ScreeningState.CHECKED
            )
            if entry is not None or completed_open_preflight:
                return self._disposition(
                    context,
                    issue=issue,
                    owner_id=_text(
                        getattr(entry, "run_id", None) if entry is not None else None
                    )
                    or _text(payload.get("owner_id"))
                    or f"duplicate:{context.job.generation}",
                    lease_expires_at=(
                        _text(
                            getattr(
                                assessment.record,
                                "claim_expires_at",
                                None,
                            )
                        )
                        if assessment.record is not None
                        and assessment.record.claim_id
                        == context.job.generation
                        else None
                    ),
                )
        return None

    async def observe(
        self, context: WorkflowJobContext
    ) -> ImplementationDisposition | None:
        receipt = await asyncio.to_thread(self.receipts.get, context)
        if receipt is not None:
            await self._publish_recovered_direct_owner_revocation(context)
            return receipt
        derived = await asyncio.to_thread(self._derive, context)
        if derived is not None:
            receipt = await asyncio.to_thread(self.receipts.record, context, derived)
            await self._publish_recovered_direct_owner_revocation(context)
            return receipt
        return None

    async def _publish_recovered_direct_owner_revocation(
        self,
        context: WorkflowJobContext,
    ) -> None:
        """Publish idempotent state after observing an applied exact release."""

        if (
            ImplementationAction(context.job.action)
            is not ImplementationAction.AUTHORITY_REVOCATION
        ):
            return
        payload = context.job.payload or {}
        if not (
            _text(payload.get("authority_kind")) == "direct_owner"
            or "claim_id" in payload
        ):
            return
        notify = getattr(self.orchestrator, "_notify_state_only", None)
        if callable(notify):
            await asyncio.to_thread(notify)

    async def apply(self, context: WorkflowJobContext) -> ImplementationDisposition:
        key = context.job.idempotency_key
        mutation = self._mutations.get(key)
        if mutation is None or mutation.done():
            mutation = asyncio.create_task(self._apply(context))
            self._mutations[key] = mutation
            mutation.add_done_callback(
                lambda completed, mutation_key=key: self._mutation_finished(
                    mutation_key, completed
                )
            )
        try:
            return await asyncio.shield(mutation)
        except asyncio.CancelledError:
            # A worker timeout must not detach a still-running tracker/process
            # mutation and let the next lease overlap it.  The durable worker
            # quarantines the exact lease and observes this shielded mutation;
            # only a marked process-recycle transfer may detach it from drain.
            raise
        finally:
            if mutation.done() and self._mutations.get(key) is mutation:
                self._mutations.pop(key, None)

    async def _apply(self, context: WorkflowJobContext) -> ImplementationDisposition:
        observed = await self.observe(context)
        if observed is not None:
            self._assert_job_current(context)
            return observed
        self._assert_job_current(context)
        action = ImplementationAction(context.job.action)
        issue = await asyncio.to_thread(self._issue, context.job.task_id)
        payload = context.job.payload or {}

        if action in {ImplementationAction.START, ImplementationAction.RECOVERY}:
            async with self._dispatch_lane():
                existing = self._project_running(issue)
                if existing is not None and self._running(
                    issue, context.job.generation
                ) is None:
                    raise WorkflowActionError(
                        "an exact live implementation generation still owns the task",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                await asyncio.to_thread(
                    self._supersede_recovery_for_direct_owner,
                    issue,
                    context,
                )
                try:
                    await self._admit_dispatch(
                        issue,
                        durable_recovery=action is ImplementationAction.RECOVERY,
                    )
                except WorkflowActionError:
                    # A claim may land after observe/preflight but before the
                    # scheduler's authoritative dispatch-policy check. Turn
                    # that exact winner into a terminal supersession instead
                    # of spending recovery attempts on a policy denial.
                    await asyncio.to_thread(
                        self._supersede_recovery_for_direct_owner,
                        issue,
                        context,
                    )
                    raise
                dispatched = await self.orchestrator._dispatch(
                    issue,
                    attempt=(int(payload.get("attempt") or 0) or None),
                    override_profile=_text(payload.get("profile")) or None,
                    workflow_generation=context.job.generation,
                    status_managed_by_workflow=True,
                )
                if dispatched is False:
                    # _dispatch repeats the owner fence at its final admission
                    # boundary. Resolve a claim which won that narrower race
                    # the same way as one observed before admission.
                    await asyncio.to_thread(
                        self._supersede_recovery_for_direct_owner,
                        issue,
                        context,
                    )
            entry = self._running(issue, context.job.generation)
            if entry is None:
                raise WorkflowActionError(
                    "implementation dispatch did not publish the exact generation",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            await self._fence_dispatched_generation(issue, context)
            disposition = self._disposition(
                context,
                issue=issue,
                owner_id=(
                    _text(payload.get("owner_id"))
                    or _text(getattr(entry, "run_id", None))
                ),
                assignment_id=_text(getattr(entry, "assignment_id", None)),
                run_id=_text(getattr(entry, "run_id", None)),
                lease_expires_at=(
                    _text(payload.get("lease_expires_at"))
                    or self._entry_lease(entry)
                ),
            )
        elif action is ImplementationAction.DIRECT_OWNER_CLAIM:
            owner = _text(payload.get("owner_id"))
            if not owner:
                raise WorkflowActionError(
                    "direct-owner claim has no owner identity",
                    category=WorkflowFailureCategory.POLICY,
                    retryable=False,
                )
            durable_issue_id = _text(payload.get("issue_id"))
            if durable_issue_id and durable_issue_id != _text(issue.id):
                raise WorkflowActionError(
                    "direct-owner claim task identity changed",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            self.orchestrator._cancel_retry_for_issue(
                issue_id=issue.id,
                identifier=issue.identifier,
                project_id=self.project_id,
                reason="durable direct owner claim",
                schedule_termination=False,
            )
            if self._project_running(issue) is not None:
                terminated = await self.orchestrator._terminate_running(
                    issue.id, cleanup_workspace=False
                )
                if not terminated:
                    raise WorkflowActionError(
                        "scheduler runtime is still retiring for direct owner",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                self._assert_job_current(context)
            try:
                async with self._issue_authority_lane(issue):
                    self._assert_job_current(context)
                    claim = await asyncio.to_thread(
                        self.orchestrator.grant_owner_claim,
                        issue_id=issue.id,
                        project_id=self.project_id,
                        owner_login=owner,
                        ttl_hours=(
                            int(payload["ttl_hours"])
                            if payload.get("ttl_hours")
                            else None
                        ),
                        claim_id=_text(payload.get("claim_id")) or None,
                    )
            except ValueError as exc:
                raise WorkflowActionError(
                    f"direct-owner claim is waiting for scheduler retirement: {exc}",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                ) from exc
            try:
                self._assert_job_current(context)
            except WorkflowActionError:
                self.orchestrator.release_owner_claim(
                    issue_id=issue.id,
                    project_id=self.project_id,
                    expected_claim_id=claim.claim_id,
                )
                raise
            disposition = self._disposition(
                context,
                issue=issue,
                owner_id=claim.owner_login,
                lease_expires_at=_iso_from_epoch(claim.expires_at),
            )
        elif action is ImplementationAction.DUPLICATE_SCREENING:
            async with self._dispatch_lane():
                await self._admit_dispatch(issue, duplicate_preflight=True)
                candidate = canonicalize_status(issue.state) == DUPLICATE_CANDIDATE
                claim = await asyncio.to_thread(
                    lambda: self.orchestrator._claim_duplicate_preflight(
                        issue,
                        allow_duplicate_candidate=candidate,
                        claim_id=context.job.generation,
                    )
                )
                if claim is not None:
                    await self.orchestrator._dispatch(
                        issue,
                        attempt=None,
                        duplicate_preflight_claim=claim,
                        workflow_generation=context.job.generation,
                        status_managed_by_workflow=True,
                    )
            entry = self._running(issue, context.job.generation)
            if entry is None:
                assessment = assess_screening(
                    issue, detector_version=DUPLICATE_DETECTOR_VERSION
                )
                if assessment.state is not ScreeningState.CHECKED:
                    raise WorkflowActionError(
                        "duplicate screening could not acquire its exact claim",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
            if entry is not None:
                await self._fence_dispatched_generation(issue, context)
            disposition = self._disposition(
                context,
                issue=issue,
                owner_id=(
                    _text(payload.get("owner_id"))
                    or (
                        _text(getattr(entry, "run_id", None))
                        if entry is not None
                        else f"duplicate:{context.job.generation}"
                    )
                ),
                assignment_id=_text(getattr(entry, "assignment_id", None))
                if entry is not None
                else None,
                run_id=_text(getattr(entry, "run_id", None))
                if entry is not None
                else None,
                lease_expires_at=(
                    _text(
                        getattr(
                            claim,
                            "claim_expires_at",
                            None,
                        )
                    )
                    if claim is not None
                    else None
                ),
            )
        elif action is ImplementationAction.FOCUS_HANDOFF:
            outgoing = self._project_running(issue)
            expected_generation = _text(payload.get("prior_generation"))
            expected_run = _text(payload.get("prior_run_id"))
            if outgoing is not None and (
                not (expected_generation or expected_run)
                or (
                    expected_generation
                    and _text(getattr(outgoing, "authority_generation", None))
                    != expected_generation
                )
                or (
                    expected_run
                    and _text(getattr(outgoing, "run_id", None)) != expected_run
                )
            ):
                raise WorkflowActionError(
                    "focus handoff no longer owns the outgoing generation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            self.orchestrator._cancel_retry_for_issue(
                issue_id=issue.id,
                identifier=issue.identifier,
                project_id=self.project_id,
                reason="durable focus handoff",
                schedule_termination=False,
            )
            if self._project_running(issue) is not None:
                terminated = await self.orchestrator._terminate_running(
                    issue.id, cleanup_workspace=False
                )
                if not terminated:
                    raise WorkflowActionError(
                        "outgoing focus runtime is still retiring",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                self._assert_job_current(context)
            issue = await asyncio.to_thread(self._issue, context.job.task_id)
            async with self._dispatch_lane():
                await self._admit_dispatch(issue, durable_recovery=True)
                await self.orchestrator._dispatch(
                    issue,
                    attempt=None,
                    workflow_generation=context.job.generation,
                    status_managed_by_workflow=True,
                )
            entry = self._running(issue, context.job.generation)
            if entry is None:
                raise WorkflowActionError(
                    "focus handoff did not publish its successor generation",
                    category=WorkflowFailureCategory.TRANSIENT,
                    retryable=True,
                )
            await self._fence_dispatched_generation(issue, context)
            disposition = self._disposition(
                context,
                issue=issue,
                owner_id=(
                    _text(payload.get("owner_id"))
                    or _text(getattr(entry, "run_id", None))
                ),
                assignment_id=_text(getattr(entry, "assignment_id", None)),
                run_id=_text(getattr(entry, "run_id", None)),
            )
        elif action is ImplementationAction.WORKER_EXIT:
            running = self._project_running(issue)
            expected_generation = _text(payload.get("prior_generation"))
            expected_run = _text(payload.get("run_id") or payload.get("owner_id"))
            if running is not None and (
                (
                    expected_generation
                    and _text(getattr(running, "authority_generation", None))
                    != expected_generation
                )
                or (
                    expected_run
                    and _text(getattr(running, "run_id", None)) != expected_run
                )
            ):
                raise WorkflowActionError(
                    "worker-exit authority no longer owns the live generation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            requested_status = _text(payload.get("requested_status"))
            if running is not None and requested_status and canonicalize_status(
                requested_status
            ) != canonicalize_status(issue.state):
                self.orchestrator._cancel_retry_for_issue(
                    issue_id=issue.id,
                    identifier=issue.identifier,
                    project_id=self.project_id,
                    reason="durable worker-exit status handoff",
                    schedule_termination=False,
                )
                terminated = await self.orchestrator._terminate_running(
                    issue.id, cleanup_workspace=False
                )
                if not terminated:
                    raise WorkflowActionError(
                        "worker-exit runtime is still retiring",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    )
                self._assert_job_current(context)
            disposition = self._disposition(context, issue=issue)
        elif action is ImplementationAction.VALIDATION_SUBMISSION:
            integration = getattr(issue, "integration", None)
            expected_head = _text(context.job.expected_head_sha)
            if integration is None or (
                expected_head and _text(getattr(integration, "head_sha", None)) != expected_head
            ):
                raise WorkflowActionError(
                    "submission evidence does not match the exact accepted head",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            submitted_entry = self._project_running(issue)
            expected_generation = _text(payload.get("prior_generation"))
            expected_run = _text(payload.get("run_id") or payload.get("owner_id"))
            if submitted_entry is not None and (
                (
                    expected_generation
                    and _text(
                        getattr(submitted_entry, "authority_generation", None)
                    )
                    != expected_generation
                )
                or (
                    expected_run
                    and _text(getattr(submitted_entry, "run_id", None))
                    != expected_run
                )
            ):
                raise WorkflowActionError(
                    "submission no longer owns the accepted worker generation",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
            enqueue = getattr(self.orchestrator, "enqueue_durable_worker_submission", None)
            if callable(enqueue):
                await asyncio.to_thread(
                    enqueue, self.project_id, issue, integration
                )
            self._assert_job_current(context)
            self.orchestrator._cancel_retry_for_issue(
                issue_id=issue.id,
                identifier=issue.identifier,
                project_id=self.project_id,
                reason="durable validation submission",
            )
            disposition = self._disposition(context, issue=issue)
        elif action is ImplementationAction.AUTHORITY_REVOCATION:
            claim = self.orchestrator._owner_claim_for_issue(
                issue.id, self.project_id
            )
            direct_owner_only = (
                _text(payload.get("authority_kind")) == "direct_owner"
                or "claim_id" in payload
            )
            if direct_owner_only:
                expected_claim_id = _text(payload.get("claim_id"))
                # A missing old claim or an ABA replacement already satisfies
                # revocation of this exact authority generation. Never remove
                # the replacement on behalf of the superseded event.
                if not expected_claim_id or _text(
                    getattr(claim, "claim_id", None)
                ) != expected_claim_id:
                    disposition = self._disposition(context, issue=issue)
                    return await asyncio.to_thread(
                        self.receipts.record, context, disposition
                    )
                if claim is not None and _text(payload.get("owner_id")) and _text(
                    getattr(claim, "owner_login", None)
                ) != _text(payload.get("owner_id")):
                    raise WorkflowActionError(
                        "direct-owner identity changed before revocation",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=False,
                    )
            else:
                running = self._project_running(issue)
                expected_generation = _text(payload.get("prior_generation"))
                expected_run = _text(
                    payload.get("prior_run_id")
                    or payload.get("run_id")
                    or payload.get("owner_id")
                )
                if running is not None and (
                    not (expected_generation or expected_run)
                    or (
                        expected_generation
                        and _text(
                            getattr(running, "authority_generation", None)
                        )
                        != expected_generation
                    )
                    or (
                        expected_run
                        and _text(getattr(running, "run_id", None))
                        != expected_run
                    )
                ):
                    raise WorkflowActionError(
                        "revocation no longer owns the live implementation generation",
                        category=WorkflowFailureCategory.STALE_EVIDENCE,
                        retryable=False,
                    )
                self.orchestrator._cancel_retry_for_issue(
                    issue_id=issue.id,
                    identifier=issue.identifier,
                    project_id=self.project_id,
                    reason=(
                        _text(payload.get("reason"))
                        or "durable authority revocation"
                    ),
                    schedule_termination=False,
                )
                if self._project_running(issue) is not None:
                    terminated = await self.orchestrator._terminate_running(
                        issue.id, cleanup_workspace=False
                    )
                    if not terminated:
                        raise WorkflowActionError(
                            "revoked implementation runtime is still retiring",
                            category=WorkflowFailureCategory.TRANSIENT,
                            retryable=True,
                        )
                    self._assert_job_current(context)
            if direct_owner_only:
                try:
                    async with self._issue_authority_lane(issue):
                        self._assert_job_current(context)
                        removed = await asyncio.to_thread(
                            self.orchestrator.release_owner_claim,
                            issue_id=issue.id,
                            project_id=self.project_id,
                            expected_claim_id=expected_claim_id,
                        )
                except OSError as exc:
                    raise WorkflowActionError(
                        "direct-owner claim release was not durably persisted",
                        category=WorkflowFailureCategory.TRANSIENT,
                        retryable=True,
                    ) from exc
                if not removed:
                    remaining = self.orchestrator._owner_claim_for_issue(
                        issue.id, self.project_id
                    )
                    if _text(getattr(remaining, "claim_id", None)) == expected_claim_id:
                        raise WorkflowActionError(
                            "direct-owner claim release did not commit",
                            category=WorkflowFailureCategory.TRANSIENT,
                            retryable=True,
                        )
                notify = getattr(self.orchestrator, "_notify_state_only", None)
                if removed and callable(notify):
                    await asyncio.to_thread(notify)
            disposition = self._disposition(context, issue=issue)
        elif action is ImplementationAction.RETRY:
            disposition = self._disposition(context, issue=issue)
        else:  # pragma: no cover - enum exhaustiveness
            raise AssertionError(action)
        return await asyncio.to_thread(self.receipts.record, context, disposition)


class ProductionImplementationWorkflowBackend:
    """Generation/head-fenced backend for all nine implementation actions."""

    def __init__(
        self,
        effects: OrchestratorImplementationEffects,
    ) -> None:
        self.effects = effects

    @staticmethod
    def _requested_status(
        action: ImplementationAction, payload: Mapping[str, Any]
    ) -> str | None:
        requested = {
            ImplementationAction.START: IN_PROGRESS,
            ImplementationAction.RECOVERY: IN_PROGRESS,
            ImplementationAction.DIRECT_OWNER_CLAIM: IN_PROGRESS,
            ImplementationAction.FOCUS_HANDOFF: IN_PROGRESS,
            ImplementationAction.VALIDATION_SUBMISSION: READY_TO_INTEGRATE,
        }.get(action)
        if action is ImplementationAction.WORKER_EXIT:
            requested = _text(payload.get("requested_status")) or None
        return requested

    async def revalidate(self, context: WorkflowJobContext) -> RevalidationResult:
        self.effects._assert_job_current(context)
        issue = await asyncio.to_thread(self.effects._issue, context.job.task_id)
        self.effects._assert_job_current(context)
        expected_evidence = _text(context.job.expected_evidence_revision)
        observed_evidence = _text(issue_authority_version(issue))
        expected_head = _text(context.job.expected_head_sha).lower()
        observed_head = _text(issue_exact_head(issue)).lower()
        payload = context.job.payload or {}
        workspace_path = _text(payload.get("workspace_path"))
        retry_head = getattr(self.effects.orchestrator, "_retry_issue_head", None)
        if expected_head and not observed_head and workspace_path and callable(retry_head):
            observed_head = _text(retry_head(issue, workspace_path)).lower()
        head_current = not expected_head or expected_head == observed_head
        evidence_current = not expected_evidence or expected_evidence == observed_evidence
        action = ImplementationAction(context.job.action)
        requested_status = self._requested_status(action, payload)
        expected_status = _text(payload.get("expected_status"))
        observed_status = canonicalize_status(issue.state)
        status_owned = bool(
            expected_status
            and observed_status
            in {
                canonicalize_status(expected_status),
                canonicalize_status(requested_status)
                if requested_status
                else canonicalize_status(expected_status),
            }
        )
        exact_effect = False
        if head_current and status_owned and not evidence_current:
            if action in {
                ImplementationAction.START,
                ImplementationAction.RECOVERY,
                ImplementationAction.FOCUS_HANDOFF,
            }:
                exact_effect = (
                    self.effects._running(issue, context.job.generation) is not None
                )
            elif action is ImplementationAction.DUPLICATE_SCREENING:
                assessment = assess_screening(
                    issue, detector_version=DUPLICATE_DETECTOR_VERSION
                )
                exact_effect = bool(
                    assessment.state is ScreeningState.RUNNING
                    and assessment.record is not None
                    and assessment.record.claim_id == context.job.generation
                )
            if not exact_effect:
                receipt = await asyncio.to_thread(
                    self.effects.receipts.get, context
                )
                exact_effect = receipt is not None
        current = head_current and (evidence_current or exact_effect)
        # The shared worker compares the returned evidence revision with the
        # job's original fence after consulting ``current``.  Once this exact
        # generation has applied its own status transition, the tracker
        # revision necessarily differs from that original fence.  The durable
        # receipt/live-generation proof above is the evidence that the change
        # belongs to this job, so preserve the job fence for that recovery
        # case.  Returning the newer tracker revision would make the generic
        # worker supersede the job before it could inspect its receipt and
        # finish the crash-safe replay.
        accepted_evidence = (
            expected_evidence if exact_effect and not evidence_current else observed_evidence
        )
        return RevalidationResult(
            context.job.generation,
            evidence_revision=accepted_evidence or None,
            head_sha=observed_head or None,
            current=current,
        )

    async def observe_disposition(
        self, context: WorkflowJobContext
    ) -> ImplementationDisposition | None:
        self.effects._assert_job_current(context)
        disposition = await self.effects.observe(context)
        self.effects._assert_job_current(context)
        return disposition

    async def execute(
        self, context: WorkflowJobContext
    ) -> ImplementationExecutionResult:
        disposition = await self.effects.apply(context)
        status = {
            ImplementationAction.START: "started",
            ImplementationAction.DIRECT_OWNER_CLAIM: "owner_claimed",
            ImplementationAction.DUPLICATE_SCREENING: "duplicate_screened",
            ImplementationAction.FOCUS_HANDOFF: "handoff_recorded",
            ImplementationAction.WORKER_EXIT: "worker_completed",
            ImplementationAction.VALIDATION_SUBMISSION: "submitted",
            ImplementationAction.AUTHORITY_REVOCATION: "revoked",
            ImplementationAction.RETRY: "retry_scheduled",
            ImplementationAction.RECOVERY: "recovered",
        }[ImplementationAction(context.job.action)]
        return ImplementationExecutionResult(status, status, disposition)

    async def build_transition(
        self,
        context: WorkflowJobContext,
        verification: VerificationResult,
    ) -> TransitionIntent | None:
        action = ImplementationAction(context.job.action)
        payload = context.job.payload or {}
        requested = self._requested_status(action, payload)
        if requested is None:
            return None
        self.effects._assert_job_current(context)
        issue = await asyncio.to_thread(self.effects._issue, context.job.task_id)
        self.effects._assert_job_current(context)
        current = canonicalize_status(issue.state)
        expected_status = _text(payload.get("expected_status"))
        if expected_status and current not in {
            canonicalize_status(expected_status),
            canonicalize_status(requested),
        }:
            raise WorkflowActionError(
                "task status changed outside the implementation disposition",
                category=WorkflowFailureCategory.STALE_EVIDENCE,
                retryable=False,
            )
        if action in {
            ImplementationAction.START,
            ImplementationAction.RECOVERY,
            ImplementationAction.FOCUS_HANDOFF,
        }:
            raw_disposition = verification.receipt.get("disposition")
            disposition = (
                ImplementationDisposition.from_dict(raw_disposition)
                if isinstance(raw_disposition, Mapping)
                else None
            )
            expected_assignment = _text(
                getattr(disposition, "assignment_id", None)
            )
            if expected_assignment and _text(
                getattr(issue, "assignment_id", None)
            ) != expected_assignment:
                raise WorkflowActionError(
                    "implementation assignment changed before status transition",
                    category=WorkflowFailureCategory.STALE_EVIDENCE,
                    retryable=False,
                )
        if current == canonicalize_status(requested):
            return None
        actor = "oompah"
        authority = TransitionAuthority.ORCHESTRATOR
        evidence_generation = context.job.generation
        if action in {
            ImplementationAction.START,
            ImplementationAction.RECOVERY,
            ImplementationAction.FOCUS_HANDOFF,
        }:
            # The durable job generation authorizes the effect, while the
            # assignment allocated by ``_dispatch`` authorizes the tracker
            # status transition.  They are deliberately distinct identities.
            # Carry the assignment proven by the exact disposition so the
            # transition service compares like with like; using the job
            # generation here leaves a live worker attached to an Open task.
            raw_disposition = verification.receipt.get("disposition")
            disposition = (
                ImplementationDisposition.from_dict(raw_disposition)
                if isinstance(raw_disposition, Mapping)
                else None
            )
            evidence_generation = _text(
                getattr(disposition, "assignment_id", None)
            )
            if not evidence_generation:
                raise WorkflowActionError(
                    "implementation transition has no exact assignment identity",
                    category=WorkflowFailureCategory.POLICY,
                    retryable=False,
                )
        if action is ImplementationAction.VALIDATION_SUBMISSION:
            # A restart-recovered accepted submission can still be owned by a
            # live direct-owner claim.  The tracker assignment is that claim,
            # not the fact-derived workflow job generation. Ordinary worker
            # submissions likewise carry the assignment captured when the
            # accepted head was published.  Prefer those immutable payload
            # identities, then the freshly read tracker assignment; the
            # finalizer uses the same direct-owner identity and cannot retire
            # an ABA replacement.
            evidence_generation = (
                _text(payload.get("owner_claim_id"))
                or _text(payload.get("assignment_id"))
                or _text(getattr(issue, "assignment_id", None))
                or evidence_generation
            )
        if action is ImplementationAction.DIRECT_OWNER_CLAIM:
            actor = _text(payload.get("owner_id"))
            evidence_generation = _text(payload.get("claim_id"))
            if not actor:
                raise WorkflowActionError(
                    "direct-owner transition has no owner identity",
                    category=WorkflowFailureCategory.POLICY,
                    retryable=False,
                )
            if not evidence_generation:
                raise WorkflowActionError(
                    "direct-owner transition has no durable claim identity",
                    category=WorkflowFailureCategory.POLICY,
                    retryable=False,
                )
            authority = TransitionAuthority.PROJECT_OWNER
        return TransitionIntent(
            project_id=context.job.project_id,
            task_id=context.job.task_id,
            expected_status=issue.state,
            expected_version=issue_authority_version(issue),
            requested_status=requested,
            actor=actor,
            authority=authority,
            reason_code=f"implementation.{action.value}",
            idempotency_key=f"{context.job.idempotency_key}:transition",
            originating_job=context.job.job_id,
            evidence_generation=evidence_generation,
            exact_head=(
                context.job.expected_head_sha
                if _HEAD_RE.fullmatch(_text(context.job.expected_head_sha).lower())
                else None
            ),
        )

    async def compensate_transition_failure(
        self,
        context: WorkflowJobContext,
        failure: TransitionOutcome | WorkflowActionError,
    ) -> Mapping[str, Any] | None:
        """Release only the direct-owner claim whose transition failed."""

        if (
            ImplementationAction(context.job.action)
            is not ImplementationAction.DIRECT_OWNER_CLAIM
        ):
            return None
        payload = context.job.payload or {}
        claim_id = _text(payload.get("claim_id"))
        owner_id = _text(payload.get("owner_id"))
        if not claim_id or not owner_id:
            raise WorkflowActionError(
                "direct-owner compensation is missing durable claim identity",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        issue = None
        issue_id = _text(payload.get("issue_id"))
        if not issue_id:
            issue = await asyncio.to_thread(
                self.effects._issue,
                context.job.task_id,
            )
            issue_id = _text(issue.id)
        if not issue_id:
            raise WorkflowActionError(
                "direct-owner compensation is missing durable task identity",
                category=WorkflowFailureCategory.POLICY,
                retryable=False,
            )
        try:
            released = await asyncio.to_thread(
                self.effects.orchestrator.release_owner_claim,
                issue_id=issue_id,
                project_id=self.effects.project_id,
                expected_claim_id=claim_id,
            )
            current = await asyncio.to_thread(
                self.effects.orchestrator._owner_claim_for_issue,
                issue_id,
                self.effects.project_id,
            )
        except Exception as exc:
            raise WorkflowActionError(
                f"direct-owner transition compensation failed: {exc}",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            ) from exc
        if _text(getattr(current, "claim_id", None)) == claim_id:
            raise WorkflowActionError(
                "direct-owner transition compensation did not release the exact claim",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )
        receipt = await asyncio.to_thread(self.effects.receipts.get, context)
        if receipt is None:
            if issue is None:
                try:
                    issue = await asyncio.to_thread(
                        self.effects._issue,
                        context.job.task_id,
                    )
                except Exception:  # tracker object may be permanently absent
                    issue = SimpleNamespace(
                        work_branch=None,
                        branch_name=None,
                        head_sha=None,
                        review_head=None,
                        integration=None,
                    )
            receipt = self.effects._disposition(
                context,
                issue=issue,
                owner_id=owner_id,
            )
        revoked = replace(
            receipt,
            state=ImplementationState.REVOKED,
            lease_expires_at=None,
            authority_revision=None,
        )
        notify = getattr(self.effects.orchestrator, "_notify_state_only", None)
        if released and callable(notify):
            await asyncio.to_thread(notify)
        reason_code = (
            failure.reason_code
            if isinstance(failure, TransitionOutcome)
            else f"workflow.{failure.category.value}"
        )
        return {
            "kind": "direct_owner_claim_released",
            "claim_id": claim_id,
            "owner_id": owner_id,
            "released": bool(released),
            "replacement_claim_id": _text(getattr(current, "claim_id", None))
            or None,
            "reason_code": reason_code,
            "disposition": revoked.to_dict(),
        }

    async def finalize_transition(
        self,
        context: WorkflowJobContext,
        transition: TransitionOutcome,
    ) -> None:
        """Retire direct-owner authority only after accepted Ready commit."""

        if (
            ImplementationAction(context.job.action)
            is not ImplementationAction.VALIDATION_SUBMISSION
        ):
            return
        if canonicalize_status(transition.observed_status) != READY_TO_INTEGRATE:
            return
        retire = getattr(
            self.effects.orchestrator,
            "_retire_owner_claim_after_validation_transition",
            None,
        )
        if not callable(retire):
            return
        retired = await asyncio.to_thread(retire, context.job)
        if retired:
            return
        payload = context.job.payload or {}
        claim_id = _text(payload.get("owner_claim_id"))
        if not claim_id:
            return
        issue = await asyncio.to_thread(self.effects._issue, context.job.task_id)
        current = await asyncio.to_thread(
            self.effects.orchestrator._owner_claim_for_issue,
            issue.id,
            self.effects.project_id,
        )
        if _text(getattr(current, "claim_id", None)) == claim_id:
            raise WorkflowActionError(
                "accepted direct-owner submission is waiting for exact claim retirement",
                category=WorkflowFailureCategory.TRANSIENT,
                retryable=True,
            )


def build_implementation_workflow_handlers(
    orchestrator: Any, binding: Any
) -> Mapping[str, ImplementationWorkflowHandler]:
    """Build total project-routed handler coverage for implementation work."""

    effects = OrchestratorImplementationEffects(
        orchestrator,
        project_id=binding.project_id,
        tracker=binding.tracker,
    )
    backend = ProductionImplementationWorkflowBackend(effects)
    handler = ImplementationWorkflowHandler(backend)
    if str(getattr(orchestrator.config, "workflow_engine_mode", "off")).lower() == "enforce":
        # Migrate the prior durable owner-claim store one task at a time.  The
        # semantic event is idempotent across restart and keeps a pre-cutover
        # direct owner from being mistaken for an orphaned implementation.
        with orchestrator._owner_claims_lock:
            claims = tuple(orchestrator.state.owner_claims.values())
        now = datetime.now(timezone.utc).timestamp()
        try:
            issues = tuple(binding.tracker.fetch_all_issues() or ())
        except Exception:
            issues = ()
        by_id = {_text(getattr(issue, "id", None)): issue for issue in issues}
        for claim in claims:
            if claim.project_id != binding.project_id or claim.expires_at <= now:
                continue
            issue = by_id.get(_text(claim.issue_id))
            if issue is None:
                continue
            issue_project = _text(getattr(issue, "project_id", None))
            if issue_project and issue_project != binding.project_id:
                continue
            issue.project_id = binding.project_id
            status = canonicalize_status(issue.state)
            direct_owner_active = (
                not claim.retirement_pending
                and status != IN_VALIDATION
                and not is_terminal_status(status)
            )
            action = (
                ImplementationAction.DIRECT_OWNER_CLAIM
                if direct_owner_active
                else ImplementationAction.AUTHORITY_REVOCATION
            )
            payload = {
                "owner_id": claim.owner_login,
                "issue_id": issue.id,
                "claim_id": claim.claim_id,
                "expected_status": issue.state,
                "work_branch": _text(issue.work_branch or issue.branch_name),
                "head_sha": _text(issue_exact_head(issue)),
            }
            if direct_owner_active:
                payload["lease_expires_at"] = _iso_from_epoch(claim.expires_at)
            else:
                payload.update(
                    {
                        "authority_kind": "direct_owner",
                        "reason": "task no longer has active owner work",
                    }
                )
            binding.implementation_controller.schedule_event(
                project_id=binding.project_id,
                task_id=issue.identifier,
                action=action,
                payload=payload,
                expected_head_sha=issue_exact_head(issue),
                expected_evidence_revision=issue_authority_version(issue),
                priority=0,
            )
    return {action: handler for action in IMPLEMENTATION_ACTIONS}


__all__ = [
    "ImplementationReceiptStore",
    "OrchestratorImplementationEffects",
    "ProductionImplementationWorkflowBackend",
    "build_implementation_workflow_handlers",
]
