"""Client-side credential resolver for oompah CLIs.

Provides secure Basic-auth credential resolution for ``oompah task``,
``oompah admin``, and Makefile lifecycle helpers when the oompah server has
htpasswd authentication enabled.

Security Model
--------------
* Credentials are **never** placed in URLs, process arguments, log output, or
  error text.
* Passwords come from environment variables or password files only.
* Exactly one password source (``OOMPAH_SERVER_PASSWORD`` or
  ``OOMPAH_SERVER_PASSWORD_FILE``) must be configured when a username is
  present; providing both is a configuration error.
* Password files are verified to be regular, non-symlink files, and the
  caller receives a warning when POSIX permissions allow group or world
  read access.
* Server URLs containing embedded credentials (``user:pass@host``) are
  rejected; error messages display only the redacted URL.
* 401 responses produce actionable remediation messages without echoing
  credential values or Authorization header content.

Environment Variables
---------------------
OOMPAH_SERVER_USERNAME
    Client username for HTTP Basic auth.

OOMPAH_SERVER_PASSWORD
    Client plaintext password (inline env-var form; less secure than a
    password file because the value may appear in shell history and
    ``ps`` output on some systems).

OOMPAH_SERVER_PASSWORD_FILE
    Path to a regular file containing **only** the client plaintext
    password (leading/trailing whitespace is stripped).  Preferred for
    unattended use.  Must be a regular, readable file.  A warning is
    logged when POSIX file-mode bits permit group or world read access.
    Symlinks are rejected outright to prevent redirection attacks.

CLI overrides (accepted by ``oompah task`` and ``oompah admin``)
-----------------------------------------------------------------
--username       Non-secret override for OOMPAH_SERVER_USERNAME.
--password-file  Path override for OOMPAH_SERVER_PASSWORD_FILE.
                 No --password / --password-file-inline option is
                 provided to avoid plaintext passwords in shell history
                 or printed Makefile recipes.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
import sys
import tempfile
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

# These values are client-side inputs only.  They must not be inherited by
# agent subprocesses launched by the server, where an agent could expose them
# in diagnostics or command output.
CLIENT_AUTH_ENV_VARS = frozenset(
    {
        "OOMPAH_SERVER_USERNAME",
        "OOMPAH_SERVER_PASSWORD",
        "OOMPAH_SERVER_PASSWORD_FILE",
    }
)

# This non-secret marker prevents client entry points from reloading Basic
# credentials from a checked-out .env file after the server deliberately
# removed them from a spawned worker's inherited environment.
CLIENT_AUTH_DISABLED_ENV = "OOMPAH_DISABLE_CLIENT_AUTH"

# A service process commonly has an active virtual environment in its own
# checkout.  Passing that environment through to a task worker lets uv select
# the service venv even when the worker is operating in another worktree.  Keep
# these selectors out of worker processes; Make receives an explicit,
# worktree-private environment path below instead.
TASK_VENV_ENV = "OOMPAH_TASK_VENV"
SERVICE_CHECKOUT_ENV = "OOMPAH_SERVICE_CHECKOUT"
SERVICE_VENV_ENV = "OOMPAH_SERVICE_VENV"
_WORKER_RUNTIME_SELECTOR_ENV_VARS = frozenset(
    {
        TASK_VENV_ENV,
        SERVICE_CHECKOUT_ENV,
        SERVICE_VENV_ENV,
        "VIRTUAL_ENV",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PYTHON",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONUSERBASE",
        "CONDA_PREFIX",
        "CONDA_DEFAULT_ENV",
        "PIPENV_ACTIVE",
        "PIP_TARGET",
        "PIP_PREFIX",
    }
)

# The service is commonly launched by a Make recipe.  GNU Make exports these
# controls to every descendant, where they can inject makefile fragments or
# command-line options into an otherwise literal ``make test`` invocation.
# They describe the operator's service-launch context, not worker intent, so
# never let them cross the agent process boundary.  A task that genuinely
# needs Make options must spell them in its command, where validation policy
# can classify the exact invocation.
_INHERITED_MAKE_CONTROL_ENV_VARS = frozenset(
    {
        "GNUMAKEFLAGS",
        "MAKEFILES",
        "MAKEFLAGS",
        "MAKEOVERRIDES",
        "MFLAGS",
    }
)

# A direct epic-rebase helper works in the shared epic checkout.  It must not
# inherit the service/operator's general shell environment: that environment
# can carry forge credentials through arbitrary names, Git's credential
# configuration, or an SSH agent.  This is deliberately an allow-list rather
# than a list of token names.  Task handoff is server-mediated through the
# in-process tool callback and is never an environment capability.
_REMOTE_WRITE_ISOLATION_SAFE_ENV_VARS = frozenset(
    {
        "PATH",
        "LANG",
        "LANGUAGE",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "COLORTERM",
        "NO_COLOR",
        "TZ",
    }
)


def _isolated_remote_write_environment(
    environment: Mapping[str, str],
) -> dict[str, str]:
    """Return a credential-free environment for an epic-rebase worker.

    The caller must remove all ambient authority, not merely known forge
    variable names: a token can use an arbitrary name and Git can obtain one
    through inherited home/config/SSH state.  A fresh 0700 runtime directory
    supplies an empty home and XDG roots.  Its parent is tracked through
    ``OOMPAH_WORKER_RUNTIME_DIR`` and cleaned by worker launchers.
    """
    isolated = {
        key: value
        for key, value in environment.items()
        if key in _REMOTE_WRITE_ISOLATION_SAFE_ENV_VARS
    }
    runtime_dir = _create_worker_runtime_directory()
    if runtime_dir is None:
        raise OSError("could not create isolated runtime directory for worker")

    home_dir = os.path.join(runtime_dir, "home")
    for directory in (
        home_dir,
        os.path.join(runtime_dir, "config"),
        os.path.join(runtime_dir, "cache"),
        os.path.join(runtime_dir, "data"),
    ):
        os.mkdir(directory, mode=0o700)

    # These controls are defence in depth.  The capability boundary is the
    # clean environment and empty home; no agent-supplied command needs to be
    # classified for that boundary to hold.
    isolated.update(
        {
            "HOME": home_dir,
            "XDG_CONFIG_HOME": os.path.join(runtime_dir, "config"),
            "XDG_CACHE_HOME": os.path.join(runtime_dir, "cache"),
            "XDG_DATA_HOME": os.path.join(runtime_dir, "data"),
            "XDG_RUNTIME_DIR": runtime_dir,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/false",
            "SSH_ASKPASS": "/bin/false",
            "GIT_SSH_COMMAND": "/bin/false",
            "OOMPAH_WORKER_RUNTIME_DIR": runtime_dir,
        }
    )
    return isolated


def _copy_private_provider_auth(
    source: Path,
    destination: Path,
) -> None:
    """Copy one explicit provider artifact without following a symlink."""
    try:
        source_stat = source.lstat()
    except OSError as exc:
        raise OSError("configured provider authentication artifact is unavailable") from exc
    if not stat.S_ISREG(source_stat.st_mode) or source.is_symlink():
        raise OSError("configured provider authentication artifact is unsafe")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o600)


def _copy_private_claude_primary_api_key(
    source: Path,
    destination: Path,
) -> None:
    """Copy only Claude's current-layout model credential.

    Recent Claude CLI releases persist subscription authentication in the
    top-level ``.claude.json`` state file instead of the older dedicated
    ``.claude/.credentials.json`` artifact.  That state file also contains
    unrelated operator configuration and workspace history, so isolated
    workers receive a new minimal document rather than a copy of the file.
    """
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(source, flags)
    except OSError as exc:
        raise OSError(
            "configured provider authentication artifact is unavailable"
        ) from exc
    try:
        source_stat = os.fstat(fd)
        if not stat.S_ISREG(source_stat.st_mode):
            raise OSError("configured provider authentication artifact is unsafe")
        with os.fdopen(fd, "r", encoding="utf-8") as source_file:
            fd = -1
            try:
                document = json.load(source_file)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise OSError(
                    "configured provider authentication artifact is invalid"
                ) from exc
    finally:
        if fd >= 0:
            os.close(fd)
    primary_api_key = (
        document.get("primaryApiKey") if isinstance(document, dict) else None
    )
    if not isinstance(primary_api_key, str) or not primary_api_key.strip():
        raise OSError("configured provider authentication artifact is invalid")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as destination_file:
        json.dump({"primaryApiKey": primary_api_key}, destination_file)
        destination_file.write("\n")
    os.chmod(destination, 0o600)


def _bootstrap_isolated_provider_auth(
    environment: dict[str, str],
    source_environment: Mapping[str, str],
    provider_auth_kind: str | None,
) -> None:
    """Install the minimum explicit model credential for an isolated worker.

    Provider access is independent of project Git access.  Unknown layouts are
    refused instead of copying an operator home or configuration tree into the
    worker.  The copied artifact remains inside the worker runtime directory
    and is removed with it when the worker exits.
    """
    if provider_auth_kind is None:
        return
    home = Path(environment["HOME"])
    source_home_raw = str(source_environment.get("HOME") or "").strip()
    source_home = Path(source_home_raw).expanduser() if source_home_raw else None

    if provider_auth_kind == "codex_subscription":
        configured_root = str(source_environment.get("CODEX_HOME") or "").strip()
        if not configured_root and source_home is None:
            raise OSError("configured provider authentication artifact is unavailable")
        source_root = Path(configured_root).expanduser() if configured_root else source_home / ".codex"
        destination_root = home / ".codex"
        _copy_private_provider_auth(source_root / "auth.json", destination_root / "auth.json")
        environment["CODEX_HOME"] = str(destination_root)
        return

    if provider_auth_kind == "claude_subscription":
        configured_root = str(source_environment.get("CLAUDE_CONFIG_DIR") or "").strip()
        if not configured_root and source_home is None:
            raise OSError("configured provider authentication artifact is unavailable")
        source_root = Path(configured_root).expanduser() if configured_root else source_home / ".claude"
        destination_root = home / ".claude"
        legacy_auth = source_root / ".credentials.json"
        try:
            legacy_auth.lstat()
        except FileNotFoundError:
            current_auth = (
                source_root / ".claude.json"
                if configured_root
                else source_home / ".claude.json"
            )
            _copy_private_claude_primary_api_key(
                current_auth,
                destination_root / ".claude.json",
            )
        except OSError as exc:
            raise OSError(
                "configured provider authentication artifact is unavailable"
            ) from exc
        else:
            _copy_private_provider_auth(
                legacy_auth,
                destination_root / ".credentials.json",
            )
        environment["CLAUDE_CONFIG_DIR"] = str(destination_root)
        return

    if provider_auth_kind == "opencode_subscription":
        configured_root = str(source_environment.get("OPENCODE_AUTH_DIR") or "").strip()
        source_xdg_data = str(source_environment.get("XDG_DATA_HOME") or "").strip()
        if configured_root:
            source_root = Path(configured_root).expanduser()
        elif source_xdg_data:
            source_root = Path(source_xdg_data).expanduser() / "opencode"
        elif source_home is not None:
            source_root = source_home / ".local" / "share" / "opencode"
        else:
            raise OSError("configured provider authentication artifact is unavailable")
        destination_root = Path(environment["XDG_DATA_HOME"]) / "opencode"
        _copy_private_provider_auth(source_root / "auth.json", destination_root / "auth.json")
        return

    key_sources = {
        "codex_api": ("OOMPAH_CODEX_API_KEY", "OPENAI_API_KEY"),
        "opencode_api": ("OOMPAH_OPENCODE_API_KEY", "OPENAI_API_KEY"),
    }
    candidates = key_sources.get(provider_auth_kind)
    if candidates is None:
        raise OSError("unknown isolated worker provider authentication layout")
    api_key = next(
        (
            str(source_environment[key]).strip()
            for key in candidates
            if str(source_environment.get(key) or "").strip()
        ),
        "",
    )
    if not api_key:
        raise OSError("configured provider API credential is unavailable")
    environment["OPENAI_API_KEY"] = api_key


def validate_isolated_provider_auth(
    provider_auth_kind: str,
    source_environment: Mapping[str, str] | None = None,
) -> None:
    """Prove that an isolated worker can bootstrap its model credential.

    This deliberately exercises the same copy/minimization path used at
    worker launch. The temporary credential domain is always removed, and
    errors contain only normalized artifact reasons.
    """
    source = dict(os.environ if source_environment is None else source_environment)
    isolated = _isolated_remote_write_environment(source)
    try:
        _bootstrap_isolated_provider_auth(isolated, source, provider_auth_kind)
    finally:
        shutil.rmtree(
            isolated.get("OOMPAH_WORKER_RUNTIME_DIR", ""),
            ignore_errors=True,
        )


def task_venv_path(workspace_path: str | os.PathLike[str]) -> str:
    """Return the disposable dependency environment for one task worktree.

    The path is intentionally below the task checkout.  It is ignored by the
    repository's ``.oompah/*`` rules, unique per managed worktree, and never
    aliases the operator/service virtual environment.
    """
    workspace = Path(workspace_path).resolve()
    return str(workspace / ".oompah" / "task-venv")


def _parse_dotenv_value(raw: str) -> str:
    """Parse the small, dependency-free .env subset needed by CLI clients."""
    raw = raw.strip()
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        inner = raw[1:-1]
        return (
            inner.replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\t", "\t")
            .replace("\\\\", "\\")
        )
    if len(raw) >= 2 and raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    return raw


def load_client_environment(
    env_file: str = ".env", *, include_server_url: bool = True
) -> int:
    """Refresh client-only settings from the current ``.env`` file.

    Standalone task/admin CLIs do not install the server's YAML dependency, so
    they use this deliberately small parser instead of importing the server
    configuration module.  Only HTTP-client inputs are read, values from the
    selected file replace stale inherited values, and neither values nor parse
    failures are logged.  Spawned workers are explicitly excluded so a worker
    cannot regain a server Basic secret from the checkout after inheritance was
    stripped.
    """
    if os.environ.get(CLIENT_AUTH_DISABLED_ENV, "").strip():
        return 0

    allowed = set(CLIENT_AUTH_ENV_VARS)
    if include_server_url:
        allowed.add("OOMPAH_SERVER_URL")

    try:
        with open(env_file, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return 0
    except OSError:
        # An unavailable client .env should preserve an explicitly exported
        # configuration.  Keep diagnostics redacted because the file can be a
        # secret-bearing deployment artifact.
        logger.warning("Unable to read client environment file")
        return 0

    loaded = 0
    configured_auth_keys: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        key, separator, raw_value = stripped.partition("=")
        key = key.strip()
        if not separator or key not in allowed:
            continue
        os.environ[key] = _parse_dotenv_value(raw_value)
        if key in CLIENT_AUTH_ENV_VARS:
            configured_auth_keys.add(key)
        loaded += 1

    # A .env that intentionally configures any client credential source is an
    # authoritative set: remove a stale alternative inherited from an earlier
    # shell so rotation cannot leave both password sources configured.  A .env
    # with no client-auth entries preserves externally supplied credentials.
    if configured_auth_keys:
        for key in CLIENT_AUTH_ENV_VARS - configured_auth_keys:
            os.environ.pop(key, None)
    return loaded

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CredentialError(Exception):
    """Raised on credential configuration errors (missing, inconsistent, unsafe)."""

    pass


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


class ClientCredentials(NamedTuple):
    """Resolved client credentials for HTTP Basic auth."""

    username: str
    password: str


# ---------------------------------------------------------------------------
# Permission check
# ---------------------------------------------------------------------------

# Bits that expose a file to group or world readers.
_UNSAFE_PERM_MASK = stat.S_IRGRP | stat.S_IROTH


def _check_password_file_permissions(path: str, st: os.stat_result) -> None:
    """Warn if *path* has unsafe POSIX permissions (group- or world-readable).

    Args:
        path: Human-readable path for the warning message.
        st:   ``os.stat_result`` for *path* (already obtained by the caller).

    This is a warning, not an error: some deployment environments (e.g. Docker
    secrets, Kubernetes secret mounts) intentionally use permissive modes on
    secret files.  Operators can suppress the warning by restricting permissions
    (``chmod 600 <path>``).
    """
    file_mode = stat.S_IMODE(st.st_mode)
    if file_mode & _UNSAFE_PERM_MASK:
        logger.warning(
            "OOMPAH_SERVER_PASSWORD_FILE %r has unsafe permissions %s "
            "(group- or world-readable). "
            "Restrict with: chmod 600 %r",
            path,
            oct(file_mode),
            path,
        )


# ---------------------------------------------------------------------------
# Password file reading
# ---------------------------------------------------------------------------


def _read_password_file(path: str) -> str:
    """Read and return the plaintext password from a password file.

    Security requirements enforced here:

    * Uses ``os.lstat`` before opening to detect and reject symlinks
      (TOCTOU window between stat and open is minimised by checking the
      inode again via ``os.fstat`` after the file is opened).
    * Regular files only; rejects directories, devices, sockets, FIFOs.
    * Empty content is an error.
    * Permission check emits a log warning (not a fatal error) for
      group/world-readable files.

    Args:
        path: Path to the password file.

    Returns:
        The plaintext password with leading/trailing whitespace stripped.

    Raises:
        CredentialError: On symlink, non-regular file, permission errors,
                         empty content, or read failures.
    """
    # Step 1: lstat — check without following symlinks.
    try:
        lst = os.lstat(path)
    except FileNotFoundError:
        raise CredentialError(
            f"OOMPAH_SERVER_PASSWORD_FILE not found: {path!r}"
        ) from None
    except OSError as exc:
        raise CredentialError(
            f"Cannot access OOMPAH_SERVER_PASSWORD_FILE {path!r}: {exc.strerror}"
        ) from exc

    if stat.S_ISLNK(lst.st_mode):
        raise CredentialError(
            f"OOMPAH_SERVER_PASSWORD_FILE {path!r} is a symbolic link. "
            "Provide the direct target path to prevent symlink-substitution attacks."
        )

    if not stat.S_ISREG(lst.st_mode):
        raise CredentialError(
            f"OOMPAH_SERVER_PASSWORD_FILE {path!r} is not a regular file "
            f"(mode={oct(lst.st_mode)})."
        )

    # Step 2: Permission warning (before we open, so we don't read and then warn).
    _check_password_file_permissions(path, lst)

    # Step 3: Open and verify inode consistency to tighten the TOCTOU window.
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
    except PermissionError:
        raise CredentialError(
            f"OOMPAH_SERVER_PASSWORD_FILE {path!r} is not readable. "
            "Check file permissions (e.g. chmod 600)."
        ) from None
    except OSError as exc:
        raise CredentialError(
            f"Failed to open OOMPAH_SERVER_PASSWORD_FILE {path!r}: {exc.strerror}"
        ) from exc

    try:
        fst = os.fstat(fd)
        # If the inode or device changed between lstat and open, a symlink or
        # rename race replaced the file under us.  Reject to be safe.
        if fst.st_ino != lst.st_ino or fst.st_dev != lst.st_dev:
            raise CredentialError(
                f"OOMPAH_SERVER_PASSWORD_FILE {path!r} changed between stat and open "
                "(possible symlink race). Aborting."
            )
        with os.fdopen(fd, "r", encoding="utf-8") as fh:
            fd = -1  # prevent double-close in finally
            content = fh.read()
    except CredentialError:
        raise
    except OSError as exc:
        raise CredentialError(
            f"Failed to read OOMPAH_SERVER_PASSWORD_FILE {path!r}: {exc.strerror}"
        ) from exc
    finally:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass

    password = content.strip()
    if not password:
        raise CredentialError(
            f"OOMPAH_SERVER_PASSWORD_FILE {path!r} is empty."
        )

    return password


# ---------------------------------------------------------------------------
# Hostname normalization
# ---------------------------------------------------------------------------


def _normalize_hostname(server_url: str) -> str:
    """Extract and normalize the hostname for netrc lookup from a server URL.

    The hostname is extracted from the server URL and normalized for netrc
    lookup.  IPv6 addresses are returned without brackets (netrc uses bare
    addresses).  The port is stripped; netrc entries are hostname-only.

    Args:
        server_url: Sanitized server URL (already validated by sanitize_server_url).

    Returns:
        The normalized hostname for netrc lookup (IPv6 without brackets).

    Raises:
        CredentialError: If the URL cannot be parsed or contains no hostname.
    """
    if not server_url or not server_url.strip():
        raise CredentialError("Cannot extract hostname from empty server URL.")

    try:
        parsed = urllib.parse.urlparse(server_url)
        hostname = parsed.hostname
    except Exception as exc:
        raise CredentialError(
            f"Cannot parse server URL to extract hostname: {exc}"
        ) from exc

    if not hostname:
        raise CredentialError(
            f"Server URL does not contain a valid hostname: {server_url}"
        )

    # Return hostname normalized for netrc (IPv6 without brackets, lowercase for DNS).
    # netrc format uses bare IPv6 without brackets; we return that form.
    return hostname.lower()


# ---------------------------------------------------------------------------
# Netrc file reading
# ---------------------------------------------------------------------------


def _read_netrc_file(path: str) -> dict[str, tuple[str, str]] | None:
    """Read and parse a netrc file, returning hostname -> (username, password) mapping.

    Security requirements enforced here:

    * Uses ``os.lstat`` before opening to detect and reject symlinks.
    * Regular files only; rejects directories, devices, sockets, FIFOs.
    * Permissions must be 0o600 (or 0o400 on some systems); stricter than password-file.
    * TOCTOU verification via inode check (lstat vs fstat).
    * Rejects malformed entries and ignores whitespace-only lines.
    * Returns a dict mapping hostname -> (username, password) for matching entries.
    * Returns None if file does not exist (not an error; netrc is optional).

    Args:
        path: Path to the netrc file (typically ~/.netrc).

    Returns:
        Dict mapping hostname -> (username, password) when file exists and is valid,
        or None when file does not exist (optional fallback).

    Raises:
        CredentialError: On symlink, unsafe permissions, non-regular file,
                         parse errors, or read failures.
    """
    # Return None if the file does not exist (netrc is optional).
    try:
        lst = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        # Other OS errors (permission denied on parent directory, etc.) are fatal.
        raise CredentialError(
            f"Cannot access netrc file {path!r}: {exc.strerror}"
        ) from exc

    # Reject symlinks to prevent substitution attacks.
    if stat.S_ISLNK(lst.st_mode):
        raise CredentialError(
            f"netrc file {path!r} is a symbolic link. "
            "Provide the direct target path to prevent symlink-substitution attacks."
        )

    # Regular file only.
    if not stat.S_ISREG(lst.st_mode):
        raise CredentialError(
            f"netrc file {path!r} is not a regular file "
            f"(mode={oct(lst.st_mode)})."
        )

    # Permissions: netrc must be owner-readable only (0o600 or 0o400).
    # This is stricter than password-file (0o644 is allowed with a warning).
    # Historically, netrc expects 0o600; we accept 0o400 (read-only) as well.
    file_mode = stat.S_IMODE(lst.st_mode)
    if file_mode not in (0o600, 0o400):
        raise CredentialError(
            f"netrc file {path!r} has unsafe permissions {oct(file_mode)}. "
            "netrc must be readable only by the owner (chmod 600). "
            "Fix with: chmod 600 {path!r}".format(path=path)
        )

    # Open and verify inode consistency (TOCTOU protection).
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
    except PermissionError:
        raise CredentialError(
            f"netrc file {path!r} is not readable. "
            "Check file permissions (chmod 600)."
        ) from None
    except OSError as exc:
        raise CredentialError(
            f"Failed to open netrc file {path!r}: {exc.strerror}"
        ) from exc

    try:
        fst = os.fstat(fd)
        if fst.st_ino != lst.st_ino or fst.st_dev != lst.st_dev:
            raise CredentialError(
                f"netrc file {path!r} changed between stat and open "
                "(possible symlink race). Aborting."
            )
        with os.fdopen(fd, "r", encoding="utf-8") as fh:
            fd = -1  # prevent double-close in finally
            content = fh.read()
    except CredentialError:
        raise
    except OSError as exc:
        raise CredentialError(
            f"Failed to read netrc file {path!r}: {exc.strerror}"
        ) from exc
    finally:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass

    # Parse the netrc file.
    # netrc format:
    #   machine <hostname>
    #   login <username>
    #   password <password>
    # [optional: account <account>]
    # Entries are whitespace-separated; comments start with '#'.
    # We parse conservatively, supporting only the fields we use.
    #
    # This is a simplified parser focused on security: we extract login and
    # password for matching machines, and ignore other fields.

    entries: dict[str, tuple[str, str]] = {}
    lines = content.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        # Skip empty lines and comments.
        if not line or line.startswith("#"):
            continue

        # Look for "machine <hostname>" keyword.
        parts = line.split()
        if not parts or parts[0] != "machine":
            continue

        if len(parts) < 2:
            raise CredentialError(
                f"Malformed netrc entry: 'machine' keyword missing hostname"
            )

        machine = parts[1]
        login = None
        password = None

        # Parse subsequent lines for login and password in this entry.
        while i < len(lines):
            entry_line = lines[i].strip()
            i += 1

            # Empty lines and comments within an entry are allowed.
            if not entry_line or entry_line.startswith("#"):
                continue

            entry_parts = entry_line.split(None, 1)
            if not entry_parts:
                continue

            keyword = entry_parts[0]

            # Stop at the next machine declaration.
            if keyword == "machine":
                i -= 1  # Back up to reprocess this line as a new machine.
                break

            # Extract login and password; ignore other keywords (account, etc.).
            if keyword == "login" and len(entry_parts) > 1:
                login = entry_parts[1]
            elif keyword == "password" and len(entry_parts) > 1:
                password = entry_parts[1]
            elif keyword not in ("account", "default"):
                # Unrecognized keywords are allowed (for forward compatibility);
                # we just skip them.
                pass

        # Require both login and password in a valid entry.
        if login and password:
            entries[machine] = (login, password)
        elif login or password:
            # Partial entry (only login or only password) is a configuration error.
            raise CredentialError(
                f"Malformed netrc: machine {machine!r} has 'login' "
                "or 'password' but not both. Both are required."
            )

    return entries if entries else None


def _lookup_netrc_credentials(
    netrc_entries: dict[str, tuple[str, str]],
    hostname: str,
) -> tuple[str, str] | None:
    """Look up hostname in netrc entries and return (username, password) or None.

    Args:
        netrc_entries: Dict mapping hostname -> (username, password) from netrc.
        hostname: Normalized hostname to look up (lowercase, no IPv6 brackets).

    Returns:
        (username, password) tuple if found, or None if not found.
    """
    if hostname in netrc_entries:
        return netrc_entries[hostname]
    return None


# ---------------------------------------------------------------------------
# URL sanitization
# ---------------------------------------------------------------------------


def sanitize_server_url(url: str) -> str:
    """Validate and return the server URL, rejecting embedded credentials.

    Callers must never embed userinfo (``user:pass@``) in
    ``OOMPAH_SERVER_URL``; that would expose the password in log output,
    error messages, shell history, and ``ps`` listings.  This function rejects
    such URLs and includes only a redacted form in the error message.

    Args:
        url: Raw server URL string (may contain trailing slash).

    Returns:
        The URL with any trailing slash stripped, if it contains no userinfo.

    Raises:
        CredentialError: If the URL contains a username or password component.
    """
    url = url.strip()
    if not url:
        return url

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        # Do not return or echo an unparseable value: malformed userinfo can
        # make urllib.parse reject the URL before it exposes parsed fields.
        raise CredentialError(
            "OOMPAH_SERVER_URL is invalid. Use an http(s) URL without embedded credentials."
        ) from None

    # ``@`` catches an empty userinfo component too (``http://@host``), while
    # username/password catches percent-encoded userinfo recognized by
    # urllib.parse.  Only emit an origin in the error message: a path, query,
    # or fragment can also contain a secret supplied by a misconfigured URL.
    if "@" in parsed.netloc or parsed.username is not None or parsed.password is not None:
        try:
            hostname = parsed.hostname or "<invalid-host>"
            if ":" in hostname and not hostname.startswith("["):
                hostname = f"[{hostname}]"
            try:
                port = parsed.port
            except ValueError:
                port = None
            netloc_redacted = hostname + (f":{port}" if port else "")
            redacted = urllib.parse.urlunparse((parsed.scheme, netloc_redacted, "", "", "", ""))
        except (TypeError, ValueError):
            redacted = "<unparseable-server-url>"
        raise CredentialError(
            "OOMPAH_SERVER_URL must not contain credentials (user:password@host). "
            "Set OOMPAH_SERVER_USERNAME and OOMPAH_SERVER_PASSWORD_FILE (preferred) "
            "or OOMPAH_SERVER_PASSWORD instead. "
            f"(Redacted URL: {redacted!r})"
        )

    return url.rstrip("/")


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------


def resolve_client_credentials(
    username_override: str | None = None,
    password_file_override: str | None = None,
    server_url: str | None = None,
) -> ClientCredentials | None:
    """Resolve client Basic-auth credentials from multiple sources with proper precedence.

    Source priority
    ~~~~~~~~~~~~~~~
    **Username precedence:**
      1. CLI ``--username`` override
      2. ``OOMPAH_SERVER_USERNAME`` environment variable
      3. Entry in ~/.netrc for the resolved server hostname (if URL provided)

    **Password precedence:**
      1. CLI ``--password-file`` override
      2. ``OOMPAH_SERVER_PASSWORD_FILE`` environment variable
      3. ``OOMPAH_SERVER_PASSWORD`` environment variable (inline)
      4. Entry in ~/.netrc for the resolved server hostname (if URL provided)

    When credentials are incomplete (username without password or vice versa),
    resolution fails with a clear error. Conflicting same-tier sources
    (e.g., both OOMPAH_SERVER_PASSWORD and OOMPAH_SERVER_PASSWORD_FILE) are
    rejected.

    Args:
        username_override: CLI ``--username`` value (highest precedence).
        password_file_override: CLI ``--password-file`` path (highest password precedence).
        server_url: Sanitized server URL for netrc hostname extraction.
                    When provided and neither CLI nor env vars supply complete
                    credentials, netrc is consulted as a fallback.

    Returns:
        :class:`ClientCredentials` ``(username, password)`` when credentials
        are configured, or ``None`` when no credential source is set (for
        backward-compatible unauthenticated operation).

    Raises:
        :exc:`CredentialError`: On inconsistent (both password sources),
            incomplete (username without password or vice versa), unreadable,
            empty, unsafe credential configuration, or netrc errors.
    """
    # Resolve username with precedence: CLI > env > netrc.
    raw_username = (
        os.environ.get("OOMPAH_SERVER_USERNAME", "")
        if username_override is None
        else username_override
    )
    username = raw_username.strip()

    if password_file_override is not None:
        # A CLI password-file is an explicit source selection.  It overrides
        # both environment password forms, including an inline password that
        # may be present in a calling shell.
        password_file = password_file_override.strip() or None
        password_env = None
    else:
        password_file = os.environ.get("OOMPAH_SERVER_PASSWORD_FILE", "").strip() or None
        password_env = os.environ.get("OOMPAH_SERVER_PASSWORD", "").strip() or None

    # Check for mutual exclusion of password sources at the environment tier.
    if password_file and password_env:
        raise CredentialError(
            "Set exactly one of OOMPAH_SERVER_PASSWORD or OOMPAH_SERVER_PASSWORD_FILE, "
            "not both. Prefer OOMPAH_SERVER_PASSWORD_FILE for unattended use."
        )

    # Try to read netrc if URL is provided and higher-tier sources didn't supply
    # complete credentials. netrc is the lowest precedence.
    netrc_username = None
    netrc_password = None
    netrc_available = False

    if server_url:
        try:
            netrc_path = str(Path.home() / ".netrc")
            netrc_entries = _read_netrc_file(netrc_path)
            if netrc_entries:
                netrc_available = True
                hostname = _normalize_hostname(server_url)
                netrc_creds = _lookup_netrc_credentials(netrc_entries, hostname)
                if netrc_creds:
                    netrc_username, netrc_password = netrc_creds
        except CredentialError:
            # netrc errors are fatal (malformed, unsafe permissions, etc.).
            raise
        except Exception:
            # Other exceptions (e.g., Path.home() might fail in unusual environments)
            # are silently ignored; netrc is optional.
            pass

    # Now apply precedence rules and validate the result.

    # If CLI or env supplied a username, use that precedence order.
    # If not, fall back to netrc username.
    if not username and netrc_username:
        username = netrc_username

    # Resolve password with precedence: CLI password-file > env password-file >
    # env inline password > netrc password.
    resolved_password = None
    password_source = None  # Track which source provided the password

    if password_file:
        resolved_password = _read_password_file(password_file)
        password_source = "password-file"
    elif password_env:
        resolved_password = password_env
        password_source = "password-env"
    elif netrc_password:
        resolved_password = netrc_password
        password_source = "netrc"

    # Validate: if any source (CLI, env, netrc) provided credentials, we need
    # both username and password.

    # Nothing configured at all → unauthenticated (backward-compatible).
    if not username and not resolved_password:
        return None

    # Username required when any password source is set.
    if not username and resolved_password:
        raise CredentialError(
            "OOMPAH_SERVER_USERNAME is required when a password source is set. "
            "Set OOMPAH_SERVER_USERNAME, OOMPAH_SERVER_PASSWORD_FILE (preferred), "
            "or OOMPAH_SERVER_PASSWORD, or provide credentials in ~/.netrc."
        )

    # Password source required when username is set.
    if username and not resolved_password:
        raise CredentialError(
            "A password source is required when OOMPAH_SERVER_USERNAME is set. "
            "Set OOMPAH_SERVER_PASSWORD_FILE (preferred), OOMPAH_SERVER_PASSWORD, "
            "or provide credentials in ~/.netrc."
        )

    # Reject netrc password paired with a CLI-overridden username (precedence conflict).
    # This catches cases where the CLI or env vars supply a different username
    # than what netrc would provide.
    if password_source == "netrc" and (username_override or os.environ.get("OOMPAH_SERVER_USERNAME", "").strip()):
        if (username_override and username_override.strip() != netrc_username) or \
           (not username_override and os.environ.get("OOMPAH_SERVER_USERNAME", "").strip() != netrc_username):
            raise CredentialError(
                "Credential conflict: netrc password cannot be used with a "
                "different username from CLI or OOMPAH_SERVER_USERNAME. "
                "Either provide both username and password from the same source, "
                "or remove the conflicting source."
            )

    assert resolved_password is not None  # guarded by checks above

    # Keep the resolved plaintext password behind the process-local redaction
    # boundary.  This is additive so a password rotation cannot make a late
    # CLI/server diagnostic expose the previous value.
    from oompah.secrets import register_secret

    register_secret(resolved_password)
    return ClientCredentials(username=username, password=resolved_password)


# ---------------------------------------------------------------------------
# Worker XDG_RUNTIME_DIR handling (OOMPAH-686)
# ---------------------------------------------------------------------------


def _is_xdg_runtime_dir_writable(xdg_runtime_dir: str | None) -> bool:
    """Check if XDG_RUNTIME_DIR is writable.

    When a worker's sandbox inherits a read-only /run/user/<uid> directory
    from the host, podman and other tools cannot configure themselves,
    failing with "chmod: read-only file system" errors. This function
    detects that condition.

    Args:
        xdg_runtime_dir: Path to check, typically from $XDG_RUNTIME_DIR env var.
                        If None or empty, returns False (not writable).

    Returns:
        True if the directory exists and is writable by the current user,
        False otherwise (including when the path doesn't exist).
    """
    if not xdg_runtime_dir:
        return False

    try:
        # Check if directory exists and is writable
        if not os.path.isdir(xdg_runtime_dir):
            return False
        # Test actual write capability: some sandboxes report permissions
        # but prevent actual writes. Check with os.access() for safety.
        return os.access(xdg_runtime_dir, os.W_OK)
    except (OSError, TypeError):
        return False


def _create_worker_runtime_directory() -> str | None:
    """Create a private, temporary XDG_RUNTIME_DIR for a worker.

    When a worker's sandbox makes the inherited XDG_RUNTIME_DIR read-only,
    create a private temporary directory. The caller is responsible for
    cleanup after the worker exits.

    Security model:
    * Uses mkdtemp() with secure defaults (mode 0o700, single-use directory)
    * Caller must clean up the directory to prevent leaking temp space
    * No attempt to set sticky bit or other /run/user semantics; just
      a private directory for the worker's temporary state

    Returns:
        Path to the created temporary directory, or None if creation fails.
        The caller is responsible for removing this directory after the
        worker exits.
    """
    try:
        # Use $TMPDIR if available (often safer in container/sandbox contexts),
        # otherwise fall back to the system temp directory
        tmpdir_root = os.environ.get("TMPDIR")
        runtime_dir = tempfile.mkdtemp(
            prefix="oompah-worker-runtime-",
            dir=tmpdir_root,
        )
        logger.debug(
            "Created private worker runtime directory: %s "
            "(caller responsible for cleanup after worker exits)",
            runtime_dir,
        )
        return runtime_dir
    except OSError as exc:
        logger.warning(
            "Failed to create private worker runtime directory: %s; "
            "worker will attempt to use inherited XDG_RUNTIME_DIR",
            exc,
        )
        return None


def agent_environment(
    base_env: Mapping[str, str] | None = None,
    *,
    workspace_path: str | os.PathLike[str] | None = None,
    isolate_remote_write: bool = False,
    provider_auth_kind: str | None = None,
) -> dict[str, str]:
    """Return an environment safe to pass to an agent subprocess.

    The server may itself be started from a shell that exports client Basic
    auth variables for ``make`` or a CLI.  Copy the supplied environment and
    remove those client-only values before an agent process can inherit them.
    ``OOMPAH_SERVER_URL`` is intentionally retained because it is a locator,
    not a credential, and existing agent workflows may use it.  When a task
    workspace is supplied, runtime selectors from the service process are
    removed and replaced with a worktree-private venv path so dependency
    setup cannot rewrite the service environment.

    Direct epic-rebase workers additionally receive a clean, per-worker home
    and a strict environment allow-list.  This prevents inherited Git/SSH or
    forge credentials from becoming a remote-write route; it is not based on
    shell-command matching.

    Also handles read-only XDG_RUNTIME_DIR: if the inherited runtime directory
    is read-only or missing, creates a private temporary directory for the
    worker (OOMPAH-686). The caller is responsible for cleanup.

    Returns:
        Dictionary of environment variables safe to pass to subprocess.
    """
    source_environment = dict(os.environ if base_env is None else base_env)
    environment = dict(source_environment)
    if isolate_remote_write:
        environment = _isolated_remote_write_environment(source_environment)
        try:
            _bootstrap_isolated_provider_auth(
                environment,
                source_environment,
                provider_auth_kind,
            )
        except Exception:
            shutil.rmtree(environment.get("OOMPAH_WORKER_RUNTIME_DIR", ""), ignore_errors=True)
            raise
    for key in CLIENT_AUTH_ENV_VARS:
        environment.pop(key, None)
    for key in _WORKER_RUNTIME_SELECTOR_ENV_VARS:
        environment.pop(key, None)
    for key in _INHERITED_MAKE_CONTROL_ENV_VARS:
        environment.pop(key, None)
    if workspace_path is not None:
        environment[TASK_VENV_ENV] = task_venv_path(workspace_path)
        environment[SERVICE_CHECKOUT_ENV] = str(
            Path(__file__).resolve().parent.parent
        )
        environment[SERVICE_VENV_ENV] = str(Path(sys.prefix).resolve())
    environment[CLIENT_AUTH_DISABLED_ENV] = "1"

    # Handle read-only XDG_RUNTIME_DIR (OOMPAH-686): if inherited runtime dir
    # is read-only or missing, provide a private writable directory so the
    # worker's podman/container tools can configure themselves.
    xdg_runtime_dir = environment.get("XDG_RUNTIME_DIR", "").strip()
    if xdg_runtime_dir and not _is_xdg_runtime_dir_writable(xdg_runtime_dir):
        logger.info(
            "Inherited XDG_RUNTIME_DIR %r is read-only or inaccessible; "
            "creating private worker runtime directory (OOMPAH-686)",
            xdg_runtime_dir,
        )
        fallback_dir = _create_worker_runtime_directory()
        if fallback_dir:
            environment["XDG_RUNTIME_DIR"] = fallback_dir
            # Mark the environment so we know cleanup is needed
            environment["OOMPAH_WORKER_RUNTIME_DIR"] = fallback_dir
        else:
            # Creation failed; worker will have to proceed with read-only dir
            # and fail gracefully at runtime (caught by Makefile gate retries)
            logger.warning(
                "Could not create fallback XDG_RUNTIME_DIR; "
                "worker may fail if it needs writable runtime directory"
            )

    return environment


# ---------------------------------------------------------------------------
# 401 remediation helper
# ---------------------------------------------------------------------------


def format_auth_error(server_url: str) -> str:
    """Return a concise 401 remediation message safe to print or log.

    The message never includes credential values, Authorization header content,
    or the raw server URL (which might have leaked credentials from a
    misconfigured environment).

    Args:
        server_url: Sanitized server URL (already passed through
                    :func:`sanitize_server_url`).

    Returns:
        A multi-line string suitable for ``sys.exit()``.
    """
    return (
        "ERROR (401): Authentication required.\n"
        "Set OOMPAH_SERVER_USERNAME and OOMPAH_SERVER_PASSWORD_FILE (preferred)\n"
        "or OOMPAH_SERVER_PASSWORD to authenticate against the oompah server.\n"
        "Verify that the credentials match the server's htpasswd configuration."
    )
