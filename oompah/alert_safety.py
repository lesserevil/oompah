"""Safe, bounded projections for dashboard alerts.

Alert producers often receive exception messages and subprocess output.  That
text is useful to an operator, but it is not suitable for an always-visible
dashboard summary.  This module keeps the two presentation concerns separate:
the compact fields are one-line and tightly bounded, while a sanitized,
bounded diagnostic remains available to an explicit details control.

The projection is intentionally applied at more than one boundary.  Producers
can use :func:`sanitize_alert` when they create a failure alert, and the state
API applies :func:`sanitize_alerts` again before a snapshot can leave the
process.  This protects cached/IPC snapshots and older producers that still
only supply ``message``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from oompah.secrets import redact_sensitive_data


# These limits are presentation contracts, not storage limits.  In
# particular, diagnostics are deliberately much larger than the fields that
# can appear in the agent bar or the compact alert-center list.
ALERT_TITLE_MAX_LENGTH = 120
ALERT_SUMMARY_MAX_LENGTH = 240
ALERT_EXPLANATION_MAX_LENGTH = 480
ALERT_ACTION_MAX_LENGTH = 480
ALERT_SOURCE_MAX_LENGTH = 160
ALERT_DIAGNOSTIC_MAX_LENGTH = 4000
ALERT_PAYLOAD_TEXT_MAX_LENGTH = 4000
ALERT_MAX_NESTED_ITEMS = 100
ALERT_MAX_NESTED_DEPTH = 8
TRUNCATION_MARKER = "… [more]"
DIAGNOSTIC_AVAILABLE_TEXT = "Additional diagnostic output is available."

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b\u200c\u200d\ufeff]")
_WHITESPACE_RE = re.compile(r"\s+")
_HORIZONTAL_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")

_DIAGNOSTIC_KEYS = (
    "diagnostic",
    "diagnostics",
    "transcript",
    "output",
    "output_tail",
    "error",
    "stderr",
    "stdout",
)


def _text(value: object) -> str:
    """Convert arbitrary producer input without allowing conversion errors."""

    if value is None:
        return ""
    try:
        return str(value)
    except Exception:  # pragma: no cover - hostile __str__ implementation
        return "[unavailable]"


def _clean_controls(value: object, *, preserve_newlines: bool) -> str:
    """Normalize Unicode and remove layout-affecting control characters."""

    text = unicodedata.normalize("NFC", _text(value))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if preserve_newlines:
        text = _CONTROL_RE.sub(" ", text)
        # U+2028/U+2029 are line separators, but treating them as ordinary
        # spaces keeps a hostile provider response from inventing extra rows.
        text = text.replace("\u2028", " ").replace("\u2029", " ")
        return _HORIZONTAL_WHITESPACE_RE.sub(" ", text).strip()
    text = _CONTROL_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def bounded_text(value: object, limit: int, *, preserve_newlines: bool = False) -> str:
    """Return deterministic, sanitized text no longer than ``limit``.

    The marker is part of the limit, so callers can rely on the returned
    length.  Python slices Unicode code points, making truncation deterministic
    for emoji and other non-ASCII input as well as ordinary text.
    """

    limit = max(int(limit), 1)
    text = _clean_controls(value, preserve_newlines=preserve_newlines)
    if len(text) <= limit:
        return text
    if limit <= len(TRUNCATION_MARKER):
        return TRUNCATION_MARKER[:limit]
    return text[: limit - len(TRUNCATION_MARKER)].rstrip() + TRUNCATION_MARKER


def compact_alert_text(value: object, limit: int = ALERT_SUMMARY_MAX_LENGTH) -> str:
    """Normalize a visible alert field to one bounded line."""

    return bounded_text(value, limit)


def diagnostic_alert_text(
    value: object,
    limit: int = ALERT_DIAGNOSTIC_MAX_LENGTH,
) -> str:
    """Normalize and bound diagnostic text while retaining useful line breaks."""

    return bounded_text(value, limit, preserve_newlines=True)


def _was_truncated(value: object, limit: int, *, preserve_newlines: bool = False) -> bool:
    text = _clean_controls(value, preserve_newlines=preserve_newlines)
    return len(text) > max(int(limit), 1)


def _is_transcript_like(value: object, limit: int) -> bool:
    """Return whether a value is unsafe for a compact presentation field."""

    text = _clean_controls(value, preserve_newlines=True)
    return "\n" in text or len(text) > max(int(limit), 1)


def _bounded_payload(value: Any, *, depth: int = 0) -> Any:
    """Bound non-presentation metadata without changing its basic shape."""

    if depth >= ALERT_MAX_NESTED_DEPTH:
        return TRUNCATION_MARKER
    if isinstance(value, str):
        return diagnostic_alert_text(value, ALERT_PAYLOAD_TEXT_MAX_LENGTH)
    if isinstance(value, Mapping):
        return {
            compact_alert_text(key, ALERT_SOURCE_MAX_LENGTH): _bounded_payload(
                item, depth=depth + 1
            )
            for key, item in list(value.items())[:ALERT_MAX_NESTED_ITEMS]
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            _bounded_payload(item, depth=depth + 1)
            for item in list(value)[:ALERT_MAX_NESTED_ITEMS]
        ]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return diagnostic_alert_text(value, ALERT_PAYLOAD_TEXT_MAX_LENGTH)


def _default_title(source: object) -> str:
    source_text = _text(source).lower()
    if "integration" in source_text:
        return "Integration failure"
    if "audit" in source_text:
        return "Audit requires attention"
    if "gate" in source_text or "ci" in source_text:
        return "Quality gate failure"
    if "transport" in source_text or "webhook" in source_text:
        return "Transport failure"
    return "Oompah alert"


def sanitize_alert(alert: Mapping[str, Any]) -> dict[str, Any]:
    """Return a redacted, bounded alert safe for dashboard state.

    Legacy alerts that only contain ``message`` are projected into a compact
    title/summary and have their long message retained as ``diagnostic``.
    Explicit ``title``, ``detail``/``explanation``, ``action``/``remediation``
    and ``diagnostic`` fields are preserved with separate limits.
    """

    # Redact before inspecting or copying any text.  This also handles
    # configured opaque credentials that do not look like a token.
    redacted = redact_sensitive_data(dict(alert))
    if not isinstance(redacted, Mapping):  # defensive; the helper is typed broadly
        redacted = {}

    result: dict[str, Any] = {
        key: _bounded_payload(value)
        for key, value in redacted.items()
    }

    source = compact_alert_text(
        redacted.get("source", ""), ALERT_SOURCE_MAX_LENGTH
    )
    raw_title = redacted.get("title")
    raw_summary = redacted.get("summary")
    raw_message = redacted.get("message")

    transcript_like_title = _is_transcript_like(
        raw_title, ALERT_TITLE_MAX_LENGTH
    )
    transcript_like_summary = _is_transcript_like(
        raw_summary, ALERT_SUMMARY_MAX_LENGTH
    )
    transcript_like_message = _is_transcript_like(
        raw_message, ALERT_SUMMARY_MAX_LENGTH
    )
    title_seed = raw_title
    if transcript_like_title:
        title_seed = None
    if not _text(title_seed).strip() and not (
        transcript_like_message or transcript_like_summary
    ):
        title_seed = raw_message or raw_summary or _default_title(source)
    title = compact_alert_text(
        title_seed or _default_title(source), ALERT_TITLE_MAX_LENGTH
    )
    # A legacy producer may put the entire provider/subprocess transcript in
    # ``message``.  Once it looks transcript-like, the compact summary must
    # not merely be the first 240 characters of that transcript.
    summary_transcript_fallback = (
        transcript_like_summary
        or (transcript_like_message and not _text(raw_summary).strip())
    )
    summary_seed = (
        f"{title}. {TRUNCATION_MARKER}"
        if summary_transcript_fallback
        else raw_summary or raw_message or title
    )
    summary = compact_alert_text(summary_seed, ALERT_SUMMARY_MAX_LENGTH)

    raw_detail = redacted.get("detail") or redacted.get("explanation")
    detail = compact_alert_text(raw_detail, ALERT_EXPLANATION_MAX_LENGTH)
    detail_transcript_like = _is_transcript_like(
        raw_detail, ALERT_EXPLANATION_MAX_LENGTH
    )
    raw_action = redacted.get("action") or redacted.get("remediation")
    action = compact_alert_text(raw_action, ALERT_ACTION_MAX_LENGTH)

    raw_diagnostic: object = None
    for key in _DIAGNOSTIC_KEYS:
        candidate = redacted.get(key)
        if _text(candidate).strip():
            raw_diagnostic = candidate
            break
    if raw_diagnostic is None and transcript_like_message:
        raw_diagnostic = raw_message
    if raw_diagnostic is None and transcript_like_summary:
        raw_diagnostic = raw_summary
    if raw_diagnostic is None and transcript_like_title:
        raw_diagnostic = raw_title
    if raw_diagnostic is None and detail_transcript_like:
        raw_diagnostic = raw_detail
    if raw_diagnostic is not None:
        diagnostic = diagnostic_alert_text(raw_diagnostic)
        result["diagnostic"] = diagnostic
        result["diagnostic_available"] = True
        result["diagnostic_truncated"] = _was_truncated(
            raw_diagnostic, ALERT_DIAGNOSTIC_MAX_LENGTH, preserve_newlines=True
        )
        if not detail:
            detail = DIAGNOSTIC_AVAILABLE_TEXT
    if detail_transcript_like:
        detail = DIAGNOSTIC_AVAILABLE_TEXT

    result.update(
        {
            "source": source,
            "title": title,
            # ``message`` remains for existing clients; it is now a compact
            # compatibility alias rather than a raw transcript.
            "summary": summary,
            "message": summary,
        }
    )
    if detail:
        result["detail"] = detail
    else:
        result.pop("detail", None)
    if action:
        result["action"] = action
    else:
        result.pop("action", None)
    result.pop("explanation", None)
    result.pop("remediation", None)
    return result


def sanitize_alerts(alerts: object) -> list[dict[str, Any]]:
    """Project an arbitrary alert collection into safe dashboard records."""

    if not isinstance(alerts, (list, tuple)):
        return []
    return [
        sanitize_alert(alert)
        for alert in alerts
        if isinstance(alert, Mapping)
    ]


__all__ = [
    "ALERT_ACTION_MAX_LENGTH",
    "ALERT_DIAGNOSTIC_MAX_LENGTH",
    "ALERT_EXPLANATION_MAX_LENGTH",
    "ALERT_SOURCE_MAX_LENGTH",
    "ALERT_SUMMARY_MAX_LENGTH",
    "ALERT_TITLE_MAX_LENGTH",
    "DIAGNOSTIC_AVAILABLE_TEXT",
    "TRUNCATION_MARKER",
    "bounded_text",
    "compact_alert_text",
    "diagnostic_alert_text",
    "sanitize_alert",
    "sanitize_alerts",
]
