"""Prompt construction and template rendering for oompah."""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
from dataclasses import dataclass, field
from typing import Any

from liquid import Environment as LiquidEnvironment

from oompah.models import Issue, Project
from oompah.provenance import (
    ContentSource,
    ProvenanceComponent,
    make_provenance,
    wrap_untrusted,
)

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


def _project_to_template_vars(project: Project | None) -> dict[str, Any]:
    """Convert a Project to a dict for Liquid template rendering.

    Always returns a dict so templates can do ``{% if project.test_command %}``
    even when no project was passed (every value is the empty string / empty
    list in that case).
    """
    if project is None:
        return {
            "name": "",
            "branch": "",
            "test_command": "",
            "test_command_full": "",
            "test_skip_paths": [],
        }
    return {
        "name": project.name or "",
        "branch": project.default_branch or "",
        "test_command": project.test_command or "",
        "test_command_full": project.test_command_full or "",
        "test_skip_paths": list(project.test_skip_paths or []),
    }


def _content_source_for_issue(issue: Issue) -> ContentSource:
    """Return the :class:`~oompah.provenance.ContentSource` for an issue's body.

    GitHub-backed issues carry ``tracker_kind="github_issues"``; everything
    else is treated as human-authored native content.
    """
    kind = str(issue.tracker_kind or "").strip().lower()
    if kind == "github_issues":
        return ContentSource.GITHUB_ISSUE_BODY
    return ContentSource.HUMAN_COMMENT


def _comment_source_for_issue(issue: Issue) -> ContentSource:
    """Return the :class:`~oompah.provenance.ContentSource` for issue comments."""
    kind = str(issue.tracker_kind or "").strip().lower()
    if kind == "github_issues":
        return ContentSource.GITHUB_ISSUE_COMMENT
    return ContentSource.HUMAN_COMMENT


def _issue_to_template_vars(issue: Issue) -> dict[str, Any]:
    """Convert an Issue to a dict suitable for Liquid template rendering."""
    return {
        "id": issue.id,
        "identifier": issue.identifier,
        "title": issue.title,
        "description": issue.description or "",
        "priority": issue.priority,
        "state": issue.state,
        "issue_type": issue.issue_type or "task",
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
        # Tracker identity fields (TASK-457.2 / TASK-460.2).
        # ``tracker_kind`` drives conditional rendering in WORKFLOW.md:
        # "github_issues" and "oompah_md" use oompah task commands.
        "tracker_kind": issue.tracker_kind or "",
        "provider_url": issue.provider_url or "",
        "display_identifier": issue.display_identifier or "",
        "project_id": issue.project_id or "",
    }


def _wrap_issue_description(issue: Issue) -> str:
    """Return the issue description wrapped in provenance delimiters.

    Empty descriptions are returned as the empty string (no wrapper needed).
    """
    desc = issue.description or ""
    if not desc:
        return desc
    provenance = make_provenance(
        ProvenanceComponent.PROMPT_RENDERER,
        _content_source_for_issue(issue),
        issue_identifier=issue.identifier,
    )
    return wrap_untrusted(desc, provenance)


def _wrap_comment_text(text: str, issue: Issue) -> str:
    """Return comment *text* wrapped in provenance delimiters for *issue*.

    Empty strings are returned unchanged.
    """
    if not text:
        return text
    provenance = make_provenance(
        ProvenanceComponent.PROMPT_RENDERER,
        _comment_source_for_issue(issue),
        issue_identifier=issue.identifier,
    )
    return wrap_untrusted(text, provenance)


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
    project: Project | None = None,
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
        attachments or [],
        caps,
        project_root,
    )

    # Surface attachment metadata to the template (paths + per-item flags
    # so authors can render their own block if desired). This intentionally
    # exposes a flat list — the template doesn't need to care about
    # capability negotiation.
    template_attachments = []
    for spec in embed_specs:
        template_attachments.append(
            {
                "path": spec["path"],
                "mime": spec["mime"],
                "embedded": True,
            }
        )
    for spec in text_only_specs:
        template_attachments.append(
            {
                "path": spec["path"],
                "mime": spec["mime"],
                "embedded": False,
                "reason": spec.get("reason", ""),
            }
        )

    # Build template variable dict. Untrusted content (description, comment
    # text) is wrapped in provenance delimiters before interpolation so that
    # any Liquid template that renders these variables emits properly
    # delimited untrusted blocks (§5, §6.3 of the threat model).
    issue_vars = _issue_to_template_vars(issue)
    issue_vars["description"] = _wrap_issue_description(issue)

    wrapped_comments: list[dict[str, Any]] = []
    for c in (comments or []):
        raw_text = str(c.get("text") or "")
        wrapped = dict(c)
        wrapped["text"] = _wrap_comment_text(raw_text, issue)
        wrapped_comments.append(wrapped)

    variables: dict[str, Any] = {
        "issue": issue_vars,
        "attempt": attempt,
        "comments": wrapped_comments,
        "focus": focus_text or "",
        "agents_md": agents_md,
        "memories": [{"key": k, "insight": v} for k, v in (memories or {}).items()],
        "attachments": template_attachments,
        "project": _project_to_template_vars(project),
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
    abs_path = os.path.join(project_root, rel) if project_root else None
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
    """Build a continuation prompt for subsequent turns on the same thread.

    The turn-limit header is trusted (server-derived).  The issue title is
    untrusted (user/GitHub-provided) and is wrapped in provenance delimiters
    so the model can distinguish it from the server instruction text (§6.4).
    """
    title_provenance = make_provenance(
        ProvenanceComponent.CONTINUATION_PROMPTS,
        _content_source_for_issue(issue),
        issue_identifier=issue.identifier,
    )
    wrapped_title = wrap_untrusted(issue.title or "", title_provenance)
    return (
        f"Continue working on {issue.identifier}: {wrapped_title}. "
        f"This is turn {turn_number} of {max_turns}. "
        f"The issue is still in state '{issue.state}'. "
        "Review your previous work and continue where you left off."
    )
