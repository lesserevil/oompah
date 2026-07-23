"""Tests for oompah.mcp_exposure_policy — OpenAPI-to-MCP exposure policy.

OOMPAH-419: Acceptance criteria for the exposure policy.

Test categories
---------------
1. ``TestRouteCategory``         — Enum values, string comparability.
2. ``TestExposedCategories``     — EXPOSED_CATEGORIES constant contents.
3. ``TestServiceDiscovery``      — MCP_ENDPOINT_PATH, OPENAPI_SCHEMA_PATH,
                                   MCP_DISCOVERY_PATH constants.
4. ``TestPathToPattern``         — _template_to_pattern helper (internal).
5. ``TestClassifyRouteSafeRead`` — All expected SAFE_READ routes are
                                   classified correctly.
6. ``TestClassifyRouteTaskMutation`` — All expected TASK_MUTATION routes.
7. ``TestClassifyRouteOrchestratorControl`` — Orchestrator routes are denied.
8. ``TestClassifyRouteWebhookIngestion``    — Webhook routes are denied.
9. ``TestClassifyRouteCredentialBearing``  — Provider/credential routes denied.
10. ``TestClassifyRouteAdminMutation``     — Admin routes are denied.
11. ``TestClassifyRouteReleaseDelivery``   — Release delivery routes denied.
12. ``TestClassifyRouteUnknown``           — Unrecognised routes fail-closed.
13. ``TestIsRouteExposed``                 — is_route_exposed() allow/deny
                                            integration for key routes.
14. ``TestFailClosed``                     — Fail-closed property for edge
                                            cases (new routes, wrong method,
                                            empty input).
15. ``TestDescribePolicy``                 — describe_policy() returns sane
                                            summary.
16. ``TestIterExposedRoutes``              — iter_exposed_routes() only yields
                                            exposed routes.
17. ``TestMethodCaseInsensitivity``        — method arg is case-insensitive.
18. ``TestInjectionResistance``            — Adversarial path strings cannot
                                            bypass the policy.
"""

from __future__ import annotations

import pytest

from oompah.mcp_exposure_policy import (
    EXPOSED_CATEGORIES,
    MCP_DISCOVERY_PATH,
    MCP_ENDPOINT_PATH,
    OPENAPI_SCHEMA_PATH,
    RouteCategory,
    _is_valid_openapi_path,
    _template_to_pattern,
    classify_route,
    describe_policy,
    is_route_exposed,
    iter_exposed_routes,
)


# ---------------------------------------------------------------------------
# 1. RouteCategory enum
# ---------------------------------------------------------------------------


class TestRouteCategory:
    def test_all_expected_values_exist(self):
        expected = {
            "safe_read",
            "task_mutation",
            "admin_mutation",
            "credential_bearing",
            "webhook_ingestion",
            "orchestrator_control",
            "release_delivery",
            "unknown",
        }
        actual = {c.value for c in RouteCategory}
        assert expected == actual

    def test_enum_extends_str(self):
        assert RouteCategory.SAFE_READ == "safe_read"
        assert RouteCategory.ORCHESTRATOR_CONTROL == "orchestrator_control"

    def test_all_values_unique(self):
        values = [c.value for c in RouteCategory]
        assert len(values) == len(set(values))

    def test_unknown_is_not_in_exposed_categories(self):
        assert RouteCategory.UNKNOWN not in EXPOSED_CATEGORIES

    def test_fail_closed_categories_are_not_exposed(self):
        denied = {
            RouteCategory.ADMIN_MUTATION,
            RouteCategory.CREDENTIAL_BEARING,
            RouteCategory.WEBHOOK_INGESTION,
            RouteCategory.ORCHESTRATOR_CONTROL,
            RouteCategory.RELEASE_DELIVERY,
            RouteCategory.UNKNOWN,
        }
        for cat in denied:
            assert cat not in EXPOSED_CATEGORIES


# ---------------------------------------------------------------------------
# 2. EXPOSED_CATEGORIES
# ---------------------------------------------------------------------------


class TestExposedCategories:
    def test_exposed_contains_safe_read(self):
        assert RouteCategory.SAFE_READ in EXPOSED_CATEGORIES

    def test_exposed_contains_task_mutation(self):
        assert RouteCategory.TASK_MUTATION in EXPOSED_CATEGORIES

    def test_exposed_has_exactly_two_categories(self):
        assert len(EXPOSED_CATEGORIES) == 2

    def test_exposed_categories_is_frozenset(self):
        assert isinstance(EXPOSED_CATEGORIES, frozenset)


# ---------------------------------------------------------------------------
# 3. Service-discovery constants
# ---------------------------------------------------------------------------


class TestServiceDiscovery:
    def test_mcp_endpoint_path(self):
        assert MCP_ENDPOINT_PATH == "/api/mcp/v1"

    def test_openapi_schema_path(self):
        assert OPENAPI_SCHEMA_PATH == "/openapi.json"

    def test_mcp_discovery_path(self):
        assert MCP_DISCOVERY_PATH == "/.well-known/mcp"

    def test_mcp_endpoint_path_starts_with_slash(self):
        assert MCP_ENDPOINT_PATH.startswith("/")

    def test_discovery_path_is_well_known(self):
        assert MCP_DISCOVERY_PATH.startswith("/.well-known/")


# ---------------------------------------------------------------------------
# 4. _template_to_pattern helper
# ---------------------------------------------------------------------------


class TestPathToPattern:
    def test_literal_path(self):
        p = _template_to_pattern("/api/v1/state")
        assert p.match("/api/v1/state")
        assert not p.match("/api/v1/state/extra")

    def test_single_param(self):
        p = _template_to_pattern("/api/v1/issues/{identifier}")
        assert p.match("/api/v1/issues/PROJ-42")
        assert p.match("/api/v1/issues/abc-123")
        assert not p.match("/api/v1/issues/PROJ-42/comments")

    def test_multiple_params(self):
        p = _template_to_pattern("/api/v1/projects/{project_id}/issues/{identifier}")
        assert p.match("/api/v1/projects/proj-abc/issues/TASK-1")
        assert not p.match("/api/v1/projects/proj-abc/issues/TASK-1/extra")

    def test_path_type_param(self):
        p = _template_to_pattern("/api/v1/attachments/{path:path}")
        assert p.match("/api/v1/attachments/dir/file.txt")
        assert p.match("/api/v1/attachments/a/b/c/d/e.png")

    def test_param_cannot_be_empty(self):
        p = _template_to_pattern("/api/v1/issues/{identifier}/detail")
        # single-segment param requires at least one character
        assert not p.match("/api/v1/issues//detail")

    def test_anchor_prevents_prefix_match(self):
        p = _template_to_pattern("/api/v1/state")
        assert not p.match("/api/v1/state/extra-path")

    def test_anchor_prevents_suffix_match(self):
        p = _template_to_pattern("/api/v1/issues/{identifier}")
        assert not p.match("prefix/api/v1/issues/PROJ-42")


# ---------------------------------------------------------------------------
# 4b. _is_valid_openapi_path input validation
# ---------------------------------------------------------------------------


class TestIsValidOpenapiPath:
    """Input sanitisation function for classify_route."""

    @pytest.mark.parametrize(
        "valid_path",
        [
            "/api/v1/state",
            "/api/v1/issues/{identifier}",
            "/api/v1/projects/{project_id}/release-delivery/commits",
            "/api/v1/attachments/{path:path}",
            "/api/v1/agent-profiles/role-matrix",
            "/",
            "",  # empty is rejected (returns False)
        ],
    )
    def test_valid_paths(self, valid_path: str):
        if valid_path == "":
            assert _is_valid_openapi_path(valid_path) is False
        else:
            assert _is_valid_openapi_path(valid_path) is True

    @pytest.mark.parametrize(
        "invalid_path",
        [
            # URL-encoding
            "/api/v1/orchestrator%2Frestart",
            "/api/v1/state%20extra",
            # Query strings
            "/api/v1/state?foo=bar",
            # Fragments
            "/api/v1/state#admin",
            # Whitespace
            " /api/v1/state",
            "/api/v1/state ",
            "\t/api/v1/state",
            "/api/v1/state\n/extra",
            # Null byte
            "/api/v1/state\x00/bad",
        ],
    )
    def test_invalid_paths_rejected(self, invalid_path: str):
        assert _is_valid_openapi_path(invalid_path) is False

    def test_empty_string_rejected(self):
        assert _is_valid_openapi_path("") is False


# ---------------------------------------------------------------------------
# 5. Classify SAFE_READ routes
# ---------------------------------------------------------------------------


class TestClassifyRouteSafeRead:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/v1/state"),
            ("GET", "/api/v1/issues"),
            ("GET", "/api/v1/issues/{identifier}/detail"),
            ("GET", "/api/v1/issues/{identifier}/comments"),
            ("GET", "/api/v1/issues/{identifier}/attachments"),
            ("GET", "/api/v1/issues/{identifier}/release-addendums"),
            ("GET", "/api/v1/issues/{identifier}/release-picks"),
            ("GET", "/api/v1/issues/{identifier}/release-picks/matrix"),
            ("GET", "/api/v1/{issue_identifier}"),
            ("GET", "/api/v1/projects"),
            ("GET", "/api/v1/projects/{project_id}"),
            ("GET", "/api/v1/projects/{project_id}/issue-quality-source"),
            ("GET", "/api/v1/projects/{project_id}/issue-templates/status"),
            ("GET", "/api/v1/projects/{project_id}/issue-templates/preview"),
            ("GET", "/api/v1/projects/{project_id}/bootstrap/status"),
            ("GET", "/api/v1/projects/{project_id}/bootstrap/preview"),
            ("GET", "/api/v1/projects/{project_id}/release-branches"),
            ("GET", "/api/v1/projects/{project_id}/release-branches/{branch_name}/addendums"),
            ("GET", "/api/v1/projects/{project_id}/release-delivery/commits"),
            ("GET", "/api/v1/projects/{project_id}/release-delivery/backlog"),
            ("GET", "/api/v1/projects/{project_id}/release-delivery/backlog/status"),
            ("GET", "/api/v1/projects/{project_id}/worktrees"),
            ("GET", "/api/v1/projects/{project_id}/state-branch/status"),
            ("GET", "/api/v1/projects/{project_id}/state-branch/sync-check"),
            ("GET", "/api/v1/agents/{identifier}/activity"),
            ("GET", "/api/v1/providers"),
            ("GET", "/api/v1/acp-backends"),
            ("GET", "/api/v1/agent-profiles"),
            ("GET", "/api/v1/agent-profiles/role-matrix"),
            ("GET", "/api/v1/roles"),
            ("GET", "/api/v1/foci"),
            ("GET", "/api/v1/foci/suggestions"),
            ("GET", "/api/v1/budget"),
            ("GET", "/api/v1/reviews"),
            ("GET", "/api/v1/attachments/{path}"),
            ("GET", "/api/v1/console/{project_id}/transcript"),
        ],
    )
    def test_safe_read_routes_are_classified(self, method: str, path: str):
        assert classify_route(method, path) == RouteCategory.SAFE_READ

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/v1/issues"),
            ("GET", "/api/v1/state"),
            ("GET", "/api/v1/projects"),
            ("GET", "/api/v1/budget"),
        ],
    )
    def test_safe_read_routes_are_exposed(self, method: str, path: str):
        assert is_route_exposed(method, path) is True


# ---------------------------------------------------------------------------
# 6. Classify TASK_MUTATION routes
# ---------------------------------------------------------------------------


class TestClassifyRouteTaskMutation:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/issues"),
            ("PATCH", "/api/v1/issues/{identifier}"),
            ("POST", "/api/v1/issues/{identifier}/labels"),
            ("DELETE", "/api/v1/issues/{identifier}/labels/{label}"),
            ("POST", "/api/v1/issues/{identifier}/dependencies"),
            ("POST", "/api/v1/issues/{identifier}/comments"),
        ],
    )
    def test_task_mutation_routes_are_classified(self, method: str, path: str):
        assert classify_route(method, path) == RouteCategory.TASK_MUTATION

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/issues"),
            ("PATCH", "/api/v1/issues/{identifier}"),
            ("POST", "/api/v1/issues/{identifier}/comments"),
        ],
    )
    def test_task_mutation_routes_are_exposed(self, method: str, path: str):
        assert is_route_exposed(method, path) is True


# ---------------------------------------------------------------------------
# 7. Classify ORCHESTRATOR_CONTROL routes (denied)
# ---------------------------------------------------------------------------


class TestClassifyRouteOrchestratorControl:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/orchestrator/restart"),
            ("POST", "/api/v1/orchestrator/pause"),
            ("POST", "/api/v1/orchestrator/resume"),
            ("POST", "/api/v1/orchestrator/dispatch/{identifier}"),
        ],
    )
    def test_orchestrator_routes_are_classified(self, method: str, path: str):
        assert classify_route(method, path) == RouteCategory.ORCHESTRATOR_CONTROL

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/orchestrator/restart"),
            ("POST", "/api/v1/orchestrator/pause"),
            ("POST", "/api/v1/orchestrator/resume"),
            ("POST", "/api/v1/orchestrator/dispatch/{identifier}"),
        ],
    )
    def test_orchestrator_routes_are_not_exposed(self, method: str, path: str):
        assert is_route_exposed(method, path) is False

    def test_restart_is_orchestrator_control(self):
        """Verify the highest-risk route is correctly denied."""
        assert classify_route("POST", "/api/v1/orchestrator/restart") == RouteCategory.ORCHESTRATOR_CONTROL

    def test_restart_is_not_exposed(self):
        """POST /orchestrator/restart must never appear in the MCP catalog."""
        assert is_route_exposed("POST", "/api/v1/orchestrator/restart") is False


# ---------------------------------------------------------------------------
# 8. Classify WEBHOOK_INGESTION routes (denied)
# ---------------------------------------------------------------------------


class TestClassifyRouteWebhookIngestion:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/webhooks/github"),
            ("POST", "/api/v1/webhooks/gitlab"),
        ],
    )
    def test_webhook_routes_are_classified(self, method: str, path: str):
        assert classify_route(method, path) == RouteCategory.WEBHOOK_INGESTION

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/webhooks/github"),
            ("POST", "/api/v1/webhooks/gitlab"),
        ],
    )
    def test_webhook_routes_are_not_exposed(self, method: str, path: str):
        assert is_route_exposed(method, path) is False

    def test_github_webhook_signature_cannot_be_bypassed_via_mcp(self):
        """GitHub webhook requires HMAC signature — must not be an MCP tool."""
        assert is_route_exposed("POST", "/api/v1/webhooks/github") is False

    def test_gitlab_webhook_token_cannot_be_bypassed_via_mcp(self):
        """GitLab webhook requires token header — must not be an MCP tool."""
        assert is_route_exposed("POST", "/api/v1/webhooks/gitlab") is False


# ---------------------------------------------------------------------------
# 9. Classify CREDENTIAL_BEARING routes (denied)
# ---------------------------------------------------------------------------


class TestClassifyRouteCredentialBearing:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/providers"),
            ("PATCH", "/api/v1/providers/{provider_id}"),
            ("DELETE", "/api/v1/providers/{provider_id}"),
            ("POST", "/api/v1/providers/{provider_id}/test"),
            ("POST", "/api/v1/providers/fetch-models"),
            ("POST", "/api/v1/providers/{provider_id}/auto-populate-contexts"),
        ],
    )
    def test_credential_bearing_routes_are_classified(self, method: str, path: str):
        assert classify_route(method, path) == RouteCategory.CREDENTIAL_BEARING

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/providers"),
            ("PATCH", "/api/v1/providers/{provider_id}"),
            ("DELETE", "/api/v1/providers/{provider_id}"),
            ("POST", "/api/v1/providers/{provider_id}/test"),
            ("POST", "/api/v1/providers/fetch-models"),
            ("POST", "/api/v1/providers/{provider_id}/auto-populate-contexts"),
        ],
    )
    def test_credential_bearing_routes_are_not_exposed(self, method: str, path: str):
        assert is_route_exposed(method, path) is False

    def test_provider_create_denied(self):
        """Creating a provider stores API keys — must not be MCP-accessible."""
        assert is_route_exposed("POST", "/api/v1/providers") is False

    def test_provider_test_denied(self):
        """Testing a provider exercises stored credentials — must not be MCP-accessible."""
        assert is_route_exposed("POST", "/api/v1/providers/{provider_id}/test") is False

    def test_provider_get_is_safe_read(self):
        """Listing providers (GET) is read-only and allowed."""
        assert classify_route("GET", "/api/v1/providers") == RouteCategory.SAFE_READ
        assert is_route_exposed("GET", "/api/v1/providers") is True


# ---------------------------------------------------------------------------
# 10. Classify ADMIN_MUTATION routes (denied)
# ---------------------------------------------------------------------------


class TestClassifyRouteAdminMutation:
    @pytest.mark.parametrize(
        "method,path",
        [
            # Project admin
            ("POST", "/api/v1/projects"),
            ("PATCH", "/api/v1/projects/{project_id}"),
            ("DELETE", "/api/v1/projects/{project_id}"),
            ("POST", "/api/v1/projects/{project_id}/pause"),
            ("POST", "/api/v1/projects/{project_id}/resume"),
            ("POST", "/api/v1/projects/{project_id}/state-branch/validate"),
            ("POST", "/api/v1/projects/{project_id}/state-branch/migrate"),
            ("POST", "/api/v1/projects/{project_id}/bootstrap/apply"),
            ("POST", "/api/v1/projects/{project_id}/issue-templates/apply"),
            # Agent profiles
            ("POST", "/api/v1/agent-profiles"),
            ("PATCH", "/api/v1/agent-profiles/{name}"),
            ("DELETE", "/api/v1/agent-profiles/{name}"),
            # Roles
            ("PUT", "/api/v1/roles"),
            ("PUT", "/api/v1/agent-profiles/role-matrix"),
            # Foci
            ("POST", "/api/v1/foci"),
            ("DELETE", "/api/v1/foci/{name}"),
            ("PATCH", "/api/v1/foci/{name}"),
            ("PATCH", "/api/v1/foci/suggestions/{name}"),
            # Console
            ("POST", "/api/v1/console/{project_id}/backend"),
            ("DELETE", "/api/v1/console/{project_id}"),
            # Reviews
            ("POST", "/api/v1/reviews/{project_id}/{review_id}/rebase"),
            ("POST", "/api/v1/reviews/{project_id}/{review_id}/retry"),
            # Misc
            ("POST", "/api/v1/refresh"),
            ("POST", "/api/v1/errors"),
            ("POST", "/api/v1/issues/{identifier}/attachments"),
            ("DELETE", "/api/v1/attachments/{path}"),
            ("POST", "/api/v1/issues/{identifier}/intake/{action}"),
        ],
    )
    def test_admin_mutation_routes_are_classified(self, method: str, path: str):
        assert classify_route(method, path) == RouteCategory.ADMIN_MUTATION

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/projects"),
            ("DELETE", "/api/v1/projects/{project_id}"),
            ("POST", "/api/v1/projects/{project_id}/state-branch/migrate"),
            ("PUT", "/api/v1/roles"),
            ("POST", "/api/v1/refresh"),
            ("POST", "/api/v1/errors"),
        ],
    )
    def test_admin_mutation_routes_are_not_exposed(self, method: str, path: str):
        assert is_route_exposed(method, path) is False

    def test_project_delete_is_admin_mutation(self):
        """Deleting a project must not be an MCP tool."""
        assert is_route_exposed("DELETE", "/api/v1/projects/{project_id}") is False

    def test_state_branch_migrate_is_admin_mutation(self):
        """State branch migration is destructive — must not be an MCP tool."""
        assert is_route_exposed("POST", "/api/v1/projects/{project_id}/state-branch/migrate") is False

    def test_intake_action_is_admin_mutation(self):
        """Issue intake actions gate agent dispatch — must not be an MCP tool."""
        assert is_route_exposed("POST", "/api/v1/issues/{identifier}/intake/{action}") is False

    def test_refresh_is_admin_mutation(self):
        """POST /refresh triggers a full orchestrator sync — must not be an MCP tool."""
        assert is_route_exposed("POST", "/api/v1/refresh") is False


# ---------------------------------------------------------------------------
# 11. Classify RELEASE_DELIVERY routes (denied)
# ---------------------------------------------------------------------------


class TestClassifyRouteReleaseDelivery:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/projects/{project_id}/release-delivery/backlog/refresh"),
            ("POST", "/api/v1/projects/{project_id}/release-delivery/commits"),
            ("POST", "/api/v1/projects/{project_id}/release-delivery/{delivery_id}/retry"),
            ("POST", "/api/v1/projects/{project_id}/release-delivery/{delivery_id}/archive"),
            ("POST", "/api/v1/issues/{identifier}/release-addendums"),
            ("POST", "/api/v1/issues/{identifier}/release-addendums/{addendum_id}/retry"),
            ("POST", "/api/v1/issues/{identifier}/release-addendums/{addendum_id}/archive"),
            ("PATCH", "/api/v1/issues/{identifier}/release-picks"),
            ("POST", "/api/v1/issues/{identifier}/release-picks/apply-all"),
        ],
    )
    def test_release_delivery_routes_are_classified(self, method: str, path: str):
        assert classify_route(method, path) == RouteCategory.RELEASE_DELIVERY

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/projects/{project_id}/release-delivery/commits"),
            ("POST", "/api/v1/issues/{identifier}/release-addendums"),
            ("POST", "/api/v1/issues/{identifier}/release-picks/apply-all"),
        ],
    )
    def test_release_delivery_routes_are_not_exposed(self, method: str, path: str):
        assert is_route_exposed(method, path) is False

    def test_release_delivery_trigger_denied(self):
        """Triggering a release delivery is a high-privilege git+CI op."""
        assert is_route_exposed("POST", "/api/v1/projects/{project_id}/release-delivery/commits") is False

    def test_release_addendum_create_denied(self):
        """Creating release addendums touches git state."""
        assert is_route_exposed("POST", "/api/v1/issues/{identifier}/release-addendums") is False

    def test_release_delivery_reads_are_safe(self):
        """GET endpoints for release delivery data are allowed."""
        assert is_route_exposed("GET", "/api/v1/projects/{project_id}/release-delivery/commits") is True
        assert is_route_exposed("GET", "/api/v1/projects/{project_id}/release-delivery/backlog") is True
        assert is_route_exposed("GET", "/api/v1/issues/{identifier}/release-addendums") is True


# ---------------------------------------------------------------------------
# 12. Classify UNKNOWN routes (fail-closed)
# ---------------------------------------------------------------------------


class TestClassifyRouteUnknown:
    @pytest.mark.parametrize(
        "method,path",
        [
            # Completely fictional routes
            ("GET", "/api/v1/secret-admin/reset"),
            ("POST", "/api/v1/super-privileged/nuke"),
            ("DELETE", "/api/v1/everything"),
            # Non-API paths
            ("GET", "/"),
            ("GET", "/favicon.ico"),
            ("GET", "/favicon.svg"),
            # WebSocket (handled separately, not an OpenAPI route)
            ("GET", "/ws"),
            # HTML pages
            ("GET", "/providers"),
            ("GET", "/projects-manage"),
            ("GET", "/reviews"),
            ("GET", "/foci"),
            ("GET", "/release-delivery"),
            # Future routes not yet in the classifier
            ("POST", "/api/v1/issues/{identifier}/new-feature-not-in-policy"),
            ("GET", "/api/v2/issues"),
            # Empty / malformed
            ("GET", ""),
            ("POST", ""),
        ],
    )
    def test_unknown_routes_fail_closed(self, method: str, path: str):
        assert classify_route(method, path) == RouteCategory.UNKNOWN

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/v1/secret-admin/reset"),
            ("POST", "/api/v1/super-privileged/nuke"),
            ("GET", "/"),
            ("GET", "/api/v2/issues"),
        ],
    )
    def test_unknown_routes_are_not_exposed(self, method: str, path: str):
        assert is_route_exposed(method, path) is False


# ---------------------------------------------------------------------------
# 13. is_route_exposed() integration
# ---------------------------------------------------------------------------


class TestIsRouteExposed:
    """Integration tests — verify the top-level is_route_exposed function."""

    # Allowed operations (should return True)
    @pytest.mark.parametrize(
        "method,path,description",
        [
            ("GET", "/api/v1/state", "global state read"),
            ("GET", "/api/v1/issues", "list issues"),
            ("GET", "/api/v1/issues/{identifier}/detail", "issue detail"),
            ("GET", "/api/v1/issues/{identifier}/comments", "read comments"),
            ("GET", "/api/v1/projects", "list projects"),
            ("GET", "/api/v1/providers", "list providers (read-only)"),
            ("GET", "/api/v1/budget", "read budget"),
            ("POST", "/api/v1/issues", "create issue"),
            ("PATCH", "/api/v1/issues/{identifier}", "update issue"),
            ("POST", "/api/v1/issues/{identifier}/comments", "post comment"),
            ("POST", "/api/v1/issues/{identifier}/labels", "add label"),
            ("DELETE", "/api/v1/issues/{identifier}/labels/{label}", "remove label"),
            ("POST", "/api/v1/issues/{identifier}/dependencies", "add dependency"),
        ],
    )
    def test_allowed_operations(self, method: str, path: str, description: str):
        assert is_route_exposed(method, path) is True, f"Expected {method} {path} to be exposed ({description})"

    # Denied operations (should return False)
    @pytest.mark.parametrize(
        "method,path,description",
        [
            ("POST", "/api/v1/orchestrator/restart", "restart orchestrator"),
            ("POST", "/api/v1/orchestrator/pause", "pause orchestrator"),
            ("POST", "/api/v1/orchestrator/dispatch/{identifier}", "manual dispatch"),
            ("POST", "/api/v1/webhooks/github", "github webhook"),
            ("POST", "/api/v1/webhooks/gitlab", "gitlab webhook"),
            ("POST", "/api/v1/providers", "create provider (credential)"),
            ("PATCH", "/api/v1/providers/{provider_id}", "update provider (credential)"),
            ("DELETE", "/api/v1/providers/{provider_id}", "delete provider"),
            ("POST", "/api/v1/providers/{provider_id}/test", "test provider credentials"),
            ("POST", "/api/v1/projects", "create project (admin)"),
            ("DELETE", "/api/v1/projects/{project_id}", "delete project (admin)"),
            ("POST", "/api/v1/projects/{project_id}/pause", "pause project (admin)"),
            ("POST", "/api/v1/projects/{project_id}/state-branch/migrate", "state branch migrate"),
            ("POST", "/api/v1/agent-profiles", "create agent profile (admin)"),
            ("DELETE", "/api/v1/agent-profiles/{name}", "delete agent profile (admin)"),
            ("PUT", "/api/v1/roles", "update roles (admin)"),
            ("POST", "/api/v1/foci", "create focus (admin)"),
            ("DELETE", "/api/v1/foci/{name}", "delete focus (admin)"),
            ("POST", "/api/v1/console/{project_id}/backend", "console backend management"),
            ("POST", "/api/v1/refresh", "manual sync refresh (admin)"),
            ("POST", "/api/v1/errors", "error reporting (admin)"),
            ("POST", "/api/v1/projects/{project_id}/release-delivery/commits", "trigger release"),
            ("POST", "/api/v1/issues/{identifier}/release-addendums", "create addendum"),
            ("PATCH", "/api/v1/issues/{identifier}/release-picks", "update release picks"),
            ("POST", "/api/v1/reviews/{project_id}/{review_id}/rebase", "rebase review"),
            ("GET", "/api/v2/issues", "unknown v2 route"),
        ],
    )
    def test_denied_operations(self, method: str, path: str, description: str):
        assert is_route_exposed(method, path) is False, f"Expected {method} {path} to be denied ({description})"


# ---------------------------------------------------------------------------
# 14. Fail-closed property (edge cases)
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_wrong_method_for_known_path_is_denied(self):
        """GET /api/v1/orchestrator/restart doesn't exist, but even if an unknown
        combination is tested, it should fail closed."""
        # A GET to an orchestrator path is UNKNOWN (not classified) — denied
        assert classify_route("GET", "/api/v1/orchestrator/restart") == RouteCategory.UNKNOWN
        assert is_route_exposed("GET", "/api/v1/orchestrator/restart") is False

    def test_new_api_version_is_denied(self):
        """Any /api/v2/... route (future API) is UNKNOWN — fail-closed."""
        assert is_route_exposed("GET", "/api/v2/issues") is False
        assert is_route_exposed("POST", "/api/v2/orchestrator/restart") is False

    def test_extra_path_segment_is_denied(self):
        """A GET to /api/v1/state/extra doesn't match the exact rule."""
        assert is_route_exposed("GET", "/api/v1/state/extra") is False

    def test_empty_method_is_denied(self):
        assert is_route_exposed("", "/api/v1/state") is False

    def test_empty_path_is_denied(self):
        assert is_route_exposed("GET", "") is False

    def test_empty_method_and_path_is_denied(self):
        assert is_route_exposed("", "") is False

    def test_post_to_safe_read_path_is_classified_separately(self):
        """POST /api/v1/state doesn't exist in the rules — UNKNOWN."""
        assert classify_route("POST", "/api/v1/state") == RouteCategory.UNKNOWN
        assert is_route_exposed("POST", "/api/v1/state") is False

    def test_delete_to_issues_list_is_unknown(self):
        """DELETE /api/v1/issues isn't in the table — UNKNOWN."""
        assert classify_route("DELETE", "/api/v1/issues") == RouteCategory.UNKNOWN

    def test_put_to_issues_is_unknown(self):
        """PUT /api/v1/issues isn't a valid oompah route — UNKNOWN."""
        assert classify_route("PUT", "/api/v1/issues") == RouteCategory.UNKNOWN

    def test_admin_route_cannot_be_exposed_via_wrong_method(self):
        """Even GET to an admin-mutation path fails closed if unclassified."""
        # GET /api/v1/projects/{id}/pause is not in the rules — UNKNOWN
        assert classify_route("GET", "/api/v1/projects/{project_id}/pause") == RouteCategory.UNKNOWN
        assert is_route_exposed("GET", "/api/v1/projects/{project_id}/pause") is False


# ---------------------------------------------------------------------------
# 15. describe_policy()
# ---------------------------------------------------------------------------


class TestDescribePolicy:
    def test_returns_dict(self):
        result = describe_policy()
        assert isinstance(result, dict)

    def test_mcp_endpoint_in_result(self):
        result = describe_policy()
        assert result["mcp_endpoint"] == "/api/mcp/v1"

    def test_openapi_source_in_result(self):
        result = describe_policy()
        assert result["openapi_source"] == "/openapi.json"

    def test_discovery_path_in_result(self):
        result = describe_policy()
        assert result["discovery_path"] == "/.well-known/mcp"

    def test_fail_closed_is_true(self):
        result = describe_policy()
        assert result["fail_closed"] is True

    def test_token_propagation_is_none(self):
        result = describe_policy()
        assert "none" in str(result["token_propagation"]).lower()

    def test_exposed_categories_matches_constant(self):
        result = describe_policy()
        exposed_in_policy = set(result["exposed_categories"])
        assert "safe_read" in exposed_in_policy
        assert "task_mutation" in exposed_in_policy

    def test_total_classified_routes_is_positive(self):
        result = describe_policy()
        assert result["total_classified_routes"] > 0

    def test_exposed_routes_is_less_than_total(self):
        result = describe_policy()
        assert result["exposed_routes"] < result["total_classified_routes"]

    def test_denied_routes_is_positive(self):
        result = describe_policy()
        assert result["denied_routes"] > 0

    def test_routes_by_category_covers_known_categories(self):
        result = describe_policy()
        cats = set(result["routes_by_category"])
        # At minimum the exposed categories should appear
        assert "safe_read" in cats
        assert "task_mutation" in cats

    def test_result_is_json_serialisable(self):
        import json
        result = describe_policy()
        # Should not raise
        json.dumps(result)


# ---------------------------------------------------------------------------
# 16. iter_exposed_routes()
# ---------------------------------------------------------------------------


class TestIterExposedRoutes:
    def test_yields_tuples(self):
        for item in iter_exposed_routes():
            assert isinstance(item, tuple)
            assert len(item) == 3

    def test_only_yields_exposed_categories(self):
        for method, path, category in iter_exposed_routes():
            assert category in EXPOSED_CATEGORIES, (
                f"{method} {path} → {category} is not in EXPOSED_CATEGORIES"
            )

    def test_safe_read_routes_appear(self):
        exposed = {(m, p) for m, p, _ in iter_exposed_routes()}
        assert ("GET", "/api/v1/state") not in [
            (m, p) for m, p, c in iter_exposed_routes() if c != RouteCategory.SAFE_READ
        ]
        # Verify at least one known safe-read route appears
        assert any(p == "/api/v1/state" for _, p, _ in iter_exposed_routes())

    def test_task_mutation_routes_appear(self):
        task_routes = [
            (m, p) for m, p, c in iter_exposed_routes()
            if c == RouteCategory.TASK_MUTATION
        ]
        assert len(task_routes) > 0

    def test_no_denied_routes_appear(self):
        denied = {
            RouteCategory.ADMIN_MUTATION,
            RouteCategory.CREDENTIAL_BEARING,
            RouteCategory.WEBHOOK_INGESTION,
            RouteCategory.ORCHESTRATOR_CONTROL,
            RouteCategory.RELEASE_DELIVERY,
            RouteCategory.UNKNOWN,
        }
        for method, path, category in iter_exposed_routes():
            assert category not in denied, (
                f"{method} {path} has denied category {category}"
            )

    def test_orchestrator_restart_not_in_exposed(self):
        exposed = [(m, p) for m, p, _ in iter_exposed_routes()]
        assert ("POST", "/api/v1/orchestrator/restart") not in exposed

    def test_webhook_not_in_exposed(self):
        exposed = [(m, p) for m, p, _ in iter_exposed_routes()]
        assert ("POST", "/api/v1/webhooks/github") not in exposed
        assert ("POST", "/api/v1/webhooks/gitlab") not in exposed

    def test_credential_routes_not_in_exposed(self):
        exposed = [(m, p) for m, p, _ in iter_exposed_routes()]
        assert ("POST", "/api/v1/providers") not in exposed


# ---------------------------------------------------------------------------
# 17. Method case insensitivity
# ---------------------------------------------------------------------------


class TestMethodCaseInsensitivity:
    @pytest.mark.parametrize(
        "method",
        ["GET", "get", "Get", "gEt"],
    )
    def test_get_method_variants(self, method: str):
        assert classify_route(method, "/api/v1/state") == RouteCategory.SAFE_READ

    @pytest.mark.parametrize(
        "method",
        ["POST", "post", "Post", "pOsT"],
    )
    def test_post_method_variants(self, method: str):
        assert classify_route(method, "/api/v1/orchestrator/restart") == RouteCategory.ORCHESTRATOR_CONTROL

    @pytest.mark.parametrize(
        "method",
        ["PATCH", "patch", "Patch"],
    )
    def test_patch_method_variants(self, method: str):
        assert classify_route(method, "/api/v1/issues/{identifier}") == RouteCategory.TASK_MUTATION

    @pytest.mark.parametrize(
        "method",
        ["DELETE", "delete", "Delete"],
    )
    def test_delete_method_variants_for_task_mutation(self, method: str):
        assert classify_route(method, "/api/v1/issues/{identifier}/labels/{label}") == RouteCategory.TASK_MUTATION

    def test_method_case_does_not_affect_exposure(self):
        assert is_route_exposed("get", "/api/v1/state") is True
        assert is_route_exposed("GET", "/api/v1/state") is True
        assert is_route_exposed("post", "/api/v1/orchestrator/restart") is False
        assert is_route_exposed("POST", "/api/v1/orchestrator/restart") is False


# ---------------------------------------------------------------------------
# 18. Injection resistance
# ---------------------------------------------------------------------------


class TestInjectionResistance:
    """Adversarial path strings cannot bypass the exposure policy."""

    @pytest.mark.parametrize(
        "adversarial_path",
        [
            # Path traversal attempts
            "/api/v1/state/../orchestrator/restart",
            "/api/v1/issues/../../../../etc/passwd",
            # Double-encoding (these arrive as literal strings in the schema)
            "/api/v1/orchestrator%2Frestart",
            "/api/v1/orchestrator%2frestart",
            # Extra slashes
            "/api/v1//orchestrator/restart",
            "/api/v1/orchestrator//restart",
            # Null byte injection
            "/api/v1/state\x00/orchestrator/restart",
            # Whitespace injection
            " /api/v1/state",
            "/api/v1/state ",
            "\t/api/v1/state",
            # Query string smuggling (paths don't have ?queries but test anyway)
            "/api/v1/state?foo=bar",
            # Fragment
            "/api/v1/state#admin",
            # Attempting to look like a safe_read route while being something else
            "/api/v1/state/orchestrator/restart",
        ],
    )
    def test_adversarial_paths_are_denied(self, adversarial_path: str):
        """Paths that do not exactly match a classified rule are denied."""
        result = is_route_exposed("GET", adversarial_path)
        # If somehow classified, it must NOT be as SAFE_READ or TASK_MUTATION
        # (i.e., it must not be exposed as a legitimate route)
        assert result is False, (
            f"Adversarial path {adversarial_path!r} was incorrectly exposed"
        )

    @pytest.mark.parametrize(
        "adversarial_path",
        [
            # These paths are denied for ALL HTTP methods — no single verb can
            # make them safe.  Note: /api/v1/providers is intentionally NOT in
            # this list because GET /api/v1/providers IS a legitimate SAFE_READ
            # route.  Only paths where every method variant is denied belong here.
            "/api/v1/orchestrator/restart",
            "/api/v1/webhooks/github",
            "/api/v1/projects/{project_id}/state-branch/migrate",
        ],
    )
    def test_canonical_denied_paths_cannot_be_made_safe(self, adversarial_path: str):
        """Verified denied paths remain denied regardless of HTTP method used."""
        # Multiple methods to confirm fail-closed for protected paths
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            result = is_route_exposed(method, adversarial_path)
            # Some methods may not match any rule (UNKNOWN → denied), or match
            # a specific denied rule — either way the path must not be exposed.
            category = classify_route(method, adversarial_path)
            if category in EXPOSED_CATEGORIES:
                pytest.fail(
                    f"{method} {adversarial_path!r} was exposed with "
                    f"category {category!r}"
                )

    def test_orchestrator_restart_cannot_be_smuggled_as_issue_path(self):
        """An issue identifier that looks like an orchestrator path is denied."""
        # /api/v1/{issue_identifier} is SAFE_READ, but
        # /api/v1/orchestrator/restart is ORCHESTRATOR_CONTROL — the more
        # specific deny rule must win.
        # classify_route sees "/api/v1/orchestrator/restart" — matches
        # ORCHESTRATOR_CONTROL rule before the generic {issue_identifier} rule.
        result = classify_route("POST", "/api/v1/orchestrator/restart")
        assert result == RouteCategory.ORCHESTRATOR_CONTROL

    def test_get_issue_snapshot_does_not_expose_orchestrator(self):
        """GET /api/v1/{issue_identifier} is SAFE_READ for issue lookups.
        Ensure a bad actor can't use that to probe orchestrator state."""
        # The single-segment generic route only matches single-segment paths.
        # /api/v1/orchestrator/restart has two segments after /api/v1/ — it
        # does not match the {issue_identifier} rule.
        result = classify_route("GET", "/api/v1/orchestrator/restart")
        assert result == RouteCategory.UNKNOWN
        assert is_route_exposed("GET", "/api/v1/orchestrator/restart") is False
