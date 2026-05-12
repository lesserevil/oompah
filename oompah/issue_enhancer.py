"""LLM-driven enhancement of operator-authored issues against project AGENTS.md.

When an operator creates an issue via the dashboard, the raw title + description
flow straight into ``bd create`` with no enhancement (server.py:api_create_issue).
AGENTS.md, which is meant to encode per-project quality standards, is only
consulted at agent dispatch time — never at issue creation time. So operator
issues land in the backlog without the project's quality criteria applied
(acceptance-criteria format, required fields, scoping conventions, etc.).

This module fills that gap. It exposes a pure-function ``enhance_issue`` that:

* Loads AGENTS.md from the target project's workspace (with a fall back to
  any WORKFLOW.md ``issue.quality`` block).
* Calls the configured LLM via the existing provider chain (default model
  role) with the operator's input as user content and the quality criteria
  as system context.
* Returns the enhanced title + description plus a diff describing what
  changed, leaving the write to the caller (which can preview, apply, or
  drop the suggestion).

The function is fail-loud: it raises ``IssueEnhancerError`` when no quality
source exists, no provider/model can be resolved, or the LLM call fails.
Callers (server.py) translate those errors into HTTP responses so the
dashboard can disable the Enhance button or show a meaningful error.

Out of scope for this module
----------------------------
* Editing existing issues (separate feature).
* Auto-enhancing agent-created beads (agents already follow AGENTS.md in
  their dispatch prompt).
* Writing the enhanced version to the tracker — the server endpoint owns
  the persistence side-effect.

See oompah-zlz_2-u8pz for the issue this implements.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Header patterns that delimit an ``issue.quality`` markdown block. We
# accept both ``issue.quality`` and ``issue quality`` for robustness, and
# match any markdown heading level. The section ends at the next markdown
# heading.
_ISSUE_QUALITY_HEADER_RE = re.compile(
    r"^#{1,6}\s*issue[.\s]quality\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_ANY_HEADER_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)

# Maximum quality-source bytes we feed into the prompt to keep tokens
# bounded. AGENTS.md tends to be a few KB, but we cap at ~20 KB to avoid
# pathological pages.
_MAX_QUALITY_BYTES = 20_000

# Timeout for individual chat completion requests, in seconds. The
# completion verifier uses the same _http_post entrypoint which has its
# own internal HTTP timeout (~600s); this constant is kept here for
# future async variants and as a documentation breadcrumb.
_LLM_TIMEOUT_S = 60.0


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


class IssueEnhancerError(Exception):
    """Raised when the enhancement cannot be produced.

    Specific causes:
    * No AGENTS.md and no WORKFLOW.md ``issue.quality`` block → caller
      should hide the Enhance button.
    * No provider/model resolvable from RoleStore → caller should surface
      a configuration error.
    * The LLM call itself failed (HTTP error, malformed response, etc.)
      → caller surfaces a transient error and lets the operator retry.

    The string message is intended for the dashboard / operator and so
    must not leak provider credentials.
    """


@dataclass
class EnhancementResult:
    """Outcome of an enhancement call.

    ``original_title`` and ``original_description`` echo the operator's
    input so the dashboard can render a before/after diff without
    re-sending the request. ``missing_fields`` is a freeform list of
    short labels (e.g. ``"acceptance criteria"``, ``"reproduction
    steps"``) that the LLM flagged as absent and could not infer a
    reasonable default for. ``diff`` is a unified-diff string built from
    the original vs. enhanced description for convenience.

    ``raw_response`` carries the parsed JSON the LLM returned, when the
    caller wants to surface the raw analysis in a debug surface (the
    dashboard's "Enhance" button shows only the structured fields).
    """

    original_title: str
    original_description: str
    enhanced_title: str
    enhanced_description: str
    missing_fields: list[str] = field(default_factory=list)
    suggested_changes: str = ""
    diff: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly serialisation for the HTTP response body."""
        return {
            "original": {
                "title": self.original_title,
                "description": self.original_description,
            },
            "enhanced": {
                "title": self.enhanced_title,
                "description": self.enhanced_description,
            },
            "missing_fields": list(self.missing_fields),
            "suggested_changes": self.suggested_changes,
            "diff": self.diff,
        }


# ---------------------------------------------------------------------------
# Quality-source loading
# ---------------------------------------------------------------------------


def read_agents_md(repo_path: str | None) -> str:
    """Return the AGENTS.md contents from ``repo_path`` or an empty string.

    Mirrors :func:`oompah.prompt._read_agents_md`. We re-implement here
    rather than importing to keep the enhancer's API surface decoupled
    from the prompt module — and because the enhancer is called from
    server.py during issue creation, where ``oompah.prompt`` would be a
    surprising dependency.
    """
    if not repo_path:
        return ""
    for name in ("AGENTS.md", "agents.md"):
        path = os.path.join(repo_path, name)
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    return f.read().strip()
            except OSError:
                logger.warning("issue_enhancer: failed to read %s", path)
    return ""


def extract_issue_quality_section(text: str) -> str:
    """Return the body of the ``# Issue Quality`` markdown section.

    Matches any heading level (``#``-``######``) containing ``issue.quality``
    or ``issue quality`` (case-insensitive). The section ends at the next
    markdown heading. Returns an empty string when the heading is
    absent.
    """
    if not text:
        return ""
    m = _ISSUE_QUALITY_HEADER_RE.search(text)
    if not m:
        return ""
    start = m.end()
    # Find the next heading after the matched one.
    tail = text[start:]
    next_m = _ANY_HEADER_RE.search(tail)
    if next_m is None:
        return tail.strip()
    return tail[: next_m.start()].strip()


def read_workflow_issue_quality(repo_path: str | None) -> str:
    """Return the WORKFLOW.md ``issue.quality`` block if present.

    Looks for ``WORKFLOW.md`` at the workspace root and extracts a
    ``# Issue Quality`` / ``## issue.quality`` section. Returns an
    empty string when the file is absent or the block is absent.
    """
    if not repo_path:
        return ""
    path = os.path.join(repo_path, "WORKFLOW.md")
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r") as f:
            content = f.read()
    except OSError:
        logger.warning("issue_enhancer: failed to read %s", path)
        return ""
    return extract_issue_quality_section(content)


def load_quality_source(repo_path: str | None) -> tuple[str, str]:
    """Return ``(source_kind, content)`` for the project's quality source.

    Precedence:
    1. ``AGENTS.md`` (workspace root)
    2. ``WORKFLOW.md`` ``issue.quality`` block
    3. ``("", "")`` — no source

    The ``source_kind`` is one of ``"agents_md"``, ``"workflow_quality"``,
    or the empty string. The Enhance UI button is hidden when the kind
    is empty (i.e., neither source exists).
    """
    agents = read_agents_md(repo_path)
    if agents:
        return "agents_md", agents[:_MAX_QUALITY_BYTES]
    quality = read_workflow_issue_quality(repo_path)
    if quality:
        return "workflow_quality", quality[:_MAX_QUALITY_BYTES]
    return "", ""


def has_quality_source(repo_path: str | None) -> bool:
    """Return True iff a quality source exists at ``repo_path``.

    Cheaper than :func:`load_quality_source` for the UI's ``hide the
    Enhance button`` check — we only need the existence answer, not the
    bytes.
    """
    if not repo_path:
        return False
    for name in ("AGENTS.md", "agents.md"):
        if os.path.isfile(os.path.join(repo_path, name)):
            return True
    workflow_path = os.path.join(repo_path, "WORKFLOW.md")
    if os.path.isfile(workflow_path):
        try:
            with open(workflow_path, "r") as f:
                if _ISSUE_QUALITY_HEADER_RE.search(f.read()):
                    return True
        except OSError:
            pass
    return False


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT_TEMPLATE = """You are an issue-quality assistant for a developer issue tracker.

Your job: take an operator's raw issue title + description, compare against the project's quality criteria (provided below), and return a polished version that conforms to the project's standards.

Project quality criteria
------------------------
{quality_source}

Output format (STRICT)
----------------------
Return a SINGLE JSON object (no prose before or after, no markdown fences) with these fields:

* ``title`` (string): A clearer title if the operator's was ambiguous, OR the original verbatim. Keep titles concise (<= 80 chars).
* ``description`` (string): The expanded markdown description that conforms to the project's quality criteria. Inline reasonable defaults where you can infer them. Preserve any specific technical details from the original.
* ``missing_fields`` (list[string]): Short labels (e.g. "acceptance criteria", "reproduction steps") for required fields you could not reasonably infer a default for. Empty list if nothing is missing.
* ``suggested_changes`` (string): A one-paragraph summary of what you changed and why. Plain prose, no markdown.

If the operator's input is already excellent and conforms to the criteria, return it essentially unchanged with ``missing_fields=[]`` and a short ``suggested_changes`` like "Original input already conforms to the project's quality criteria; no changes needed."

Never invent technical details. If you don't know something, list it in ``missing_fields`` instead of fabricating an answer."""


_USER_PROMPT_TEMPLATE = """Operator-authored issue
-----------------------
Title: {title}

Description:
{description}"""


def _build_messages(
    title: str,
    description: str,
    quality_source: str,
) -> list[dict[str, str]]:
    """Build the chat-completions message array.

    System: criteria + output schema. User: the operator's raw fields.
    Kept as a pure function so tests can assert the prompt shape
    without an LLM round-trip.
    """
    system = _SYSTEM_PROMPT_TEMPLATE.format(quality_source=quality_source.strip())
    user_desc = (description or "(no description provided)").strip()
    user = _USER_PROMPT_TEMPLATE.format(title=title.strip(), description=user_desc)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _strip_code_fence(text: str) -> str:
    """Remove a leading/trailing `````json`` fence if present.

    Some chat models wrap structured-output responses in markdown code
    fences despite explicit instructions not to. We strip them
    defensively so the caller's JSON parse succeeds.
    """
    s = text.strip()
    if s.startswith("```"):
        # Drop the opening fence (possibly with ``json`` language tag).
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1 :]
    if s.endswith("```"):
        s = s[: -3]
    return s.strip()


def parse_llm_response(content: str) -> dict[str, Any]:
    """Parse the LLM's JSON output into a normalised dict.

    Raises :class:`IssueEnhancerError` when the content can't be parsed
    or the required fields are missing.
    """
    if not content or not content.strip():
        raise IssueEnhancerError("LLM returned an empty response")
    body = _strip_code_fence(content)
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise IssueEnhancerError(f"LLM response was not valid JSON: {exc}")
    if not isinstance(data, dict):
        raise IssueEnhancerError(
            f"LLM response was JSON but not an object: {type(data).__name__}"
        )
    title = data.get("title")
    description = data.get("description")
    if not isinstance(title, str) or not title.strip():
        raise IssueEnhancerError("LLM response missing required 'title' string")
    if not isinstance(description, str):
        raise IssueEnhancerError("LLM response missing required 'description' string")
    missing = data.get("missing_fields") or []
    if not isinstance(missing, list):
        missing = []
    suggested = data.get("suggested_changes") or ""
    if not isinstance(suggested, str):
        suggested = ""
    return {
        "title": title.strip(),
        "description": description,
        "missing_fields": [str(m) for m in missing],
        "suggested_changes": suggested.strip(),
        "raw": data,
    }


# ---------------------------------------------------------------------------
# Diff helper
# ---------------------------------------------------------------------------


def build_unified_diff(original: str, enhanced: str) -> str:
    """Return a unified-diff string of original→enhanced description.

    Empty when the two are byte-identical. Used by the dashboard to
    render a side-by-side preview.
    """
    if original == enhanced:
        return ""
    diff = difflib.unified_diff(
        (original or "").splitlines(keepends=True),
        (enhanced or "").splitlines(keepends=True),
        fromfile="original",
        tofile="enhanced",
        lineterm="",
    )
    return "".join(diff)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def enhance_issue(
    *,
    title: str,
    description: str | None,
    repo_path: str | None,
    provider: Any,
    model: str | None,
) -> EnhancementResult:
    """Run the enhancement pipeline against ``provider``/``model``.

    Inputs
    ------
    title, description
        The operator's raw fields. ``description`` may be ``None`` —
        treated as empty.
    repo_path
        Workspace root containing AGENTS.md and/or WORKFLOW.md. When
        neither file carries a quality source, raises
        :class:`IssueEnhancerError` so the caller can surface that the
        Enhance button is misconfigured (the dashboard should never get
        here because it hides the button when no source exists, but we
        defend in depth).
    provider
        :class:`oompah.models.ModelProvider` (or equivalent test
        double). Must carry ``base_url`` and ``api_key``.
    model
        The chat-completions model name. Required.

    Raises
    ------
    IssueEnhancerError
        On any failure that should propagate as a user-visible error.

    Performs one chat-completions call. The temperature is set to 0.0
    for stable repeat-results — operators clicking Enhance twice on
    the same input should get the same answer.
    """
    if not title or not title.strip():
        raise IssueEnhancerError("title must be non-empty")
    source_kind, quality_source = load_quality_source(repo_path)
    if not quality_source:
        raise IssueEnhancerError(
            "No quality source found: AGENTS.md and WORKFLOW.md "
            "'Issue Quality' block both absent"
        )
    if provider is None:
        raise IssueEnhancerError("no provider resolved for the 'default' model role")
    base_url = (getattr(provider, "base_url", "") or "").rstrip("/")
    if not base_url:
        raise IssueEnhancerError("provider has no base_url configured")
    if not model:
        raise IssueEnhancerError("no model resolved for the 'default' role")

    messages = _build_messages(title=title, description=description or "", quality_source=quality_source)
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.0,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {getattr(provider, 'api_key', None) or ''}",
        "User-Agent": "oompah/0.1 issue-enhancer",
    }
    url = f"{base_url}/chat/completions"

    try:
        from oompah.api_agent import _build_ssl_context, _http_post  # lazy

        ssl_ctx = _build_ssl_context()
        response = _http_post(url, headers, body, ssl_ctx)
    except Exception as exc:
        raise IssueEnhancerError(f"LLM call failed: {exc}") from exc

    try:
        content = response["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise IssueEnhancerError(f"unexpected LLM response shape: {exc}") from exc

    parsed = parse_llm_response(content)
    enhanced_desc = parsed["description"]
    result = EnhancementResult(
        original_title=title,
        original_description=description or "",
        enhanced_title=parsed["title"],
        enhanced_description=enhanced_desc,
        missing_fields=parsed["missing_fields"],
        suggested_changes=parsed["suggested_changes"],
        diff=build_unified_diff(description or "", enhanced_desc),
        raw_response=parsed["raw"],
    )
    logger.info(
        "issue_enhancer: enhanced issue (source=%s, model=%s, missing=%d)",
        source_kind, model, len(result.missing_fields),
    )
    return result
