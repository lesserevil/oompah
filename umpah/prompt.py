"""Prompt construction and template rendering for umpah."""

from __future__ import annotations

import logging
from typing import Any

from liquid import Environment as LiquidEnvironment

from umpah.models import Issue

logger = logging.getLogger(__name__)

_liquid_env = LiquidEnvironment()


class PromptError(Exception):
    """Raised when prompt rendering fails."""

    def __init__(self, message: str, error_class: str = "template_render_error"):
        super().__init__(message)
        self.error_class = error_class


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


def render_prompt(
    template_source: str,
    issue: Issue,
    attempt: int | None = None,
) -> str:
    """Render a Liquid prompt template with issue and attempt variables.

    Raises PromptError on parse or render failure.
    """
    if not template_source.strip():
        return f"You are working on an issue from the project tracker.\n\nIssue: {issue.identifier} - {issue.title}"

    try:
        template = _liquid_env.from_string(template_source)
    except Exception as exc:
        raise PromptError(
            f"Failed to parse prompt template: {exc}",
            error_class="template_parse_error",
        ) from exc

    variables: dict[str, Any] = {
        "issue": _issue_to_template_vars(issue),
        "attempt": attempt,
    }

    try:
        rendered = template.render(**variables)
    except Exception as exc:
        raise PromptError(
            f"Failed to render prompt template: {exc}",
            error_class="template_render_error",
        ) from exc

    return rendered.strip()


def build_continuation_prompt(issue: Issue, turn_number: int, max_turns: int) -> str:
    """Build a continuation prompt for subsequent turns on the same thread."""
    return (
        f"Continue working on {issue.identifier}: {issue.title}. "
        f"This is turn {turn_number} of {max_turns}. "
        f"The issue is still in state '{issue.state}'. "
        "Review your previous work and continue where you left off."
    )
