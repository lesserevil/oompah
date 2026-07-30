"""Durable metadata for a completed worker's integration handoff."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping


INTEGRATION_RECORD_VERSION = 1
INTEGRATION_STATES = frozenset(
    {
        "working",
        "ready",
        "queued",
        "integrating",
        "blocked",
        "integrated",
    }
)


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def expected_submission_branch(issue: object) -> str:
    """Return the branch a task is allowed to submit from.

    Dispatch persists ``work_branch`` before handing a task its worktree.
    Older tracker records may only have ``branch_name``; native tasks created
    before that metadata existed use their sanitized identifier, which is also
    ProjectStore's default branch name.
    """

    for attribute in ("work_branch", "branch_name"):
        value = str(getattr(issue, attribute, "") or "").strip()
        if value:
            return value
    identifier = str(getattr(issue, "identifier", "") or "").strip()
    if not identifier:
        raise ValueError("task identifier is required to validate task_branch")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", identifier).strip("._-") or "unnamed"


def validate_submission_branch(issue: object, task_branch: object) -> str:
    """Reject evidence captured from a checkout other than the task's branch."""

    submitted = str(task_branch or "").strip()
    if not submitted:
        raise ValueError("task_branch is required for task submission")
    expected = expected_submission_branch(issue)
    if submitted != expected:
        raise ValueError(
            f"submitted branch {submitted!r} does not match the task's expected "
            f"work branch {expected!r}; submit from the assigned task checkout"
        )
    return submitted


@dataclass(frozen=True)
class IntegrationRecord:
    """Versioned tracker record describing one task's integration state."""

    state: str
    task_branch: str | None = None
    base_branch: str | None = None
    base_sha: str | None = None
    head_sha: str | None = None
    integrated_sha: str | None = None
    attempts: int = 0
    submitted_at: str | None = None
    updated_at: str | None = None
    last_error: str | None = None
    dependency_heads: dict[str, str] = field(default_factory=dict)
    version: int = INTEGRATION_RECORD_VERSION

    def __post_init__(self) -> None:
        if self.version != INTEGRATION_RECORD_VERSION:
            raise ValueError(
                f"unsupported integration record version: {self.version}"
            )
        if self.state not in INTEGRATION_STATES:
            raise ValueError(f"unsupported integration state: {self.state!r}")
        if self.attempts < 0:
            raise ValueError("integration attempts cannot be negative")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IntegrationRecord":
        """Parse persisted metadata while ignoring unknown future fields."""

        raw_heads = value.get("dependency_heads")
        dependency_heads = (
            {
                str(identifier): str(sha)
                for identifier, sha in raw_heads.items()
                if str(identifier).strip() and str(sha).strip()
            }
            if isinstance(raw_heads, Mapping)
            else {}
        )
        try:
            version = int(value.get("version", INTEGRATION_RECORD_VERSION))
            attempts = int(value.get("attempts", 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("integration version and attempts must be integers") from exc
        return cls(
            version=version,
            state=str(value.get("state") or "").strip().lower(),
            task_branch=_optional_text(value.get("task_branch")),
            base_branch=_optional_text(value.get("base_branch")),
            base_sha=_optional_text(value.get("base_sha")),
            head_sha=_optional_text(value.get("head_sha")),
            integrated_sha=_optional_text(value.get("integrated_sha")),
            attempts=attempts,
            submitted_at=_optional_text(value.get("submitted_at")),
            updated_at=_optional_text(value.get("updated_at")),
            last_error=_optional_text(value.get("last_error")),
            dependency_heads=dependency_heads,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSON/YAML representation stored by trackers."""

        result: dict[str, Any] = {
            "version": self.version,
            "state": self.state,
            "attempts": self.attempts,
        }
        for key in (
            "task_branch",
            "base_branch",
            "base_sha",
            "head_sha",
            "integrated_sha",
            "submitted_at",
            "updated_at",
            "last_error",
        ):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        if self.dependency_heads:
            result["dependency_heads"] = dict(self.dependency_heads)
        return result


def parse_integration_record(value: object) -> IntegrationRecord | None:
    """Return a valid record, or ``None`` for missing/malformed metadata."""

    if not isinstance(value, Mapping):
        return None
    try:
        return IntegrationRecord.from_dict(value)
    except ValueError:
        return None


def validate_task_branch_authority(issue: object, task_branch: str) -> None:
    """Reject submission evidence from a branch owned by another task."""

    canonical_branch = _optional_text(
        getattr(issue, "work_branch", None)
        or getattr(issue, "branch_name", None)
    )
    if canonical_branch is None:
        existing = getattr(issue, "integration", None)
        canonical_branch = _optional_text(
            getattr(existing, "task_branch", None)
        )
    if canonical_branch is not None and task_branch != canonical_branch:
        raise ValueError(
            "task_branch does not match the task's canonical work branch"
        )
