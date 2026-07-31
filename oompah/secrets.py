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
* **Safe defaults:** Returns original value if type is unknown.
* **Pattern-based:** Uses regex + key-name heuristics to find secrets.
* **Configurable:** See ``SECRET_PATTERNS`` and ``SECRET_KEYS`` for customization.
"""

from __future__ import annotations

import dataclasses
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Marker used in place of actual secrets
_REDACTED = "[REDACTED]"

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
    # HTTP Basic Auth in URLs: http://user:pass@host or https://admin:12345@db.com
    # Redact everything between :// and @ to handle both user and password
    (r"(https?://)([^@\s/]+)(?::([^@\s/]+))?(@)", r"\1[REDACTED]\4"),
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

    # Detect if string looks like it contains secrets before applying patterns
    # This avoids unnecessary regex work on normal strings
    value_lower = value.lower()
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
        return value

    result = value
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
            "redact_sensitive_data: max recursion depth %d reached",
            _max_depth,
        )
        return value

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
        try:
            decoded = value.decode("utf-8", errors="replace")
            redacted = _redact_string(decoded)
            if redacted != decoded:
                # String was modified; return as-is since we can't safely
                # encode back to bytes (encoding might vary)
                return redacted.encode("utf-8", errors="replace")
        except Exception:
            pass
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
        except (TypeError, ValueError) as exc:
            # If reconstruction fails, return a safe string representation (defensive)
            logger.debug(
                "Failed to reconstruct dataclass %s: %s",
                type(value).__name__, exc,
            )
            # Return the original value unchanged rather than converting to string
            return value

    # For unknown types, attempt to handle repr() forms (for credential objects)
    # Only do this if the type name or module suggests it might contain credentials
    type_name = type(value).__name__.lower()
    module_name = type(value).__module__.lower() if hasattr(type(value), "__module__") else ""

    credential_indicators = ("credential", "auth", "client", "secret", "token", "key")
    is_credential_like = any(
        indicator in type_name or indicator in module_name
        for indicator in credential_indicators
    )

    if is_credential_like:
        try:
            repr_str = repr(value)
            # Only if repr looks like it contains secrets should we redact
            redacted_repr = _redact_string(repr_str)
            if redacted_repr != repr_str:
                # Repr was modified; return a note indicating redaction
                logger.debug(
                    "redact_sensitive_data: redacted repr of %s",
                    type(value).__name__,
                )
                # Return a safe string representation
                return f"{type(value).__name__}([REDACTED])"
        except Exception:
            pass

    # Return value unchanged if we don't know how to redact it
    return value


__all__ = [
    "redact_sensitive_data",
    "SECRET_KEYS",
    "SECRET_PATTERNS",
]
