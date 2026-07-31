"""HTTP Basic authentication via Apache htpasswd files.

This module provides secure credential loading and verification for optional
HTTP Basic authentication in Oompah. It parses Apache-style htpasswd files
and verifies supplied credentials with maintained password verification library.

Security Model:
  - Credentials are revalidated from a safely opened file on each verification
    so atomic ``rename(2)`` rotations take effect without a restart
  - A replacement is parsed completely before its verifier becomes visible;
    malformed, missing, or unsafe replacements retain the last known-good map
  - Plaintext passwords are rejected (bcrypt/APR1 only)
  - Invalid credentials fail with a generic message (no user/password distinction)
  - Verification uses passlib for constant-time comparison
  - No credentials, passwords, or Authorization headers are logged

Supported Hash Formats:
  - bcrypt ($2y$, $2b$, $2a$): Recommended, modern, adaptive cost
  - APR1 ($apr1$): Common in Apache htpasswd, supported for compatibility

Unsupported/Rejected:
  - Plaintext (no prefix)
  - SHA ($sha$)
  - MD5 ($1$) - non-password contexts
  - Crypt variants
  - Custom/unknown prefixes

Dependencies:
  - passlib: Installed as server extra, not required for standalone CLI
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import stat
import threading
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Mapping

logger = logging.getLogger(__name__)


# htpasswd files are intentionally small.  Bounding a reload prevents a file
# replacement from turning every authenticated request into an unbounded read.
_MAX_HTPASSWD_BYTES = 1024 * 1024
_BCRYPT_HASH_RE = re.compile(r"^\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}$")
_APR1_HASH_RE = re.compile(r"^\$apr1\$[./A-Za-z0-9]{1,8}\$[./A-Za-z0-9]{22}$")


class AuthError(Exception):
    """Raised on authentication system failures (missing file, parsing errors)."""

    pass


class VerificationError(Exception):
    """Raised when credential verification fails (invalid user/password).

    This is a distinct exception type used to signal failed verification
    so callers can return appropriate HTTP 401 responses. It does NOT
    contain credential details that would leak authentication state.
    """

    pass


@dataclass
class HtpasswdCredentials:
    """Container for parsed htpasswd credentials.

    Attributes:
        enabled: True if a valid htpasswd file was found and loaded.
        verifier: Callable that verifies (username, password) pairs.
                 Raises VerificationError on failure.
        htpasswd_path: Absolute path to the loaded htpasswd file, or None.
    """

    enabled: bool
    verifier: Callable[[str, str], None] | None = None
    htpasswd_path: str | None = None
    _reloader: "_HtpasswdReloader | None" = field(default=None, repr=False)

    def reload_status(self) -> dict[str, object]:
        """Return a redacted credential-reload status for authenticated clients.

        The response deliberately excludes paths, file identities, usernames,
        hashes, parse details, and timestamps.  Those details can disclose
        deployment layout or credential state and are not needed by operators
        deciding whether a rotation was accepted.
        """
        if self._reloader is not None:
            return self._reloader.status()
        return {
            "enabled": bool(self.enabled),
            "reload": {
                "state": "static",
                "generation": 0,
                "retaining_last_known_good": False,
            },
        }


@dataclass(frozen=True)
class _FileFingerprint:
    """Opaque identity for one complete htpasswd file observation."""

    device: int
    inode: int
    mtime_ns: int
    ctime_ns: int
    size: int
    digest: bytes


@dataclass(frozen=True)
class _HtpasswdSnapshot:
    """A complete, parsed credential map and the file observation that made it."""

    credentials: Mapping[str, str]
    fingerprint: _FileFingerprint


def _verify_password(hashed_password: str, supplied_password: str) -> bool:
    """Verify a password against a hashed value using passlib.

    Supports bcrypt ($2y$, $2b$, $2a$) and APR1 ($apr1$) hashes.

    Args:
        hashed_password: The hashed password string from htpasswd
        supplied_password: The plaintext password to verify

    Returns:
        True if passwords match, False otherwise.
        Verification uses constant-time comparison.
    """
    try:
        from passlib.context import CryptContext

        # passlib's HtpasswdFile and CryptContext handle APR1 and bcrypt
        # with constant-time verification internally.
        # We use verify_password() which returns True/False (constant-time).

        # Check for bcrypt ($2y$, $2b$, $2a$)
        if hashed_password.startswith(("$2y$", "$2b$", "$2a$")):
            # Use bcrypt scheme
            ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            return ctx.verify(supplied_password, hashed_password)

        # Check for APR1 ($apr1$)
        elif hashed_password.startswith("$apr1$"):
            # APR1 scheme via passlib
            ctx = CryptContext(schemes=["apr_md5_crypt"], deprecated="auto")
            return ctx.verify(supplied_password, hashed_password)

        # Should not reach here if _load_htpasswd_file validated correctly
        return False

    except Exception:  # noqa: BLE001
        # passlib not installed, invalid hash, invalid UTF-8, etc.
        # Fail safely (wrong password) rather than crashing
        logger.debug("Password verification failed (exception)", exc_info=True)
        return False


def _constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Args:
        a: First string
        b: Second string

    Returns:
        True if strings are equal, False otherwise.
        Timing does not depend on string contents.
    """
    # Avoid early-exit path comparisons by always comparing all bytes
    a_bytes = a.encode("utf-8")
    b_bytes = b.encode("utf-8")

    # Use hashlib for guaranteed constant-time comparison
    a_digest = hashlib.sha256(a_bytes).digest()
    b_digest = hashlib.sha256(b_bytes).digest()

    # XOR all bytes then check if result is zero
    return all(x == y for x, y in zip(a_digest, b_digest))


def _same_file_observation(left: os.stat_result, right: os.stat_result) -> bool:
    """Return whether two stat results identify the same unchanged regular file."""
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def _lstat_regular_htpasswd(path: str) -> os.stat_result:
    """Validate *path* without following a symlink and return its metadata."""
    try:
        observed = os.lstat(path)
    except FileNotFoundError:
        raise AuthError(f"htpasswd file not found: {path}") from None
    except (OSError, ValueError) as exc:
        raise AuthError(f"Failed to inspect htpasswd file: {exc}") from exc

    if stat.S_ISLNK(observed.st_mode):
        raise AuthError(f"htpasswd file must not be a symbolic link: {path}")
    if not stat.S_ISREG(observed.st_mode):
        raise AuthError(f"htpasswd file is not a regular file: {path}")
    if not observed.st_mode & (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH):
        raise AuthError(f"htpasswd file not readable: {path}")
    return observed


def _read_htpasswd_file(path: str) -> tuple[str, _FileFingerprint]:
    """Return a complete stable read of *path* without following symlinks.

    ``lstat`` before opening, ``O_NOFOLLOW`` where available, and metadata
    checks before and after reading close the normal symlink/rename race.  A
    replacement that races this read is rejected and the caller retains its
    last known-good verifier instead of consuming a partial or redirected file.
    """
    before = _lstat_regular_htpasswd(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except PermissionError:
        raise AuthError(f"htpasswd file not readable: {path}") from None
    except (OSError, ValueError) as exc:
        raise AuthError(f"Failed to open htpasswd file: {exc}") from exc

    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise AuthError(f"htpasswd file is not a regular file: {path}")
        if not _same_file_observation(before, opened):
            raise AuthError(f"htpasswd file changed while opening: {path}")

        content = bytearray()
        while len(content) <= _MAX_HTPASSWD_BYTES:
            chunk = os.read(fd, min(64 * 1024, _MAX_HTPASSWD_BYTES + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        if len(content) > _MAX_HTPASSWD_BYTES:
            raise AuthError(f"htpasswd file exceeds maximum size: {path}")

        after = os.fstat(fd)
        if not _same_file_observation(opened, after):
            raise AuthError(f"htpasswd file changed while reading: {path}")
    except OSError as exc:
        raise AuthError(f"Failed to read htpasswd file: {exc}") from exc
    finally:
        try:
            os.close(fd)
        except OSError:
            pass

    # Confirm the path still resolves to the file we completely read.  This
    # detects an atomic rename that happened after the descriptor was opened.
    current = _lstat_regular_htpasswd(path)
    if not _same_file_observation(after, current):
        raise AuthError(f"htpasswd file changed while reading: {path}")

    try:
        text = bytes(content).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuthError(f"htpasswd file is not valid UTF-8: {path}") from exc

    return text, _FileFingerprint(
        device=after.st_dev,
        inode=after.st_ino,
        mtime_ns=after.st_mtime_ns,
        ctime_ns=after.st_ctime_ns,
        size=after.st_size,
        digest=hashlib.blake2b(content, digest_size=16).digest(),
    )


def _parse_htpasswd_text(text: str, path: str) -> dict[str, str]:
    """Validate a complete Apache-style htpasswd file body."""
    if not text:
        raise AuthError(f"htpasswd file is empty: {path}")

    credentials: dict[str, str] = {}
    for line_no, line in enumerate(text.splitlines(), start=1):
        # Skip comments and blank lines.  Leading whitespace is significant in
        # an entry and is stripped below only to retain existing compatibility.
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise AuthError(
                f"htpasswd file {path}:{line_no}: missing ':' delimiter"
            )

        username, hashed_password = line.split(":", 1)
        username = username.strip()
        hashed_password = hashed_password.strip()

        if not username:
            raise AuthError(
                f"htpasswd file {path}:{line_no}: empty username"
            )
        if any(char in username for char in "\x00\r\n:"):
            raise AuthError(
                f"htpasswd file {path}:{line_no}: invalid username"
            )
        if not hashed_password:
            raise AuthError(
                f"htpasswd file {path}:{line_no}: empty password hash"
            )
        if not hashed_password.startswith("$"):
            raise AuthError(
                f"htpasswd file {path}:{line_no}: plaintext password "
                "(rejected; use bcrypt or APR1)"
            )

        if hashed_password.startswith(("$2y$", "$2b$", "$2a$")):
            valid_hash = bool(_BCRYPT_HASH_RE.fullmatch(hashed_password))
            if valid_hash:
                # bcrypt accepts work factors 04 through 31 only.  Loading an
                # impossible value would otherwise publish a verifier that
                # rejects every password after the next rotation.
                valid_hash = 4 <= int(hashed_password[4:6]) <= 31
        elif hashed_password.startswith("$apr1$"):
            valid_hash = bool(_APR1_HASH_RE.fullmatch(hashed_password))
        else:
            algo = hashed_password.split("$")[1] if "$" in hashed_password else "unknown"
            raise AuthError(
                f"htpasswd file {path}:{line_no}: unsupported password "
                f"algorithm: {algo} (supported: bcrypt, APR1)"
            )

        if not valid_hash:
            raise AuthError(
                f"htpasswd file {path}:{line_no}: malformed password hash"
            )
        if username in credentials:
            raise AuthError(
                f"htpasswd file {path}:{line_no}: duplicate username"
            )
        credentials[username] = hashed_password

    if not credentials:
        raise AuthError(f"htpasswd file has no valid entries: {path}")
    return credentials


def _load_htpasswd_snapshot(path: str) -> _HtpasswdSnapshot:
    """Read and parse one stable htpasswd snapshot."""
    text, fingerprint = _read_htpasswd_file(path)
    credentials = MappingProxyType(_parse_htpasswd_text(text, path))
    return _HtpasswdSnapshot(credentials=credentials, fingerprint=fingerprint)


def _load_htpasswd_file(path: str) -> dict[str, str]:
    """Load and parse an Apache-style htpasswd file.

    This compatibility helper returns a copy of a securely read snapshot.
    Reloading code uses :func:`_load_htpasswd_snapshot` directly so the map
    and its identity are updated together.
    """
    return dict(_load_htpasswd_snapshot(path).credentials)


class _HtpasswdReloader:
    """Atomically publish complete, safe htpasswd replacements.

    The normal request path reads a bounded file snapshot and compares its
    identity plus content digest.  It then either keeps the immutable current
    map or swaps in a fully validated replacement while holding a short lock.
    Requests already verifying with an earlier map complete safely; no request
    can observe a partially rebuilt dictionary.
    """

    def __init__(self, path: str, initial: _HtpasswdSnapshot) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._reload_lock = threading.Lock()
        self._credentials = initial.credentials
        self._fingerprint = initial.fingerprint
        self._generation = 1
        self._reload_state = "ready"
        self._retaining_last_known_good = False
        self._failed_fingerprint: _FileFingerprint | None = None
        self._reported_unreadable_failure = False

    def verify(self, username: str, password: str) -> None:
        """Reload if needed, then verify against one immutable credential map."""
        self._reload_if_changed()
        with self._lock:
            credentials = self._credentials

        # Verify a real hash even for an unknown username.  The result remains
        # a generic failure, but the expensive password-hash path avoids an
        # easy username-enumeration timing oracle.
        hashed_password = credentials.get(username)
        candidate_hash = hashed_password or next(iter(credentials.values()))
        password_matches = _verify_password(candidate_hash, password)
        if hashed_password is None or not password_matches:
            raise VerificationError("Invalid credentials")

    def _reload_if_changed(self) -> None:
        """Attempt a replacement reload, preserving the last good map on error."""
        # One reload attempt at a time prevents concurrent requests from each
        # parsing the same replacement.  The state lock remains available to
        # password verifications while bounded file I/O is in progress.
        with self._reload_lock:
            try:
                text, fingerprint = _read_htpasswd_file(self._path)
            except AuthError:
                with self._lock:
                    self._record_unreadable_failure_locked()
                return

            with self._lock:
                if fingerprint == self._fingerprint:
                    return
                if fingerprint == self._failed_fingerprint:
                    return

            try:
                credentials = MappingProxyType(_parse_htpasswd_text(text, self._path))
            except AuthError:
                with self._lock:
                    self._failed_fingerprint = fingerprint
                    self._record_unreadable_failure_locked()
                return

            # Parsing completed before publication.  Assigning an immutable
            # mapping is atomic for readers that already copied the old map.
            with self._lock:
                self._credentials = credentials
                self._fingerprint = fingerprint
                self._generation += 1
                self._reload_state = "reloaded"
                self._retaining_last_known_good = False
                self._failed_fingerprint = None
                self._reported_unreadable_failure = False
        logger.info("HTTP Basic auth credentials reloaded")

    def _record_unreadable_failure_locked(self) -> None:
        """Record a generic failure without leaking filesystem or hash details."""
        self._reload_state = "reload_rejected"
        self._retaining_last_known_good = True
        if not self._reported_unreadable_failure:
            logger.warning(
                "HTTP Basic auth credential reload rejected; retaining last-known-good credentials"
            )
            self._reported_unreadable_failure = True

    def status(self) -> dict[str, object]:
        """Return status that is safe to include in an authenticated API response."""
        with self._lock:
            return {
                "enabled": True,
                "reload": {
                    "state": self._reload_state,
                    "generation": self._generation,
                    "retaining_last_known_good": self._retaining_last_known_good,
                },
            }


def _path_exists_without_following_symlinks(path: str) -> bool:
    """Return whether *path* exists, rejecting links and non-regular entries."""
    try:
        observed = os.lstat(path)
    except FileNotFoundError:
        return False
    except (OSError, ValueError) as exc:
        raise AuthError(f"Failed to inspect htpasswd file: {exc}") from exc
    if stat.S_ISLNK(observed.st_mode):
        raise AuthError(f"htpasswd file must not be a symbolic link: {path}")
    if not stat.S_ISREG(observed.st_mode):
        raise AuthError(f"htpasswd file is not a regular file: {path}")
    return True


def load_credentials(htpasswd_path: str | None, env_file_dir: str) -> HtpasswdCredentials:
    """Load optional htpasswd credentials with safe path resolution.

    Path Resolution:
      - None or empty: Try discovery (default .htpasswd beside env file)
      - Relative path: Resolve against env_file_dir
      - Absolute path: Use as-is (for container secrets)
      - Missing discovered file: Return disabled (not an error)
      - Explicit configured missing file: Raise fatal error
      - Unreadable/malformed/empty: Raise fatal error (fail-closed)

    Args:
        htpasswd_path: Override path from OOMPAH_HTPASSWD_FILE, or None
        env_file_dir: Directory of the selected .env file (for relative path resolution)

    Returns:
        HtpasswdCredentials with enabled=False if auth is disabled,
        enabled=True with a verifier callable if valid credentials loaded.

    Raises:
        AuthError: On explicit configuration, unreadable file, or invalid content
    """
    # Determine which path to use
    resolved_path: str | None = None

    if htpasswd_path:
        # Explicit override: must be valid
        if os.path.isabs(htpasswd_path):
            resolved_path = htpasswd_path
        else:
            # Relative: resolve against env_file_dir
            resolved_path = os.path.normpath(
                os.path.join(env_file_dir, htpasswd_path)
            )

        # Explicit configuration means file is required to exist and be valid
        if not _path_exists_without_following_symlinks(resolved_path):
            raise AuthError(
                f"Configured OOMPAH_HTPASSWD_FILE not found: {resolved_path}"
            )
    else:
        # Discovery: try default .htpasswd beside env file
        default_path = os.path.join(env_file_dir, ".htpasswd")
        if _path_exists_without_following_symlinks(default_path):
            resolved_path = default_path
        else:
            # Default file absent = auth disabled (not an error)
            logger.debug(
                "No .htpasswd found beside env file; HTTP Basic auth disabled"
            )
            return HtpasswdCredentials(enabled=False)

    # Load the file (may raise AuthError)
    if resolved_path is None:
        # Should not happen, but handle gracefully
        return HtpasswdCredentials(enabled=False)

    snapshot = _load_htpasswd_snapshot(resolved_path)
    reloader = _HtpasswdReloader(resolved_path, snapshot)

    logger.info("Loaded HTTP Basic auth credentials from: %s", resolved_path)
    return HtpasswdCredentials(
        enabled=True,
        verifier=reloader.verify,
        htpasswd_path=resolved_path,
        _reloader=reloader,
    )
