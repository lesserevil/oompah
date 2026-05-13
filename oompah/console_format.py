"""Normalized event format for the operator Console (oompah-zlz_2-hoop).

The console transcript on disk (managed by :mod:`oompah.console_store`) is
backend-agnostic: events from the Claude Agent SDK and from Codex's
``openai-agents`` SDK both deserialize into the same :class:`ConsoleEvent`
shape. That lets the console UI render a uniform stream regardless of which
backend produced it, and lets a transcript recorded under one backend be
replayed (rehydrated) into a different backend later — the cross-agent
backend-switch story tracked in the umbrella epic.

Backend ↔ normalized translation lives next door in
:mod:`oompah.console_translators`. This module just defines the schema.

Design notes
------------

* **One flat list of events, not a tree.** Tool calls and their results
  are linked by ``args["_tool_use_id"]`` / ``result["tool_use_id"]``
  rather than nesting — the JSONL store is append-only and a tree
  shape would force re-writes.

* **Optional everything.** Every field except ``ts`` and ``kind`` is
  optional so a single dataclass covers all eight kinds. The
  per-kind expectations are documented in the :class:`ConsoleEvent`
  docstring.

* **String ISO-8601 timestamps.** The console_store JSONL uses string
  timestamps already; we keep that convention so ``since_ts`` string
  comparison keeps working without parsing.

* **Unknown kinds preserved.** ``raw_event_kind`` carries the
  original backend-specific kind when the translator falls back to
  ``session_meta`` for kinds it doesn't recognize. Drop-on-the-floor
  loses transcript context.

* **Replayability.** ``attachments`` (list of file paths the operator
  uploaded) is kept on ``operator_input`` events so a transcript
  replay can re-stage the attachment dir on the new backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

NORMALIZED_KINDS: tuple[str, ...] = (
    "operator_input",
    "agent_text",
    "agent_thinking",
    "tool_call",
    "tool_result",
    "permission",
    "session_meta",
    "error",
)
"""The eight normalized event kinds.

Per-kind field expectations:

* ``operator_input`` — ``text`` (required), ``attachments`` (optional)
* ``agent_text`` — ``text`` (required), ``model`` (optional)
* ``agent_thinking`` — ``text`` (required), ``model`` (optional)
* ``tool_call`` — ``tool`` (required), ``args`` (optional dict, may
  contain ``_tool_use_id`` link to a future ``tool_result``)
* ``tool_result`` — ``result`` (required dict, may contain
  ``tool_use_id``), ``is_error`` (defaults False)
* ``permission`` — ``tool`` (required), ``args`` (optional),
  ``is_error`` (True for deny, False for grant)
* ``session_meta`` — anything backend-specific (model, cwd, usage,
  result subtype, etc.) is opaquely passed through ``args`` /
  ``usage``; ``raw_event_kind`` carries the original kind for
  unknown-event passthrough
* ``error`` — ``text`` (required, human-readable), ``is_error=True``
"""


# Internal: cheap O(1) membership lookup used by from_dict.
_NORMALIZED_KINDS_SET = frozenset(NORMALIZED_KINDS)


# ---------------------------------------------------------------------------
# ConsoleEvent
# ---------------------------------------------------------------------------


@dataclass
class ConsoleEvent:
    """A single console transcript entry, in normalized form.

    See :data:`NORMALIZED_KINDS` for the per-kind field contract.

    Construction is permissive — any string is accepted as ``kind``,
    even one not in :data:`NORMALIZED_KINDS`. Validation (when needed)
    is opt-in via :meth:`is_known_kind`. This mirrors how the rest of
    oompah handles event schemas: fail-open at boundaries, log at the
    rare callsites that actually want to assert.

    ``to_dict`` / ``from_dict`` round-trip cleanly — fields whose
    value is ``None`` are omitted from the dict form so the on-disk
    JSONL stays compact and human-readable.
    """

    ts: str
    kind: str
    backend: str | None = None
    model: str | None = None
    text: str | None = None
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    is_error: bool = False
    usage: dict[str, Any] | None = None
    raw_event_kind: str | None = None
    # For replaying operator inputs into a fresh backend session.
    attachments: list[str] | None = None

    # ------------------------------------------------------------------
    # Predicates
    # ------------------------------------------------------------------

    def is_known_kind(self) -> bool:
        """``True`` iff ``kind`` is one of :data:`NORMALIZED_KINDS`."""
        return self.kind in _NORMALIZED_KINDS_SET

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Round-trippable dict form. Omits ``None`` and default-False fields.

        Required keys (always present): ``ts``, ``kind``.

        Optional keys appear only when their value differs from the
        dataclass default. This keeps the on-disk JSONL compact and
        makes diffing transcripts easy.
        """
        out: dict[str, Any] = {"ts": self.ts, "kind": self.kind}
        if self.backend is not None:
            out["backend"] = self.backend
        if self.model is not None:
            out["model"] = self.model
        if self.text is not None:
            out["text"] = self.text
        if self.tool is not None:
            out["tool"] = self.tool
        if self.args is not None:
            out["args"] = self.args
        if self.result is not None:
            out["result"] = self.result
        if self.is_error:
            out["is_error"] = True
        if self.usage is not None:
            out["usage"] = self.usage
        if self.raw_event_kind is not None:
            out["raw_event_kind"] = self.raw_event_kind
        if self.attachments is not None:
            out["attachments"] = list(self.attachments)
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ConsoleEvent":
        """Round-trip counterpart of :meth:`to_dict`.

        Permissive on missing/extra keys:

        * Missing ``ts`` defaults to ``""`` (caller's responsibility
          to validate when needed — we don't want a bad row in the
          JSONL to crash the whole transcript load).
        * Missing ``kind`` defaults to ``"session_meta"`` and the
          original kind (if any) is preserved in ``raw_event_kind``.
        * Extra keys are silently ignored.
        * Type coercion is best-effort: ``is_error`` is forced to
          bool; ``args``/``result``/``usage`` are coerced to dict (or
          dropped if not coercible); ``attachments`` to list (or
          dropped).
        """
        if not isinstance(d, dict):
            raise TypeError(
                f"ConsoleEvent.from_dict expects a dict, got {type(d).__name__}"
            )

        ts_raw = d.get("ts", "")
        ts = str(ts_raw) if ts_raw is not None else ""

        kind_raw = d.get("kind")
        raw_event_kind = d.get("raw_event_kind")
        if isinstance(kind_raw, str) and kind_raw:
            kind = kind_raw
        else:
            # Don't drop unknown rows — funnel them into session_meta
            # so they remain visible in the transcript.
            kind = "session_meta"
            if raw_event_kind is None and kind_raw is not None:
                raw_event_kind = str(kind_raw)

        def _opt_str(key: str) -> str | None:
            val = d.get(key)
            if val is None:
                return None
            return str(val)

        def _opt_dict(key: str) -> dict[str, Any] | None:
            val = d.get(key)
            if val is None:
                return None
            if isinstance(val, dict):
                # Shallow copy so the on-disk row and the in-memory
                # event don't share mutable state.
                return dict(val)
            # Best-effort: drop rather than crash on garbage.
            return None

        attachments_raw = d.get("attachments")
        if attachments_raw is None:
            attachments: list[str] | None = None
        elif isinstance(attachments_raw, list):
            attachments = [str(x) for x in attachments_raw]
        else:
            attachments = None

        return cls(
            ts=ts,
            kind=kind,
            backend=_opt_str("backend"),
            model=_opt_str("model"),
            text=_opt_str("text"),
            tool=_opt_str("tool"),
            args=_opt_dict("args"),
            result=_opt_dict("result"),
            is_error=bool(d.get("is_error", False)),
            usage=_opt_dict("usage"),
            raw_event_kind=(
                str(raw_event_kind) if raw_event_kind is not None else None
            ),
            attachments=attachments,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def make_operator_input(
    ts: str,
    text: str,
    *,
    attachments: list[str] | None = None,
    backend: str | None = None,
) -> ConsoleEvent:
    """Convenience constructor for the operator-input event.

    Used by the WS endpoint in oompah-zlz_2-g73s and by tests. Kept
    here (next to the dataclass) so the operator-input shape can't
    drift between callsites.
    """
    return ConsoleEvent(
        ts=ts,
        kind="operator_input",
        text=text,
        attachments=list(attachments) if attachments else None,
        backend=backend,
    )


def make_error(
    ts: str,
    text: str,
    *,
    backend: str | None = None,
    raw_event_kind: str | None = None,
) -> ConsoleEvent:
    """Convenience constructor for an error event. ``is_error=True``."""
    return ConsoleEvent(
        ts=ts,
        kind="error",
        text=text,
        backend=backend,
        is_error=True,
        raw_event_kind=raw_event_kind,
    )
