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

import logging
import os
import stat
import urllib.parse
from typing import NamedTuple

logger = logging.getLogger(__name__)

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
        fd = os.open(path, os.O_RDONLY)
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
    if not url:
        return url

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        # Unparseable URL — let the HTTP client report the error.
        return url.rstrip("/")

    if parsed.username or parsed.password:
        # Build a redacted URL for the error message: strip userinfo entirely.
        netloc_redacted = parsed.hostname or ""
        if parsed.port:
            netloc_redacted += f":{parsed.port}"
        redacted = urllib.parse.urlunparse((
            parsed.scheme,
            netloc_redacted,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))
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
) -> ClientCredentials | None:
    """Resolve client Basic-auth credentials from environment and/or overrides.

    Source priority
    ~~~~~~~~~~~~~~~
    username:  CLI ``--username`` > ``OOMPAH_SERVER_USERNAME`` env var
    password:  CLI ``--password-file`` > ``OOMPAH_SERVER_PASSWORD_FILE`` env var
               OR ``OOMPAH_SERVER_PASSWORD`` env var
               (exactly one must be provided when a username is configured)

    Returns:
        :class:`ClientCredentials` ``(username, password)`` when credentials
        are configured, or ``None`` when no credential source is set (for
        backward-compatible unauthenticated operation).

    Raises:
        :exc:`CredentialError`: On inconsistent (both password sources),
            incomplete (username without password or vice versa), unreadable,
            empty, or unsafe credential configuration.
    """
    username: str = (
        username_override
        or os.environ.get("OOMPAH_SERVER_USERNAME", "")
    ).strip()

    password_file: str | None = (
        password_file_override
        or os.environ.get("OOMPAH_SERVER_PASSWORD_FILE", "")
    ).strip() or None

    password_env: str | None = (
        os.environ.get("OOMPAH_SERVER_PASSWORD", "")
    ).strip() or None

    # Nothing configured at all → unauthenticated (backward-compatible).
    if not username and not password_file and not password_env:
        return None

    # Username required when any password source is set.
    if not username and (password_file or password_env):
        raise CredentialError(
            "OOMPAH_SERVER_USERNAME is required when "
            "OOMPAH_SERVER_PASSWORD or OOMPAH_SERVER_PASSWORD_FILE is set."
        )

    # Password source required when username is set.
    if username and not password_file and not password_env:
        raise CredentialError(
            "A password source is required when OOMPAH_SERVER_USERNAME is set. "
            "Set OOMPAH_SERVER_PASSWORD_FILE (preferred) or OOMPAH_SERVER_PASSWORD."
        )

    # Mutual exclusion: exactly one password source.
    if password_file and password_env:
        raise CredentialError(
            "Set exactly one of OOMPAH_SERVER_PASSWORD or OOMPAH_SERVER_PASSWORD_FILE, "
            "not both. Prefer OOMPAH_SERVER_PASSWORD_FILE for unattended use."
        )

    # Resolve the password.
    if password_file:
        password = _read_password_file(password_file)
    else:
        assert password_env is not None  # guarded by mutual-exclusion checks above
        password = password_env

    return ClientCredentials(username=username, password=password)


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
