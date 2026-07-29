"""Durable metadata for a completed worker's integration handoff."""

from __future__ import annotations

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
