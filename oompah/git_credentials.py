"""Ephemeral, non-interactive credentials for authenticated Git commands.

Project access tokens must never be written into remote URLs, command
arguments, repository configuration, or logs.  This module exposes a
short-lived ``GIT_ASKPASS`` environment that keeps the token in child-process
environment only and removes the token-free helper script after use.
"""

from __future__ import annotations

import contextlib
import os
import re
import stat
import subprocess
import tempfile
import urllib.parse
from collections.abc import Iterator, Mapping
from pathlib import Path


_CREDENTIAL_URL_RE = re.compile(
    r"(?P<scheme>https?://)(?P<credentials>[^/\s@]+)@",
    flags=re.IGNORECASE,
)


def forge_display_name(forge_kind: str | None) -> str:
    """Return the operator-facing name for a configured forge."""
    return "GitLab" if str(forge_kind or "").strip().lower() == "gitlab" else "GitHub"


_GIT_AUTH_FAILURE_MARKERS = (
    "authentication failed",
    "authentication required",
    "access denied",
    "http basic: access denied",
    "invalid username or password",
    "invalid credentials",
    "not authorized",
    "unauthorized",
    "terminal prompts disabled",
    "could not read username",
    "could not read password",
    "repository not found",
    "403",
    "401",
)


def git_authentication_failure(
    *,
    forge_kind: str | None,
    access_token: str | None,
    output: str | None,
    operation: str = "Git operation",
) -> str | None:
    """Return a safe, actionable message for an authenticated Git failure.

    Git deliberately emits similar non-interactive errors for an absent
    credential and a rejected credential.  Keep that distinction at the
    managed-project boundary so operators know whether to configure a token
    or rotate/check its scopes.  The returned message never includes output or
    credential material.
    """
    lowered = str(output or "").lower()
    if not any(marker in lowered for marker in _GIT_AUTH_FAILURE_MARKERS):
        return None
    forge = forge_display_name(forge_kind)
    if not str(access_token or "").strip():
        return (
            f"{forge} project forge credential is missing for {operation}; "
            "configure the project's access_token before integrating a private repository"
        )
    return (
        f"{forge} project forge credential was rejected during {operation}; "
        "verify the token, expiry, and repository scope"
    )


def redact_git_output(text: str | None, secrets: tuple[str, ...] = ()) -> str:
    """Remove tokens and credential-bearing URL userinfo from Git output."""
    redacted = str(text or "")
    for secret in secrets:
        if not secret:
            continue
        redacted = redacted.replace(secret, "[REDACTED]")
        encoded = urllib.parse.quote(secret, safe="")
        if encoded != secret:
            redacted = redacted.replace(encoded, "[REDACTED]")
    return _CREDENTIAL_URL_RE.sub(r"\g<scheme>[REDACTED]@", redacted)


def _append_git_config(
    env: dict[str, str],
    key: str,
    value: str,
) -> None:
    """Append one ``GIT_CONFIG_*`` entry without overwriting caller entries."""
    try:
        count = max(0, int(env.get("GIT_CONFIG_COUNT", "0")))
    except ValueError:
        count = 0
    env[f"GIT_CONFIG_KEY_{count}"] = key
    env[f"GIT_CONFIG_VALUE_{count}"] = value
    env["GIT_CONFIG_COUNT"] = str(count + 1)


def _url_rewrite_matches_canonical(prefix: str, canonical_url: str) -> bool:
    """Return whether an insteadOf prefix can rewrite the canonical URL.

    Git applies ``url.<base>.insteadOf`` when the configured value is a prefix
    of the requested URL. Compare credential-free forms so a local rule cannot
    evade cleanup by embedding HTTP userinfo in its match prefix.
    """

    def credential_free(value: str) -> str:
        try:
            parsed = urllib.parse.urlsplit(str(value).strip())
        except ValueError:
            return str(value).strip()
        if parsed.scheme.lower() not in {"http", "https"}:
            return str(value).strip()
        return parsed._replace(netloc=parsed.netloc.rsplit("@", 1)[-1]).geturl()

    candidate = credential_free(canonical_url)
    match_prefix = credential_free(prefix)
    return bool(match_prefix and candidate.startswith(match_prefix))


def sanitize_managed_clone_credentials(
    repo_path: str,
    *,
    canonical_url: str | None = None,
) -> None:
    """Sanitize credential routes from a managed clone's local Git config.

    Removes HTTP(S) remote userinfo, credential helpers, and extraheader
    entries from a managed clone to prevent unauthorized credential access.
    Normalizes managed remotes to the credential-free canonical URL if
    provided.

    This function is idempotent and should be called whenever a managed clone
    is created, adopted, migrated, self-healed, or prepared for direct
    maintenance.

    Args:
        repo_path: Path to the managed clone repository
        canonical_url: Optional credential-free canonical remote URL to use
                       for normalization

    Raises:
        ValueError: If the repository path is invalid or Git operations fail
    """
    repo_dir = Path(repo_path)
    if not repo_dir.is_dir():
        raise ValueError(f"Repository path is not a directory: {repo_path}")

    git_dir = repo_dir / ".git"
    if not git_dir.is_dir():
        raise ValueError(f"Not a Git repository: {repo_path}")

    # First, normalize all remote URLs to remove embedded credentials
    # Use git config directly to avoid shell expansion
    try:
        # Get all remote.*.url entries via git config
        config_result = subprocess.run(
            ["git", "config", "--local", "--get-regexp", r"^remote\..*\.url$"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if config_result.returncode == 0:
            for line in config_result.stdout.splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    continue
                key = parts[0]  # e.g., "remote.origin.url"
                url = parts[1]
                remote_name = key.split(".")[1]  # Extract remote name

                # For the 'origin' remote, use canonical URL if provided
                if remote_name == "origin" and canonical_url:
                    subprocess.run(
                        ["git", "config", "--local", key, canonical_url],
                        cwd=str(repo_dir),
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                    continue

                # For other remotes, strip userinfo from HTTP(S) URLs
                try:
                    parsed = urllib.parse.urlsplit(url)
                    if (
                        parsed.scheme.lower() in {"http", "https"}
                        and parsed.username is not None
                    ):
                        # Strip userinfo and reconstruct URL
                        cleaned = parsed._replace(
                            netloc=parsed.netloc.rsplit("@", 1)[-1]
                        ).geturl()
                        subprocess.run(
                            ["git", "config", "--local", key, cleaned],
                            cwd=str(repo_dir),
                            capture_output=True,
                            timeout=10,
                            check=False,
                        )
                except ValueError:
                    # Invalid URL, skip it
                    pass
    except (OSError, subprocess.TimeoutExpired):
        pass  # Non-fatal; continue with credential config cleanup

    # Second, remove local url.*.insteadOf entries that can rewrite the
    # canonical project URL before Git contacts the remote. A stale rewrite
    # such as
    #
    #   url.git@gitlab.example:.insteadOf=https://gitlab.example/
    #
    # makes ``remote.origin.url`` look correct while silently routing every
    # fetch back through SSH. Only remove repository-local entries whose
    # prefix matches the canonical URL; unrelated rewrites and global/system
    # configuration remain untouched. (OOMPAH-1335)
    if canonical_url:
        try:
            rewrite_result = subprocess.run(
                ["git", "config", "--local", "--get-regexp", r"^url\..*\.insteadof$"],
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if rewrite_result.returncode == 0:
                for line in rewrite_result.stdout.splitlines():
                    parts = line.split(maxsplit=1)
                    if len(parts) != 2:
                        continue
                    key, prefix = parts
                    if not _url_rewrite_matches_canonical(prefix, canonical_url):
                        continue
                    subprocess.run(
                        ["git", "config", "--local", "--unset-all", key],
                        cwd=str(repo_dir),
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
        except (OSError, subprocess.TimeoutExpired):
            pass  # Non-fatal; continue with credential config cleanup

    # Third, remove credential.helper entries
    try:
        # Get all credential.helper configurations
        config_result = subprocess.run(
            ["git", "config", "--local", "--get-regexp", r"^credential.*\.helper$"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if config_result.returncode == 0:
            for line in config_result.stdout.splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) >= 1:
                    key = parts[0]
                    subprocess.run(
                        ["git", "config", "--local", "--unset", key],
                        cwd=str(repo_dir),
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
    except (OSError, subprocess.TimeoutExpired):
        pass  # Non-fatal; continue

    # Fourth, remove http.*.extraheader entries
    try:
        config_result = subprocess.run(
            ["git", "config", "--local", "--get-regexp", r"^http\..*\.extraheader$"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if config_result.returncode == 0:
            for line in config_result.stdout.splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) >= 1:
                    key = parts[0]
                    subprocess.run(
                        ["git", "config", "--local", "--unset", key],
                        cwd=str(repo_dir),
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
    except (OSError, subprocess.TimeoutExpired):
        pass  # Non-fatal


@contextlib.contextmanager
def git_credential_environment(
    *,
    forge_kind: str | None,
    access_token: str | None,
    base_env: Mapping[str, str] | None = None,
) -> Iterator[dict[str, str]]:
    """Yield an environment for non-interactive project Git operations.

    When a project token is configured, Git receives a temporary askpass
    helper.  The helper contains no credential material: it reads the
    forge-specific username and token from its child environment.  Existing
    credential helpers are reset so a cached credential cannot override the
    explicitly configured project token.
    """
    env = dict(base_env) if base_env is not None else os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    token = str(access_token or "")
    if not token:
        yield env
        return

    username = (
        "oauth2"
        if str(forge_kind or "").strip().lower() == "gitlab"
        else "x-access-token"
    )
    with tempfile.TemporaryDirectory(prefix="oompah-git-askpass-") as tmp_dir:
        askpass = Path(tmp_dir) / "askpass.sh"
        askpass.write_text(
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "  *sername*) printf '%s\\n' \"$OOMPAH_GIT_USERNAME\" ;;\n"
            "  *assword*) printf '%s\\n' \"$OOMPAH_GIT_PASSWORD\" ;;\n"
            "  *) exit 1 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        askpass.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

        env["GIT_ASKPASS"] = str(askpass)
        env["GIT_ASKPASS_REQUIRE"] = "force"
        env["OOMPAH_GIT_USERNAME"] = username
        env["OOMPAH_GIT_PASSWORD"] = token
        _append_git_config(env, "credential.helper", "")
        _append_git_config(env, "credential.useHttpPath", "true")
        yield env
