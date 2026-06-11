"""Intake readiness schema and metadata for oompah-managed GitHub issues (#283).

Defines the formal typed schema for the ``oompah.intake`` metadata field used
to record whether a proposed GitHub issue is ready to become backlog work.

Overview
--------

When a GitHub issue is created in a project tracked by oompah, it may start
in a ``Proposed`` state.  The intake workflow validates the issue, asks the
requestor for missing information, and — once the issue is sufficiently
well-formed and the requestor has approved the proposed scope — promotes it to
``Backlog``.  Project owners may bypass this flow with an explicit override.

This module defines the machine-readable intake state persisted in the hidden
``<!-- oompah:metadata … -->`` block in the issue body as ``"intake"``::

    <!-- oompah:metadata
    {"project_id": "proj-123", "target_branch": "main", "intake": {
        "missing_fields": [],
        "scope": "small",
        "requestor_approved": true,
        "requestor_approved_at": "2026-06-11T16:00:00Z",
        "requestor_actor": "alice",
        "owner_override": false,
        "owner_override_at": null,
        "owner_actor": null,
        "decomposition_status": "not_needed",
        "proposal_fingerprint": null,
        "last_validator_result": "pass",
        "last_validated_at": "2026-06-11T16:00:00Z"
    }}
    -->

The block is written by :func:`set_intake_metadata` and read by
:func:`get_intake_metadata` using the existing
:meth:`~oompah.github_tracker.GitHubIssueTracker.set_metadata_field` /
:meth:`~oompah.github_tracker.GitHubIssueTracker.get_metadata` API so that
existing metadata (``project_id``, ``target_branch``, ``work_branch``,
review fields, ``backports``, etc.) is always preserved.

Schema
------

``oompah.intake`` is a JSON object with the following fields:

=========================  ==========  =============================================
Field                      Type        Description
=========================  ==========  =============================================
``missing_fields``         list[str]   Required issue fields that are absent
                                       (e.g. ``["acceptance_criteria", "repro"]``)
``scope``                  string      Scope classification — one of
                                       ``"small"``, ``"large"``,
                                       ``"needs_decomposition"``, ``"unknown"``
``requestor_approved``     bool        True once the original requestor has
                                       approved the proposed scope
``requestor_approved_at``  str|null    ISO 8601 timestamp of requestor approval
``requestor_actor``        str|null    GitHub login of the approving requestor
``owner_override``         bool        True if a project owner overrode the
                                       intake result without requestor approval
``owner_override_at``      str|null    ISO 8601 timestamp of owner override
``owner_actor``            str|null    GitHub login of the overriding owner
``decomposition_status``   string      Status of epic/child decomposition —
                                       ``"not_needed"``, ``"pending"``,
                                       ``"proposed"``, ``"accepted"``,
                                       ``"rejected"``
``proposal_fingerprint``   str|null    Stable fingerprint of the latest
                                       generated epic/child-task proposal
``last_validator_result``  str|null    Result of the latest validation run —
                                       ``"pass"``, ``"fail"``, ``"pending"``,
                                       or ``null`` (never validated)
``last_validated_at``      str|null    ISO 8601 timestamp of the last validation
=========================  ==========  =============================================

Readiness contract
------------------

An issue is **ready** to be promoted from ``Proposed`` to ``Backlog`` when ALL
of the following hold:

1. ``missing_fields`` is empty (no required information absent).
2. ``scope`` is NOT ``"needs_decomposition"`` (issue is appropriately sized).
3. ``requestor_approved`` is ``True`` **OR** ``owner_override`` is ``True``.
4. ``last_validator_result`` is ``"pass"`` (most recent validator passed).

The :attr:`IntakeReadiness.is_ready` property encodes this contract.

Python API
----------

Module: ``oompah.intake_schema``

.. code-block:: python

    from oompah.intake_schema import (
        IntakeScopeKind,
        DecompositionStatus,
        ValidatorResult,
        IntakeReadiness,
        parse_intake_metadata,
        intake_to_raw,
    )

    # Parse from raw tracker metadata
    meta = tracker.get_metadata("lesserevil/oompah#42")
    readiness = parse_intake_metadata(meta.get("oompah.intake"))

    # Update
    readiness.requestor_approved = True
    readiness.requestor_approved_at = "2026-06-11T16:00:00Z"
    readiness.requestor_actor = "alice"

    # Persist (preserves all existing oompah metadata)
    tracker.set_metadata_field(
        "lesserevil/oompah#42",
        "oompah.intake",
        intake_to_raw(readiness),
    )

Compatibility
-------------

The schema is compatible with both ``task`` and ``epic`` issues.  An epic may
have ``decomposition_status = "accepted"`` to record that it was deliberately
converted from an oversized issue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class IntakeScopeKind(str, Enum):
    """Scope classification for a proposed issue.

    Values are lower-cased strings so they serialise cleanly as JSON and are
    readable by non-Python tooling.
    """

    #: Issue is well-scoped for a single implementation task.
    SMALL = "small"
    #: Issue is large but does not require decomposition (e.g. an intended epic).
    LARGE = "large"
    #: Issue is too large for one task and must be decomposed into an epic.
    NEEDS_DECOMPOSITION = "needs_decomposition"
    #: Scope has not been classified yet.
    UNKNOWN = "unknown"

    @classmethod
    def from_raw(cls, raw: Any) -> "IntakeScopeKind":
        """Parse a raw string into an :class:`IntakeScopeKind`.

        Returns :attr:`UNKNOWN` for unrecognised or missing values.
        """
        if isinstance(raw, cls):
            return raw
        if not raw:
            return cls.UNKNOWN
        normalised = str(raw).strip().lower().replace("-", "_")
        try:
            return cls(normalised)
        except ValueError:
            return cls.UNKNOWN


class DecompositionStatus(str, Enum):
    """Status of the epic/child-task decomposition proposal.

    Values are lower-cased strings for clean JSON serialisation.
    """

    #: Issue is appropriately sized; no decomposition required.
    NOT_NEEDED = "not_needed"
    #: Issue needs decomposition; proposal has not yet been generated.
    PENDING = "pending"
    #: An epic/child-task breakdown has been proposed and is awaiting review.
    PROPOSED = "proposed"
    #: The requestor or owner has accepted the proposed breakdown.
    ACCEPTED = "accepted"
    #: The proposed breakdown was rejected; issue may need rescoping.
    REJECTED = "rejected"

    @classmethod
    def from_raw(cls, raw: Any) -> "DecompositionStatus":
        """Parse a raw string into a :class:`DecompositionStatus`.

        Returns :attr:`NOT_NEEDED` for unrecognised or missing values.
        """
        if isinstance(raw, cls):
            return raw
        if not raw:
            return cls.NOT_NEEDED
        normalised = str(raw).strip().lower().replace("-", "_")
        try:
            return cls(normalised)
        except ValueError:
            return cls.NOT_NEEDED


class ValidatorResult(str, Enum):
    """Result of the latest automated intake validation run.

    Values are lower-cased strings for clean JSON serialisation.
    """

    #: Validation passed — issue meets all quality gates.
    PASS = "pass"
    #: Validation failed — issue is missing required information.
    FAIL = "fail"
    #: Validation is in progress or has not produced a result yet.
    PENDING = "pending"

    @classmethod
    def from_raw(cls, raw: Any) -> "ValidatorResult | None":
        """Parse a raw string into a :class:`ValidatorResult`.

        Returns ``None`` when *raw* is ``None`` or empty (i.e. never
        validated), and :attr:`PENDING` for unrecognised non-empty values.
        """
        if isinstance(raw, cls):
            return raw
        if raw is None or raw == "":
            return None
        normalised = str(raw).strip().lower()
        try:
            return cls(normalised)
        except ValueError:
            return cls.PENDING


# ---------------------------------------------------------------------------
# IntakeReadiness dataclass
# ---------------------------------------------------------------------------


@dataclass
class IntakeReadiness:
    """Machine-readable intake state for a proposed oompah-managed issue.

    Stored as the ``oompah.intake`` field in the hidden body metadata block.
    All fields are optional / have safe defaults so that a newly-created
    :class:`IntakeReadiness` represents the initial state of a fresh proposal.

    Attributes:
        missing_fields:
            Required issue fields that are absent from the current issue body.
            An empty list means all required fields are present.
            Example: ``["acceptance_criteria", "repro_steps"]``.
        scope:
            Scope classification of the proposed issue.
        requestor_approved:
            ``True`` once the original issue requestor has explicitly approved
            the proposed scope and acceptance criteria.
        requestor_approved_at:
            ISO 8601 timestamp string recording when requestor approval was
            granted, or ``None`` if not yet approved.
        requestor_actor:
            GitHub login of the requestor who approved, or ``None``.
        owner_override:
            ``True`` if a project owner has overridden the normal intake flow
            (e.g. fast-tracked an issue to ``Backlog`` without requestor
            approval, or force-rejected an approved issue).
        owner_override_at:
            ISO 8601 timestamp string recording when the owner override was
            applied, or ``None`` if no override is active.
        owner_actor:
            GitHub login of the project owner who applied the override, or
            ``None``.
        decomposition_status:
            Current state of the epic/child-task decomposition proposal.
        proposal_fingerprint:
            Stable fingerprint of the latest generated epic/child-task
            proposal.  Used to suppress duplicate proposal comments and child
            issue creation for unchanged decompositions.
        last_validator_result:
            Result of the most recent automated validation run, or ``None``
            if the issue has never been validated.
        last_validated_at:
            ISO 8601 timestamp string recording when the last validation was
            run, or ``None`` if never validated.
    """

    missing_fields: list[str] = field(default_factory=list)
    scope: IntakeScopeKind = IntakeScopeKind.UNKNOWN
    requestor_approved: bool = False
    requestor_approved_at: str | None = None
    requestor_actor: str | None = None
    owner_override: bool = False
    owner_override_at: str | None = None
    owner_actor: str | None = None
    decomposition_status: DecompositionStatus = DecompositionStatus.NOT_NEEDED
    proposal_fingerprint: str | None = None
    last_validator_result: ValidatorResult | None = None
    last_validated_at: str | None = None

    @property
    def is_ready(self) -> bool:
        """Return ``True`` when the issue satisfies all intake readiness criteria.

        The readiness contract requires ALL of the following:

        1. ``missing_fields`` is empty.
        2. ``scope`` is not :attr:`~IntakeScopeKind.NEEDS_DECOMPOSITION`.
        3. :attr:`requestor_approved` is ``True`` **or**
           :attr:`owner_override` is ``True``.
        4. :attr:`last_validator_result` is :attr:`~ValidatorResult.PASS`.
        """
        if self.missing_fields:
            return False
        if self.scope == IntakeScopeKind.NEEDS_DECOMPOSITION:
            return False
        if not (self.requestor_approved or self.owner_override):
            return False
        if self.last_validator_result != ValidatorResult.PASS:
            return False
        return True

    def to_raw(self) -> dict[str, Any]:
        """Serialise to a plain JSON-compatible dict for storage in body metadata.

        All fields are included so the stored representation is unambiguous.
        ``None`` values are preserved as ``null`` in JSON to allow callers to
        distinguish "never set" from "missing key".

        Returns:
            A dict suitable for passing to
            :meth:`~oompah.github_tracker.GitHubIssueTracker.set_metadata_field`
            as the ``"oompah.intake"`` value.
        """
        return {
            "missing_fields": list(self.missing_fields),
            "scope": self.scope.value,
            "requestor_approved": self.requestor_approved,
            "requestor_approved_at": self.requestor_approved_at,
            "requestor_actor": self.requestor_actor,
            "owner_override": self.owner_override,
            "owner_override_at": self.owner_override_at,
            "owner_actor": self.owner_actor,
            "decomposition_status": self.decomposition_status.value,
            "proposal_fingerprint": self.proposal_fingerprint,
            "last_validator_result": (
                self.last_validator_result.value
                if self.last_validator_result is not None
                else None
            ),
            "last_validated_at": self.last_validated_at,
        }

    @classmethod
    def from_raw(cls, raw: Any) -> "IntakeReadiness":
        """Parse a raw dict (from body metadata JSON) into an :class:`IntakeReadiness`.

        Missing keys use safe defaults so that the schema is forward- and
        backward-compatible: old issues without an ``intake`` block parse as
        a fresh :class:`IntakeReadiness`, and new fields added to the schema
        degrade gracefully on old stored data.

        Args:
            raw:
                Raw value from ``tracker.get_metadata(identifier).get("oompah.intake")``.
                Accepts a dict or ``None`` / any falsy value (returns defaults).

        Returns:
            An :class:`IntakeReadiness` parsed from *raw*.
        """
        if not raw or not isinstance(raw, dict):
            return cls()

        raw_missing = raw.get("missing_fields") or []
        if isinstance(raw_missing, str):
            raw_missing = [raw_missing]
        missing_fields = [str(f).strip() for f in raw_missing if str(f).strip()]

        return cls(
            missing_fields=missing_fields,
            scope=IntakeScopeKind.from_raw(raw.get("scope")),
            requestor_approved=bool(raw.get("requestor_approved", False)),
            requestor_approved_at=(
                str(raw["requestor_approved_at"])
                if raw.get("requestor_approved_at") is not None
                else None
            ),
            requestor_actor=(
                str(raw["requestor_actor"])
                if raw.get("requestor_actor") is not None
                else None
            ),
            owner_override=bool(raw.get("owner_override", False)),
            owner_override_at=(
                str(raw["owner_override_at"])
                if raw.get("owner_override_at") is not None
                else None
            ),
            owner_actor=(
                str(raw["owner_actor"])
                if raw.get("owner_actor") is not None
                else None
            ),
            decomposition_status=DecompositionStatus.from_raw(
                raw.get("decomposition_status")
            ),
            proposal_fingerprint=(
                str(raw["proposal_fingerprint"]).strip()
                if raw.get("proposal_fingerprint") is not None
                and str(raw.get("proposal_fingerprint")).strip()
                else None
            ),
            last_validator_result=ValidatorResult.from_raw(
                raw.get("last_validator_result")
            ),
            last_validated_at=(
                str(raw["last_validated_at"])
                if raw.get("last_validated_at") is not None
                else None
            ),
        )


# ---------------------------------------------------------------------------
# Top-level parsing helpers
# ---------------------------------------------------------------------------


def parse_intake_metadata(raw: Any) -> IntakeReadiness:
    """Parse the raw ``oompah.intake`` metadata value.

    Convenience wrapper around :meth:`IntakeReadiness.from_raw`.  Always
    returns an :class:`IntakeReadiness` — never raises; missing or malformed
    data produces a safe default state.

    Args:
        raw:
            Raw value from
            ``tracker.get_metadata(identifier).get("oompah.intake")``.

    Returns:
        An :class:`IntakeReadiness` representing the current intake state.
        Returns a fresh default instance when *raw* is ``None`` or empty.
    """
    return IntakeReadiness.from_raw(raw)


def intake_to_raw(readiness: IntakeReadiness) -> dict[str, Any]:
    """Serialise an :class:`IntakeReadiness` to a raw JSON-compatible dict.

    Convenience wrapper around :meth:`IntakeReadiness.to_raw`.

    Args:
        readiness: The :class:`IntakeReadiness` to serialise.

    Returns:
        A dict suitable for writing to the ``"oompah.intake"`` metadata field
        via :meth:`~oompah.github_tracker.GitHubIssueTracker.set_metadata_field`.
    """
    return readiness.to_raw()
