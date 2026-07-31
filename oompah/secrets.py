"""Centralized secret redaction for logs, events, and state.

This module provides recursive redaction of secrets from any data structure
(dicts, lists, strings, dataclasses) before persistence or exposure. It
handles:

- Plain-text passwords and tokens in dicts/lists
- Authorization headers (Bearer, Basic, etc.)
- URLs with embedded userinfo (http://user:pass@host)
- Environment variable assignments
- Credential dataclass instances
- Known configured secret values
- Stringified representations of any of the above

Usage::

    from oompah.secrets import redact_sensitive_data

    # Redact a dict containing passwords
    data = {"password": "secret123", "username": "alice"}
    clean = redact_sensitive_data(data)
    # clean: {"password": "[REDACTED]", "username": "alice"}

    # Redact nested structures
    nested = {"db": {"host": "localhost", "password": "xyz"}, "items": []}
    clean = redact_sensitive_data(nested)
    # Recursively redacts all secret fields

Design:

* **Recursive:** Walks dicts, lists, strings, dataclasses, and repr() forms.
* **Fail-closed:** Unknown-type objects are rendered via repr()/str() and
  scanned for secret patterns *before* being returned. The raw object is
  never returned — a downstream ``json.dumps(..., default=str)`` can only
  ever serialize text that has already passed the redaction pass. This
  closes a leak in earlier designs where an innocuously named object whose
  ``__str__``/``__repr__`` embedded a bearer token could bypass redaction
  entirely.
* **Pattern-based:** Uses regex + key-name heuristics to find secrets.
* **Configurable:** See ``SECRET_PATTERNS`` and ``SECRET_KEYS`` for customization.
* **Logging integration:** :class:`SecretRedactionFilter` +
  :func:`install_secret_redaction_filter` wire the same pattern set into
  Python ``logging`` so ``logger.warning("...: %s", url_with_userinfo)``
  cannot leak plaintext into service logs.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import re
import threading
import time
import traceback
from collections.abc import Iterable, Mapping
from typing import Any

logger = logging.getLogger(__name__)

# Marker used in place of actual secrets
_REDACTED = "[REDACTED]"

# Configured values are deliberately kept in a process-local registry.  A
# secret must be redacted even when it appears in an innocuous field such as
# ``detail`` and therefore has no useful key or textual marker around it.
# Values are never exposed by this module and registry updates never log the
# values.  The lock makes updates safe while agent workers and log handlers
# redact concurrently.
_KNOWN_SECRET_LOCK = threading.RLock()
_KNOWN_SECRET_STRINGS: dict[str, float | None] = {}
_KNOWN_SECRET_BYTES: dict[bytes, float | None] = {}
# The registry is process-local and bounded.  Expiring values (such as task
# handoff capabilities) are removed on each snapshot; the cap is a final
# guard against an operator repeatedly rotating configured credentials.
_MAX_REGISTERED_SECRET_VALUES = 4096
_DEFAULT_DYNAMIC_SECRET_RETENTION_SECONDS = 60 * 60
# Literal registration is for opaque values in arbitrary text.  Very short
# values (common in unit-test provider fixtures and not useful as bearer/API
# credentials) would redact ordinary prose everywhere; credential-shaped
# fields remain protected by SECRET_KEYS regardless of this threshold.
_MIN_REGISTERED_SECRET_LENGTH = 8

# Environment sources which can contain plaintext credentials in a running
# oompah process.  Keep this allow-list explicit: registering every process
# environment value would cause unrelated configuration values to disappear
# from diagnostics and could turn a user-controlled value into a redaction
# denial of service.
_CONFIGURED_SECRET_ENV_NAMES = frozenset(
    {
        "OOMPAH_SERVER_PASSWORD",
        "OOMPAH_TASK_HANDOFF_TOKEN",
        "OOMPAH_GITHUB_TOKEN",
        "OOMPAH_GITLAB_TOKEN",
        "OOMPAH_GITLAB_SELF_MANAGED_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "GITLAB_TOKEN",
        "GITLAB_API_TOKEN",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AZURE_CLIENT_SECRET",
        "GOOGLE_APPLICATION_CREDENTIALS_JSON",
        "OOMPAH_CODEX_API_KEY",
        "OOMPAH_OPENCODE_API_KEY",
    }
)
_CONFIGURED_SECRET_FILE_ENV_NAMES = frozenset(
    {
        "OOMPAH_SERVER_PASSWORD_FILE",
        "OOMPAH_TASK_HANDOFF_TOKEN_FILE",
        "OOMPAH_GITHUB_TOKEN_FILE",
        "OOMPAH_GITLAB_TOKEN_FILE",
        "GITHUB_TOKEN_FILE",
        "GITLAB_TOKEN_FILE",
        "OPENAI_API_KEY_FILE",
        "ANTHROPIC_API_KEY_FILE",
        "OOMPAH_GITHUB_APP_PRIVATE_KEY_PATH",
    }
)
_CONFIGURED_SECRET_ENV_PATTERN = re.compile(
    r"(?:PASSWORD|PASSWD|TOKEN|SECRET|API[_-]?KEY|PRIVATE[_-]?KEY|ACCESS[_-]?KEY)(?:_|$)",
    re.IGNORECASE,
)


def _normalise_registered_secret(value: Any) -> tuple[str | None, bytes | None]:
    """Return a safe registry representation without logging *value*.

    Secret values are expected to be text, but accepting bytes covers callers
    that read a credential file in binary mode.  Empty and whitespace-only
    values are ignored because registering them would redact every string.
    """
    if isinstance(value, bytes):
        if len(value) < _MIN_REGISTERED_SECRET_LENGTH or not value.strip():
            return None, None
        try:
            decoded = value.decode("utf-8")
        except UnicodeDecodeError:
            return None, value
        if len(decoded) < _MIN_REGISTERED_SECRET_LENGTH or not decoded.strip():
            return None, None
        return decoded, value
    if isinstance(value, str):
        if len(value) < _MIN_REGISTERED_SECRET_LENGTH or not value.strip():
            return None, None
        return value, None
    return None, None


def _store_registered_secret_locked(
    registry: dict[Any, float | None],
    value: Any,
    expires_at: float | None,
) -> None:
    """Store one value and evict the oldest expiring values if over the cap."""
    if value not in registry:
        registry[value] = expires_at
    else:
        current_expiry = registry[value]
        # A permanent registration must never be downgraded by a later
        # short-lived registration of the same value.
        if current_expiry is not None and (
            expires_at is None or expires_at > current_expiry
        ):
            registry[value] = expires_at

    total = len(_KNOWN_SECRET_STRINGS) + len(_KNOWN_SECRET_BYTES)
    while total > _MAX_REGISTERED_SECRET_VALUES:
        # Prefer evicting a retired/expiring value.  Permanent configured
        # values are retained unless the bounded cap is exhausted entirely by
        # permanent rotations.
        expiring = [
            (expiry, key)
            for key, expiry in _KNOWN_SECRET_STRINGS.items()
            if expiry is not None
        ] + [
            (expiry, key)
            for key, expiry in _KNOWN_SECRET_BYTES.items()
            if expiry is not None
        ]
        if expiring:
            _, evict_key = min(expiring, key=lambda item: item[0])
            if evict_key in _KNOWN_SECRET_STRINGS:
                _KNOWN_SECRET_STRINGS.pop(evict_key, None)
            else:
                _KNOWN_SECRET_BYTES.pop(evict_key, None)
        elif _KNOWN_SECRET_STRINGS:
            _KNOWN_SECRET_STRINGS.pop(next(iter(_KNOWN_SECRET_STRINGS)))
        elif _KNOWN_SECRET_BYTES:
            _KNOWN_SECRET_BYTES.pop(next(iter(_KNOWN_SECRET_BYTES)))
        total = len(_KNOWN_SECRET_STRINGS) + len(_KNOWN_SECRET_BYTES)


def _prune_registered_secrets_locked(now: float) -> None:
    """Remove expired dynamic values without exposing their contents."""
    for registry in (_KNOWN_SECRET_STRINGS, _KNOWN_SECRET_BYTES):
        expired = [
            value for value, expires_at in registry.items()
            if expires_at is not None and expires_at <= now
        ]
        for value in expired:
            registry.pop(value, None)


def register_secret(
    value: str | bytes | None,
    *,
    expires_in: float | None = None,
) -> None:
    """Register one configured secret for literal redaction.

    Registration is additive. Permanent configured values are retained for
    the process lifetime; short-lived values may supply ``expires_in`` so a
    bounded grace period protects delayed workers, retries, and shutdown
    paths without retaining every historical capability forever. The
    function never logs or returns the value.
    """
    text_value, bytes_value = _normalise_registered_secret(value)
    if text_value is None and bytes_value is None:
        return
    expires_at = (
        None
        if expires_in is None
        else time.monotonic() + max(float(expires_in), 0.0)
    )
    with _KNOWN_SECRET_LOCK:
        _prune_registered_secrets_locked(time.monotonic())
        if text_value is not None:
            _store_registered_secret_locked(
                _KNOWN_SECRET_STRINGS, text_value, expires_at
            )
        if bytes_value is not None:
            _store_registered_secret_locked(
                _KNOWN_SECRET_BYTES, bytes_value, expires_at
            )


def register_secret_values(
    values: Iterable[str | bytes | None],
    *,
    expires_in: float | None = None,
) -> None:
    """Atomically register a batch of configured secret values.

    The values are consumed without producing diagnostics.  Individual
    registration is lock-safe; taking one lock for the batch also prevents a
    redaction call from observing a partially applied startup/rotation set.
    """
    normalised = [_normalise_registered_secret(value) for value in values]
    expires_at = (
        None
        if expires_in is None
        else time.monotonic() + max(float(expires_in), 0.0)
    )
    with _KNOWN_SECRET_LOCK:
        _prune_registered_secrets_locked(time.monotonic())
        for text_value, bytes_value in normalised:
            if text_value is not None:
                _store_registered_secret_locked(
                    _KNOWN_SECRET_STRINGS, text_value, expires_at
                )
            if bytes_value is not None:
                _store_registered_secret_locked(
                    _KNOWN_SECRET_BYTES, bytes_value, expires_at
                )


def clear_registered_secrets() -> None:
    """Clear the process-local registry.

    This is primarily useful for isolated test processes.  Production code
    should use additive registration so a rotation cannot make an old value
    visible to a late log/event writer.
    """
    with _KNOWN_SECRET_LOCK:
        _KNOWN_SECRET_STRINGS.clear()
        _KNOWN_SECRET_BYTES.clear()


def registered_secret_count() -> int:
    """Return registry size without exposing any registered value."""
    with _KNOWN_SECRET_LOCK:
        _prune_registered_secrets_locked(time.monotonic())
        return len(_KNOWN_SECRET_STRINGS) + len(_KNOWN_SECRET_BYTES)


def _registered_secret_snapshot() -> tuple[tuple[str, ...], tuple[bytes, ...]]:
    """Return longest-first literal replacement values under the lock."""
    with _KNOWN_SECRET_LOCK:
        _prune_registered_secrets_locked(time.monotonic())
        strings = tuple(sorted(_KNOWN_SECRET_STRINGS, key=len, reverse=True))
        byte_values = tuple(sorted(_KNOWN_SECRET_BYTES, key=len, reverse=True))
    return strings, byte_values


def register_configured_secrets(
    environment: Mapping[str, str] | None = None,
) -> None:
    """Register plaintext credentials from configured env/file sources.

    This startup hook intentionally reads only the explicit credential source
    names above.  Missing/unreadable files are ignored without logging their
    paths or contents; the authoritative credential loader remains responsible
    for reporting configuration errors.  A file path itself is never
    registered as a secret.
    """
    env = os.environ if environment is None else environment
    values: list[str] = []
    dynamic_values: list[str] = []
    for name, raw_value in env.items():
        upper_name = str(name).upper()
        if upper_name in _CONFIGURED_SECRET_FILE_ENV_NAMES or (
            upper_name.endswith("_FILE")
            and _CONFIGURED_SECRET_ENV_PATTERN.search(upper_name[:-5])
        ):
            path = raw_value
            if not path:
                continue
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    value = handle.read().strip()
            except (OSError, UnicodeError, TypeError, ValueError):
                continue
            if value:
                if upper_name == "OOMPAH_TASK_HANDOFF_TOKEN_FILE":
                    dynamic_values.append(value)
                else:
                    values.append(value)
        elif upper_name in _CONFIGURED_SECRET_ENV_NAMES or (
            _CONFIGURED_SECRET_ENV_PATTERN.search(upper_name) is not None
        ):
            if raw_value:
                if upper_name == "OOMPAH_TASK_HANDOFF_TOKEN":
                    dynamic_values.append(raw_value)
                else:
                    values.append(raw_value)
    register_secret_values(values)
    register_secret_values(
        dynamic_values,
        expires_in=_DEFAULT_DYNAMIC_SECRET_RETENTION_SECONDS,
    )

# Keys that likely contain secrets (case-insensitive)
SECRET_KEYS = frozenset({
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "auth_token",
    "authtoken",
    "auth-token",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
    "bearer",
    "bearer_token",
    "bearertoken",
    "bearer-token",
    "oauth_token",
    "oauthtoken",
    "oauth-token",
    "private_key",
    "privatekey",
    "private-key",
    "ssh_key",
    "sshkey",
    "ssh-key",
    "api_secret",
    "apisecret",
    "api-secret",
    "client_secret",
    "clientsecret",
    "client-secret",
    "client_credentials",
    "clientcredentials",
    "client-credentials",

    "session_key",
    "sessionkey",
    "session-key",
    "session_token",
    "sessiontoken",
    "session-token",
    "auth",
    "x-api-key",
    "x-auth-token",
    "x-access-token",
    "authorization",
    "authorization_header",
    "authorizationheader",
    "authorization-header",
    "task_handoff",
    "taskhandoff",
    "task-handoff",
    "task_handoff_token",
    "taskhandofftoken",
    "task-handoff-token",
    "oompah_server_password",
    "oompah_server_username",
})

# Regex patterns that identify secrets in text
# Each tuple is (pattern, replacement)
SECRET_PATTERNS = [
    # URLs with embedded userinfo (any scheme): http://user:pass@host, postgresql://user:pass@host, etc.
    # Redact everything between :// and @ to handle both user and password
    (r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^@\s/]+(?::[^@\s/]+)?)(@)", r"\1[REDACTED]\3"),
    # Bearer tokens: Bearer xxxxx (with optional padding)
    (r"(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)", r"\1[REDACTED]"),
    # API keys: with = or : as separator (both query strings and config files)
    (r"((?:\?|&)?api[_-]?key)\s*(?:=|:)\s*([^\s&\"\';,]+)", r"\1=[REDACTED]", re.IGNORECASE),
    # Authorization/X-* headers with any scheme
    (r"((?:Authorization|X-API-Key|X-Auth-Token|X-Access-Token)\s*:\s*)([^\s]+)", r"\1[REDACTED]", re.IGNORECASE),
    # Common password/token patterns with various delimiters
    # Matches: password=xxx, password: xxx, password was 'xxx', token: xxx, --password xxx, etc.
    # Note: character class excludes & to respect query string delimiters
    (r"((?:--)?(?:password|passwd|pwd|token|api[_-]?key|secret|bearer)\s*(?:=|:|was|is)?\s*)['\"]?([a-zA-Z0-9\-._~+/!@#$%^*=\[\]{}]+)['\"]?", r"\1[REDACTED]", re.IGNORECASE),
]


def _is_secret_key(key: Any) -> bool:
    """Check if a key name suggests the value is a secret.
    
    Uses exact match, plus selective substring matches for patterns that are
    unlikely to match innocent keys (e.g., "password_reset" yes, "input_tokens" no).
    """
    if not isinstance(key, str):
        return False
    key_lower = key.lower()
    # Direct match against known secret keys
    if key_lower in SECRET_KEYS:
        return True
    # Selective substring matches only for specific multi-word patterns
    # to avoid false positives like "input_tokens" matching "token"
    substring_patterns = (
        "password",  # matches: password_reset, password_hash, etc.
        "secret",    # matches: api_secret, client_secret, etc.
        "api_key",   # matches: app_api_key, etc.
        "bearer",    # matches: bearer_token (already exact), but be conservative
        "private_key",  # matches: rsa_private_key, etc.
        "ssh_key",   # matches: ssh_key_file, etc.
        "client_credentials",  # matches variants
    )
    for pattern in substring_patterns:
        if pattern in key_lower:
            return True
    return False


def _redact_string(value: str) -> str:
    """Apply regex patterns to redact secrets within a string."""
    if not isinstance(value, str) or len(value) == 0:
        return value

    # Literal replacement runs before the heuristic fast path.  Configured
    # credentials are often opaque strings with no ``password=``/``Bearer``
    # marker, and must still be removed from innocuous fields.  Longest-first
    # ordering avoids exposing the remainder when one credential is a prefix
    # of another during a rotation.
    registered_strings, _ = _registered_secret_snapshot()
    result = value
    for secret in registered_strings:
        result = result.replace(secret, _REDACTED)

    # Detect if string looks like it contains secrets before applying patterns
    # This avoids unnecessary regex work on normal strings
    value_lower = result.lower()
    # Include patterns that suggest secrets (URLs with userinfo, headers, assignments)
    secret_indicators = (
        "password", "token", "bearer", "api_key", "secret",
        "auth", "credential", "private", "ssh", "oauth",
        "://", # URLs (may contain userinfo)
        ":", # Headers or assignments
        "=", # Query strings or assignments
        "@", # URLs with userinfo
    )
    if not any(indicator in value_lower for indicator in secret_indicators):
        # No obvious secret indicators; skip regex processing
        return result

    for pattern_info in SECRET_PATTERNS:
        if len(pattern_info) == 2:
            pattern, replacement = pattern_info
            flags = 0
        else:
            pattern, replacement, flags = pattern_info

        try:
            result = re.sub(pattern, replacement, result, flags=flags)
        except (re.error, TypeError):
            # Pattern compilation or substitution failed; skip this pattern
            logger.debug("Secret pattern regex failed: %s", pattern)
            continue

    return result


def redact_sensitive_data(
    value: Any,
    *,
    _depth: int = 0,
    _max_depth: int = 100,
) -> Any:
    """Recursively redact secrets from any data structure.

    Handles:
    - Dicts: redacts values whose keys are secret indicators
    - Lists: redacts each element
    - Strings: redacts patterns matching known secret formats
    - Dataclasses: redacts fields matching secret indicators
    - Repr/str forms: attempts pattern-based redaction

    Args:
        value: Any data to redact
        _depth: Internal recursion depth counter (prevent infinite loops)
        _max_depth: Maximum recursion depth (default 100)

    Returns:
        Redacted copy of the input, same shape as input
    """
    # Depth guard: prevent infinite loops on circular structures
    if _depth >= _max_depth:
        logger.debug(
            "redact_sensitive_data: max recursion depth %d reached; "
            "returning marker for safety",
            _max_depth,
        )
        # Fail-closed: at max depth, we can't recursively inspect nested
        # structures, so return a marker rather than the potentially
        # secret-containing value.
        return _REDACTED

    # None and bool are immutable and never secret
    if value is None or isinstance(value, bool):
        return value

    # Strings: apply regex patterns
    if isinstance(value, str):
        return _redact_string(value)

    # Numbers are never secret
    if isinstance(value, (int, float, complex)):
        return value

    # Bytes: attempt to decode and redact
    if isinstance(value, bytes):
        _, registered_bytes = _registered_secret_snapshot()
        byte_result = value
        for secret in registered_bytes:
            byte_result = byte_result.replace(secret, _REDACTED.encode("utf-8"))
        try:
            decoded = byte_result.decode("utf-8", errors="replace")
            redacted = _redact_string(decoded)
            encoded = redacted.encode("utf-8", errors="replace")
            if redacted != decoded:
                return encoded
            if byte_result != value:
                return byte_result
        except (UnicodeError, TypeError, ValueError):
            # If the bytes are not valid text, preserve the existing bytes
            # contract unless a registered literal was replaced above.
            if byte_result != value:
                return byte_result
        return value

    # Dicts: redact values for secret keys
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if _is_secret_key(k):
                # Redact the value of a secret key
                # But if it's a dict or list, still recurse to handle nested secrets
                if isinstance(v, (dict, list)):
                    # Recursively redact nested structures, then replace with marker
                    result[k] = _REDACTED
                else:
                    result[k] = _REDACTED
            else:
                # Recursively redact non-secret values (they may contain nested secrets)
                result[k] = redact_sensitive_data(
                    v, _depth=_depth + 1, _max_depth=_max_depth
                )
        return result

    # Lists/tuples: redact each element
    if isinstance(value, (list, tuple)):
        redacted_items = [
            redact_sensitive_data(
                item, _depth=_depth + 1, _max_depth=_max_depth
            )
            for item in value
        ]
        # Preserve the original type
        return type(value)(redacted_items)

    # Dataclasses: treat like dicts, redacting fields matching secret patterns
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        redacted_fields = {}
        for field in dataclasses.fields(value):
            field_value = getattr(value, field.name)
            if _is_secret_key(field.name):
                # Redact secret fields - preserve the original type if possible
                if isinstance(field_value, str):
                    redacted_fields[field.name] = _REDACTED
                elif isinstance(field_value, (list, dict)):
                    # For containers, still redact but preserve structure
                    redacted_fields[field.name] = _REDACTED
                else:
                    # For other types, use string representation
                    redacted_fields[field.name] = _REDACTED
            else:
                # Recursively redact other fields
                redacted_fields[field.name] = redact_sensitive_data(
                    field_value, _depth=_depth + 1, _max_depth=_max_depth
                )

        # Reconstruct the dataclass with redacted fields
        try:
            return type(value)(**redacted_fields)
        except (TypeError, ValueError):
            # If reconstruction fails, fail-closed: return a safe marker
            # rather than the original unredacted dataclass.
            logger.debug(
                "Failed to reconstruct dataclass %s; returning marker",
                type(value).__name__,
            )
            # Fail-closed: return a marker indicating redaction occurred
            return f"{type(value).__name__}([REDACTED])"

    # For unknown types (arbitrary objects with __str__ / __repr__):
    # fail-closed. Any downstream serializer (e.g. json.dumps(...,
    # default=str)) will stringify these objects, so we can't just pass
    # them through — a plain-named "Session" or "Message" object whose
    # __str__ dumps an Authorization header would leak plaintext.
    #
    # Policy:
    #   1. Credential-like class or module name → always return a
    #      typed marker, never expose repr().
    #   2. Every other unknown object → attempt to render via repr()
    #      then str(). If either rendering surfaces a known secret
    #      pattern, return the redacted rendering. Otherwise fall
    #      back to returning the redacted rendering itself (never the
    #      raw object) so a downstream default=str serializer can only
    #      ever see already-scanned text.
    #
    # This means: a caller that hands us an object whose repr contains
    # `Authorization: Bearer <tok>` will get back the string
    # `... Authorization: [REDACTED] ...`, not the raw object. And a
    # caller that hands us a plain domain object whose repr is
    # `Point(x=1, y=2)` will get back that repr string, unchanged, but
    # never the object itself.
    type_name = type(value).__name__
    type_name_lower = type_name.lower()
    module_name = type(value).__module__.lower() if hasattr(type(value), "__module__") else ""

    credential_indicators = ("credential", "secret", "token", "bearer", "apikey", "api_key", "passwd", "password")
    is_credential_like = any(
        indicator in type_name_lower or indicator in module_name
        for indicator in credential_indicators
    )

    if is_credential_like:
        # Never let a credential-like class expose any part of its state.
        logger.debug(
            "redact_sensitive_data: credential-like object %s "
            "returned as typed marker for safety",
            type_name,
        )
        return f"{type_name}([REDACTED])"

    # Non-credential-like unknown object: render safely and scan for
    # secret patterns. We render via repr() first because repr() is the
    # canonical debug form; if repr() explodes, fall back to str().
    try:
        rendered = repr(value)
    except Exception:
        try:
            rendered = str(value)
        except Exception:
            logger.debug(
                "redact_sensitive_data: str/repr of %s failed; "
                "returning safe marker",
                type_name,
            )
            return f"{type_name}([REDACTED])"

    redacted_rendered = _redact_string(rendered)
    # Always return the scanned/rendered form rather than the raw
    # object so that downstream default=str serializers can never
    # bypass the redaction pass.
    return redacted_rendered


class SecretRedactionFilter(logging.Filter):
    """logging.Filter that scans every log record for secret patterns.

    Attach to the ``oompah`` logger namespace to catch anything a developer
    accidentally logs — for example ``logger.warning("connect failed to %s",
    url_with_userinfo)`` — without requiring the callsite to remember to
    redact.

    Design:

    * Rewrites ``record.msg`` (the format string) if it is a string.
    * Rewrites ``record.args`` (positional args) so that ``%s`` formatting
      cannot re-expose a secret after the msg is scrubbed.
    * Runs against args of every type via ``redact_sensitive_data`` so that
      an object whose ``__str__`` embeds credentials is redacted before
      Python's logging machinery formats it. Container args (dicts, lists,
      tuples) are scanned recursively.
    * Never raises. If any part of the redaction blows up, the record is
      replaced with a safe marker rather than passed through unchanged.

    Tracebacks are rendered once through the same redaction boundary and the
    raw ``exc_info`` tuple is removed from the record. This may omit traceback
    frames for a malformed exception, but it prevents a formatter from
    re-introducing a credential after ``msg`` and ``args`` were scrubbed.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        try:
            if isinstance(record.msg, str):
                record.msg = _redact_string(record.msg)
            args = record.args
            if args is None:
                pass
            elif isinstance(args, tuple):
                record.args = tuple(
                    redact_sensitive_data(a) for a in args
                )
            elif isinstance(args, dict):
                record.args = {
                    k: redact_sensitive_data(v) for k, v in args.items()
                }
            else:
                # Some callers pass a single non-tuple arg for %s formatting.
                record.args = redact_sensitive_data(args)
            if record.exc_info:
                # ``Formatter`` normally renders exc_info after logger
                # filters have run.  Pre-render it through the same boundary
                # and remove the raw exception tuple so a traceback cannot
                # reintroduce a credential that was absent from msg/args.
                try:
                    rendered_exception = "".join(
                        traceback.format_exception(*record.exc_info)
                    )
                    record.exc_text = _redact_string(rendered_exception)
                    record.exc_info = None
                except Exception:
                    # Fail closed if a hostile/broken exception object cannot
                    # be rendered safely.  Losing a traceback is preferable
                    # to writing an unsanitized one.
                    record.exc_text = _REDACTED
                    record.exc_info = None
        except Exception:
            # A broken filter must never pass the original record through: a
            # formatter would otherwise be able to serialize its raw args.
            record.msg = _REDACTED
            record.args = ()
            record.exc_info = None
            record.exc_text = _REDACTED
        return True


def install_secret_redaction_filter(logger_name: str = "oompah") -> SecretRedactionFilter:
    """Attach a :class:`SecretRedactionFilter` to a logger namespace.

    Idempotent: if the target logger already has an instance of this filter,
    the existing one is returned. Safe to call multiple times (e.g. from
    both server startup and test fixtures).
    """
    target = logging.getLogger(logger_name)
    flt = next(
        (f for f in target.filters if isinstance(f, SecretRedactionFilter)),
        None,
    )
    if flt is None:
        flt = SecretRedactionFilter()
        target.addFilter(flt)

    # Logger filters do not run on records propagated from child loggers
    # (e.g. ``oompah.api_agent`` → ``oompah``).  Install the same filter on
    # current root handlers as well so every service log sink gets the
    # boundary.  The handler check keeps repeated startup/reload calls
    # idempotent.
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, SecretRedactionFilter) for f in handler.filters):
            handler.addFilter(flt)
    return flt


__all__ = [
    "redact_sensitive_data",
    "register_secret",
    "register_secret_values",
    "register_configured_secrets",
    "clear_registered_secrets",
    "registered_secret_count",
    "SECRET_KEYS",
    "SECRET_PATTERNS",
    "SecretRedactionFilter",
    "install_secret_redaction_filter",
]
