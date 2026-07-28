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
