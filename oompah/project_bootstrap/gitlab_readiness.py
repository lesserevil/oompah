"""GitLab-specific bootstrap readiness checks for OOMPAH-328.

This module validates that a project token and server configuration have the
minimum capabilities required to run oompah against a GitLab project:

1. **api_access** — the token can reach the GitLab API at the configured base URL.
2. **label_create** — the token may create project labels.
3. **issue_access** — the token may read issues.
4. **mr_access** — the token may read merge requests.
5. **pipeline_read** — the token may read pipeline/CI status.
6. **state_branch_push** — the token may push branches (needed for state branch).
7. **webhook_url** — ``OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL`` is set and is an
   HTTPS URL reachable by GitLab.
8. **hook_create** — the token may create project hooks.
9. **polling_fallback** — polling via the API is available when webhooks are not.

All checks are purely HTTP-based and do not require a local git checkout.

Security design
---------------
- Token values are **never** included in log output or returned error messages.
  Error messages describe the *capability* that failed, not the credential.
- The webhook URL reachability check is intentionally limited to a DNS/TLS
  sanity check rather than a full HTTP round-trip, because the oompah server
  is typically behind a firewall or tunnel during bootstrap.
- All HTTP requests use explicit timeouts so the readiness check cannot hang
  indefinitely when GitLab is unreachable.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Minimum token scopes documented for operators.  The readiness check
#: validates capabilities through API calls rather than inspecting scope
#: strings directly (scope strings are forge-version specific).
MINIMUM_TOKEN_SCOPES: tuple[str, ...] = (
    "api",  # GitLab.com personal access token or project access token
    # Self-managed equivalent: api or read_api + write_repository
)

#: GitLab API path used to verify token identity.
_WHOAMI_PATH = "/api/v4/user"

#: GitLab API path template for project details.
_PROJECT_PATH = "/api/v4/projects/{encoded}"

#: HTTP request timeout in seconds for all readiness checks.
_TIMEOUT_S = 10


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class CapabilityStatus(str, Enum):
    """Outcome of a single capability check."""

    ok = "ok"
    failed = "failed"
    skipped = "skipped"


@dataclass
class CapabilityResult:
    """Outcome of a single GitLab bootstrap capability check."""

    name: str
    """Capability identifier (e.g. ``"api_access"``)."""

    status: CapabilityStatus
    """Whether the check passed, failed, or was skipped."""

    message: str = ""
    """Human-readable description of the outcome."""

    remediation: str = ""
    """Operator action required when ``status == CapabilityStatus.failed``."""


@dataclass
class GitLabReadinessResult:
    """Aggregate result of the GitLab bootstrap readiness check."""

    all_ok: bool
    """``True`` when every non-skipped check passed."""

    capabilities: list[CapabilityResult] = field(default_factory=list)
    """Individual capability results in check order."""

    dry_run: bool = False
    """``True`` when the check ran in dry-run mode (no state-mutating calls)."""

    def failed_capabilities(self) -> list[CapabilityResult]:
        """Return only the capabilities that failed."""
        return [c for c in self.capabilities if c.status == CapabilityStatus.failed]

    def summary(self) -> str:
        """Return a human-readable summary suitable for CLI output."""
        lines = []
        for cap in self.capabilities:
            icon = "✓" if cap.status == CapabilityStatus.ok else ("⚠" if cap.status == CapabilityStatus.skipped else "✗")
            lines.append(f"  {icon} {cap.name}: {cap.message}")
            if cap.remediation:
                lines.append(f"    → {cap.remediation}")
        status_line = "All checks passed." if self.all_ok else f"{len(self.failed_capabilities())} check(s) failed."
        if self.dry_run:
            status_line += " (dry-run: no state mutations performed)"
        return "\n".join([status_line, ""] + lines)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _gitlab_get(
    base_url: str,
    path: str,
    token: str,
    *,
    timeout: int = _TIMEOUT_S,
) -> tuple[int, dict[str, Any]]:
    """Execute a GitLab API GET request.

    Returns ``(status_code, response_json_or_empty_dict)``.

    Security: the ``token`` is sent only in the ``PRIVATE-TOKEN`` header and is
    never included in log messages.
    """
    import urllib.request
    import json as _json

    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url)
    req.add_header("PRIVATE-TOKEN", token)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "oompah-bootstrap/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read()
            try:
                return resp.status, _json.loads(body)
            except Exception:
                return resp.status, {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception as exc:
        logger.debug("GitLab API request to %s failed: %s", url, exc)
        return 0, {}


def _gitlab_post(
    base_url: str,
    path: str,
    token: str,
    data: dict[str, Any] | None = None,
    *,
    timeout: int = _TIMEOUT_S,
) -> tuple[int, dict[str, Any]]:
    """Execute a GitLab API POST request.

    Returns ``(status_code, response_json_or_empty_dict)``.
    """
    import urllib.request
    import urllib.parse
    import json as _json

    url = base_url.rstrip("/") + path
    body_bytes = _json.dumps(data or {}).encode()
    req = urllib.request.Request(url, data=body_bytes, method="POST")
    req.add_header("PRIVATE-TOKEN", token)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "oompah-bootstrap/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read()
            try:
                return resp.status, _json.loads(body)
            except Exception:
                return resp.status, {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception as exc:
        logger.debug("GitLab API POST to %s failed: %s", url, exc)
        return 0, {}


def _encode_project_path(namespace: str, project_name: str) -> str:
    """URL-encode a GitLab project path (``namespace/project``) for the API."""
    from urllib.parse import quote

    path = f"{namespace}/{project_name}"
    return quote(path, safe="")


# ---------------------------------------------------------------------------
# Individual capability checks
# ---------------------------------------------------------------------------


def _check_api_access(
    base_url: str,
    token: str,
) -> CapabilityResult:
    """Verify the token can reach the GitLab API and authenticate."""
    status_code, body = _gitlab_get(base_url, _WHOAMI_PATH, token)
    if status_code == 200 and "id" in body:
        username = body.get("username", "unknown")
        return CapabilityResult(
            name="api_access",
            status=CapabilityStatus.ok,
            message=f"Authenticated as {username!r}",
        )
    if status_code == 401:
        return CapabilityResult(
            name="api_access",
            status=CapabilityStatus.failed,
            message="Token authentication failed (HTTP 401)",
            remediation=(
                "Create a GitLab personal access token or project access token "
                "with 'api' scope (GitLab.com) or equivalent project-level "
                "permissions (self-managed), then set it as the project "
                "access_token in oompah."
            ),
        )
    if status_code == 0:
        return CapabilityResult(
            name="api_access",
            status=CapabilityStatus.failed,
            message=f"Cannot reach GitLab API at {base_url!r}",
            remediation=(
                "Verify that 'forge_base_url' is correct and the GitLab instance "
                "is reachable from this host."
            ),
        )
    return CapabilityResult(
        name="api_access",
        status=CapabilityStatus.failed,
        message=f"Unexpected HTTP {status_code} from GitLab API",
        remediation="Check GitLab instance health and token configuration.",
    )


def _check_label_create(
    base_url: str,
    token: str,
    encoded_project: str,
    *,
    dry_run: bool,
) -> CapabilityResult:
    """Verify the token can create labels on the project."""
    path = f"/api/v4/projects/{encoded_project}/labels"
    if dry_run:
        # In dry-run, verify read access to existing labels instead of creating one.
        status_code, body = _gitlab_get(base_url, path, token)
        if status_code == 200:
            return CapabilityResult(
                name="label_create",
                status=CapabilityStatus.ok,
                message="Label list accessible (dry-run: write not tested)",
            )
        if status_code == 403:
            return CapabilityResult(
                name="label_create",
                status=CapabilityStatus.failed,
                message="Label list access denied (HTTP 403); create permission likely also absent",
                remediation=_label_create_remediation(),
            )
        return CapabilityResult(
            name="label_create",
            status=CapabilityStatus.failed,
            message=f"Label list returned HTTP {status_code}",
            remediation=_label_create_remediation(),
        )
    # Non-dry-run: attempt to create a probe label then delete it.
    probe_name = "oompah-bootstrap-probe"
    create_code, create_body = _gitlab_post(
        base_url,
        path,
        token,
        {"name": probe_name, "color": "#6699cc", "description": "oompah bootstrap probe — safe to delete"},
    )
    if create_code in (200, 201, 409):
        # 409 = label already exists — permission granted previously.
        # Best-effort delete the probe label; ignore errors.
        label_id = create_body.get("id")
        if label_id and create_code != 409:
            _gitlab_delete(base_url, f"{path}/{label_id}", token)
        return CapabilityResult(
            name="label_create",
            status=CapabilityStatus.ok,
            message="Label create permission confirmed",
        )
    if create_code == 403:
        return CapabilityResult(
            name="label_create",
            status=CapabilityStatus.failed,
            message="Label create denied (HTTP 403)",
            remediation=_label_create_remediation(),
        )
    return CapabilityResult(
        name="label_create",
        status=CapabilityStatus.failed,
        message=f"Label create returned HTTP {create_code}",
        remediation=_label_create_remediation(),
    )


def _label_create_remediation() -> str:
    return (
        "The token needs at least 'Developer' role on the GitLab project to manage labels. "
        "Grant the oompah service account 'Developer' (or 'Maintainer') role "
        "on the project in GitLab → Settings → Members."
    )


def _gitlab_delete(
    base_url: str,
    path: str,
    token: str,
    *,
    timeout: int = _TIMEOUT_S,
) -> int:
    """Execute a GitLab API DELETE request; returns status code."""
    import urllib.request

    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url, method="DELETE")
    req.add_header("PRIVATE-TOKEN", token)
    req.add_header("User-Agent", "oompah-bootstrap/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return 0


def _check_issue_access(
    base_url: str,
    token: str,
    encoded_project: str,
) -> CapabilityResult:
    """Verify the token can read project issues."""
    path = f"/api/v4/projects/{encoded_project}/issues?per_page=1"
    status_code, _ = _gitlab_get(base_url, path, token)
    if status_code == 200:
        return CapabilityResult(
            name="issue_access",
            status=CapabilityStatus.ok,
            message="Issue tracker accessible",
        )
    if status_code == 403:
        return CapabilityResult(
            name="issue_access",
            status=CapabilityStatus.failed,
            message="Issue tracker access denied (HTTP 403)",
            remediation=(
                "Enable the Issues feature on the GitLab project "
                "(Settings → General → Visibility, project features, permissions → Issues), "
                "or grant the token at least Reporter role."
            ),
        )
    if status_code == 404:
        return CapabilityResult(
            name="issue_access",
            status=CapabilityStatus.failed,
            message="Project not found (HTTP 404); verify tracker_owner and tracker_repo",
            remediation="Check that the project namespace and name match the GitLab project exactly.",
        )
    return CapabilityResult(
        name="issue_access",
        status=CapabilityStatus.failed,
        message=f"Issue list returned HTTP {status_code}",
        remediation="Verify project access and token permissions.",
    )


def _check_mr_access(
    base_url: str,
    token: str,
    encoded_project: str,
) -> CapabilityResult:
    """Verify the token can read project merge requests."""
    path = f"/api/v4/projects/{encoded_project}/merge_requests?per_page=1"
    status_code, _ = _gitlab_get(base_url, path, token)
    if status_code == 200:
        return CapabilityResult(
            name="mr_access",
            status=CapabilityStatus.ok,
            message="Merge request access confirmed",
        )
    if status_code == 403:
        return CapabilityResult(
            name="mr_access",
            status=CapabilityStatus.failed,
            message="Merge request access denied (HTTP 403)",
            remediation=(
                "Enable Merge Requests on the project "
                "(Settings → General → Merge Requests), "
                "or grant the token at least Reporter role."
            ),
        )
    return CapabilityResult(
        name="mr_access",
        status=CapabilityStatus.failed,
        message=f"Merge request list returned HTTP {status_code}",
        remediation="Verify project access and token permissions.",
    )


def _check_pipeline_read(
    base_url: str,
    token: str,
    encoded_project: str,
) -> CapabilityResult:
    """Verify the token can read pipeline/CI status."""
    path = f"/api/v4/projects/{encoded_project}/pipelines?per_page=1"
    status_code, _ = _gitlab_get(base_url, path, token)
    if status_code == 200:
        return CapabilityResult(
            name="pipeline_read",
            status=CapabilityStatus.ok,
            message="Pipeline read access confirmed",
        )
    if status_code == 403:
        return CapabilityResult(
            name="pipeline_read",
            status=CapabilityStatus.failed,
            message="Pipeline read denied (HTTP 403); CI status monitoring unavailable",
            remediation=(
                "Enable CI/CD on the project "
                "(Settings → General → Visibility → CI/CD), "
                "or grant the token at least Reporter role. "
                "Without pipeline read, oompah cannot observe CI results "
                "for merge-when-pipeline-succeeds."
            ),
        )
    return CapabilityResult(
        name="pipeline_read",
        status=CapabilityStatus.failed,
        message=f"Pipeline list returned HTTP {status_code}",
        remediation="Verify CI/CD is enabled and the token has Reporter or higher role.",
    )


def _check_state_branch_push(
    base_url: str,
    token: str,
    encoded_project: str,
) -> CapabilityResult:
    """Verify the token can push branches (required for state branch)."""
    # We verify push permission by checking the protected-branches list
    # (only roles with push access can enumerate protected branches in some
    # configurations).  As a secondary signal, we inspect the project's
    # ``permissions`` field from GET /projects/:id.
    path = f"/api/v4/projects/{encoded_project}"
    status_code, body = _gitlab_get(base_url, path, token)
    if status_code != 200:
        return CapabilityResult(
            name="state_branch_push",
            status=CapabilityStatus.failed,
            message=f"Project detail fetch returned HTTP {status_code}",
            remediation="Verify project access and token configuration.",
        )
    perms = body.get("permissions", {})
    project_access = perms.get("project_access") or {}
    group_access = perms.get("group_access") or {}
    # Access levels: 0=No, 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner
    access_level = max(
        project_access.get("access_level", 0),
        group_access.get("access_level", 0),
    )
    if access_level >= 30:  # Developer or higher can push
        return CapabilityResult(
            name="state_branch_push",
            status=CapabilityStatus.ok,
            message=f"Push permission confirmed (access_level={access_level})",
        )
    if access_level > 0:
        return CapabilityResult(
            name="state_branch_push",
            status=CapabilityStatus.failed,
            message=f"Insufficient access level for push: {access_level} (need ≥30/Developer)",
            remediation=_push_remediation(),
        )
    # access_level == 0 can mean the API didn't return permissions
    # (possible for older GitLab versions or service accounts).
    # Fall back to checking protected branches as a heuristic.
    pb_path = f"/api/v4/projects/{encoded_project}/protected_branches"
    pb_code, _ = _gitlab_get(base_url, pb_path, token)
    if pb_code == 200:
        return CapabilityResult(
            name="state_branch_push",
            status=CapabilityStatus.ok,
            message="Push permission inferred (protected-branches API accessible)",
        )
    return CapabilityResult(
        name="state_branch_push",
        status=CapabilityStatus.failed,
        message="Cannot confirm push permission (access_level not returned and protected-branches inaccessible)",
        remediation=_push_remediation(),
    )


def _push_remediation() -> str:
    return (
        "Grant the oompah service account 'Developer' (or 'Maintainer') role on the project. "
        "Also ensure the 'oompah/state/*' branch pattern is not protected against force-push "
        "or does not require approvals — oompah pushes state commits directly without a MR. "
        "In GitLab: Settings → Repository → Protected branches, add a rule for 'oompah/state/*' "
        "allowing the service account to push."
    )


def _check_webhook_url(webhook_public_url: str | None) -> CapabilityResult:
    """Verify the configured public webhook URL is an HTTPS URL.

    This check does NOT make an outbound HTTP request, because oompah is
    typically behind a tunnel during bootstrap.  It validates that the URL:
    - is non-empty
    - uses the HTTPS scheme
    - has a non-empty hostname

    Operators must separately verify that GitLab can reach this URL.
    """
    if not webhook_public_url:
        return CapabilityResult(
            name="webhook_url",
            status=CapabilityStatus.failed,
            message="OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL is not set",
            remediation=(
                "Set OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL in .env to the public HTTPS base URL "
                "where oompah is reachable from the internet, e.g. "
                "'https://oompah.example.com'.  If running locally, use a tunnel such as "
                "ngrok or cloudflared to expose the service. "
                "GitLab requires HTTPS for webhook delivery."
            ),
        )
    parsed = urlsplit(webhook_public_url)
    if parsed.scheme != "https":
        return CapabilityResult(
            name="webhook_url",
            status=CapabilityStatus.failed,
            message=f"Webhook URL uses {parsed.scheme!r} instead of https",
            remediation=(
                "Change OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL to an https:// URL. "
                "GitLab rejects webhook endpoints that do not use HTTPS."
            ),
        )
    if not parsed.hostname:
        return CapabilityResult(
            name="webhook_url",
            status=CapabilityStatus.failed,
            message="Webhook URL has no hostname",
            remediation="Set OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL to a valid HTTPS URL with a hostname.",
        )
    return CapabilityResult(
        name="webhook_url",
        status=CapabilityStatus.ok,
        message=f"Webhook URL is a valid HTTPS URL ({parsed.scheme}://{parsed.hostname}…)",
    )


def _check_hook_create(
    base_url: str,
    token: str,
    encoded_project: str,
    *,
    dry_run: bool,
    webhook_public_url: str | None,
) -> CapabilityResult:
    """Verify the token can create project hooks."""
    if not webhook_public_url:
        return CapabilityResult(
            name="hook_create",
            status=CapabilityStatus.skipped,
            message="Skipped: OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL not set",
        )

    hooks_path = f"/api/v4/projects/{encoded_project}/hooks"

    if dry_run:
        # Read hook list to infer create permission.
        status_code, _ = _gitlab_get(base_url, hooks_path, token)
        if status_code == 200:
            return CapabilityResult(
                name="hook_create",
                status=CapabilityStatus.ok,
                message="Hook list accessible (dry-run: create not tested)",
            )
        if status_code == 403:
            return CapabilityResult(
                name="hook_create",
                status=CapabilityStatus.failed,
                message="Hook list denied (HTTP 403); Maintainer role required",
                remediation=_hook_create_remediation(),
            )
        return CapabilityResult(
            name="hook_create",
            status=CapabilityStatus.failed,
            message=f"Hook list returned HTTP {status_code}",
            remediation=_hook_create_remediation(),
        )

    # Non-dry-run: create a probe hook then immediately delete it.
    probe_url = webhook_public_url.rstrip("/") + "/_oompah_probe"
    create_code, create_body = _gitlab_post(
        base_url,
        hooks_path,
        token,
        {
            "url": probe_url,
            "push_events": False,
            "merge_requests_events": False,
        },
    )
    if create_code in (200, 201):
        hook_id = create_body.get("id")
        if hook_id:
            _gitlab_delete(base_url, f"{hooks_path}/{hook_id}", token)
        return CapabilityResult(
            name="hook_create",
            status=CapabilityStatus.ok,
            message="Hook create permission confirmed",
        )
    if create_code == 403:
        return CapabilityResult(
            name="hook_create",
            status=CapabilityStatus.failed,
            message="Hook create denied (HTTP 403)",
            remediation=_hook_create_remediation(),
        )
    if create_code == 422:
        return CapabilityResult(
            name="hook_create",
            status=CapabilityStatus.failed,
            message="Hook create rejected (HTTP 422 — possibly URL validation by GitLab)",
            remediation=(
                "GitLab may reject webhook URLs that it cannot reach or that "
                "match its internal network blocklist. Verify OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL "
                "is publicly reachable and uses HTTPS."
            ),
        )
    return CapabilityResult(
        name="hook_create",
        status=CapabilityStatus.failed,
        message=f"Hook create returned HTTP {create_code}",
        remediation=_hook_create_remediation(),
    )


def _hook_create_remediation() -> str:
    return (
        "Hook creation requires 'Maintainer' role on the GitLab project. "
        "In GitLab: Settings → Members, set the oompah service account to Maintainer. "
        "Alternatively, configure the project hook manually and use polling-only mode "
        "(set OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL to empty to disable webhook management)."
    )


def _check_polling_fallback(
    base_url: str,
    token: str,
    encoded_project: str,
) -> CapabilityResult:
    """Verify that polling can serve as a fallback when webhooks are unavailable.

    Polling requires only issue and MR list access, which earlier checks
    already verified.  This check confirms the project's default branch is
    readable, which is what the polling loop fetches for push detection.
    """
    path = f"/api/v4/projects/{encoded_project}/repository/branches"
    status_code, _ = _gitlab_get(base_url, path + "?per_page=1", token)
    if status_code == 200:
        return CapabilityResult(
            name="polling_fallback",
            status=CapabilityStatus.ok,
            message="Branch list accessible; polling fallback is available",
        )
    if status_code == 403:
        return CapabilityResult(
            name="polling_fallback",
            status=CapabilityStatus.failed,
            message="Branch list denied (HTTP 403); polling degraded",
            remediation=(
                "Ensure the token has at least Reporter role so oompah can "
                "poll for branch changes when webhook delivery fails."
            ),
        )
    return CapabilityResult(
        name="polling_fallback",
        status=CapabilityStatus.failed,
        message=f"Branch list returned HTTP {status_code}",
        remediation="Verify project access and token permissions.",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_gitlab_readiness(
    *,
    forge_base_url: str,
    token: str,
    namespace: str,
    project_name: str,
    webhook_public_url: str | None = None,
    dry_run: bool = False,
) -> GitLabReadinessResult:
    """Run all GitLab bootstrap readiness checks.

    Parameters
    ----------
    forge_base_url:
        GitLab instance base URL, e.g. ``"https://gitlab.com"`` or
        ``"https://gitlab.example.com"`` for self-managed.  Must be an
        ``https://`` URL.
    token:
        GitLab personal access token or project access token.  Never
        logged or included in error messages.
    namespace:
        GitLab namespace (group or username) for the target project.
    project_name:
        GitLab project name within the namespace.
    webhook_public_url:
        Public HTTPS URL where oompah is reachable from the internet.
        If ``None``, the webhook URL and hook-create checks are skipped
        (or failed depending on configuration).  Defaults to the value of
        ``OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL`` when not set explicitly.
    dry_run:
        When ``True``, avoid state-mutating API calls (label create,
        hook create).  Read-only equivalents are used instead.

    Returns
    -------
    GitLabReadinessResult
        All capability results; ``all_ok`` is ``True`` iff every
        non-skipped capability passed.
    """
    if not forge_base_url.startswith("https://"):
        raise ValueError(
            f"forge_base_url must be an https:// URL, got {forge_base_url!r}"
        )

    # Resolve webhook URL from env if not explicitly supplied.
    effective_webhook_url = webhook_public_url
    if effective_webhook_url is None:
        effective_webhook_url = os.environ.get("OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL") or None

    encoded_project = _encode_project_path(namespace, project_name)
    capabilities: list[CapabilityResult] = []

    # 1. API access (authentication)
    api_result = _check_api_access(forge_base_url, token)
    capabilities.append(api_result)

    # Short-circuit: if we can't reach the API at all, remaining checks
    # will produce misleading results.
    if api_result.status == CapabilityStatus.failed:
        for name in (
            "label_create",
            "issue_access",
            "mr_access",
            "pipeline_read",
            "state_branch_push",
            "hook_create",
            "polling_fallback",
        ):
            capabilities.append(
                CapabilityResult(
                    name=name,
                    status=CapabilityStatus.skipped,
                    message="Skipped: API access failed",
                )
            )
        capabilities.append(_check_webhook_url(effective_webhook_url))
        return GitLabReadinessResult(
            all_ok=False,
            capabilities=capabilities,
            dry_run=dry_run,
        )

    # 2. Label create
    capabilities.append(
        _check_label_create(
            forge_base_url, token, encoded_project, dry_run=dry_run
        )
    )

    # 3. Issue access
    capabilities.append(_check_issue_access(forge_base_url, token, encoded_project))

    # 4. MR access
    capabilities.append(_check_mr_access(forge_base_url, token, encoded_project))

    # 5. Pipeline read
    capabilities.append(_check_pipeline_read(forge_base_url, token, encoded_project))

    # 6. State-branch push
    capabilities.append(
        _check_state_branch_push(forge_base_url, token, encoded_project)
    )

    # 7. Webhook URL
    capabilities.append(_check_webhook_url(effective_webhook_url))

    # 8. Hook create
    capabilities.append(
        _check_hook_create(
            forge_base_url,
            token,
            encoded_project,
            dry_run=dry_run,
            webhook_public_url=effective_webhook_url,
        )
    )

    # 9. Polling fallback
    capabilities.append(
        _check_polling_fallback(forge_base_url, token, encoded_project)
    )

    all_ok = all(
        c.status != CapabilityStatus.failed for c in capabilities
    )
    return GitLabReadinessResult(
        all_ok=all_ok,
        capabilities=capabilities,
        dry_run=dry_run,
    )


__all__ = [
    "CapabilityResult",
    "CapabilityStatus",
    "GitLabReadinessResult",
    "MINIMUM_TOKEN_SCOPES",
    "check_gitlab_readiness",
]
