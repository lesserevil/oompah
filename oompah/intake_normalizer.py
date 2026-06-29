"""Normalize Proposed task bodies to the canonical oompah native task template.

This module is intentionally pure: no I/O, no LLM calls, no side effects.
Callers handle all tracker reads and writes; this module only transforms body
strings.

## Normalization algorithm

1. Parse the full raw body to extract **all** headings (H1–H6) and their
   content, regardless of nesting level or position in the file.
2. Map each heading to a canonical field using the same keyword lists as the
   intake validator (:mod:`oompah.issue_validator`).
3. Build a new canonical body with:
   - A single ``## Summary`` section containing H3 sub-sections for each
     recognized field whose content is non-trivial.
   - Machine-marked placeholders (``<!-- oompah:placeholder field="…" -->``)
     for *required* fields whose content is absent or trivially empty.
   - Unrecognized content appended to ``## Notes``.
   - ``## External GitHub Issue`` and ``## Comments`` sections preserved
     verbatim at the top level.
4. Return the normalized body and a boolean indicating whether it changed.

## Placeholder format

    <!-- oompah:placeholder field="acceptance_criteria" -->
    _Please add acceptance criteria here._

Placeholders are machine-readable HTML comments.  The intake validator's
:func:`oompah.issue_validator._section_nonempty` function recognizes this
prefix and treats the section as absent, so placeholders never falsely satisfy
a required-field check.

## Integration helper

:func:`normalize_native_task` is a thin integration wrapper that reads the raw
body from a native tracker (``OompahMarkdownTracker``), calls
:func:`normalize_body`, and writes the result back when the body changed.  It
is a no-op for trackers that do not expose the ``get_raw_body`` /
``set_raw_body`` protocol — GitHub trackers are unaffected.
"""

from __future__ import annotations

import re
from typing import Any, NamedTuple

# ---------------------------------------------------------------------------
# Placeholder helpers
# ---------------------------------------------------------------------------

#: HTML comment prefix that marks an oompah-generated placeholder.
PLACEHOLDER_MARKER = "<!-- oompah:placeholder"

_PLACEHOLDER_RE = re.compile(r"<!--\s*oompah:placeholder\b", re.IGNORECASE)


def is_placeholder_content(text: str) -> bool:
    """Return ``True`` iff *text* contains a machine-marked placeholder."""
    return bool(_PLACEHOLDER_RE.search(text.strip()))


def make_placeholder(field_name: str) -> str:
    """Return a machine-marked placeholder string for *field_name*."""
    label = field_name.replace("_", " ")
    return (
        f'<!-- oompah:placeholder field="{field_name}" -->\n'
        f"_Please add {label} here._"
    )


# ---------------------------------------------------------------------------
# Canonical section definitions
# ---------------------------------------------------------------------------

#: Ordered list of canonical field names for the normalized body.
_CANONICAL_ORDER: list[str] = [
    "problem_statement",
    "desired_behavior",
    "repro_steps",
    "actual_behavior",
    "environment",
    "acceptance_criteria",
]

#: Human-readable H3 heading for each canonical field.
CANONICAL_HEADINGS: dict[str, str] = {
    "problem_statement": "Problem",
    "desired_behavior": "Desired Behavior",
    "repro_steps": "Steps to Reproduce",
    "actual_behavior": "Actual Behavior",
    "environment": "Environment",
    "acceptance_criteria": "Acceptance Criteria",
}

#: Fields that *must* have non-placeholder content for each issue type.
#: Placeholders are inserted only for fields listed here that are absent.
REQUIRED_BY_TYPE: dict[str, list[str]] = {
    "bug": ["problem_statement", "acceptance_criteria"],
    "feature": ["problem_statement", "acceptance_criteria"],
    "task": ["problem_statement", "acceptance_criteria"],
    "chore": ["problem_statement", "acceptance_criteria"],
    "epic": ["problem_statement"],
}

#: Map from lower-cased heading text to canonical field name.
_HEADING_TO_FIELD: dict[str, str] = {
    # problem_statement
    "problem": "problem_statement",
    "problem statement": "problem_statement",
    "background": "problem_statement",
    "context": "problem_statement",
    "motivation": "problem_statement",
    "rationale": "problem_statement",
    "overview": "problem_statement",
    "summary": "problem_statement",
    "description": "problem_statement",
    # desired_behavior
    "desired behavior": "desired_behavior",
    "desired behaviour": "desired_behavior",
    "expected behavior": "desired_behavior",
    "expected behaviour": "desired_behavior",
    "goal": "desired_behavior",
    "goals": "desired_behavior",
    "proposed solution": "desired_behavior",
    "solution": "desired_behavior",
    "approach": "desired_behavior",
    # acceptance_criteria
    "acceptance criteria": "acceptance_criteria",
    "acceptance criterion": "acceptance_criteria",
    "success criteria": "acceptance_criteria",
    "success criterion": "acceptance_criteria",
    "ac": "acceptance_criteria",
    "done criteria": "acceptance_criteria",
    "definition of done": "acceptance_criteria",
    "dod": "acceptance_criteria",
    # repro_steps (bugs)
    "steps to reproduce": "repro_steps",
    "reproduction steps": "repro_steps",
    "repro steps": "repro_steps",
    "how to reproduce": "repro_steps",
    "reproduce": "repro_steps",
    "repro": "repro_steps",
    # actual_behavior (bugs)
    "actual behavior": "actual_behavior",
    "actual behaviour": "actual_behavior",
    "current behavior": "actual_behavior",
    "current behaviour": "actual_behavior",
    "observed behavior": "actual_behavior",
    "observed behaviour": "actual_behavior",
    # environment
    "environment": "environment",
    "env": "environment",
    "setup": "environment",
    "system info": "environment",
}

#: Top-level H2 headings that are preserved verbatim (not folded into Summary).
_PRESERVED_HEADINGS: frozenset[str] = frozenset(
    {"external github issue", "notes", "comments"}
)

# ---------------------------------------------------------------------------
# Body section extraction
# ---------------------------------------------------------------------------

_ALL_HEADINGS_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$", re.MULTILINE)

# Regex matching trivial / default-template content.
_TRIVIAL_RE = re.compile(
    r"^[\s\-*_#|.\[\]]*"
    r"(?:tbd|todo|n/?a|none|unknown|\?+"
    r"|define\s+(?:acceptance|success)\s+criteria\.?"
    r")?"
    r"[\s\-*_#|.\[\]]*$",
    re.IGNORECASE,
)


class _Section(NamedTuple):
    level: int
    heading: str
    content: str


def _extract_sections(body: str) -> tuple[str, list[_Section]]:
    """Return ``(preamble, sections)`` from a raw body string.

    *preamble* is any text that appears before the first Markdown heading.
    *sections* is an ordered list of :class:`_Section` tuples, one per heading.
    """
    matches = list(_ALL_HEADINGS_RE.finditer(body))
    if not matches:
        return body.strip(), []

    preamble = body[: matches[0].start()].strip()
    sections: list[_Section] = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        heading = m.group(2).strip()
        content_start = m.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[content_start:content_end].strip()
        sections.append(_Section(level=level, heading=heading, content=content))
    return preamble, sections


def _is_trivial(text: str) -> bool:
    """Return ``True`` when *text* is effectively empty or a known placeholder."""
    return bool(_TRIVIAL_RE.fullmatch(text.strip()))


def _heading_to_field(heading: str) -> str | None:
    """Map *heading* to a canonical field name, or ``None``."""
    return _HEADING_TO_FIELD.get(heading.strip().lower())


def _is_preserved(heading: str) -> bool:
    """Return ``True`` when *heading* should stay as a top-level H2 section."""
    return heading.strip().lower() in _PRESERVED_HEADINGS


# ---------------------------------------------------------------------------
# Core normalization
# ---------------------------------------------------------------------------


def normalize_body(body: str, issue_type: str = "task") -> tuple[str, bool]:
    """Normalize a native oompah task body string.

    Parses *body* for all Markdown headings (H1–H6), maps recognized headings
    to canonical fields, and rebuilds the body with H3 sub-sections inside
    ``## Summary``.  Preserved top-level sections (``## External GitHub
    Issue``, ``## Notes``, ``## Comments``) are kept intact.  Unrecognized
    content is appended to ``## Notes``.

    Parameters
    ----------
    body:
        Raw body text from the native Markdown task file (after the YAML
        front matter ``---`` delimiter).
    issue_type:
        One of ``"bug"``, ``"feature"``, ``"task"``, ``"chore"``,
        ``"epic"``.  Determines which fields receive placeholder markup when
        they are absent.

    Returns
    -------
    tuple[str, bool]
        ``(normalized_body, was_changed)`` — the new body string and whether
        it differs meaningfully from the input.
    """
    effective_type = (issue_type or "task").strip().lower()
    required: set[str] = set(REQUIRED_BY_TYPE.get(effective_type, ["problem_statement", "acceptance_criteria"]))

    preamble, sections = _extract_sections(body)

    # ---- Step 1: classify sections ----------------------------------------
    field_contents: dict[str, list[str]] = {}   # field_name -> [content …]
    preserved_sections: list[_Section] = []     # kept as top-level H2
    extra_sections: list[_Section] = []         # unrecognized → fold into Notes

    for sec in sections:
        if _is_preserved(sec.heading):
            preserved_sections.append(sec)
            continue
        field = _heading_to_field(sec.heading)
        if field:
            # Accept only non-trivial, non-placeholder content.
            if sec.content and not _is_trivial(sec.content) and not is_placeholder_content(sec.content):
                field_contents.setdefault(field, []).append(sec.content)
        else:
            # Unrecognized heading — preserve content in Notes if non-trivial.
            if sec.content and not _is_trivial(sec.content):
                extra_sections.append(sec)

    # ---- Step 2: build canonical Summary content --------------------------
    summary_parts: list[str] = []

    # Preserve pre-heading preamble text (e.g. "Triggered by: OOMPAH-158").
    if preamble:
        summary_parts.append(preamble)

    for field in _CANONICAL_ORDER:
        if field in field_contents:
            combined = "\n\n".join(field_contents[field])
            heading = CANONICAL_HEADINGS[field]
            summary_parts.append(f"### {heading}\n\n{combined}")
        elif field in required:
            heading = CANONICAL_HEADINGS[field]
            summary_parts.append(f"### {heading}\n\n{make_placeholder(field)}")
        # Fields not found and not required are simply omitted.

    # Append unrecognized sections as H3 sub-sections (content preserved).
    for sec in extra_sections:
        summary_parts.append(f"### {sec.heading}\n\n{sec.content}")

    summary_content = "\n\n".join(summary_parts)

    # ---- Step 3: build full body ------------------------------------------
    body_parts: list[str] = [f"## Summary\n\n{summary_content}"]

    # Collect Notes content and the verbatim Comments block separately.
    notes_parts: list[str] = []
    comments_block: str | None = None

    for sec in preserved_sections:
        key = sec.heading.strip().lower()
        if key == "notes":
            if sec.content:
                notes_parts.append(sec.content)
        elif key == "comments":
            # Preserve verbatim including <!-- COMMENTS:BEGIN/END --> markers.
            block = f"## Comments\n\n{sec.content}" if sec.content else "## Comments\n\n"
            comments_block = block
        else:
            # External GitHub Issue or other unknown preserved section.
            block = f"## {sec.heading}\n\n{sec.content}" if sec.content else f"## {sec.heading}\n\n"
            body_parts.append(block)

    notes_text = "\n\n".join(notes_parts)
    body_parts.append(f"## Notes\n\n{notes_text}")

    if comments_block is not None:
        body_parts.append(comments_block)

    normalized = "\n\n".join(body_parts) + "\n"

    # ---- Step 4: change detection ----------------------------------------
    was_changed = _collapse_ws(normalized) != _collapse_ws(body)
    return normalized, was_changed


def _collapse_ws(text: str) -> str:
    """Collapse all whitespace runs for change-detection comparisons."""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Tracker integration helper
# ---------------------------------------------------------------------------


def normalize_native_task(
    tracker: Any,
    identifier: str,
    issue_type: str = "task",
) -> bool:
    """Normalize the body of a native oompah task if the tracker supports it.

    This function is a no-op for GitHub trackers or any tracker that does not
    implement ``get_raw_body`` / ``set_raw_body`` — the normalization is
    intentionally restricted to internal native Markdown tasks so that
    external GitHub issue bodies are never rewritten.

    Parameters
    ----------
    tracker:
        Any tracker object.  Only trackers exposing ``get_raw_body(identifier)``
        and ``set_raw_body(identifier, body)`` are normalised.
    identifier:
        Task identifier (e.g. ``"OOMPAH-159"``).
    issue_type:
        Issue type used to determine which required fields receive placeholders.

    Returns
    -------
    bool
        ``True`` when the body was rewritten; ``False`` when unchanged or
        unsupported.
    """
    get_body = getattr(tracker, "get_raw_body", None)
    set_body = getattr(tracker, "set_raw_body", None)
    if not callable(get_body) or not callable(set_body):
        return False

    try:
        current = get_body(identifier)
    except Exception:
        return False

    if current is None:
        return False

    normalized, was_changed = normalize_body(current, issue_type)
    if not was_changed:
        return False

    try:
        set_body(identifier, normalized)
    except Exception:
        return False

    return True
