"""OpenAPI-to-MCP tool-exposure policy for oompah's generated FastAPI schema.

OOMPAH-419: Define the oompah OpenAPI-to-MCP exposure policy.

Design decisions
----------------
1. **Fail-closed default**: any route not explicitly classified falls into
   :attr:`RouteCategory.UNKNOWN` and is denied.  The gateway layer
   (OOMPAH-420) must call :func:`is_route_exposed` before including any
   operation in the MCP tool catalog.

2. **Only two categories are exposed**: :attr:`RouteCategory.SAFE_READ`
   (read-only GET endpoints) and :attr:`RouteCategory.TASK_MUTATION` (core
   issue/task CRUD).  All other categories are denied.

3. **Denied categories and rationale**:
   - ``ADMIN_MUTATION`` — alters oompah service configuration.
   - ``CREDENTIAL_BEARING`` — manages external API keys/secrets.
   - ``WEBHOOK_INGESTION`` — requires HMAC/token validation at the HTTP layer
     that is meaningless over MCP transport.
   - ``ORCHESTRATOR_CONTROL`` — high-privilege lifecycle operations (restart,
     pause, resume, dispatch) that must not be agent-accessible.
   - ``RELEASE_DELIVERY`` — git-state and external-delivery mutations.
   - ``UNKNOWN`` — fail-closed catch-all.

4. **Authentication / token propagation**: the MCP gateway (OOMPAH-420)
   communicates with oompah's own API over loopback only.  It does NOT:
   - Forward ``Authorization`` headers from MCP clients to the oompah HTTP
     API.
   - Return credential material from oompah API responses to MCP clients.
   - Accept inbound authentication material from MCP clients.

5. **Service-discovery paths**:
   - MCP endpoint: ``/api/mcp/v1``
   - OpenAPI source consumed by the gateway: ``/openapi.json``
   - Well-known discovery metadata: ``/.well-known/mcp``

This module is the single source of truth for the exposure policy.  The
gateway (OOMPAH-420) imports :func:`classify_route` and
:func:`is_route_exposed` to filter OpenAPI operations before building the
MCP tool catalog.  No external configuration file can override the policy at
runtime — changes require a code review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Sequence


# ---------------------------------------------------------------------------
# Route category enum
# ---------------------------------------------------------------------------


class RouteCategory(str, Enum):
    """Classification for a single oompah API route (method + path template).

    The category determines whether the route is exposed as an MCP tool.
    """

    #: Read-only GET endpoints.  Exposed.
    SAFE_READ = "safe_read"

    #: Core issue/task CRUD: create, update state, comments, labels,
    #: dependencies.  Exposed — these are the bread-and-butter operations an
    #: MCP client needs for task management.
    TASK_MUTATION = "task_mutation"

    #: Administrative configuration mutations: project create/update/delete,
    #: project pause/resume, state-branch migration, bootstrap apply, template
    #: apply, agent-profile CRUD, role management, focus CRUD, console backend
    #: management, manual sync refresh, error reporting, review rebase/retry,
    #: attachment upload/delete, issue intake actions.  Denied.
    ADMIN_MUTATION = "admin_mutation"

    #: Provider and credential-management endpoints: add/update/delete
    #: providers, test provider credentials, fetch models using stored keys,
    #: auto-populate provider contexts.  Denied — these store, retrieve, or
    #: exercise external credentials.
    CREDENTIAL_BEARING = "credential_bearing"

    #: Inbound webhook handlers (GitHub, GitLab).  Denied — these require
    #: HMAC/token signature validation that is meaningless over MCP transport.
    WEBHOOK_INGESTION = "webhook_ingestion"

    #: Orchestrator lifecycle control: pause, resume, restart, manual dispatch.
    #: Denied — high-privilege operations that affect the oompah service itself.
    #: ``POST /api/v1/orchestrator/restart`` is especially sensitive.
    ORCHESTRATOR_CONTROL = "orchestrator_control"

    #: Release delivery pipeline mutations: trigger delivery, retry, archive,
    #: backlog refresh, release addendum create/retry/archive, release-pick
    #: mutations.  Denied — release delivery involves git state and external
    #: delivery systems.
    RELEASE_DELIVERY = "release_delivery"

    #: Catch-all for any route not matched by the classifier.  Denied — the
    #: policy defaults **fail-closed** for unrecognised routes.
    UNKNOWN = "unknown"


# Categories that are exposed as MCP tools (allow-list).
# Everything else is denied.
EXPOSED_CATEGORIES: frozenset[RouteCategory] = frozenset(
    {
        RouteCategory.SAFE_READ,
        RouteCategory.TASK_MUTATION,
    }
)

# ---------------------------------------------------------------------------
# Service-discovery constants
# ---------------------------------------------------------------------------

#: Path where the embedded MCP gateway (OOMPAH-420) mounts its endpoint.
MCP_ENDPOINT_PATH: str = "/api/mcp/v1"

#: FastAPI's generated OpenAPI schema path consumed by the gateway.
OPENAPI_SCHEMA_PATH: str = "/openapi.json"

#: Well-known metadata path for MCP service discovery.
MCP_DISCOVERY_PATH: str = "/.well-known/mcp"

# ---------------------------------------------------------------------------
# Internal rule representation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _RouteRule:
    """A single classification rule.

    ``method`` is an upper-cased HTTP method or ``"*"`` for any method.
    ``pattern`` matches against the OpenAPI path template string (with
    ``{param}`` placeholders) — converted from a FastAPI path template by
    :func:`_template_to_pattern`.
    """

    method: str
    pattern: re.Pattern[str]
    category: RouteCategory


def _template_to_pattern(path_template: str) -> re.Pattern[str]:
    """Convert a FastAPI/OpenAPI path template to a compiled full-match regex.

    Handles:
    * ``{param}`` → ``[^/]+`` (single path segment)
    * ``{param:path}`` → ``.+``  (path-type: can contain slashes)

    The returned pattern matches the full string (anchored ``^...$``).
    """
    # Escape everything, then un-escape the curly-brace groups we need to
    # expand.  re.escape turns ``{`` → ``\\{`` and ``}`` → ``\\}``.
    escaped = re.escape(path_template)
    escaped = escaped.replace(r"\{", "{").replace(r"\}", "}")
    # Expand ``{name:path}`` first (greedy — contains a colon)
    result = re.sub(r"\{[^}]+:[^}]+\}", ".+", escaped)
    # Expand plain ``{name}`` (single segment)
    result = re.sub(r"\{[^}]+\}", "[^/]+", result)
    return re.compile(r"^" + result + r"$")


# ---------------------------------------------------------------------------
# Classification rule table
# ---------------------------------------------------------------------------
#
# ORDER MATTERS: rules are evaluated top-to-bottom; the first match wins.
# More-specific patterns must appear before more-general ones.
#
# FastAPI path templates use ``{param}`` notation.  These are converted to
# regex patterns by :func:`_template_to_pattern`.  The ``method`` field is
# compared case-insensitively.


def _build_rules() -> list[_RouteRule]:  # noqa: PLR0915  (long but intentional)
    """Return the canonical ordered rule list for the exposure policy.

    Defined as a function (rather than a module-level list) so it can be
    called once and cached, and so test code can inspect the rule table
    without importing side-effects.
    """
    entries: list[tuple[str, str, RouteCategory]] = [
        # ----------------------------------------------------------------
        # ORCHESTRATOR_CONTROL — deny first (before any catch-all GET rule)
        # ----------------------------------------------------------------
        ("POST", "/api/v1/orchestrator/restart", RouteCategory.ORCHESTRATOR_CONTROL),
        ("POST", "/api/v1/orchestrator/pause", RouteCategory.ORCHESTRATOR_CONTROL),
        ("POST", "/api/v1/orchestrator/resume", RouteCategory.ORCHESTRATOR_CONTROL),
        ("POST", "/api/v1/orchestrator/dispatch/{identifier}", RouteCategory.ORCHESTRATOR_CONTROL),

        # ----------------------------------------------------------------
        # WEBHOOK_INGESTION — deny (signature-verified inbound handlers)
        # ----------------------------------------------------------------
        ("POST", "/api/v1/webhooks/github", RouteCategory.WEBHOOK_INGESTION),
        ("POST", "/api/v1/webhooks/gitlab", RouteCategory.WEBHOOK_INGESTION),

        # ----------------------------------------------------------------
        # CREDENTIAL_BEARING — deny (manage or exercise API keys/secrets)
        # ----------------------------------------------------------------
        ("POST", "/api/v1/providers", RouteCategory.CREDENTIAL_BEARING),
        ("PATCH", "/api/v1/providers/{provider_id}", RouteCategory.CREDENTIAL_BEARING),
        ("DELETE", "/api/v1/providers/{provider_id}", RouteCategory.CREDENTIAL_BEARING),
        ("POST", "/api/v1/providers/{provider_id}/test", RouteCategory.CREDENTIAL_BEARING),
        ("POST", "/api/v1/providers/fetch-models", RouteCategory.CREDENTIAL_BEARING),
        ("POST", "/api/v1/providers/{provider_id}/auto-populate-contexts", RouteCategory.CREDENTIAL_BEARING),

        # ----------------------------------------------------------------
        # RELEASE_DELIVERY — deny (git state + external delivery mutations)
        # ----------------------------------------------------------------
        # Specific release-delivery sub-paths must come before the generic
        # release-delivery base path rule.
        ("POST", "/api/v1/projects/{project_id}/release-delivery/backlog/refresh", RouteCategory.RELEASE_DELIVERY),
        ("POST", "/api/v1/projects/{project_id}/release-delivery/commits", RouteCategory.RELEASE_DELIVERY),
        ("POST", "/api/v1/projects/{project_id}/release-delivery/{delivery_id}/retry", RouteCategory.RELEASE_DELIVERY),
        ("POST", "/api/v1/projects/{project_id}/release-delivery/{delivery_id}/archive", RouteCategory.RELEASE_DELIVERY),
        ("POST", "/api/v1/issues/{identifier}/release-addendums", RouteCategory.RELEASE_DELIVERY),
        ("POST", "/api/v1/issues/{identifier}/release-addendums/{addendum_id}/retry", RouteCategory.RELEASE_DELIVERY),
        ("POST", "/api/v1/issues/{identifier}/release-addendums/{addendum_id}/archive", RouteCategory.RELEASE_DELIVERY),
        ("PATCH", "/api/v1/issues/{identifier}/release-picks", RouteCategory.RELEASE_DELIVERY),
        ("POST", "/api/v1/issues/{identifier}/release-picks/apply-all", RouteCategory.RELEASE_DELIVERY),

        # ----------------------------------------------------------------
        # ADMIN_MUTATION — deny (service configuration mutations)
        # ----------------------------------------------------------------
        # Project admin
        ("POST", "/api/v1/projects", RouteCategory.ADMIN_MUTATION),
        ("PATCH", "/api/v1/projects/{project_id}", RouteCategory.ADMIN_MUTATION),
        ("DELETE", "/api/v1/projects/{project_id}", RouteCategory.ADMIN_MUTATION),
        ("POST", "/api/v1/projects/{project_id}/pause", RouteCategory.ADMIN_MUTATION),
        ("POST", "/api/v1/projects/{project_id}/resume", RouteCategory.ADMIN_MUTATION),
        ("POST", "/api/v1/projects/{project_id}/state-branch/validate", RouteCategory.ADMIN_MUTATION),
        ("POST", "/api/v1/projects/{project_id}/state-branch/migrate", RouteCategory.ADMIN_MUTATION),
        ("POST", "/api/v1/projects/{project_id}/bootstrap/apply", RouteCategory.ADMIN_MUTATION),
        ("POST", "/api/v1/projects/{project_id}/issue-templates/apply", RouteCategory.ADMIN_MUTATION),
        # Agent-profile management
        ("POST", "/api/v1/agent-profiles", RouteCategory.ADMIN_MUTATION),
        ("PATCH", "/api/v1/agent-profiles/{name}", RouteCategory.ADMIN_MUTATION),
        ("DELETE", "/api/v1/agent-profiles/{name}", RouteCategory.ADMIN_MUTATION),
        # Role and role-matrix management
        ("PUT", "/api/v1/roles", RouteCategory.ADMIN_MUTATION),
        ("PUT", "/api/v1/agent-profiles/role-matrix", RouteCategory.ADMIN_MUTATION),
        # Focus management
        ("POST", "/api/v1/foci", RouteCategory.ADMIN_MUTATION),
        ("DELETE", "/api/v1/foci/{name}", RouteCategory.ADMIN_MUTATION),
        ("PATCH", "/api/v1/foci/{name}", RouteCategory.ADMIN_MUTATION),
        ("PATCH", "/api/v1/foci/suggestions/{name}", RouteCategory.ADMIN_MUTATION),
        # Console management
        ("POST", "/api/v1/console/{project_id}/backend", RouteCategory.ADMIN_MUTATION),
        ("DELETE", "/api/v1/console/{project_id}", RouteCategory.ADMIN_MUTATION),
        # Review operations
        ("POST", "/api/v1/reviews/{project_id}/{review_id}/rebase", RouteCategory.ADMIN_MUTATION),
        ("POST", "/api/v1/reviews/{project_id}/{review_id}/retry", RouteCategory.ADMIN_MUTATION),
        # Miscellaneous admin
        ("POST", "/api/v1/refresh", RouteCategory.ADMIN_MUTATION),
        ("POST", "/api/v1/errors", RouteCategory.ADMIN_MUTATION),
        ("POST", "/api/v1/issues/{identifier}/attachments", RouteCategory.ADMIN_MUTATION),
        ("DELETE", "/api/v1/attachments/{path}", RouteCategory.ADMIN_MUTATION),
        ("POST", "/api/v1/issues/{identifier}/intake/{action}", RouteCategory.ADMIN_MUTATION),

        # ----------------------------------------------------------------
        # TASK_MUTATION — allow (core issue/task management operations)
        # These must appear AFTER the more-specific deny rules above so that
        # overlapping POST /api/v1/issues/{identifier}/release-addendums and
        # similar are already claimed by RELEASE_DELIVERY.
        # ----------------------------------------------------------------
        ("POST", "/api/v1/issues", RouteCategory.TASK_MUTATION),
        ("PATCH", "/api/v1/issues/{identifier}", RouteCategory.TASK_MUTATION),
        ("POST", "/api/v1/issues/{identifier}/labels", RouteCategory.TASK_MUTATION),
        ("DELETE", "/api/v1/issues/{identifier}/labels/{label}", RouteCategory.TASK_MUTATION),
        ("POST", "/api/v1/issues/{identifier}/dependencies", RouteCategory.TASK_MUTATION),
        ("POST", "/api/v1/issues/{identifier}/comments", RouteCategory.TASK_MUTATION),

        # ----------------------------------------------------------------
        # SAFE_READ — allow (all read-only GET endpoints)
        # ----------------------------------------------------------------
        # Global
        ("GET", "/api/v1/state", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/issues", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/issues/{identifier}/detail", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/issues/{identifier}/comments", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/issues/{identifier}/attachments", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/issues/{identifier}/release-addendums", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/issues/{identifier}/release-picks", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/issues/{identifier}/release-picks/matrix", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/{issue_identifier}", RouteCategory.SAFE_READ),
        # Projects (read)
        ("GET", "/api/v1/projects", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/issue-quality-source", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/issue-templates/status", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/issue-templates/preview", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/bootstrap/status", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/bootstrap/preview", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/release-branches", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/release-branches/{branch_name}/addendums", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/release-delivery/commits", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/release-delivery/backlog", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/release-delivery/backlog/status", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/worktrees", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/state-branch/status", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/projects/{project_id}/state-branch/sync-check", RouteCategory.SAFE_READ),
        # Agents
        ("GET", "/api/v1/agents/{identifier}/activity", RouteCategory.SAFE_READ),
        # Providers (read-only — list without credential material)
        ("GET", "/api/v1/providers", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/acp-backends", RouteCategory.SAFE_READ),
        # Agent profiles (read)
        ("GET", "/api/v1/agent-profiles", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/agent-profiles/role-matrix", RouteCategory.SAFE_READ),
        # Roles (read)
        ("GET", "/api/v1/roles", RouteCategory.SAFE_READ),
        # Foci (read)
        ("GET", "/api/v1/foci", RouteCategory.SAFE_READ),
        ("GET", "/api/v1/foci/suggestions", RouteCategory.SAFE_READ),
        # Budget
        ("GET", "/api/v1/budget", RouteCategory.SAFE_READ),
        # Reviews (read)
        ("GET", "/api/v1/reviews", RouteCategory.SAFE_READ),
        # Attachments (read)
        ("GET", "/api/v1/attachments/{path}", RouteCategory.SAFE_READ),
        # Console transcript (read)
        ("GET", "/api/v1/console/{project_id}/transcript", RouteCategory.SAFE_READ),
    ]

    return [
        _RouteRule(
            method=method.upper(),
            pattern=_template_to_pattern(path),
            category=category,
        )
        for method, path, category in entries
    ]


# Module-level rule cache — built once at import time.
_RULES: list[_RouteRule] = _build_rules()

# ---------------------------------------------------------------------------
# Input validation for path strings
# ---------------------------------------------------------------------------
#
# Valid OpenAPI path template characters:
#   - ASCII letters, digits, ``/``, ``_``, ``-``, ``.``, ``~``
#   - ``{`` and ``}`` wrapping parameter names (e.g. ``{identifier}``)
#   - A colon inside braces for path-typed params: ``{path:path}``
#
# Anything else (``%``-encoding, ``?`` query strings, ``#`` fragments,
# whitespace, null bytes) indicates a malformed or adversarial input and is
# rejected before pattern matching.  This prevents adversarial strings from
# accidentally matching a broad rule (e.g. the generic ``{issue_identifier}``
# single-segment catch-all).

_VALID_OPENAPI_PATH_RE = re.compile(
    r"^[a-zA-Z0-9/_\{\}\.\-~:]*$"
)


def _is_valid_openapi_path(path: str) -> bool:
    """Return ``True`` when *path* looks like a plausible OpenAPI path template.

    Rejects URL-encoded segments (``%``), query strings (``?``), fragments
    (``#``), and any whitespace.  A path that fails this check is returned as
    :attr:`RouteCategory.UNKNOWN` (denied) by :func:`classify_route`.
    """
    if not path:
        return False
    return bool(_VALID_OPENAPI_PATH_RE.match(path))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_route(method: str, path: str) -> RouteCategory:
    """Return the :class:`RouteCategory` for the given HTTP method and path.

    *method* is the HTTP verb (case-insensitive, e.g. ``"GET"``, ``"post"``).
    *path* is the OpenAPI path template string, e.g.
    ``"/api/v1/issues/{identifier}"``.

    The classification is derived from the ordered rule table defined in this
    module.  **Unrecognised routes return** :attr:`RouteCategory.UNKNOWN`
    (denied by :func:`is_route_exposed`), implementing the fail-closed default.

    Input validation
    ~~~~~~~~~~~~~~~~
    Paths that contain URL-encoding (``%``), query strings (``?``), fragments
    (``#``), or whitespace are rejected as :attr:`RouteCategory.UNKNOWN`
    before any pattern matching occurs.  Valid OpenAPI path templates contain
    only ASCII letters, digits, ``/``, ``_``, ``-``, ``.``, ``~``, and
    parameter placeholders such as ``{identifier}`` or ``{path:path}``.

    This function is the primary entry-point for the gateway (OOMPAH-420)
    when it filters the OpenAPI schema.
    """
    if not method or not method.strip():
        return RouteCategory.UNKNOWN

    # Reject malformed / adversarial path strings before pattern matching.
    if not _is_valid_openapi_path(path):
        return RouteCategory.UNKNOWN

    method_upper = method.upper().strip()
    for rule in _RULES:
        if rule.method != "*" and rule.method != method_upper:
            continue
        if rule.pattern.match(path):
            return rule.category
    return RouteCategory.UNKNOWN


def is_route_exposed(method: str, path: str) -> bool:
    """Return ``True`` when the route should be included in the MCP tool catalog.

    A route is exposed only if :func:`classify_route` returns a category that
    is in :data:`EXPOSED_CATEGORIES` (:attr:`RouteCategory.SAFE_READ` or
    :attr:`RouteCategory.TASK_MUTATION`).

    All other categories — including :attr:`RouteCategory.UNKNOWN` — are
    denied.  This implements the **fail-closed** default: an unrecognised or
    newly-added route is not automatically exposed.

    Parameters
    ----------
    method:
        HTTP method string (case-insensitive).
    path:
        OpenAPI path template string (with ``{param}`` placeholders).

    Returns
    -------
    bool
        ``True`` → include in MCP catalog.
        ``False`` → exclude from MCP catalog.
    """
    return classify_route(method, path) in EXPOSED_CATEGORIES


def iter_exposed_routes() -> Iterator[tuple[str, str, RouteCategory]]:
    """Yield ``(method, openapi_path_template, category)`` for every rule that
    is currently exposed (i.e. :func:`is_route_exposed` would return ``True``).

    Useful for generating documentation and for debugging the effective tool
    surface.  The path templates use ``{param}`` notation from the original
    rule table — they match, but are not byte-for-byte identical to, the
    compiled regex patterns stored internally.
    """
    # Reconstruct the (method, path, category) triples from the rule list.
    # We store them alongside the compiled regex so we can emit them here.
    # Re-read the source entries for their original string form.
    for rule in _RULES:
        if rule.category in EXPOSED_CATEGORIES:
            # Recover the original path template from the pattern source.
            # The pattern.pattern is ``^...anchored...``, so we strip anchors.
            raw = rule.pattern.pattern.lstrip("^").rstrip("$")
            yield rule.method, raw, rule.category


def describe_policy() -> dict[str, object]:
    """Return a JSON-serialisable summary of the exposure policy.

    Intended for use in operator tooling and health/debug endpoints.  Does not
    include the compiled regex patterns (not serialisable) — use
    :func:`classify_route` for runtime checks.
    """
    total = len(_RULES)
    exposed = sum(1 for r in _RULES if r.category in EXPOSED_CATEGORIES)
    by_category: dict[str, int] = {}
    for rule in _RULES:
        key = rule.category.value
        by_category[key] = by_category.get(key, 0) + 1

    return {
        "mcp_endpoint": MCP_ENDPOINT_PATH,
        "openapi_source": OPENAPI_SCHEMA_PATH,
        "discovery_path": MCP_DISCOVERY_PATH,
        "total_classified_routes": total,
        "exposed_routes": exposed,
        "denied_routes": total - exposed,
        "exposed_categories": sorted(c.value for c in EXPOSED_CATEGORIES),
        "routes_by_category": by_category,
        "token_propagation": (
            "none — gateway communicates with oompah API over loopback only; "
            "no Authorization headers are forwarded to or from MCP clients"
        ),
        "fail_closed": True,
    }
