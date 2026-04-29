"""Prompt construction and template rendering for oompah."""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
from dataclasses import dataclass, field
from typing import Any

from liquid import Environment as LiquidEnvironment

from oompah.models import Issue

logger = logging.getLogger(__name__)

_liquid_env = LiquidEnvironment()


# Cap on bytes serialized into a single user message. Multimodal payloads
# bloat fast as base64; this keeps prompts under typical provider limits.
_PER_PROMPT_BYTE_CAP = 20 * 1024 * 1024  # 20 MB
_PER_ATTACHMENT_BYTE_CAP = 25 * 1024 * 1024  # 25 MB (matches AttachmentStore)


class PromptError(Exception):
    """Raised when prompt rendering fails."""

    def __init__(self, message: str, error_class: str = "template_render_error"):
        super().__init__(message)
        self.error_class = error_class


@dataclass
class RenderedPrompt:
    """Result of :func:`render_prompt`.

    ``text`` is the canonical text rendering. When ``parts`` is set, the
    caller should send the OpenAI-style content array as the first user
    message; otherwise it falls back to a string ``content``. ``elided``
    lists attachment paths that exceeded a cap and were not embedded
    (a one-line note appears in ``text``).
    """

    text: str
    parts: list[dict[str, Any]] | None = None
    elided: list[str] = field(default_factory=list)


def _issue_to_template_vars(issue: Issue) -> dict[str, Any]:
    """Convert an Issue to a dict suitable for Liquid template rendering."""
    return {
        "id": issue.id,
        "identifier": issue.identifier,
        "title": issue.title,
        "description": issue.description or "",
        "priority": issue.priority,
        "state": issue.state,
        "branch_name": issue.branch_name or "",
        "url": issue.url or "",
        "labels": issue.labels,
        "blocked_by": [
            {
                "id": b.id or "",
                "identifier": b.identifier or "",
                "state": b.state or "",
            }
            for b in issue.blocked_by
        ],
        "created_at": issue.created_at.isoformat() if issue.created_at else "",
        "updated_at": issue.updated_at.isoformat() if issue.updated_at else "",
    }


def _read_agents_md(workspace_path: str | None) -> str:
    """Read AGENTS.md from the workspace if it exists."""
    if not workspace_path:
        return ""
    for name in ("AGENTS.md", "agents.md"):
        path = os.path.join(workspace_path, name)
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    return f.read().strip()
            except OSError:
                pass
    return ""


def render_prompt(
    template_source: str,
    issue: Issue,
    attempt: int | None = None,
    comments: list[dict] | None = None,
    focus_text: str | None = None,
    workspace_path: str | None = None,
    memories: dict[str, str] | None = None,
    attachments: list[str] | None = None,
    capabilities: list[str] | None = None,
    project_root: str | None = None,
) -> str | RenderedPrompt:
    """Render a Liquid prompt template with issue and attempt variables.

    Without ``attachments``/``capabilities``/``project_root`` the function
    behaves exactly as before and returns a plain string for callers that
    haven't migrated. When a project root and attachment list are
    supplied, returns a :class:`RenderedPrompt` whose ``parts`` carries an
    OpenAI-style content array if the resolved model supports image or
    audio. Unsupported attachments are still listed in the text portion
    with a "not sent — model lacks <modality>" note. Raises PromptError
    on parse or render failure.
    """
    if not template_source.strip():
        text = f"You are working on an issue from the project tracker.\n\nIssue: {issue.identifier} - {issue.title}"
        if attachments is not None:
            return RenderedPrompt(text=text, parts=None)
        return text

    try:
        template = _liquid_env.from_string(template_source)
    except Exception as exc:
        raise PromptError(
            f"Failed to parse prompt template: {exc}",
            error_class="template_parse_error",
        ) from exc

    agents_md = _read_agents_md(workspace_path)

    # Decide which attachments are embedded vs only mentioned in text.
    caps = set(capabilities or ["text"])
    embed_specs, text_only_specs, elided = _classify_attachments(
        attachments or [], caps, project_root,
    )

    # Surface attachment metadata to the template (paths + per-item flags
    # so authors can render their own block if desired). This intentionally
    # exposes a flat list — the template doesn't need to care about
    # capability negotiation.
    template_attachments = []
    for spec in embed_specs:
        template_attachments.append({
            "path": spec["path"], "mime": spec["mime"], "embedded": True,
        })
    for spec in text_only_specs:
        template_attachments.append({
            "path": spec["path"], "mime": spec["mime"], "embedded": False,
            "reason": spec.get("reason", ""),
        })

    variables: dict[str, Any] = {
        "issue": _issue_to_template_vars(issue),
        "attempt": attempt,
        "comments": comments or [],
        "focus": focus_text or "",
        "agents_md": agents_md,
        "memories": [
            {"key": k, "insight": v}
            for k, v in (memories or {}).items()
        ],
        "attachments": template_attachments,
    }

    try:
        rendered = template.render(**variables)
    except Exception as exc:
        raise PromptError(
            f"Failed to render prompt template: {exc}",
            error_class="template_render_error",
        ) from exc

    text = rendered.strip()

    # Append a small attachment note for anything that couldn't be
    # embedded so the agent at least knows the file exists.
    note_lines: list[str] = []
    for spec in text_only_specs:
        note_lines.append(
            f"- {spec['path']} ({spec['mime']}) — not sent: {spec.get('reason', 'unsupported')}"
        )
    if elided:
        note_lines.append(
            "(some attachments were elided to fit prompt size cap; see logs)"
        )
    if note_lines:
        text = text + "\n\n## Attachments (paths only)\n" + "\n".join(note_lines)

    if attachments is None:
        # Legacy callers — preserve the plain-string return type.
        return text

    parts: list[dict[str, Any]] | None = None
    if embed_specs:
        parts = [{"type": "text", "text": text}]
        for spec in embed_specs:
            parts.append(_content_part_for(spec))

    return RenderedPrompt(text=text, parts=parts, elided=elided)


def _classify_attachments(
    paths: list[str],
    capabilities: set[str],
    project_root: str | None,
) -> tuple[list[dict], list[dict], list[str]]:
    """Walk ``paths`` and split into (embed, text-only, elided) buckets.

    ``embed`` items are loaded into memory (within the per-prompt cap);
    ``text-only`` items are referenced in the text body only. ``elided``
    is the subset of paths that exceeded the cap and were dropped from
    embedding. Each bucket returns an attachment-spec dict (path, mime,
    abs_path, size, modality, reason).
    """
    embed: list[dict] = []
    text_only: list[dict] = []
    elided: list[str] = []
    running_total = 0

    for rel in paths:
        spec = _attachment_spec(rel, project_root)
        modality = _modality_of(spec["mime"])
        # Capability gate.
        if modality not in capabilities:
            spec["reason"] = f"model lacks {modality}"
            text_only.append(spec)
            continue
        # Size gate per-attachment.
        if spec["size"] > _PER_ATTACHMENT_BYTE_CAP:
            spec["reason"] = "exceeds per-attachment cap"
            text_only.append(spec)
            continue
        # Cumulative cap per prompt.
        if running_total + spec["size"] > _PER_PROMPT_BYTE_CAP:
            elided.append(spec["path"])
            spec["reason"] = "elided to fit prompt size cap"
            text_only.append(spec)
            continue
        # Read bytes only when we know we'll embed.
        if spec["abs_path"] and os.path.isfile(spec["abs_path"]):
            try:
                with open(spec["abs_path"], "rb") as f:
                    spec["data"] = f.read()
            except OSError as exc:
                logger.warning("attachment read failed for %s: %s", spec["path"], exc)
                spec["reason"] = f"read failed: {exc}"
                text_only.append(spec)
                continue
        else:
            spec["reason"] = "file not found in workspace"
            text_only.append(spec)
            continue
        embed.append(spec)
        running_total += spec["size"]

    return embed, text_only, elided


def _attachment_spec(rel: str, project_root: str | None) -> dict:
    abs_path = (
        os.path.join(project_root, rel) if project_root else None
    )
    size = 0
    if abs_path and os.path.isfile(abs_path):
        try:
            size = os.path.getsize(abs_path)
        except OSError:
            size = 0
    mime, _ = mimetypes.guess_type(rel)
    return {
        "path": rel,
        "abs_path": abs_path,
        "size": size,
        "mime": mime or "application/octet-stream",
    }


def _modality_of(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime == "application/pdf":
        # Many providers accept PDFs through the image content type after
        # a per-page render. For now treat PDFs as image-modality and let
        # the renderer decide whether to actually embed.
        return "image"
    return "text"


def _content_part_for(spec: dict) -> dict[str, Any]:
    """Build an OpenAI-style content part for an embed-bound spec."""
    data: bytes = spec.get("data") or b""
    mime: str = spec["mime"]
    b64 = base64.b64encode(data).decode("ascii")
    if mime.startswith("audio/"):
        # OpenAI input_audio.format expects a codec name, not the full
        # MIME subtype — strip x- prefixes and map common synonyms.
        subtype = mime.split("/", 1)[1].lower()
        fmt = subtype[2:] if subtype.startswith("x-") else subtype
        if fmt == "mpeg":
            fmt = "mp3"
        return {
            "type": "input_audio",
            "input_audio": {"data": b64, "format": fmt},
        }
    # image/* and pdf go through image_url.
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{b64}"},
    }


def build_continuation_prompt(issue: Issue, turn_number: int, max_turns: int) -> str:
    """Build a continuation prompt for subsequent turns on the same thread."""
    return (
        f"Continue working on {issue.identifier}: {issue.title}. "
        f"This is turn {turn_number} of {max_turns}. "
        f"The issue is still in state '{issue.state}'. "
        "Review your previous work and continue where you left off."
    )
