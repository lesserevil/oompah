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
from typing import Any

from oompah.statuses import (
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    canonicalize_status,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Environment variable that controls the watchdog interval.
ENV_VAR = "OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS"

#: Default watchdog interval: 30 minutes.
DEFAULT_INTERVAL_SECONDS: int = 1800

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
) -> StalledTaskDecision:
    """Classify a stalled task and decide on a remediation action.

    This function is pure: it reads the supplied state and returns a
    :class:`StalledTaskDecision` without performing I/O. The orchestrator
    is responsible for executing the action described in the decision.

    Classification logic by state:

    **Needs Human**:
    - If the last agent comment signals completion without any question →
      ``actionable`` with action ``"reopen"`` (accidental stall).
    - If any recent comment contains an explicit question or focus-handoff
      that names a human blocker → ``human_blocked``.
    - Otherwise → ``insufficient_evidence``.

    **Needs CI Fix / Needs Rebase**:
    - If a recent comment explicitly states CI passed / conflict resolved /
      PR merged → ``actionable`` with action ``"reopen"``.
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
        comments:       Ordered list of comment dicts (oldest-first).
        project_id:     Owning project identifier for logging.
        run_id:         Current watchdog run counter.

    Returns:
        A :class:`StalledTaskDecision` describing the classification and
        recommended action.
    """
    canonical = canonicalize_status(stalled_status)
    recent = comments[-_COMMENT_INSPECTION_WINDOW:] if comments else []

    # ---- Idempotency check -----------------------------------------------
    last_wc = _last_watchdog_comment(comments)
    if last_wc is not None:
        if not _has_changed_since_watchdog_comment(comments, last_wc):
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
        recent_texts = [_get_comment_body(c) for c in recent]
        combined = "\n".join(recent_texts)

        # Check for pending question / explicit human blocker
        for c in reversed(recent):
            body = _get_comment_body(c)
            if not body.strip():
                continue
            if WATCHDOG_COMMENT_MARKER in body:
                continue
            if _text_has_handoff_question(body) or _text_has_question(body):
                return StalledTaskDecision(
                    task_id=task_id,
                    project_id=project_id,
                    stalled_status=stalled_status,
                    classification="human_blocked",
                    action="none",
                    evidence=(
                        "Recent comment contains an explicit question or "
                        "focus-handoff noting a human dependency."
                    ),
                    watchdog_run_id=run_id,
                )

        # Check for accidental stall: last agent comment signals completion
        # but no question was asked.
        for c in reversed(recent):
            body = _get_comment_body(c)
            if not body.strip():
                continue
            if WATCHDOG_COMMENT_MARKER in body:
                continue
            if (
                _text_has_completion_without_question(body)
                and not _text_has_question(body)
                and not _text_has_handoff_question(body)
            ):
                return StalledTaskDecision(
                    task_id=task_id,
                    project_id=project_id,
                    stalled_status=stalled_status,
                    classification="actionable",
                    action="reopen",
                    evidence=(
                        "Last agent comment signals completion without a human question; "
                        "the Needs Human transition appears accidental."
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
    """Return the oompah-authored comment to post when taking an action."""
    lines = [
        f"{WATCHDOG_COMMENT_MARKER} Stalled-task watchdog audit (run #{decision.watchdog_run_id})",
        "",
        f"**State audited:** `{decision.stalled_status}`",
        f"**Classification:** `{decision.classification}`",
        f"**Action:** `{decision.action}`",
        f"**Evidence:** {decision.evidence}",
        "",
        "*This comment is posted automatically by the oompah stalled-task watchdog. "
        "No human action required unless the classification above is incorrect.*",
    ]
    return "\n".join(lines)


def run_watchdog_audit(
    projects_and_trackers: list[tuple[str | None, Any]],
    *,
    run_id: int = 0,
    dry_run: bool = False,
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

            decision = classify_stalled_task(
                identifier,
                state,
                comments,
                project_id=project_id,
                run_id=run_id,
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
                try:
                    tracker.archive_issue(identifier)
                    logger.info(
                        "Watchdog archived %s (project=%s) — %s",
                        identifier, project_id, decision.evidence,
                    )
                    result.actions_taken += 1
                except Exception as exc:
                    msg = f"Failed to archive {identifier}: {exc}"
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
