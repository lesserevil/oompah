"""Deterministic fault hooks for restart and workflow-boundary testing.

These adapters deliberately live outside the production decision path.  Tests
wrap the real durable stores, action handlers, trackers, journals, and Git
repositories, then inject a one-shot failure immediately before or after an
observable boundary.  A consumed script is serializable, so a failure can be
replayed exactly and a simulated process restart does not accidentally fire a
one-shot fault twice.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TypeVar

from oompah.workflow_jobs import WorkflowFailureCategory
from oompah.workflow_worker import WorkflowActionDomain, WorkflowActionError

FAULT_SCRIPT_SCHEMA_VERSION = 1
_SAFE_GIT_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_T = TypeVar("_T")


class FaultBoundary(str, Enum):
    JOB_ENQUEUE = "job_enqueue"
    JOB_LEASE = "job_lease"
    REVALIDATION = "revalidation"
    EXTERNAL_EFFECT = "external_effect"
    TRACKER_MUTATION = "tracker_mutation"
    VERIFICATION = "verification"
    TRANSITION_JOURNAL = "transition_journal"
    COMPLETION = "completion"


class FaultMoment(str, Enum):
    BEFORE = "before"
    AFTER = "after"


@dataclass(frozen=True, slots=True)
class FaultPoint:
    boundary: FaultBoundary | str
    moment: FaultMoment | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "boundary", FaultBoundary(self.boundary))
        object.__setattr__(self, "moment", FaultMoment(self.moment))

    @property
    def key(self) -> str:
        return f"{self.moment.value}:{self.boundary.value}"

    @classmethod
    def parse(cls, value: str) -> FaultPoint:
        moment, separator, boundary = str(value).partition(":")
        if not separator:
            raise ValueError("fault point must use '<moment>:<boundary>'")
        return cls(boundary, moment)


ALL_RESTART_POINTS = tuple(
    FaultPoint(boundary, moment) for boundary in FaultBoundary for moment in FaultMoment
)


class FaultKind(str, Enum):
    PROCESS_DEATH = "process_death"
    RETRYABLE_EXCEPTION = "retryable_exception"
    ACTION_REQUIRED = "action_required"


@dataclass(frozen=True, slots=True)
class FaultRule:
    point: FaultPoint
    kind: FaultKind | str = FaultKind.PROCESS_DEATH
    remaining: int = 1
    detail: str = "injected workflow fault"

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", FaultKind(self.kind))
        if self.remaining < 0:
            raise ValueError("fault rule remaining count cannot be negative")
        if not str(self.detail).strip():
            raise ValueError("fault rule detail is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "point": self.point.key,
            "kind": self.kind.value,
            "remaining": self.remaining,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> FaultRule:
        return cls(
            FaultPoint.parse(str(raw["point"])),
            str(raw.get("kind", FaultKind.PROCESS_DEATH.value)),
            int(raw.get("remaining", 1)),
            str(raw.get("detail", "injected workflow fault")),
        )


class InjectedProcessDeath(BaseException):
    """Simulated abrupt process loss; normal exception handlers cannot catch it."""

    def __init__(self, point: FaultPoint, detail: str) -> None:
        super().__init__(f"{point.key}: {detail}")
        self.point = point


class InjectedWorkflowFailure(WorkflowActionError):
    """Typed recoverable or action-required external failure."""

    def __init__(
        self, point: FaultPoint, detail: str, *, action_required: bool = False
    ) -> None:
        super().__init__(
            f"{point.key}: {detail}",
            category=(
                WorkflowFailureCategory.POLICY
                if action_required
                else WorkflowFailureCategory.TRANSIENT
            ),
            retryable=not action_required,
        )
        self.point = point
        self.action_required = bool(action_required)


class DeterministicFaultScript:
    """Ordered one-shot rules with stable JSON replay and observation counts."""

    def __init__(self, rules: Sequence[FaultRule] = ()) -> None:
        self._rules = list(rules)
        self._observations: dict[str, int] = {}

    def hit(self, point: FaultPoint) -> None:
        self._observations[point.key] = self._observations.get(point.key, 0) + 1
        for index, rule in enumerate(self._rules):
            if rule.point != point or rule.remaining == 0:
                continue
            self._rules[index] = FaultRule(
                rule.point,
                rule.kind,
                rule.remaining - 1,
                rule.detail,
            )
            if rule.kind is FaultKind.PROCESS_DEATH:
                raise InjectedProcessDeath(point, rule.detail)
            raise InjectedWorkflowFailure(
                point,
                rule.detail,
                action_required=rule.kind is FaultKind.ACTION_REQUIRED,
            )

    def observations(self, point: FaultPoint) -> int:
        return self._observations.get(point.key, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": FAULT_SCRIPT_SCHEMA_VERSION,
            "rules": [rule.to_dict() for rule in self._rules],
            "observations": dict(sorted(self._observations.items())),
        }

    def stable_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> DeterministicFaultScript:
        if int(raw.get("schema_version", 1)) != FAULT_SCRIPT_SCHEMA_VERSION:
            raise ValueError("unsupported fault-script schema_version")
        script = cls(tuple(FaultRule.from_dict(item) for item in raw.get("rules", ())))
        script._observations = {
            str(key): int(value)
            for key, value in dict(raw.get("observations") or {}).items()
        }
        return script

    @classmethod
    def from_json(cls, raw: str) -> DeterministicFaultScript:
        value = json.loads(raw)
        if not isinstance(value, Mapping):
            raise ValueError("fault script must be a JSON object")
        return cls.from_dict(value)


def run_sync_boundary(
    script: DeterministicFaultScript,
    boundary: FaultBoundary,
    operation: Callable[..., _T],
    *args: Any,
    **kwargs: Any,
) -> _T:
    script.hit(FaultPoint(boundary, FaultMoment.BEFORE))
    result = operation(*args, **kwargs)
    script.hit(FaultPoint(boundary, FaultMoment.AFTER))
    return result


async def run_async_boundary(
    script: DeterministicFaultScript,
    boundary: FaultBoundary,
    operation: Callable[..., Awaitable[_T]],
    *args: Any,
    **kwargs: Any,
) -> _T:
    script.hit(FaultPoint(boundary, FaultMoment.BEFORE))
    result = await operation(*args, **kwargs)
    script.hit(FaultPoint(boundary, FaultMoment.AFTER))
    return result


class FaultInjectingJobStore:
    """Duck-typed wrapper around a real :class:`WorkflowJobStore`."""

    def __init__(self, store: Any, script: DeterministicFaultScript) -> None:
        self.store = store
        self.script = script

    def enqueue(self, *args: Any, **kwargs: Any) -> Any:
        return run_sync_boundary(
            self.script, FaultBoundary.JOB_ENQUEUE, self.store.enqueue, *args, **kwargs
        )

    def claim_next(self, *args: Any, **kwargs: Any) -> Any:
        return run_sync_boundary(
            self.script, FaultBoundary.JOB_LEASE, self.store.claim_next, *args, **kwargs
        )

    def complete(self, *args: Any, **kwargs: Any) -> Any:
        return run_sync_boundary(
            self.script, FaultBoundary.COMPLETION, self.store.complete, *args, **kwargs
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.store, name)


class ActionHandler(Protocol):
    domain: WorkflowActionDomain | str

    async def revalidate(self, context: Any) -> Any: ...

    async def inspect(self, context: Any) -> Any: ...

    async def apply(self, context: Any) -> Any: ...

    async def verify(self, context: Any, effect: Any) -> Any: ...

    async def build_transition(self, context: Any, verification: Any) -> Any: ...


class FaultInjectingActionHandler:
    """Wrap revalidation, external effect, and verification boundaries."""

    def __init__(
        self, handler: ActionHandler, script: DeterministicFaultScript
    ) -> None:
        self.handler = handler
        self.script = script
        self.domain = WorkflowActionDomain(handler.domain)

    async def revalidate(self, context: Any) -> Any:
        return await run_async_boundary(
            self.script,
            FaultBoundary.REVALIDATION,
            self.handler.revalidate,
            context,
        )

    async def inspect(self, context: Any) -> Any:
        return await self.handler.inspect(context)

    async def apply(self, context: Any) -> Any:
        return await run_async_boundary(
            self.script,
            FaultBoundary.EXTERNAL_EFFECT,
            self.handler.apply,
            context,
        )

    async def verify(self, context: Any, effect: Any) -> Any:
        return await run_async_boundary(
            self.script,
            FaultBoundary.VERIFICATION,
            self.handler.verify,
            context,
            effect,
        )

    async def build_transition(self, context: Any, verification: Any) -> Any:
        return await self.handler.build_transition(context, verification)


class FaultInjectingTransitionJournal:
    """Wrap durable journal mutations while preserving the journal interface."""

    def __init__(self, journal: Any, script: DeterministicFaultScript) -> None:
        self.journal = journal
        self.script = script

    def begin(self, *args: Any, **kwargs: Any) -> Any:
        return run_sync_boundary(
            self.script,
            FaultBoundary.TRANSITION_JOURNAL,
            self.journal.begin,
            *args,
            **kwargs,
        )

    def append(self, *args: Any, **kwargs: Any) -> Any:
        return run_sync_boundary(
            self.script,
            FaultBoundary.TRANSITION_JOURNAL,
            self.journal.append,
            *args,
            **kwargs,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.journal, name)


class FaultInjectingTracker:
    """Wrap tracker mutation while allowing controlled read-path faults."""

    def __init__(
        self,
        tracker: Any,
        script: DeterministicFaultScript,
        *,
        reads: FaultedValueSource | None = None,
    ) -> None:
        self.tracker = tracker
        self.script = script
        self.reads = reads

    def update_issue(self, *args: Any, **kwargs: Any) -> Any:
        return run_sync_boundary(
            self.script,
            FaultBoundary.TRACKER_MUTATION,
            self.tracker.update_issue,
            *args,
            **kwargs,
        )

    def fetch_issue_detail(self, identifier: str) -> Any:
        current = self.tracker.fetch_issue_detail(identifier)
        return self.reads.read(current) if self.reads else current

    def __getattr__(self, name: str) -> Any:
        return getattr(self.tracker, name)


class ValueFaultMode(str, Enum):
    CURRENT = "current"
    MISSING = "missing"
    STALE = "stale"
    FETCH_FAILURE = "fetch_failure"
    TRANSPORT_FAILURE = "transport_failure"


class FaultedValueSource:
    """One-shot stale/missing/failing snapshot or transport adapter."""

    def __init__(
        self,
        mode: ValueFaultMode | str = ValueFaultMode.CURRENT,
        *,
        stale_value: Any = None,
        repeat: int = 1,
    ) -> None:
        if repeat < 0:
            raise ValueError("repeat cannot be negative")
        self.mode = ValueFaultMode(mode)
        self.stale_value = stale_value
        self.remaining = repeat

    def read(self, current: _T) -> _T | None:
        if self.remaining == 0 or self.mode is ValueFaultMode.CURRENT:
            return current
        self.remaining -= 1
        if self.mode is ValueFaultMode.MISSING:
            return None
        if self.mode is ValueFaultMode.STALE:
            return self.stale_value
        if self.mode is ValueFaultMode.FETCH_FAILURE:
            raise InjectedWorkflowFailure(
                FaultPoint(FaultBoundary.REVALIDATION, FaultMoment.BEFORE),
                "injected fetch failure",
            )
        raise InjectedWorkflowFailure(
            FaultPoint(FaultBoundary.EXTERNAL_EFFECT, FaultMoment.BEFORE),
            "injected transport failure",
        )


class EventDeliveryMode(str, Enum):
    NORMAL = "normal"
    DROP = "drop"
    DUPLICATE = "duplicate"


class EventDeliveryAdapter:
    """Deterministically drop or duplicate event notifications."""

    def __init__(self, mode: EventDeliveryMode | str) -> None:
        self.mode = EventDeliveryMode(mode)

    def deliver(self, event: _T) -> tuple[_T, ...]:
        if self.mode is EventDeliveryMode.DROP:
            return ()
        if self.mode is EventDeliveryMode.DUPLICATE:
            return (event, event)
        return (event,)


class AuthorityFaultAdapter:
    """Mutable auth/policy gate used to turn unsafe retries into action-required."""

    def __init__(self, *, authenticated: bool = True, policy_allows: bool = True):
        self.authenticated = authenticated
        self.policy_allows = policy_allows

    def require(self) -> None:
        if not self.authenticated:
            raise InjectedWorkflowFailure(
                FaultPoint(FaultBoundary.EXTERNAL_EFFECT, FaultMoment.BEFORE),
                "authentication changed",
                action_required=True,
            )
        if not self.policy_allows:
            raise InjectedWorkflowFailure(
                FaultPoint(FaultBoundary.EXTERNAL_EFFECT, FaultMoment.BEFORE),
                "policy changed",
                action_required=True,
            )


class ManualLeaseClock:
    """Controllable monotonic clock for deterministic lease expiry."""

    def __init__(self, now: float = 0) -> None:
        self.now = float(now)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("clock cannot move backwards")
        self.now += seconds


class GitFaultAdapter:
    """Apply explicit deleted-branch and moving-head faults to a real Git repo."""

    def __init__(self, repo: str | Path) -> None:
        self.repo = Path(repo).resolve()
        if not (self.repo / ".git").exists():
            raise ValueError("Git fault adapter requires a repository root")

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "git fault command failed")
        return result.stdout.strip()

    @staticmethod
    def _ref(value: str) -> str:
        ref = str(value).strip()
        if not _SAFE_GIT_REF.fullmatch(ref) or ref.startswith("-") or ".." in ref:
            raise ValueError("unsafe Git ref")
        return ref

    def delete_branch(self, branch: str) -> None:
        self._git("branch", "-D", self._ref(branch))

    def move_branch(self, branch: str, target: str) -> None:
        self._git("branch", "-f", self._ref(branch), self._ref(target))

    def change_head(self, branch: str, target: str) -> str:
        branch = self._ref(branch)
        target = self._ref(target)
        self._git("update-ref", f"refs/heads/{branch}", target)
        return self._git("rev-parse", f"refs/heads/{branch}")
