"""Stalled-task remediation watchdog.

Periodically audits tasks stuck in stalled states (Needs Human, Needs CI Fix,
Needs Rebase, Needs Answer, Blocked/Stalled) across all managed projects and
performs safe, evidence-backed remediations when the evidence supports them.

Design principles
-----------------

* **Conservative by default.** When evidence is ambiguous or incomplete, the
  watchdog classifies the task as ``insufficient_evidence`` and leaves it
  alone. This guarantees genuine human blockers are never silently cleared.

* **Idempotent.** Each task carries a sentinel comment written by the watchdog
  on its most recent action. Before acting again, the watchdog checks whether
  the task has changed since that comment — if not, it skips re-filing to
  prevent duplicate comments on repeated runs.

* **Pure classification.** :func:`classify_stalled_task` inspects task state
  and comment history passed in by the orchestrator and returns a
  :class:`StalledTaskDecision` without performing any side effects. The
  orchestrator owns the I/O.

* **Telemetry.** :func:`run_watchdog_audit` returns a
  :class:`WatchdogAuditResult` with full counts, last-run time, and per-task
  decisions. The orchestrator surfaces these in the API/dashboard maintenance
  snapshot.

States audited
--------------
* ``Needs Human``   — agent requested human input; may have resolved itself.
* ``Needs CI Fix``  — waiting for CI to pass; may now be passing or merged.
* ``Needs Rebase``  — branch conflict; may have been rebased or merged.
* ``Needs Answer``  — waiting for a human answer to a clarifying question.
* Any custom ``Blocked`` or ``Stalled`` status.

Classification outcomes
-----------------------
* ``actionable``            — safe automated remediation is available.
* ``human_blocked``         — a genuine open question or human dependency; leave
                              untouched.
* ``obsolete``              — the underlying work is done/superseded; can be
                              archived.
* ``insufficient_evidence`` — not enough information to act safely; skip.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import Callable, Mapping
from typing import Any

from oompah.statuses import (
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    canonicalize_status,
)
from oompah.archived_audit_requests import request_archived_audit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Environment variable that controls the watchdog interval.
ENV_VAR = "OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS"

#: Default watchdog interval: 5 minutes.
DEFAULT_INTERVAL_SECONDS: int = 300

#: States the watchdog audits.
STALLED_STATES: frozenset[str] = frozenset(
    {NEEDS_HUMAN, NEEDS_CI_FIX, NEEDS_REBASE, NEEDS_ANSWER}
)

#: Additional status keywords treated as stalled (matched case-insensitively).
STALLED_STATUS_KEYWORDS: tuple[str, ...] = ("blocked", "stalled")

#: Sentinel prefix written in watchdog comments to detect previous actions.
WATCHDOG_COMMENT_MARKER = "[watchdog:stalled_task]"

#: Maximum length of evidence strings stored in decisions.
_MAX_EVIDENCE_LEN = 500

#: Number of recent comments to inspect when classifying a task.
_COMMENT_INSPECTION_WINDOW = 10

#: Regex patterns that indicate a human question was genuinely asked.
_QUESTION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\?\s*$", re.MULTILINE),       # Ends with a question mark
    re.compile(r"\bquestion\b", re.IGNORECASE),
    re.compile(r"\bcan you\b", re.IGNORECASE),
    re.compile(r"\bwould you\b", re.IGNORECASE),
    re.compile(r"\bcould you\b", re.IGNORECASE),
    re.compile(r"\bplease (clarify|confirm|advise|review|check)\b", re.IGNORECASE),
    re.compile(r"\bneed(s)? (your|human|manual|operator)\b", re.IGNORECASE),
)

#: Regex patterns that indicate a "focus handoff" completion with a pending
#: question (versus an accidental stall with no real question).
_HANDOFF_WITH_QUESTION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"focus handoff", re.IGNORECASE),
    re.compile(r"needs.{0,20}answer", re.IGNORECASE),
    re.compile(r"human.{0,20}needed", re.IGNORECASE),
    re.compile(r"waiting.{0,30}(response|input|approval|review)", re.IGNORECASE),
    re.compile(r"blocked.{0,30}(human|operator|you|team)", re.IGNORECASE),
)

# A handoff can contain words such as "human", "review", or "question"
# without representing an unanswered product decision.  These patterns are
# deliberately narrower than the legacy question patterns: they identify a
# decision or authority that a human must actually make.
_HUMAN_DECISION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(
        r"\b(should we|which (?:option|approach|one)|choose|decide|decision|"
        r"product requirement|architecture decision|requirements? (?:are|need)|"
        r"approve|approval|authorize|authorization|authority|go ahead)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(waiting|blocked|need(?:s)?|requires?)\b.{0,45}\b(approval|"
        r"authorization|authority|decision|answer|clarification|direction)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bhuman\b.{0,30}\b(review|input|help)\b", re.IGNORECASE),
)

#: Patterns that indicate a successful completion *without* a blocker.
#: If these appear in the last agent comment and there is no question pattern,
#: the NEEDS_HUMAN transition is likely accidental.
_COMPLETION_WITHOUT_QUESTION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\b(completed|done|finished|implemented|fixed|closed|pushed|committed)\b",
               re.IGNORECASE),
    re.compile(r"focus.{0,20}complete", re.IGNORECASE),
    re.compile(r"agent completed", re.IGNORECASE),
    re.compile(r"set.status.*done", re.IGNORECASE),
)

#: Patterns that indicate CI is now passing in comments.
_CI_PASSING_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bCI.{0,20}(pass(?:ing|ed)?|green|succeed(?:ed)?|success(?:ful)?)\b",
               re.IGNORECASE),
    re.compile(r"\bcheck(?:s)?.{0,20}(pass(?:ing|ed)?|green|succeed(?:ed)?|success(?:ful)?)\b",
               re.IGNORECASE),
    re.compile(r"\btests?.{0,20}(pass(?:ing|ed)?|green|succeed(?:ed)?|success(?:ful)?)\b",
               re.IGNORECASE),
    re.compile(r"\bmerged\b", re.IGNORECASE),
    re.compile(r"\bPR.{0,20}(closed|merged|landed)\b", re.IGNORECASE),
)

#: Patterns that indicate a rebase or merge conflict has been resolved.
_REBASE_RESOLVED_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\b(rebase|conflict).{0,30}(resolved|fixed|done|clean(?:ed)?|clear(?:ed)?)\b",
               re.IGNORECASE),
    re.compile(r"\bno.{0,20}conflict\b", re.IGNORECASE),
    re.compile(r"\bclean\b.{0,20}\bno\b.{0,20}\bconflict\b", re.IGNORECASE),
    re.compile(r"\bmerged\b", re.IGNORECASE),
    re.compile(r"\bPR.{0,20}(closed|merged|landed)\b", re.IGNORECASE),
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StalledTaskDecision:
    """Outcome of classifying a single stalled task.

    Attributes:
        task_id:            The task/issue identifier.
        project_id:         The project that owns the task.
        stalled_status:     The current status that triggered the audit.
        classification:     One of ``actionable``, ``human_blocked``,
                            ``obsolete``, ``insufficient_evidence``.
        action:             The remediation taken (or ``"none"`` if no action).
        evidence:           Human-readable summary of evidence for the decision.
        comment_posted:     Whether a watchdog comment was posted on the task.
        watchdog_run_id:    Monotonic run counter for correlation.
        already_actioned:   True if the watchdog already acted on this task in
                            a prior run and nothing has changed since.
        evidence_head:      The exact accepted-head SHA the evidence refers
                            to.  Recorded so a race between the authoritative
                            gate and the watchdog cannot report a decision on
                            a stale head without leaving a durable trace.
        evidence_result:    The authoritative combined-tree gate verdict
                            observed for that head (``passed``, ``failed``,
                            ``needs_rebase``, ``interrupted``, etc.).  Empty
                            when no authoritative outcome was consulted.
        evidence_generation: Compare-and-set generation captured with the
                            authoritative evidence.  A gate completion or
                            integration-row transition that changes this
                            token invalidates the classification.
    """

    task_id: str
    project_id: str | None
    stalled_status: str
    classification: str
    action: str
    evidence: str
    comment_posted: bool = False
    watchdog_run_id: int = 0
    already_actioned: bool = False
    evidence_head: str = ""
    evidence_result: str = ""
    evidence_generation: str = ""


@dataclass(frozen=True)
class WatchdogEvidence:
    """Current machine evidence used to classify a stalled task.

    The watchdog receives this small, tracker-neutral envelope from the
    orchestrator.  The nested values intentionally remain mappings/objects so
    SCM and terminal-audit packages can evolve without coupling this module to
    either provider implementation.  Missing values mean *unknown*, never
    false.  In particular, a provider exception is represented explicitly in
    ``provider`` instead of being inferred from an empty review list.

    ``gate`` carries the latest authoritative combined-tree quality-gate
    outcome (head, status, generation, verdict).  It dominates the softer
    ``ci`` signal so a newer failing result cannot be overridden by an older
    focused/passing SCM check.  ``integration`` exposes the tracker's
    integration record (accepted head, task branch, integration state,
    authority generation) so the classifier can require exact accepted-head
    and branch identity before recommending an automatic reopen.
    """

    review: Any | None = None
    branch: Any | None = None
    audit: Any | None = None
    ci: Any | None = None
    provider: Any | None = None
    issue: Any | None = None
    gate: Any | None = None
    integration: Any | None = None
    errors: tuple[str, ...] = ()


@dataclass
class WatchdogAuditResult:
    """Aggregate result of one watchdog audit pass.

    Attributes:
        run_id:             Monotonically increasing run counter.
        started_at:         ISO-8601 UTC timestamp when the audit started.
        finished_at:        ISO-8601 UTC timestamp when the audit finished
                            (or None if still running).
        duration_s:         Elapsed seconds for the completed run.
        tasks_audited:      Total tasks inspected.
        tasks_actionable:   Count classified as actionable.
        tasks_human_blocked: Count classified as human_blocked (untouched).
        tasks_obsolete:     Count classified as obsolete.
        tasks_insufficient_evidence: Count classified as insufficient_evidence.
        actions_taken:      Total automated changes performed.
        actions_skipped:    Tasks skipped (already actioned, or in-flight).
        decisions:          Per-task decision records.
        errors:             Any non-fatal errors during the run.
    """

    run_id: int = 0
    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0.0
    tasks_audited: int = 0
    tasks_actionable: int = 0
    tasks_human_blocked: int = 0
    tasks_obsolete: int = 0
    tasks_insufficient_evidence: int = 0
    actions_taken: int = 0
    actions_skipped: int = 0
    decisions: list[StalledTaskDecision] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict for inclusion in the maintenance snapshot."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": self.duration_s,
            "tasks_audited": self.tasks_audited,
            "tasks_actionable": self.tasks_actionable,
            "tasks_human_blocked": self.tasks_human_blocked,
            "tasks_obsolete": self.tasks_obsolete,
            "tasks_insufficient_evidence": self.tasks_insufficient_evidence,
            "actions_taken": self.actions_taken,
            "actions_skipped": self.actions_skipped,
            "error_count": len(self.errors),
            "errors": self.errors[:5],  # cap for snapshot size
            "decisions": [
                {
                    "task_id": d.task_id,
                    "project_id": d.project_id,
                    "stalled_status": d.stalled_status,
                    "classification": d.classification,
                    "action": d.action,
                    "evidence": d.evidence[:200],
                    "comment_posted": d.comment_posted,
                    "already_actioned": d.already_actioned,
                    "evidence_head": d.evidence_head,
                    "evidence_result": d.evidence_result,
                    "evidence_generation": d.evidence_generation,
                }
                for d in self.decisions
            ],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_stalled_status(status: str | None) -> bool:
    """Return True if *status* is one the watchdog should audit."""
    canonical = canonicalize_status(status)
    if canonical in STALLED_STATES:
        return True
    if status:
        lower = status.lower()
        return any(kw in lower for kw in STALLED_STATUS_KEYWORDS)
    return False


def _text_has_question(text: str) -> bool:
    """Return True if *text* contains genuine question patterns."""
    return any(p.search(text) for p in _QUESTION_PATTERNS)


def _text_has_human_decision(text: str) -> bool:
    """Return True when *text* asks for a human decision or authority."""
    return any(p.search(text) for p in _HUMAN_DECISION_PATTERNS)


def _handoff_has_human_decision(text: str) -> bool:
    """Return True for an explicit decision in a handoff, not mere review."""
    if not _text_has_human_decision(text):
        return False
    # "Focus handoff: needs human review" is required routing syntax, not an
    # unanswered decision.  Approval/authority/answer language remains
    # actionable human-dependency evidence.
    review_only = re.compile(
        r"\bhuman\b.{0,30}\b(review|input|help)\b", re.IGNORECASE
    )
    without_review = review_only.sub("", text)
    return _text_has_human_decision(without_review)


def _text_has_handoff_question(text: str) -> bool:
    """Return True if *text* signals a focus handoff with a pending question."""
    return any(p.search(text) for p in _HANDOFF_WITH_QUESTION_PATTERNS)


def _text_has_completion_without_question(text: str) -> bool:
    """Return True if *text* signals agent completion with no question."""
    return any(p.search(text) for p in _COMPLETION_WITHOUT_QUESTION_PATTERNS)


def _text_has_ci_passing(text: str) -> bool:
    """Return True if *text* mentions CI passing or PR merged."""
    return any(p.search(text) for p in _CI_PASSING_PATTERNS)


def _text_has_rebase_resolved(text: str) -> bool:
    """Return True if *text* mentions conflict/rebase resolved."""
    return any(p.search(text) for p in _REBASE_RESOLVED_PATTERNS)


def _get_comment_body(comment: dict) -> str:
    """Extract body text from a comment dict (handles various field names)."""
    return str(
        comment.get("body")
        or comment.get("text")
        or comment.get("message")
        or comment.get("content")
        or ""
    )


def _get_comment_author(comment: dict) -> str:
    """Extract author from a comment dict."""
    return str(
        comment.get("author")
        or comment.get("user", {}).get("login", "")
        if isinstance(comment.get("user"), dict)
        else comment.get("author", "")
        or ""
    )


def _comment_time(comment: Mapping[str, Any]) -> datetime | None:
    """Return a parsed comment timestamp when the tracker supplied one."""
    for key in ("created_at", "created", "timestamp", "date", "updated_at"):
        value = comment.get(key)
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                return datetime.fromtimestamp(float(value), tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                continue
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                continue
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _ordered_comments(comments: list[dict]) -> list[dict]:
    """Return comments oldest-first, using timestamps when they are present."""
    if not comments or not all(_comment_time(comment) is not None for comment in comments):
        return list(comments)
    return sorted(
        comments,
        key=lambda comment: _comment_time(comment)
        or datetime.min.replace(tzinfo=timezone.utc),
    )


def _as_mapping(value: Any) -> dict[str, Any]:
    """Coerce a provider/audit object into a shallow mapping for inspection."""
    if isinstance(value, Mapping):
        return dict(value)
    # Test doubles and failed optional integrations often expose arbitrary
    # attributes.  Treat those as unavailable rather than truthy evidence.
    if value is not None and value.__class__.__module__ == "unittest.mock":
        return {}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            converted = to_dict()
        except Exception:  # noqa: BLE001 - evidence must never break the audit
            converted = None
        if isinstance(converted, Mapping):
            return dict(converted)
    if value is None or isinstance(value, (str, bytes, int, float, bool)):
        return {}
    fields = (
        "id", "number", "state", "review_state", "source_branch", "target_branch",
        "head_sha", "merged", "merged_at", "branch", "branch_ref", "canonical_ref",
        "exists", "branch_exists", "on_target", "on_canonical", "status", "verdict",
        "failure_classification", "failure_reason", "failure", "error", "available",
        "provider_available", "ci_status", "mergeable_state", "review_number",
        "review_url", "review_head", "work_branch", "branch_name", "branch_key",
    )
    result: dict[str, Any] = {}
    for field_name in fields:
        try:
            field_value = getattr(value, field_name, None)
        except Exception:  # noqa: BLE001 - provider objects are external evidence
            continue
        if field_value is not None and not callable(field_value):
            result[field_name] = field_value
    return result


def _nested_mapping(value: Any, *keys: str) -> dict[str, Any]:
    """Return the first mapping-like child under *keys*."""
    mapping = _as_mapping(value)
    for key in keys:
        child_mapping = _as_mapping(mapping.get(key))
        if child_mapping:
            return child_mapping
    return {}


def _latest_audit_mapping(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Extract the newest attempt/result from a terminal-audit envelope."""
    candidates: list[Any] = []
    for key in ("pending_chain", "attempt_history", "attempts"):
        raw = audit.get(key)
        if isinstance(raw, list):
            candidates.extend(raw)
    for candidate in reversed(candidates):
        candidate_mapping = _as_mapping(candidate)
        attempts = candidate_mapping.get("attempts")
        if isinstance(attempts, list) and attempts:
            latest_attempt = _as_mapping(attempts[-1])
            if latest_attempt:
                return {**candidate_mapping, **latest_attempt}
        if candidate_mapping:
            return candidate_mapping
    return {}


def _first_value(*mappings: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    """Find the first non-empty value for *keys* across mappings."""
    for mapping in mappings:
        for key in keys:
            value = mapping.get(key)
            if value is not None and value != "":
                return value
    return None


def _string_signal(value: Any) -> str:
    """Stringify enum-like provider values by their wire value."""
    raw = getattr(value, "value", value)
    return str(raw).strip().lower().replace("-", "_") if raw not in (None, "") else ""


def _normalise_watchdog_evidence(evidence: Any) -> WatchdogEvidence:
    """Accept the public envelope or a plain mapping from integrations/tests."""
    if isinstance(evidence, WatchdogEvidence):
        return evidence
    mapping = _as_mapping(evidence)
    review = mapping.get("review") or mapping.get("scm_review")
    if review is None:
        review = {
            key: mapping[key]
            for key in (
                "review_state", "state", "merged", "merged_pr", "is_merged",
                "review_number", "review_url", "review_head",
            )
            if key in mapping
        }
    branch = mapping.get("branch") or mapping.get("scm_branch")
    if branch is None:
        branch = {
            key: mapping[key]
            for key in (
                "canonical_ref", "canonical_branch", "target_ref", "target_branch",
                "audit_branch", "branch_ref", "branch_exists", "exists", "on_target",
                "on_canonical", "scm_state", "resolution",
            )
            if key in mapping
        }
    audit = mapping.get("audit") or mapping.get("terminal_audit")
    if audit is None:
        audit = {
            key: mapping[key]
            for key in (
                "audit_verdict", "verdict", "failure_classification", "classification",
                "failure_reason", "audit_branch", "canonical_ref", "pending_chain",
            )
            if key in mapping
        }
    provider = mapping.get("provider") or mapping.get("provider_status")
    if provider is None:
        provider = {
            key: mapping[key]
            for key in (
                "provider_available", "available", "healthy", "provider_error",
                "provider_failure", "scm_error", "technical_blocker", "error", "last_error",
            )
            if key in mapping
        }
    gate = mapping.get("gate") or mapping.get("quality_gate")
    if gate is None:
        gate = {
            key: mapping[key]
            for key in (
                "gate_status", "gate_head_sha", "gate_verdict",
                "gate_generation", "gate_owner", "gate_completed_at",
            )
            if key in mapping
        } or None
    integration = mapping.get("integration") or mapping.get("integration_record")
    if integration is None:
        integration = {
            key: mapping[key]
            for key in (
                "accepted_head_sha", "integration_state", "task_branch",
                "authority_generation", "integrated_sha",
            )
            if key in mapping
        } or None
    return WatchdogEvidence(
        review=review,
        branch=branch,
        audit=audit,
        ci=mapping.get("ci") or mapping.get("ci_status"),
        provider=provider,
        issue=mapping.get("issue") or mapping.get("tracker"),
        gate=gate,
        integration=integration,
        errors=tuple(
            str(error) for error in (mapping.get("errors") or ()) if str(error)
        ),
    )


def _normalise_head(value: Any) -> str:
    """Return a lowercase hex SHA fragment, or empty string."""
    text = str(value or "").strip().lower()
    return text if text else ""


_PASSING_STATUSES: frozenset[str] = frozenset(
    {"passed", "pass", "green", "success", "successful", "not_configured"}
)
_FAILING_STATUSES: frozenset[str] = frozenset(
    {
        "failed", "fail", "failure", "red", "error", "errored",
        "ci_failure", "needs_rebase", "timed_out", "timeout", "interrupted",
        "infrastructure_error",
    }
)


def _evidence_signals(evidence: Any) -> dict[str, Any]:
    """Extract conservative, forge-neutral signals from current evidence."""
    envelope = _normalise_watchdog_evidence(evidence)
    review = _as_mapping(envelope.review)
    branch = _as_mapping(envelope.branch)
    audit = _as_mapping(envelope.audit)
    ci = _as_mapping(envelope.ci)
    provider = _as_mapping(envelope.provider)
    issue = _as_mapping(envelope.issue)
    gate = _as_mapping(envelope.gate)
    integration = _as_mapping(envelope.integration)

    if isinstance(envelope.ci, str):
        ci = {"status": envelope.ci}
    review_detail = _nested_mapping(review, "review", "current", "latest")
    if review_detail:
        review = {**review, **review_detail}
    audit_detail = _nested_mapping(audit, "latest", "latest_attempt", "result")
    if not audit_detail:
        audit_detail = _latest_audit_mapping(audit)
    if audit_detail:
        audit = {**audit, **audit_detail}
    branch_detail = _nested_mapping(branch, "branch", "scm", "current")
    if branch_detail:
        branch = {**branch, **branch_detail}

    review_state = _string_signal(
        _first_value(review, issue, keys=("review_state", "state", "status"))
    )
    audit_verdict = _string_signal(
        _first_value(audit, keys=("verdict", "audit_verdict", "result"))
    )
    failure_classification = _string_signal(
        _first_value(
            audit,
            provider,
            keys=("failure_classification", "classification", "failure_type"),
        )
    )
    ci_status = _string_signal(
        _first_value(ci, review, keys=("ci_status", "status", "state", "verdict"))
    )

    merged_value = _first_value(
        review, issue, keys=("merged", "is_merged", "merged_at", "merged_pr")
    )
    merged = bool(merged_value) or review_state == "merged"
    provider_error = _first_value(
        provider,
        audit,
        keys=(
            "error", "provider_error", "provider_failure", "scm_error",
            "technical_blocker", "failure_reason", "failure", "last_error",
        ),
    )
    provider_available = _first_value(
        provider, keys=("available", "provider_available", "healthy")
    )
    branch_exists = _first_value(branch, keys=("exists", "branch_exists", "present"))
    canonical_ref = _first_value(
        branch,
        audit,
        issue,
        keys=("canonical_ref", "canonical_branch", "target_ref", "target_branch", "target"),
    )
    audit_branch = _first_value(
        audit,
        branch,
        keys=("audit_branch", "branch", "branch_ref", "branch_key", "source_branch", "work_branch"),
    )
    branch_on_target = _first_value(
        branch,
        keys=("on_target", "on_canonical", "head_on_target", "implementation_on_main"),
    )
    scm_state = _string_signal(
        _first_value(branch, provider, keys=("scm_state", "resolution", "state"))
    )

    # Exact-head evidence: the accepted head the tracker considers current,
    # the branch head the SCM reports, and the head the authoritative
    # combined-tree quality gate was actually run against.  Comparing these
    # three catches the OOMPAH-814 regression where a passing focused/SCM
    # signal was reported after the authoritative gate had already failed
    # on the exact same accepted head.
    accepted_head_sha = _normalise_head(
        _first_value(
            integration,
            issue,
            gate,
            keys=("accepted_head_sha", "head_sha", "submitted_head_sha"),
        )
    )
    branch_head_sha = _normalise_head(
        _first_value(
            branch,
            issue,
            keys=("head_sha", "branch_head_sha", "sha"),
        )
    )
    gate_head_sha = _normalise_head(
        _first_value(gate, keys=("head_sha", "expected_head_sha", "gate_head_sha"))
    )
    gate_status = _string_signal(
        _first_value(gate, keys=("status", "gate_status", "verdict", "result"))
    )
    gate_verdict = _string_signal(
        _first_value(gate, keys=("verdict", "gate_verdict"))
    )
    gate_generation = str(
        _first_value(
            gate,
            integration,
            keys=(
                "generation", "gate_generation", "authority_generation",
                "cas_generation",
            ),
        )
        or ""
    ).strip()
    integration_state = _string_signal(
        _first_value(integration, keys=("state", "integration_state"))
    )
    integration_task_branch = str(
        _first_value(
            integration,
            issue,
            keys=("task_branch", "work_branch", "branch_name", "branch"),
        )
        or ""
    ).strip()

    return {
        "review_state": review_state,
        "merged": merged,
        "ci_status": ci_status,
        "audit_verdict": audit_verdict,
        "failure_classification": failure_classification,
        "provider_error": str(provider_error).strip() if provider_error else "",
        "provider_available": provider_available,
        "branch_exists": branch_exists,
        "canonical_ref": str(canonical_ref).strip() if canonical_ref else "",
        "audit_branch": str(audit_branch).strip() if audit_branch else "",
        "branch_on_target": branch_on_target,
        "scm_state": scm_state,
        "errors": envelope.errors,
        "review": review,
        "accepted_head_sha": accepted_head_sha,
        "branch_head_sha": branch_head_sha,
        "gate_head_sha": gate_head_sha,
        "gate_status": gate_status,
        "gate_verdict": gate_verdict,
        "gate_generation": gate_generation,
        "integration_state": integration_state,
        "integration_task_branch": integration_task_branch,
    }


def _current_evidence_decision(
    task_id: str,
    stalled_status: str,
    evidence: Any,
    *,
    project_id: str | None,
    run_id: int,
) -> StalledTaskDecision | None:
    """Return a decision from authoritative current evidence, if decisive.

    Ordering here is important.  The authoritative combined-tree gate result
    for the exact accepted head dominates every softer signal: a newer
    failing result must never be overridden by an older focused or SCM CI
    verdict.  For :data:`NEEDS_CI_FIX` and :data:`NEEDS_REBASE` we also
    require the current branch head to differ from the failing accepted head
    (positive evidence that a repair was pushed) before treating a passing
    SCM signal as safe.
    """
    if evidence is None:
        return None
    signals = _evidence_signals(evidence)
    details: list[str] = []
    canonical = canonicalize_status(stalled_status)

    accepted_head = signals["accepted_head_sha"]
    branch_head = signals["branch_head_sha"]
    gate_head = signals["gate_head_sha"]
    gate_status = signals["gate_status"]
    gate_generation = signals["gate_generation"]
    integration_state = signals["integration_state"]

    # Authoritative gate result at the exact accepted head dominates before
    # any softer merge/audit/branch signal has a chance to reopen a task.
    if canonical in {NEEDS_CI_FIX, NEEDS_REBASE} and gate_head and gate_status:
        matches_accepted = (not accepted_head) or gate_head == accepted_head
        if matches_accepted and gate_status in _FAILING_STATUSES:
            return StalledTaskDecision(
                task_id, project_id, stalled_status,
                "insufficient_evidence", "none",
                (
                    f"authoritative combined-tree gate at exact accepted head "
                    f"{gate_head[:12]} is {gate_status}; a newer failing "
                    "result dominates older focused/SCM passing evidence and "
                    "the task must remain in "
                    f"{canonical} for repair."
                ),
                watchdog_run_id=run_id,
                evidence_head=gate_head,
                evidence_result=gate_status,
                evidence_generation=gate_generation,
            )

    # Integration record ``state == "blocked"`` is the tracker-side proof
    # that the last combined-tree gate did not pass at the recorded head.
    # If the branch has not advanced past that accepted head, no repair has
    # been pushed and the failing exact-head evidence still dominates.  See
    # OOMPAH-814/818 for the concrete regression this closes.
    if (
        canonical in {NEEDS_CI_FIX, NEEDS_REBASE}
        and integration_state in {"blocked", "needs_human"}
        and accepted_head
        and branch_head
        and branch_head == accepted_head
    ):
        return StalledTaskDecision(
            task_id, project_id, stalled_status,
            "insufficient_evidence", "none",
            (
                "integration record is blocked at accepted head "
                f"{accepted_head[:12]} and the branch head has not advanced; "
                "no repair has been pushed, the failing exact-head gate still "
                "dominates and the stalled task must remain in "
                f"{canonical}."
            ),
            watchdog_run_id=run_id,
            evidence_head=accepted_head,
            evidence_result=f"integration_{integration_state}",
            evidence_generation=gate_generation,
        )

    if signals["merged"]:
        review_id = signals["review"].get("id") or signals["review"].get("number")
        detail = (
            f"current review {review_id} is merged"
            if review_id
            else "current review evidence is merged"
        )
        return StalledTaskDecision(
            task_id, project_id, stalled_status, "actionable", "reopen", detail,
            watchdog_run_id=run_id,
            evidence_head=accepted_head or branch_head,
            evidence_result="merged",
            evidence_generation=gate_generation,
        )
    if signals["audit_verdict"] in {"pass", "passed", "success", "successful"}:
        return StalledTaskDecision(
            task_id, project_id, stalled_status, "actionable", "reopen",
            "current terminal-audit evidence passed; the stalled handoff is superseded.",
            watchdog_run_id=run_id,
            evidence_head=accepted_head or branch_head,
            evidence_result="audit_passed",
            evidence_generation=gate_generation,
        )
    if signals["branch_on_target"] is True:
        return StalledTaskDecision(
            task_id, project_id, stalled_status, "actionable", "reopen",
            "current branch evidence shows the implementation head is on the canonical target.",
            watchdog_run_id=run_id,
            evidence_head=accepted_head or branch_head,
            evidence_result="on_canonical_target",
            evidence_generation=gate_generation,
        )

    technical_failures = {
        "infrastructure_error", "external_capability", "no_auditor", "missing_evidence",
        "provider_failure", "provider_error", "technical_blocker", "branch_missing",
        "audit_branch_missing", "ci_failure", "conflict", "out_of_date",
    }
    if signals["provider_error"]:
        details.append(f"provider evidence failed: {signals['provider_error']}")
    if signals["provider_available"] is False:
        details.append("SCM provider is unavailable")
    if signals["failure_classification"] in technical_failures:
        details.append(
            f"terminal-audit failure is technical ({signals['failure_classification']})"
        )
    if signals["canonical_ref"] and not signals["audit_branch"]:
        details.append(
            f"audit branch is missing while canonical ref {signals['canonical_ref']} is resolvable"
        )
    if signals["scm_state"] in {"ambiguous", "unknown", "unavailable", "indeterminate"}:
        details.append(f"SCM state is {signals['scm_state']}")
    if signals["errors"]:
        details.extend(str(error) for error in signals["errors"])
    if details:
        return StalledTaskDecision(
            task_id, project_id, stalled_status, "insufficient_evidence", "none",
            "Current technical evidence requires machine/operator repair; "
            + "; ".join(details),
            watchdog_run_id=run_id,
            evidence_head=accepted_head or branch_head,
            evidence_result="technical_blocker",
            evidence_generation=gate_generation,
        )

    if canonical == NEEDS_CI_FIX:
        # Positive path: an authoritative gate at the exact accepted head
        # has already passed.  Reopen and record the exact evidence.
        if (
            gate_head
            and gate_status in _PASSING_STATUSES
            and (not accepted_head or gate_head == accepted_head)
        ):
            return StalledTaskDecision(
                task_id, project_id, stalled_status, "actionable", "reopen",
                (
                    f"authoritative combined-tree gate passed at exact "
                    f"accepted head {gate_head[:12]}; safe to reopen the "
                    "stalled task."
                ),
                watchdog_run_id=run_id,
                evidence_head=gate_head,
                evidence_result=gate_status,
                evidence_generation=gate_generation,
            )
        # Compatibility path: no authoritative gate outcome is available.
        # A passing SCM/CI signal alone can only be trusted when it applies
        # to an exact head that is distinct from the failing accepted head
        # (positive evidence that a repair was actually pushed).  Refusing
        # to reopen without that evidence is the OOMPAH-818 fence.
        if signals["ci_status"] in _PASSING_STATUSES:
            if accepted_head and branch_head:
                if branch_head == accepted_head:
                    return StalledTaskDecision(
                        task_id, project_id, stalled_status,
                        "insufficient_evidence", "none",
                        (
                            "SCM CI reports passing at the same accepted head "
                            f"{accepted_head[:12]} that failed the combined-tree "
                            "gate.  No repair has been pushed, so the stalled "
                            "task must remain in Needs CI Fix until the "
                            "accepted head advances and the exact-head gate "
                            "reruns."
                        ),
                        watchdog_run_id=run_id,
                        evidence_head=accepted_head,
                        evidence_result="ci_status_stale_at_accepted_head",
                        evidence_generation=gate_generation,
                    )
                return StalledTaskDecision(
                    task_id, project_id, stalled_status, "actionable", "reopen",
                    (
                        f"current CI evidence is passing at branch head "
                        f"{branch_head[:12]} (repair advanced past accepted "
                        f"head {accepted_head[:12]}); safe to reopen."
                    ),
                    watchdog_run_id=run_id,
                    evidence_head=branch_head,
                    evidence_result="ci_passing_at_advanced_head",
                    evidence_generation=gate_generation,
                )
            # No accepted-head evidence at all: legacy compatibility.
            return StalledTaskDecision(
                task_id, project_id, stalled_status, "actionable", "reopen",
                "current CI evidence is passing; safe to reopen the stalled task.",
                watchdog_run_id=run_id,
                evidence_head=branch_head or accepted_head,
                evidence_result="ci_passing",
                evidence_generation=gate_generation,
            )
    if canonical == NEEDS_REBASE:
        if (
            gate_head
            and gate_status in _PASSING_STATUSES
            and (not accepted_head or gate_head == accepted_head)
        ):
            return StalledTaskDecision(
                task_id, project_id, stalled_status, "actionable", "reopen",
                (
                    f"authoritative combined-tree gate passed at exact "
                    f"accepted head {gate_head[:12]}; safe to reopen the "
                    "stalled rebase task."
                ),
                watchdog_run_id=run_id,
                evidence_head=gate_head,
                evidence_result=gate_status,
                evidence_generation=gate_generation,
            )
        if (
            signals["ci_status"] in _PASSING_STATUSES
            or (signals["branch_exists"] is True and signals["scm_state"] in {"clean", "resolved"})
        ):
            if accepted_head and branch_head and branch_head == accepted_head:
                return StalledTaskDecision(
                    task_id, project_id, stalled_status,
                    "insufficient_evidence", "none",
                    (
                        "SCM CI/branch signal is at the same accepted head "
                        f"{accepted_head[:12]} that failed the combined-tree "
                        "gate.  No rebase/repair has been pushed."
                    ),
                    watchdog_run_id=run_id,
                    evidence_head=accepted_head,
                    evidence_result="ci_status_stale_at_accepted_head",
                    evidence_generation=gate_generation,
                )
            return StalledTaskDecision(
                task_id, project_id, stalled_status, "actionable", "reopen",
                "current SCM evidence shows the stalled branch/rebase condition is resolved.",
                watchdog_run_id=run_id,
                evidence_head=branch_head or accepted_head,
                evidence_result="rebase_resolved",
                evidence_generation=gate_generation,
            )
    return None


def _watchdog_comment_contains_evidence(comment: Mapping[str, Any], evidence: str) -> bool:
    """Check whether a prior sentinel records the same decisive evidence."""
    body = _get_comment_body(dict(comment))
    marker = "**Evidence:**"
    if marker not in body:
        return False
    recorded = body.split(marker, 1)[1].split("\n", 1)[0].strip()
    return recorded == evidence.strip()



def _last_watchdog_comment(comments: list[dict]) -> dict | None:
    """Return the most recent watchdog sentinel comment, or None."""
    for comment in reversed(comments):
        body = _get_comment_body(comment)
        if WATCHDOG_COMMENT_MARKER in body:
            return comment
    return None


def _has_changed_since_watchdog_comment(
    comments: list[dict],
    watchdog_comment: dict,
) -> bool:
    """Return True if any non-watchdog comment was posted after *watchdog_comment*.

    Used to detect whether the task has had new human or agent activity
    since we last acted on it. If the most recent watchdog comment is the
    *last* comment overall, the task hasn't changed → skip.
    """
    wc_idx = None
    for i, c in enumerate(comments):
        if c is watchdog_comment:
            wc_idx = i
            break
    if wc_idx is None:
        return True  # Couldn't locate — assume changed
    for c in comments[wc_idx + 1:]:
        body = _get_comment_body(c)
        if WATCHDOG_COMMENT_MARKER not in body:
            return True
    return False


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_stalled_task(
    task_id: str,
    stalled_status: str,
    comments: list[dict],
    *,
    project_id: str | None = None,
    run_id: int = 0,
    evidence: WatchdogEvidence | Mapping[str, Any] | None = None,
    current_evidence: WatchdogEvidence | Mapping[str, Any] | None = None,
) -> StalledTaskDecision:
    """Classify a stalled task and decide on a remediation action.

    This function is pure: it reads the supplied state and returns a
    :class:`StalledTaskDecision` without performing I/O. The orchestrator
    is responsible for executing the action described in the decision.

    Classification logic by state:

    **Needs Human**:
    - Current review/audit/branch evidence is evaluated first.  Merged or
      landed work is ``actionable``; provider failures, missing technical
      evidence, and ambiguous SCM state are ``insufficient_evidence``.
    - Otherwise only the newest comment can establish a human blocker, and it
      must contain an explicit product/authority decision.  A focus-handoff
      marker alone is not enough.
    - A newest completion comment without a decision is ``actionable``;
      otherwise the result is ``insufficient_evidence``.

    **Needs CI Fix / Needs Rebase**:
    - Current CI/SCM evidence is preferred.  A recent comment stating CI
      passed / conflict resolved / PR merged remains a compatibility fallback
      and produces ``actionable`` with action ``"reopen"``.
    - Otherwise → ``insufficient_evidence`` (need SCM state to confirm).

    **Needs Answer**:
    - There is always a pending question; the watchdog leaves these alone →
      ``human_blocked``.

    **Blocked / Stalled** (custom statuses):
    - If the last N comments are all watchdog comments (no new activity) →
      ``insufficient_evidence``.
    - If a recent human or agent comment signals resolution → ``actionable``
      with action ``"reopen"``.
    - Otherwise → ``human_blocked`` (external dependency, leave alone).

    Idempotency:
    - If the most recent watchdog comment is still the last comment (nothing
      has changed since the previous run), set ``already_actioned=True`` and
      return ``"none"`` action to prevent duplicate comments.

    Args:
        task_id:        Issue identifier.
        stalled_status: The current status string of the task.
        comments:       Comment dicts; timestamps are used when available,
                        otherwise the supplied order is treated as oldest-first.
        project_id:     Owning project identifier for logging.
        run_id:         Current watchdog run counter.
        evidence:       Optional current tracker/SCM/audit evidence envelope.
        current_evidence: Readable alias for ``evidence``.

    Returns:
        A :class:`StalledTaskDecision` describing the classification and
        recommended action.
    """
    canonical = canonicalize_status(stalled_status)
    ordered = _ordered_comments(comments)
    recent = ordered[-_COMMENT_INSPECTION_WINDOW:] if ordered else []

    # Current tracker/SCM/audit evidence has precedence over prose.  The
    # alias keeps integrations readable while preserving the short public
    # ``evidence=`` spelling used by tests and callers.
    supplied_evidence = current_evidence if current_evidence is not None else evidence
    evidence_decision = _current_evidence_decision(
        task_id,
        stalled_status,
        supplied_evidence,
        project_id=project_id,
        run_id=run_id,
    )

    # ---- Idempotency check -----------------------------------------------
    last_wc = _last_watchdog_comment(ordered)
    if last_wc is not None:
        unchanged = not _has_changed_since_watchdog_comment(ordered, last_wc)
        if unchanged and evidence_decision is not None:
            # A restart may discover new SCM/audit evidence without a new
            # tracker comment.  Re-run only when that evidence differs from
            # the sentinel we already recorded.
            if not _watchdog_comment_contains_evidence(last_wc, evidence_decision.evidence):
                return evidence_decision
        if unchanged:
            return StalledTaskDecision(
                task_id=task_id,
                project_id=project_id,
                stalled_status=stalled_status,
                classification="insufficient_evidence",
                action="none",
                evidence="Watchdog already acted on this task and no new activity detected.",
                watchdog_run_id=run_id,
                already_actioned=True,
            )

    if evidence_decision is not None:
        return evidence_decision

    # ---- Needs Answer -------------------------------------------------------
    if canonical == NEEDS_ANSWER:
        return StalledTaskDecision(
            task_id=task_id,
            project_id=project_id,
            stalled_status=stalled_status,
            classification="human_blocked",
            action="none",
            evidence="Task is awaiting a human answer to an open question; leaving untouched.",
            watchdog_run_id=run_id,
        )

    # ---- Needs Human --------------------------------------------------------
    if canonical == NEEDS_HUMAN:
        # Only the newest meaningful comment can describe the current
        # decision.  Older questions are historical context once a newer
        # completion or clarification supersedes them.  A focus-handoff
        # marker by itself is intentionally not evidence of a human blocker.
        latest = next(
            (
                comment for comment in reversed(recent)
                if _get_comment_body(comment).strip()
                and WATCHDOG_COMMENT_MARKER not in _get_comment_body(comment)
            ),
            None,
        )
        if latest is not None:
            body = _get_comment_body(latest)
            # A question-word or "please review" phrase in a handoff is not
            # enough.  Require a question mark or the narrower decision
            # vocabulary above so routing prose cannot become a blocker.
            explicit_question = bool(re.search(r"\?\s*$", body, re.MULTILINE))
            is_handoff = "focus handoff" in body.lower()
            handoff_only = is_handoff and not _handoff_has_human_decision(body)
            if (
                (is_handoff and _handoff_has_human_decision(body))
                or (not is_handoff and _text_has_human_decision(body))
                or (explicit_question and not handoff_only)
            ):
                return StalledTaskDecision(
                    task_id=task_id,
                    project_id=project_id,
                    stalled_status=stalled_status,
                    classification="human_blocked",
                    action="none",
                    evidence=(
                        "The newest comment contains an unanswered product or "
                        "authority question; older handoff wording is superseded."
                    ),
                    watchdog_run_id=run_id,
                )
            if _text_has_completion_without_question(body) and not explicit_question:
                return StalledTaskDecision(
                    task_id=task_id,
                    project_id=project_id,
                    stalled_status=stalled_status,
                    classification="actionable",
                    action="reopen",
                    evidence=(
                        "The newest comment signals completion without a current "
                        "human decision; the Needs Human transition appears accidental."
                    ),
                    watchdog_run_id=run_id,
                )

        return StalledTaskDecision(
            task_id=task_id,
            project_id=project_id,
            stalled_status=stalled_status,
            classification="insufficient_evidence",
            action="none",
            evidence=(
                "Cannot determine whether the Needs Human state is intentional "
                "without clearer question or completion signals in comments."
            ),
            watchdog_run_id=run_id,
        )

    # ---- Needs CI Fix -------------------------------------------------------
    if canonical == NEEDS_CI_FIX:
        for c in reversed(recent):
            body = _get_comment_body(c)
            if WATCHDOG_COMMENT_MARKER in body:
                continue
            if _text_has_ci_passing(body):
                return StalledTaskDecision(
                    task_id=task_id,
                    project_id=project_id,
                    stalled_status=stalled_status,
                    classification="actionable",
                    action="reopen",
                    evidence=(
                        "Recent comment indicates CI is now passing or PR has been merged; "
                        "safe to reopen for dispatch."
                    ),
                    watchdog_run_id=run_id,
                )
        return StalledTaskDecision(
            task_id=task_id,
            project_id=project_id,
            stalled_status=stalled_status,
            classification="insufficient_evidence",
            action="none",
            evidence=(
                "No comment evidence that CI has passed. External SCM state "
                "must be verified before acting."
            ),
            watchdog_run_id=run_id,
        )

    # ---- Needs Rebase -------------------------------------------------------
    if canonical == NEEDS_REBASE:
        for c in reversed(recent):
            body = _get_comment_body(c)
            if WATCHDOG_COMMENT_MARKER in body:
                continue
            if _text_has_rebase_resolved(body):
                return StalledTaskDecision(
                    task_id=task_id,
                    project_id=project_id,
                    stalled_status=stalled_status,
                    classification="actionable",
                    action="reopen",
                    evidence=(
                        "Recent comment indicates the conflict or rebase has been resolved; "
                        "safe to reopen."
                    ),
                    watchdog_run_id=run_id,
                )
        return StalledTaskDecision(
            task_id=task_id,
            project_id=project_id,
            stalled_status=stalled_status,
            classification="insufficient_evidence",
            action="none",
            evidence=(
                "No comment evidence that the merge conflict or rebase has been resolved."
            ),
            watchdog_run_id=run_id,
        )

    # ---- Custom Blocked / Stalled -------------------------------------------
    # For unknown stalled statuses, look for resolution signals in recent
    # comments. Otherwise classify as human_blocked to be conservative.
    for c in reversed(recent):
        body = _get_comment_body(c)
        if WATCHDOG_COMMENT_MARKER in body:
            continue
        if _text_has_ci_passing(body) or _text_has_rebase_resolved(body):
            return StalledTaskDecision(
                task_id=task_id,
                project_id=project_id,
                stalled_status=stalled_status,
                classification="actionable",
                action="reopen",
                evidence=(
                    "Recent comment indicates the blocking condition has been resolved."
                ),
                watchdog_run_id=run_id,
            )

    return StalledTaskDecision(
        task_id=task_id,
        project_id=project_id,
        stalled_status=stalled_status,
        classification="human_blocked",
        action="none",
        evidence=(
            f"Custom stalled status '{stalled_status}' with no resolution signals. "
            "Treating as a genuine human blocker."
        ),
        watchdog_run_id=run_id,
    )


# ---------------------------------------------------------------------------
# Audit loop
# ---------------------------------------------------------------------------


def build_watchdog_comment(decision: StalledTaskDecision) -> str:
    """Return the oompah-authored comment to post when taking an action.

    The exact-head SHA, authoritative result, and compare-and-set generation
    are surfaced so an operator (and any downstream event consumer) can tell
    at a glance which authoritative result the watchdog acted on.  A blank
    field is elided rather than rendered as ``none``.
    """
    lines = [
        f"{WATCHDOG_COMMENT_MARKER} Stalled-task watchdog audit (run #{decision.watchdog_run_id})",
        "",
        f"**State audited:** `{decision.stalled_status}`",
        f"**Classification:** `{decision.classification}`",
        f"**Action:** `{decision.action}`",
        f"**Evidence:** {decision.evidence}",
    ]
    if decision.evidence_head:
        lines.append(f"**Evidence head:** `{decision.evidence_head}`")
    if decision.evidence_result:
        lines.append(f"**Evidence result:** `{decision.evidence_result}`")
    if decision.evidence_generation:
        lines.append(f"**Evidence generation:** `{decision.evidence_generation}`")
    lines.extend([
        "",
        "*This comment is posted automatically by the oompah stalled-task watchdog. "
        "No human action required unless the classification above is incorrect.*",
    ])
    return "\n".join(lines)


def _tracker_issue_evidence(tracker: Any, issue: Any) -> WatchdogEvidence:
    """Collect tracker-owned evidence without requiring a provider call."""
    issue_mapping = _as_mapping(issue)
    metadata: Mapping[str, Any] = {}
    get_metadata = getattr(tracker, "get_metadata", None)
    if callable(get_metadata):
        try:
            raw_metadata = get_metadata(str(getattr(issue, "identifier", "")))
        except Exception:  # noqa: BLE001 - missing metadata is unknown evidence
            raw_metadata = None
        if isinstance(raw_metadata, Mapping):
            metadata = raw_metadata
    audit = metadata.get("oompah.terminal_audit") or metadata.get("terminal_audit")
    integration_obj = getattr(issue, "integration", None)
    integration_mapping: dict[str, Any] = {}
    if integration_obj is not None:
        to_dict = getattr(integration_obj, "to_dict", None)
        if callable(to_dict):
            try:
                raw = to_dict()
            except Exception:  # noqa: BLE001 - defensive
                raw = None
            if isinstance(raw, Mapping):
                integration_mapping = dict(raw)
        if not integration_mapping:
            integration_mapping = _as_mapping(integration_obj)
    return WatchdogEvidence(
        issue=issue_mapping,
        review={
            key: issue_mapping[key]
            for key in ("review_state", "review_number", "review_url", "review_head", "merged_at")
            if issue_mapping.get(key) not in (None, "")
        },
        branch={
            key: issue_mapping[key]
            for key in ("work_branch", "branch_name", "target_branch")
            if issue_mapping.get(key) not in (None, "")
        },
        audit=audit,
        integration=integration_mapping or None,
    )


def run_watchdog_audit(
    projects_and_trackers: list[tuple[str | None, Any]],
    *,
    run_id: int = 0,
    dry_run: bool = False,
    evidence_provider: Callable[..., Any] | None = None,
    evidence_by_task: Mapping[str, Any] | None = None,
) -> WatchdogAuditResult:
    """Run a full stalled-task watchdog audit across all projects.

    For each project, fetches all issues in stalled states, classifies each
    one, and performs the safe automated action (reopen) when evidence
    supports it. Posts an oompah-authored comment on every task that is
    acted upon (or noted as already-actioned).

    Args:
        projects_and_trackers: List of ``(project_id, tracker)`` tuples.
            ``project_id`` may be ``None`` for the legacy single-project mode.
        run_id: Monotonically increasing counter for correlation.
        dry_run: When True, classify but do not perform any tracker writes.
        evidence_provider: Optional callback receiving ``(project_id, issue,
            tracker)`` and returning current machine evidence.
        evidence_by_task: Optional pre-collected evidence keyed by identifier;
            useful for deterministic callers and tests.

    Returns:
        A :class:`WatchdogAuditResult` with full audit telemetry.
    """
    started_at = datetime.now(timezone.utc)
    result = WatchdogAuditResult(
        run_id=run_id,
        started_at=started_at.isoformat(),
    )
    t0 = time.monotonic()

    states_to_audit = list(STALLED_STATES)

    for project_id, tracker in projects_and_trackers:
        try:
            issues = tracker.fetch_issues_by_states(states_to_audit)
        except Exception as exc:
            msg = f"Failed to fetch stalled issues for project={project_id}: {exc}"
            logger.warning(msg)
            result.errors.append(msg)
            continue

        for issue in issues:
            identifier = str(getattr(issue, "identifier", "") or "")
            state = str(getattr(issue, "state", "") or "")
            if not identifier or not is_stalled_status(state):
                continue

            result.tasks_audited += 1

            # Fetch comments for this task.
            try:
                comments: list[dict] = list(tracker.fetch_comments(identifier))
            except Exception as exc:
                msg = f"Failed to fetch comments for {identifier}: {exc}"
                logger.debug(msg)
                result.errors.append(msg)
                decision = StalledTaskDecision(
                    task_id=identifier,
                    project_id=project_id,
                    stalled_status=state,
                    classification="insufficient_evidence",
                    action="none",
                    evidence=f"Could not fetch comments: {exc}",
                    watchdog_run_id=run_id,
                )
                result.tasks_insufficient_evidence += 1
                result.decisions.append(decision)
                continue

            current_evidence: Any = None
            if evidence_by_task is not None:
                current_evidence = evidence_by_task.get(identifier)
            if current_evidence is None:
                current_evidence = _tracker_issue_evidence(tracker, issue)
            if evidence_provider is not None:
                try:
                    provided_evidence = evidence_provider(project_id, issue, tracker)
                    if provided_evidence is not None:
                        current_evidence = provided_evidence
                except Exception as exc:  # noqa: BLE001 - fail closed per task
                    msg = f"Failed to collect current evidence for {identifier}: {exc}"
                    logger.debug(msg)
                    result.errors.append(msg)
                    current_evidence = WatchdogEvidence(errors=("current evidence unavailable",))

            decision = classify_stalled_task(
                identifier,
                state,
                comments,
                project_id=project_id,
                run_id=run_id,
                current_evidence=current_evidence,
            )
            result.decisions.append(decision)

            # Update classification counts.
            if decision.already_actioned:
                result.actions_skipped += 1
                logger.debug(
                    "Watchdog skipping %s (already actioned, no new activity)",
                    identifier,
                )
                continue

            {
                "actionable": lambda: setattr(result, "tasks_actionable",
                                              result.tasks_actionable + 1),
                "human_blocked": lambda: setattr(result, "tasks_human_blocked",
                                                 result.tasks_human_blocked + 1),
                "obsolete": lambda: setattr(result, "tasks_obsolete",
                                            result.tasks_obsolete + 1),
                "insufficient_evidence": lambda: setattr(
                    result, "tasks_insufficient_evidence",
                    result.tasks_insufficient_evidence + 1),
            }.get(decision.classification, lambda: None)()

            if decision.action == "none":
                logger.debug(
                    "Watchdog: %s classification=%s action=none evidence=%s",
                    identifier, decision.classification, decision.evidence[:120],
                )
                continue

            # Perform the remediation.
            if dry_run:
                logger.info(
                    "Watchdog dry-run: would %s task %s (project=%s) — %s",
                    decision.action, identifier, project_id, decision.evidence,
                )
                result.actions_taken += 1
                continue

            comment_body = build_watchdog_comment(decision)

            try:
                # Post the evidence comment BEFORE the state change so the
                # audit trail is always present even if the state update fails.
                tracker.add_comment(identifier, comment_body, author="oompah")
                logger.info(
                    "Watchdog posted comment on %s (project=%s)",
                    identifier, project_id,
                )
            except Exception as exc:
                msg = f"Failed to post watchdog comment on {identifier}: {exc}"
                logger.warning(msg)
                result.errors.append(msg)
                # Don't abort the state change — comment failure is non-fatal.

            if decision.action == "reopen":
                try:
                    tracker.update_issue(identifier, status=OPEN)
                    logger.info(
                        "Watchdog reopened %s (project=%s) — %s",
                        identifier, project_id, decision.evidence,
                    )
                    result.actions_taken += 1
                except Exception as exc:
                    msg = f"Failed to reopen {identifier}: {exc}"
                    logger.warning(msg)
                    result.errors.append(msg)

            elif decision.action == "archive":
                disposition_reason = f"Watchdog stalled-task archive: {decision.evidence}"
                if request_archived_audit(
                    issue,
                    tracker,
                    project_id,
                    disposition_reason,
                    trigger_source="stalled_task_watchdog",
                ):
                    logger.info(
                        "Watchdog queued archive audit for %s (project=%s) — %s",
                        identifier, project_id, decision.evidence,
                    )
                    result.actions_taken += 1
                else:
                    msg = f"Failed to queue archive audit for {identifier}"
                    logger.warning(msg)
                    result.errors.append(msg)

            else:
                logger.warning(
                    "Watchdog: unknown action %r for %s; skipping",
                    decision.action, identifier,
                )

    finished_at = datetime.now(timezone.utc)
    result.finished_at = finished_at.isoformat()
    result.duration_s = time.monotonic() - t0

    logger.info(
        "Stalled-task watchdog run #%d complete: "
        "audited=%d actionable=%d human_blocked=%d obsolete=%d "
        "insufficient=%d actions=%d skipped=%d errors=%d duration=%.2fs",
        run_id,
        result.tasks_audited,
        result.tasks_actionable,
        result.tasks_human_blocked,
        result.tasks_obsolete,
        result.tasks_insufficient_evidence,
        result.actions_taken,
        result.actions_skipped,
        len(result.errors),
        result.duration_s,
    )

    return result
