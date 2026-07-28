"""HTTP Basic authentication via Apache htpasswd files.

This module provides secure credential loading and verification for optional
HTTP Basic authentication in Oompah. It parses Apache-style htpasswd files
and verifies supplied credentials with maintained password verification library.

Security Model:
  - Credentials are loaded at startup; restarts required for changes
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
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


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
        from passlib.apache import HtpasswdFile
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


def _load_htpasswd_file(path: str) -> dict[str, str]:
    """Load and parse an Apache-style htpasswd file.

    Format (one entry per line):
        username:hashed_password

    Security:
      - Rejects plaintext passwords (no $ prefix = no algorithm)
      - Rejects unsupported hash types (SHA, MD5 crypt, etc.)
      - Fails on malformed lines (no colon, empty fields)
      - Fails on empty file (no credentials = not a valid htpasswd)

    Args:
        path: Absolute path to htpasswd file

    Returns:
        Dictionary mapping usernames to hashed passwords

    Raises:
        AuthError: On file read failures, parsing errors, or invalid content
    """
    if not os.path.isfile(path):
        raise AuthError(f"htpasswd file not found: {path}")

    if not os.access(path, os.R_OK):
        raise AuthError(f"htpasswd file not readable: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as exc:
        raise AuthError(f"Failed to read htpasswd file: {exc}")

    if not lines:
        raise AuthError(f"htpasswd file is empty: {path}")

    credentials: dict[str, str] = {}
    line_no = 0

    for line_no, line in enumerate(lines, start=1):
        # Strip trailing newline/whitespace
        line = line.rstrip("\n").rstrip("\r")

        # Skip comments and blank lines
        if not line or line.startswith("#"):
            continue

        # Each line must be username:password_hash
        if ":" not in line:
            raise AuthError(
                f"htpasswd file {path}:{line_no}: missing ':' delimiter"
            )

        parts = line.split(":", 1)
        if len(parts) != 2:
            raise AuthError(
                f"htpasswd file {path}:{line_no}: invalid format"
            )

        username, hashed_password = parts
        username = username.strip()
        hashed_password = hashed_password.strip()

        if not username:
            raise AuthError(
                f"htpasswd file {path}:{line_no}: empty username"
            )

        if not hashed_password:
            raise AuthError(
                f"htpasswd file {path}:{line_no}: empty password hash"
            )

        # Reject plaintext passwords (must have $ prefix for algorithm marker)
        if not hashed_password.startswith("$"):
            raise AuthError(
                f"htpasswd file {path}:{line_no}: plaintext password "
                "(rejected; use bcrypt or APR1)"
            )

        # Reject unsupported hash types early
        # Supported: $2y$, $2b$, $2a$ (bcrypt), $apr1$ (APR1)
        if not (
            hashed_password.startswith("$2y$")
            or hashed_password.startswith("$2b$")
            or hashed_password.startswith("$2a$")
            or hashed_password.startswith("$apr1$")
        ):
            algo = hashed_password.split("$")[1] if "$" in hashed_password else "unknown"
            raise AuthError(
                f"htpasswd file {path}:{line_no}: unsupported password "
                f"algorithm: {algo} (supported: bcrypt, APR1)"
            )

        credentials[username] = hashed_password

    # Require at least one valid entry
    if not credentials:
        raise AuthError(f"htpasswd file has no valid entries: {path}")

    return credentials


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
        if not os.path.isfile(resolved_path):
            raise AuthError(
                f"Configured OOMPAH_HTPASSWD_FILE not found: {resolved_path}"
            )
    else:
        # Discovery: try default .htpasswd beside env file
        default_path = os.path.join(env_file_dir, ".htpasswd")
        if os.path.isfile(default_path):
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

    try:
        credentials_dict = _load_htpasswd_file(resolved_path)
    except AuthError:
        raise  # Re-raise with original message

    # Create the verifier callable
    def verify_credentials(username: str, password: str) -> None:
        """Verify username and password against loaded credentials.

        Args:
            username: Username to verify
            password: Password to verify

        Raises:
            VerificationError: If credentials don't match (no details leaked)
        """
        supplied_password_valid = False

        # Check username exists and verify password
        if username in credentials_dict:
            hashed_password = credentials_dict[username]
            # Use passlib for constant-time verification
            supplied_password_valid = _verify_password(hashed_password, password)

        # Return same error for unknown user and wrong password
        # (Prevent user enumeration attacks)
        if not supplied_password_valid:
            raise VerificationError("Invalid credentials")

    logger.info("Loaded HTTP Basic auth credentials from: %s", resolved_path)
    return HtpasswdCredentials(
        enabled=True,
        verifier=verify_credentials,
        htpasswd_path=resolved_path,
    )
