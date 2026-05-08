"""YOLO-loop block watchdog.

Detects recurring no-progress patterns in the YOLO review-action loop and
proposes P0 escalation beads. The watchdog is intentionally pure — it
inspects state passed in by the orchestrator and returns descriptions
of what to file. The orchestrator owns the side effects (filing beads,
mutating its own caches).

Design principles
-----------------

* **Deterministic thresholds** beat fancy detection. Each detector is a
  small, comprehensible rule with a numeric threshold.
* **Per-PR isolation.** v1 doesn't try to correlate patterns across
  projects — each (project, review) pair is its own watchdog timeline.
* **Idempotent.** When the same pattern fires for the same PR repeatedly,
  the orchestrator's filed-bead cache prevents re-filing.
* **No auto-repair.** The watchdog escalates by filing operator-attention
  beads. Per-pattern repair lives elsewhere (it's exactly the code we've
  already been writing reactively).

The four detectors implemented for v1 are:

* **D1** — recurring identical failure on the same PR for ≥5 ticks.
* **D2** — loop coverage: ``reviews_considered < total_reviews`` for
  ≥3 consecutive ticks (a starvation signal).
* **D3** — bead-PR coherence: a PR with ``has_conflicts=True`` or
  ``ci_status=='failed'`` whose recovery bead has been closed without
  resolving the underlying problem.
* **D4** — "PR already mergeable" stuck loop: if ``enable_auto_merge``
  has reported "already mergeable" ≥3 ticks running, the orchestrator
  should switch strategy to direct merge.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default maximum number of action records held in the orchestrator's
#: action history deque. ~50 PRs × 4 ticks of headroom is plenty for a
#: project of any realistic scale.
DEFAULT_HISTORY_MAX: int = 400

#: Recurrence threshold for D1: this many consecutive failures of the
#: same (project, review, action) tuple before we file a P0 bead.
D1_RECURRENCE_THRESHOLD: int = 5

#: Coverage threshold for D2: this many consecutive ticks where
#: ``reviews_considered < total_reviews`` before we log a WARNING.
D2_COVERAGE_THRESHOLD: int = 3

#: Already-mergeable threshold for D4: this many consecutive
#: "PR already mergeable" failures before strategy switch.
D4_ALREADY_MERGEABLE_THRESHOLD: int = 3

#: Coverage history window for D2: must be at least the threshold so
#: we can scan the most recent N ticks.
DEFAULT_COVERAGE_WINDOW: int = 10


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class YoloActionRecord:
    """One YOLO action attempt against a specific review.

    Action history is kept as a chronologically-ordered deque of these
    on the orchestrator. Detectors scan the deque to find patterns.

    ``error_msg`` is the failure message captured at attempt time, used
    by the watchdog body to give the operator immediate context (rather
    than making them grep logs).

    Attributes:
        project_id: The project ID owning this PR.
        review_id: The PR/MR identifier (string for stability across
            providers — GitHub uses ints, GitLab uses ints, but we
            normalize to str).
        action_type: One of ``"merge"``, ``"enqueue"``, ``"notify_conflict"``,
            ``"retry_ci"``. Free-form to allow future detector additions.
        outcome: ``"success"`` or ``"failure"``.
        error_msg: Empty on success; failure message otherwise.
        tick: Monotonically increasing tick counter, used by detectors
            to determine "consecutive ticks" semantics. Tick numbering
            is per-process; the watchdog only cares about ordering.
        timestamp: Wall-clock seconds at attempt time. Surfaced in the
            P0 bead body so the operator can correlate with logs.
    """

    project_id: str
    review_id: str
    action_type: str
    outcome: str
    error_msg: str
    tick: int
    timestamp: float


@dataclass
class CoverageRecord:
    """One tick's worth of YOLO loop-coverage stats.

    D2 scans these to detect starvation: when the loop sees fewer
    reviews than were available, that's a sign one PR is monopolizing
    the loop or a guard is short-circuiting the loop.

    Attributes:
        tick: Monotonic tick counter.
        project_id: The project this record belongs to.
        considered: How many reviews the loop iterated over.
        total: How many reviews the project had open at this tick.
        actions: How many actions the loop fired this tick.
        missing_review_ids: Review IDs that were skipped (for the
            WARNING body). Empty when ``considered >= total``.
    """

    tick: int
    project_id: str
    considered: int
    total: int
    actions: int
    missing_review_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WatchdogPattern:
    """A detected pattern to be escalated by the orchestrator.

    The orchestrator translates this into either a P0 bead (D1, D3, D4
    when escalating) or a log warning (D2). The ``pattern_key`` is the
    idempotency key — the orchestrator stamps it on its filed-bead
    cache so the same pattern doesn't re-file every tick.

    ``severity`` is ``"p0"`` for bead-filing patterns and ``"warning"``
    for log-only patterns (D2). The orchestrator handles each
    appropriately.

    Attributes:
        project_id: Owning project for the bead.
        review_id: PR/MR id (string). Empty for project-level
            patterns (D2).
        pattern_key: Detector-specific idempotency key.
        detector: Detector tag (``"d1"`` / ``"d2"`` / ``"d3"`` / ``"d4"``).
        title: Bead title (for bead-filing patterns) or warning summary.
        body: Bead description / warning detail.
        labels: Labels to attach to the filed bead.
        severity: ``"p0"`` or ``"warning"``.
    """

    project_id: str
    review_id: str
    pattern_key: str
    detector: str
    title: str
    body: str
    labels: tuple[str, ...]
    severity: str  # "p0" | "warning"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_action_history(maxlen: int = DEFAULT_HISTORY_MAX) -> "deque[YoloActionRecord]":
    """Construct a bounded action-history deque.

    Kept as a function (rather than instantiated inline) so tests can
    seed deterministic fixtures and the orchestrator's state-init
    callsite is one line.
    """
    return deque(maxlen=maxlen)


def make_coverage_history(maxlen: int = DEFAULT_COVERAGE_WINDOW) -> "deque[CoverageRecord]":
    """Construct a bounded coverage-history deque."""
    return deque(maxlen=maxlen)


def _consecutive_failures_for(
    history: Iterable[YoloActionRecord],
    project_id: str,
    review_id: str,
    action_type: str,
) -> tuple[int, str]:
    """Return (consecutive failure count, latest error msg) for the trailing run.

    Walks the history *backwards* from the most recent record for this
    (project, review, action) tuple. Counts only the *trailing* run of
    consecutive failures — once a success is encountered the run breaks.

    The record stream is pre-filtered to a single (project, review,
    action) tuple before walking. Inter-tuple ticks where unrelated
    PRs got attention don't reset our counter.
    """
    pertuple = [
        r for r in history
        if r.project_id == project_id
        and r.review_id == review_id
        and r.action_type == action_type
    ]
    if not pertuple:
        return 0, ""
    pertuple.sort(key=lambda r: r.tick)
    # Walk from newest backward.
    count = 0
    latest_err = ""
    for record in reversed(pertuple):
        if record.outcome != "failure":
            break
        if not latest_err and record.error_msg:
            latest_err = record.error_msg
        count += 1
    return count, latest_err


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def detect_d1_recurrent_failures(
    history: Iterable[YoloActionRecord],
    *,
    threshold: int = D1_RECURRENCE_THRESHOLD,
    project_lookup: dict[str, str] | None = None,
) -> list[WatchdogPattern]:
    """D1 — same (PR, action, failure) tuple ≥ threshold consecutive ticks.

    Scans the action history and returns one ``WatchdogPattern`` per
    distinct (project, review, action) tuple whose trailing run of
    consecutive failures has reached or exceeded ``threshold``.

    The orchestrator's idempotency cache (keyed by ``pattern_key``)
    prevents re-filing the same pattern on subsequent ticks — this
    detector merely identifies the candidates.
    """
    history = list(history)
    if not history:
        return []
    project_lookup = project_lookup or {}

    # Find the unique (project, review, action) tuples in the recent window.
    seen: set[tuple[str, str, str]] = set()
    for r in history:
        seen.add((r.project_id, r.review_id, r.action_type))

    patterns: list[WatchdogPattern] = []
    for project_id, review_id, action_type in sorted(seen):
        count, latest_err = _consecutive_failures_for(
            history, project_id, review_id, action_type,
        )
        if count < threshold:
            continue
        project_name = project_lookup.get(project_id, project_id)
        pattern_key = f"d1:{project_id}:{review_id}:{action_type}"
        title = (
            f"YOLO stuck on {project_name}/{review_id}: "
            f"{action_type} failing {count} ticks running"
        )
        body = (
            f"The YOLO loop has tried action `{action_type}` against "
            f"{project_name} review #{review_id} for {count} consecutive "
            f"ticks. Each attempt has failed, and the most recent error "
            f"was:\n\n```\n{latest_err or '(no error message captured)'}\n```\n\n"
            "This bead was filed automatically by the YOLO watchdog. The "
            "loop is not making progress on this PR — operator attention "
            "is required to either fix the underlying condition or close "
            "the PR.\n\n"
            f"- project_id: `{project_id}`\n"
            f"- review_id: `{review_id}`\n"
            f"- action_type: `{action_type}`\n"
            f"- consecutive_failures: {count}\n"
        )
        patterns.append(WatchdogPattern(
            project_id=project_id,
            review_id=review_id,
            pattern_key=pattern_key,
            detector="d1",
            title=title,
            body=body,
            labels=("needs-human", "yolo-watchdog"),
            severity="p0",
        ))
    return patterns


def detect_d2_loop_coverage(
    coverage_history: Iterable[CoverageRecord],
    *,
    threshold: int = D2_COVERAGE_THRESHOLD,
) -> list[WatchdogPattern]:
    """D2 — loop coverage starvation across ≥ threshold consecutive ticks.

    Returns a single warning-severity pattern per project where the most
    recent ``threshold`` ticks all had ``considered < total``. The
    orchestrator emits this as a log WARNING rather than a bead.
    """
    by_project: dict[str, list[CoverageRecord]] = {}
    for r in coverage_history:
        by_project.setdefault(r.project_id, []).append(r)

    patterns: list[WatchdogPattern] = []
    for project_id, records in by_project.items():
        records.sort(key=lambda r: r.tick)
        recent = records[-threshold:]
        if len(recent) < threshold:
            continue
        if not all(r.considered < r.total for r in recent):
            continue
        # Aggregate missing review IDs across the window for the warning.
        missing: list[str] = []
        for r in recent:
            for rid in r.missing_review_ids:
                if rid not in missing:
                    missing.append(rid)
        last = recent[-1]
        body_lines = [
            f"YOLO loop has skipped reviews for {threshold} consecutive ticks "
            f"on project {project_id}.",
            f"Most recent tick: considered={last.considered}/{last.total}, "
            f"actions={last.actions}.",
        ]
        if missing:
            body_lines.append(f"Missing review IDs (window union): {', '.join(missing)}")
        body_lines.append(
            "This is the next-shape starvation signal — investigate the YOLO "
            "loop's iteration order and any short-circuit guards."
        )
        patterns.append(WatchdogPattern(
            project_id=project_id,
            review_id="",
            pattern_key=f"d2:{project_id}",
            detector="d2",
            title=(
                f"YOLO loop coverage starvation on {project_id}: "
                f"{last.considered}/{last.total} reviews considered for "
                f"{threshold} consecutive ticks"
            ),
            body="\n".join(body_lines),
            labels=("yolo-watchdog",),
            severity="warning",
        ))
    return patterns


def detect_d3_bead_pr_coherence(
    *,
    incoherent_prs: Iterable[dict],
    project_lookup: dict[str, str] | None = None,
) -> list[WatchdogPattern]:
    """D3 — bead-PR coherence breakdown.

    The caller (orchestrator) determines incoherence by inspecting open
    PRs and the orphan-recovery cache. Each entry in ``incoherent_prs``
    is a dict with keys: ``project_id``, ``review_id``, ``kind``
    ("merge-conflict" | "ci-fix"), ``source_branch``, ``reason``
    (free-form description of the incoherence).

    Returns one P0 watchdog pattern per incoherent PR. The pattern body
    explains what the orchestrator detected and asks the operator to
    re-run the YOLO recovery path. The orchestrator's separate orphan-
    recovery-cache reset action runs alongside this bead filing.
    """
    project_lookup = project_lookup or {}
    patterns: list[WatchdogPattern] = []
    for entry in incoherent_prs:
        project_id = entry["project_id"]
        review_id = str(entry["review_id"])
        kind = entry["kind"]
        source_branch = entry.get("source_branch", "")
        reason = entry.get("reason", "")
        project_name = project_lookup.get(project_id, project_id)
        pattern_key = f"d3:{project_id}:{review_id}:{kind}"
        title = (
            f"YOLO bead-PR coherence break on {project_name}/{review_id}: "
            f"{kind} recovery bead missing or stale"
        )
        body = (
            f"PR #{review_id} on {project_name} (branch `{source_branch}`) "
            f"is in a state requiring `{kind}` recovery, but no matching "
            f"open bead exists.\n\n"
            f"- Reason: {reason or '(no detail)'}\n"
            f"- Detector: D3 (bead-PR coherence)\n"
            f"- Recovery: the YOLO orphan-recovery cache for this PR has "
            f"been cleared, so the next tick will re-attempt to file the "
            f"correct recovery bead. If this watchdog bead recurs without "
            f"resolution, an operator must investigate the PR by hand.\n"
        )
        patterns.append(WatchdogPattern(
            project_id=project_id,
            review_id=review_id,
            pattern_key=pattern_key,
            detector="d3",
            title=title,
            body=body,
            labels=("needs-human", "yolo-watchdog"),
            severity="p0",
        ))
    return patterns


# ---------------------------------------------------------------------------
# D4 — "PR already mergeable" detector
# ---------------------------------------------------------------------------


_ALREADY_MERGEABLE_NEEDLES: tuple[str, ...] = (
    "already mergeable",
    "pull request is in clean status",
)


def is_already_mergeable_error(msg: str) -> bool:
    """Heuristic: does this error message indicate "already mergeable"?

    Matches the GitHub GraphQL response when ``enablePullRequestAutoMerge``
    is called on a PR that has nothing blocking it. The PR can't enter
    auto-merge in that case because there's no condition to wait on —
    it should be merged directly.
    """
    if not msg:
        return False
    haystack = msg.lower()
    return any(needle in haystack for needle in _ALREADY_MERGEABLE_NEEDLES)


def count_consecutive_already_mergeable(
    history: Iterable[YoloActionRecord],
    project_id: str,
    review_id: str,
    *,
    action_type: str = "enqueue",
) -> int:
    """Count consecutive trailing 'already mergeable' failures.

    Used by D4 (and the orchestrator's strategy-switch logic) to decide
    whether to swap from auto-merge to direct merge for a given PR.
    """
    pertuple = [
        r for r in history
        if r.project_id == project_id
        and r.review_id == review_id
        and r.action_type == action_type
    ]
    pertuple.sort(key=lambda r: r.tick)
    count = 0
    for record in reversed(pertuple):
        if record.outcome != "failure":
            break
        if not is_already_mergeable_error(record.error_msg):
            break
        count += 1
    return count


def detect_d4_already_mergeable(
    history: Iterable[YoloActionRecord],
    *,
    threshold: int = D4_ALREADY_MERGEABLE_THRESHOLD,
    project_lookup: dict[str, str] | None = None,
) -> list[WatchdogPattern]:
    """D4 — same PR keeps reporting "already mergeable" on enqueue.

    Returns a P0 pattern per (project, review) once the consecutive-
    "already mergeable" count crosses ``threshold``. The orchestrator
    uses ``count_consecutive_already_mergeable`` separately to decide
    whether to switch strategy *before* the bead-filing threshold —
    the bead is only filed when the strategy switch itself has been
    insufficient (still failing).
    """
    history = list(history)
    if not history:
        return []
    project_lookup = project_lookup or {}

    seen: set[tuple[str, str]] = set()
    for r in history:
        seen.add((r.project_id, r.review_id))

    patterns: list[WatchdogPattern] = []
    for project_id, review_id in sorted(seen):
        # D4 counts consecutive "already mergeable" failures across BOTH
        # the original enqueue attempts AND any direct-merge fallback
        # attempts that report the same error. The orchestrator records
        # the fallback as action_type="merge_after_already_mergeable" so
        # we can tell them apart in the body.
        enqueue_run = count_consecutive_already_mergeable(
            history, project_id, review_id, action_type="enqueue",
        )
        fallback_run = count_consecutive_already_mergeable(
            history, project_id, review_id,
            action_type="merge_after_already_mergeable",
        )
        # Only escalate when the FALLBACK has also been failing for at
        # least one tick — i.e. we already switched strategy and it
        # didn't help. The orchestrator switches strategy at threshold
        # for the original enqueue, so when we see fallback_run >= 1
        # AND enqueue_run >= threshold, we know the switch is not
        # working and operator help is needed.
        if enqueue_run < threshold or fallback_run < 1:
            continue
        project_name = project_lookup.get(project_id, project_id)
        pattern_key = f"d4:{project_id}:{review_id}"
        title = (
            f"YOLO stuck on {project_name}/{review_id}: "
            f"'already mergeable' for {enqueue_run} ticks, "
            f"direct-merge fallback also failing"
        )
        body = (
            f"The YOLO loop has been told 'PR already mergeable' on "
            f"{project_name} review #{review_id} for {enqueue_run} "
            f"consecutive ticks. The orchestrator switched strategy to "
            f"direct merge after {threshold} ticks but the direct merge "
            f"is also failing ({fallback_run} ticks).\n\n"
            "This pattern matches the #59 case — operator must "
            "investigate why GitHub considers the PR mergeable while the "
            "merge endpoint refuses to land it.\n\n"
            f"- project_id: `{project_id}`\n"
            f"- review_id: `{review_id}`\n"
            f"- enqueue_already_mergeable_ticks: {enqueue_run}\n"
            f"- direct_merge_failure_ticks: {fallback_run}\n"
        )
        patterns.append(WatchdogPattern(
            project_id=project_id,
            review_id=review_id,
            pattern_key=pattern_key,
            detector="d4",
            title=title,
            body=body,
            labels=("needs-human", "yolo-watchdog"),
            severity="p0",
        ))
    return patterns


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def run_all_detectors(
    *,
    history: Iterable[YoloActionRecord],
    coverage_history: Iterable[CoverageRecord] = (),
    incoherent_prs: Iterable[dict] = (),
    project_lookup: dict[str, str] | None = None,
) -> list[WatchdogPattern]:
    """Run every v1 detector and return all patterns in dispatch order.

    The orchestrator calls this once per YOLO tick after recording
    actions and coverage stats. Returned patterns are ordered:
    D1 → D4 → D3 → D2.

    Note that D1 will catch D4-eligible patterns once they reach the
    D1 threshold (5 consecutive failures of any kind). The orchestrator
    handles deduplication by pattern_key — D4's key is more specific
    so D1+D4 simultaneous matches still file as separate beads only
    if neither has already been filed.
    """
    history = list(history)
    coverage_history = list(coverage_history)

    patterns: list[WatchdogPattern] = []
    patterns.extend(detect_d1_recurrent_failures(
        history, project_lookup=project_lookup,
    ))
    patterns.extend(detect_d4_already_mergeable(
        history, project_lookup=project_lookup,
    ))
    patterns.extend(detect_d3_bead_pr_coherence(
        incoherent_prs=incoherent_prs, project_lookup=project_lookup,
    ))
    patterns.extend(detect_d2_loop_coverage(coverage_history))
    return patterns
