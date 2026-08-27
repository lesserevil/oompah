"""Provider health check: send a tiny prompt to a configured provider.

Supports POST /api/v1/providers/{provider_id}/test.

Design goals (TASK-407.3):
- Send a short, deterministic prompt (``What is 2 + 2? Answer with only the
  number.``) using the smallest possible OpenAI-compatible request.
- Do NOT create oompah tasks, update role round-robin usage, claim backlog
  work, or mutate any provider config.
- Return a structured :class:`ProviderTestResult` with success/failure,
  provider id, provider name, model used, latency, response text (truncated),
  and a normalized :attr:`~ProviderTestResult.error_reason`.
- Use short timeouts so the UI test does not hang the operator.

Error-reason normalization mirrors the categories the implementation plan
calls out: ``missing_credentials``, ``auth_failed``, ``rate_limited``,
``budget_blocked``, ``timeout``, ``overloaded``, ``invalid_model``,
``provider_unavailable``, and ``unknown_error``.
"""

from __future__ import annotations

import asyncio
import copy
import contextlib
import hashlib
import json
import logging
import math
import os
import re
import shutil
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable
from urllib.parse import urlsplit

from oompah.auditor_policy_authority import AUDITOR_POLICY_AUTHORITY

if TYPE_CHECKING:
    from oompah.models import ModelProvider

logger = logging.getLogger(__name__)

# Hard timeout for the health-check HTTP request (seconds).  Short so the
# operator's UI test does not hang.
HEALTH_CHECK_TIMEOUT = 10

# Hard timeout for the ACP live probe (seconds).  Larger than the HTTP
# timeout because an ACP probe spins up a real backend session (SDK or
# CLI subprocess), which is heavier than a single HTTP round-trip.
ACP_HEALTH_CHECK_TIMEOUT = 60.0

# Maximum number of response characters to include in the result.
MAX_RESPONSE_LENGTH = 200

_TEST_PROMPT = "What is 2 + 2? Answer with only the number."


class ProviderProbeAuthorityError(RuntimeError):
    """Raised when live policy revokes a probe before provider contact."""


def snapshot_provider_for_probe(
    provider: "ModelProvider",
) -> tuple["ModelProvider", str, int]:
    """Capture immutable probe inputs under provider-policy authority.

    ``ProviderStore.update`` mutates records in place. Passing that live object
    across an await/thread boundary lets an old request acquire a new
    configuration signature before its result is published. A deep snapshot
    keeps endpoint, credentials, model catalog, backend, and billing inputs
    bound to one generation; callers revalidate the signature at contact and
    publication boundaries.
    """

    while True:
        generation = AUDITOR_POLICY_AUTHORITY.generation()
        with AUDITOR_POLICY_AUTHORITY.admission(generation) as current:
            if not current:
                continue
            snapshot = copy.deepcopy(provider)
            signature = ProviderHealthCache.configuration_signature(snapshot)
            return snapshot, signature, generation


def _require_probe_contact(
    callback: Callable[[], str | None] | None,
) -> None:
    """Apply a caller's policy fence at the concrete probe transport edge."""

    if callback is None:
        return
    denial = callback()
    if denial is not None:
        raise ProviderProbeAuthorityError(str(denial))


# ---------------------------------------------------------------------------
# Normalized error reasons
# ---------------------------------------------------------------------------

#: All valid normalized error-reason strings.
ERROR_REASONS = frozenset(
    {
        "invalid_base_url",
        "missing_credentials",
        "auth_failed",
        "rate_limited",
        "budget_blocked",
        "timeout",
        "overloaded",
        "invalid_model",
        "provider_unavailable",
        "health_unknown",
        "unknown_error",
    }
)


def openai_base_url_error(base_url: object) -> str | None:
    """Return a safe configuration error for an OpenAI-compatible base URL.

    A base URL is a transport boundary.  It must be an absolute HTTP(S) URL
    with a host before any caller appends ``/chat/completions``.  The returned
    text is deliberately independent of the supplied value so malformed URLs
    and embedded credentials can never be reflected in health or dispatch
    diagnostics.
    """

    if not isinstance(base_url, str) or not base_url.strip():
        return "base_url is missing; configure an absolute http:// or https:// URL"

    value = base_url.strip()
    if any(char.isspace() or ord(char) < 32 for char in value) or "\\" in value:
        return "base_url must be an absolute http:// or https:// URL"
    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme.casefold()
        hostname = parsed.hostname
        # Accessing .port validates malformed and out-of-range ports.
        _ = parsed.port
    except ValueError:
        return "base_url must be an absolute http:// or https:// URL"

    if scheme not in {"http", "https"} or not parsed.netloc or not hostname:
        return "base_url must be an absolute http:// or https:// URL"
    # Query strings/fragments are not part of a transport base and would make
    # naive endpoint joining ambiguous (and commonly carry credentials).
    if parsed.query or parsed.fragment:
        return "base_url must not contain a query or fragment"
    # Credentials in a URL are both unnecessary (the API key belongs in the
    # Authorization header) and easy to leak through URL exceptions/logs.
    if parsed.username is not None or parsed.password is not None:
        return "base_url must not contain embedded credentials"
    return None


def validate_openai_base_url(base_url: object) -> bool:
    """Return whether *base_url* is safe for an OpenAI-compatible request."""

    return openai_base_url_error(base_url) is None


def openai_chat_completions_url(base_url: object) -> str:
    """Build a chat-completions URL only after validating its base URL."""

    error = openai_base_url_error(base_url)
    if error is not None:
        raise ValueError(error)
    return f"{str(base_url).strip().rstrip('/')}/chat/completions"


_BEARER_RE = re.compile(r"(?i)(\bbearer\s+)[^\s,;]+")
_URL_CREDENTIALS_RE = re.compile(r"(?i)(https?://)[^/\s@]+@")
_URL_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret|token)=)"
    r"[^&#\s]+"
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)((?:api[ _-]?key|access[ _-]?token|auth[ _-]?token|password|secret|token)"
    r"\s*[:=]\s*)([\"']?)[^\"'\s,;}]+"
)


def redact_sensitive_text(value: object) -> str:
    """Remove common credential forms from provider-facing diagnostics."""

    text = str(value or "")
    text = _URL_CREDENTIALS_RE.sub(r"\1[REDACTED]@", text)
    text = _URL_QUERY_SECRET_RE.sub(r"\1[REDACTED]", text)
    text = _BEARER_RE.sub(r"\1[REDACTED]", text)
    text = _SECRET_VALUE_RE.sub(r"\1\2[REDACTED]", text)
    # Common provider keys are prefixed this way. Redacting the shape catches
    # upstream errors that mention a key without naming the field.
    return re.sub(r"(?i)\bsk-[A-Za-z0-9_-]{4,}\b", "[REDACTED]", text)


@dataclass
class ProviderTestResult:
    """Result of a single provider health-check call."""

    provider_id: str
    provider_name: str
    model: str
    success: bool
    latency_ms: float
    response_text: str = ""
    # One of the :data:`ERROR_REASONS` strings, or ``""`` on success.
    error_reason: str = ""
    error_detail: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "model": self.model,
            "success": self.success,
            "latency_ms": round(self.latency_ms, 1),
        }
        if self.response_text:
            d["response_text"] = redact_sensitive_text(self.response_text)[
                :MAX_RESPONSE_LENGTH
            ]
        if self.error_reason:
            d["error_reason"] = self.error_reason
        if self.error_detail:
            d["error_detail"] = redact_sensitive_text(self.error_detail)[:500]
        return d


class ProviderHealthCache:
    """Thread-safe cache of authoritative provider probe/startup outcomes.

    The HTTP health endpoint, provider startup path, and bounded pre-dispatch
    probe all publish here. Candidate selection itself reads snapshots only.
    Entries are tied to a non-secret provider configuration signature;
    editing transport/model configuration immediately makes an old
    observation inapplicable.
    """

    _FORMAT_VERSION = 1

    def __init__(self, path: str | None = None) -> None:
        self._lock = threading.RLock()
        self._entries: dict[
            tuple[str, str], tuple[str, dict[str, object]]
        ] = {}
        self._path: str | None = None
        self._persistence_error: str | None = None
        if path:
            self.configure(path)

    @staticmethod
    def _signature(provider: "ModelProvider") -> str:
        api_key = str(getattr(provider, "api_key", "") or "")
        payload = {
            "mode": str(getattr(provider, "mode", "api") or "api"),
            "provider_type": str(
                getattr(provider, "provider_type", "openai_compatible")
                or "openai_compatible"
            ),
            "backend": str(getattr(provider, "backend", "") or ""),
            "transport": str(
                getattr(provider, "transport", "openai_compatible")
                or "openai_compatible"
            ),
            "pi_provider_id": str(
                getattr(provider, "pi_provider_id", "") or ""
            ),
            "billing_model": str(
                getattr(provider, "billing_model", "subscription") or "subscription"
            ),
            "acp_subscription_only": bool(
                getattr(provider, "acp_subscription_only", False)
            ),
            "acp_permission_mode": str(
                getattr(provider, "acp_permission_mode", "") or ""
            ),
            "base_url": str(getattr(provider, "base_url", "") or ""),
            "api_key_digest": (
                hashlib.sha256(api_key.encode("utf-8")).hexdigest()
                if api_key
                else ""
            ),
            "models": list(getattr(provider, "models", None) or ()),
            "default_model": str(getattr(provider, "default_model", "") or ""),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @classmethod
    def configuration_signature(cls, provider: "ModelProvider") -> str:
        """Return the non-secret identity of one provider configuration.

        Worker admission snapshots this value while provider policy is stable.
        A terminal outcome may only update the health ledger when the live
        provider still has the same signature; otherwise an old endpoint or
        credential generation would be recorded as evidence for its replacement.
        """

        return cls._signature(provider)

    def configure(self, path: str) -> None:
        """Bind this cache to one durable ledger and load it atomically."""

        normalized = os.path.abspath(path)
        with self._lock:
            if self._path == normalized:
                return
            self._path = normalized
            self._entries = {}
            self._persistence_error = None
            if not os.path.exists(normalized):
                return
            try:
                with open(normalized, "r", encoding="utf-8") as handle:
                    raw = json.load(handle)
                if not isinstance(raw, dict) or raw.get("version") != self._FORMAT_VERSION:
                    raise ValueError("unsupported provider-health ledger format")
                entries = raw.get("entries")
                if not isinstance(entries, list):
                    raise ValueError("provider-health entries must be a list")
                for item in entries:
                    if not isinstance(item, dict):
                        raise ValueError("provider-health entry must be a mapping")
                    provider_id = str(item.get("provider_id") or "")
                    model = str(item.get("model") or "")
                    signature = str(item.get("signature") or "")
                    value = item.get("value")
                    if not provider_id or not signature or not isinstance(value, dict):
                        raise ValueError("provider-health entry is incomplete")
                    if (
                        len(signature) != 64
                        or re.fullmatch(r"[0-9a-f]{64}", signature) is None
                        or value.get("provider_id") != provider_id
                        or str(value.get("model") or "") != model
                        or not isinstance(value.get("success"), bool)
                        or isinstance(value.get("observed_at"), bool)
                        or not isinstance(value.get("observed_at"), (int, float))
                        or not math.isfinite(float(value.get("observed_at")))
                    ):
                        raise ValueError("provider-health authority fields are invalid")
                    reason = str(value.get("error_reason") or "")
                    if reason and reason not in ERROR_REASONS:
                        raise ValueError("provider-health reason is invalid")
                    self._entries[(provider_id, model)] = (signature, dict(value))
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self._entries = {}
                self._persistence_error = (
                    f"provider-health ledger {normalized!r} is unreadable: "
                    f"{type(exc).__name__}"
                )

    def _persist_locked(self) -> bool:
        if self._path is None:
            return True
        if self._persistence_error is not None:
            return False
        directory = os.path.dirname(self._path) or "."
        temp_path = ""
        try:
            os.makedirs(directory, exist_ok=True)
            descriptor, temp_path = tempfile.mkstemp(
                prefix=f".{os.path.basename(self._path)}.",
                suffix=".tmp",
                dir=directory,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                os.chmod(temp_path, 0o600)
                entries = [
                    {
                        "provider_id": provider_id,
                        "model": model,
                        "signature": signature,
                        "value": value,
                    }
                    for (provider_id, model), (signature, value) in sorted(
                        self._entries.items()
                    )
                ]
                json.dump(
                    {"version": self._FORMAT_VERSION, "entries": entries},
                    handle,
                    indent=2,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._path)
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return True
        except (OSError, TypeError, ValueError) as exc:
            self._persistence_error = (
                "provider-health ledger could not be durably updated: "
                f"{type(exc).__name__}"
            )
            return False
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass

    def persistence_error(self) -> str | None:
        with self._lock:
            return self._persistence_error

    def record(self, provider: "ModelProvider", result: ProviderTestResult) -> bool:
        value = result.to_dict()
        value["provider_id"] = str(provider.id)
        value.pop("response_text", None)
        value.pop("error_detail", None)
        value["observed_at"] = time.time()
        key = (str(provider.id), str(result.model or ""))
        with AUDITOR_POLICY_AUTHORITY.mutation():
            with self._lock:
                self._entries[key] = (self._signature(provider), value)
                return self._persist_locked()

    def record_if_configuration(
        self,
        provider: "ModelProvider",
        result: ProviderTestResult,
        *,
        expected_signature: str,
        current_provider: Callable[[], "ModelProvider | None"] | None = None,
    ) -> bool:
        """Record *result* only for the admitted provider generation.

        The signature comparison and ledger write share the policy mutation
        lock with ProviderStore updates. This closes the check/write race where
        a provider could be edited after a worker compared its snapshot but
        before the health result was persisted.
        """

        value = result.to_dict()
        value["provider_id"] = str(provider.id)
        value.pop("response_text", None)
        value.pop("error_detail", None)
        value["observed_at"] = time.time()
        key = (str(provider.id), str(result.model or ""))
        with AUDITOR_POLICY_AUTHORITY.mutation():
            try:
                authoritative_provider = (
                    current_provider() if current_provider is not None else provider
                )
            except Exception:
                return False
            if (
                authoritative_provider is None
                or str(authoritative_provider.id) != str(provider.id)
                or self._signature(authoritative_provider) != str(expected_signature)
            ):
                return False
            with self._lock:
                self._entries[key] = (str(expected_signature), value)
                return self._persist_locked()

    def record_failure(
        self,
        provider: "ModelProvider",
        *,
        model: str | None,
        reason: str,
        detail: str = "",
    ) -> bool:
        return self.record(
            provider,
            ProviderTestResult(
                provider_id=str(provider.id),
                provider_name=str(getattr(provider, "name", provider.id)),
                model=str(model or ""),
                success=False,
                latency_ms=0.0,
                error_reason=(reason if reason in ERROR_REASONS else "unknown_error"),
                error_detail=detail,
            ),
        )

    def get(
        self,
        provider: "ModelProvider",
        model: str | None = None,
        *,
        max_age_seconds: float | None = None,
        now: float | None = None,
    ) -> dict[str, object] | None:
        key = (str(provider.id), str(model or ""))
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry[0] != self._signature(provider):
                return None
            if max_age_seconds is not None:
                observed_at = entry[1].get("observed_at")
                if not isinstance(observed_at, (int, float)):
                    return None
                age = (time.time() if now is None else now) - float(observed_at)
                if age < 0 or age > max(0.0, max_age_seconds):
                    return None
            return dict(entry[1])

    def snapshot(
        self,
        providers: list["ModelProvider"],
        *,
        max_age_seconds: float | None = None,
        now: float | None = None,
    ) -> dict[tuple[str, str], dict[str, object]]:
        result: dict[tuple[str, str], dict[str, object]] = {}
        by_id = {str(provider.id): provider for provider in providers}
        with self._lock:
            entries = list(self._entries.items())
        for key, (signature, value) in entries:
            provider = by_id.get(key[0])
            observed_at = value.get("observed_at")
            fresh = (
                max_age_seconds is None
                or (
                    isinstance(observed_at, (int, float))
                    and 0
                    <= (time.time() if now is None else now) - float(observed_at)
                    <= max(0.0, max_age_seconds)
                )
            )
            if (
                provider is not None
                and signature == self._signature(provider)
                and fresh
            ):
                result[key] = dict(value)
        return result

    def invalidate(self, provider_id: str) -> None:
        with AUDITOR_POLICY_AUTHORITY.mutation():
            with self._lock:
                doomed = [key for key in self._entries if key[0] == str(provider_id)]
                for key in doomed:
                    self._entries.pop(key, None)
                self._persist_locked()

    def clear(self) -> None:
        with AUDITOR_POLICY_AUTHORITY.mutation():
            with self._lock:
                self._entries.clear()
                self._persistence_error = None
                self._persist_locked()


PROVIDER_HEALTH_CACHE = ProviderHealthCache()


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _normalize_http_error(exc: urllib.error.HTTPError, body: str) -> str:
    """Map an HTTP status code (+ body hints) to a normalized reason string."""
    code = exc.code
    body_lower = body.lower()
    if code == 401:
        # 401 can mean the key is completely absent or clearly invalid.
        # When the server explicitly says "invalid" or "wrong", the key
        # was sent but rejected → auth_failed.  An empty body or no
        # diagnostic hint → the key is likely absent → missing_credentials.
        if "invalid" in body_lower or "wrong" in body_lower:
            return "auth_failed"
        return "missing_credentials"
    if code == 403:
        return "auth_failed"
    if code == 429:
        return "rate_limited"
    if code == 529:
        # Anthropic / some proxies: "overloaded"
        return "overloaded"
    if code in (503, 504):
        return "overloaded"
    if code == 404 or code == 422:
        # 404 on /chat/completions or 422 Unprocessable often means the
        # model name is wrong or the route doesn't exist.
        if "model" in body_lower or "not found" in body_lower:
            return "invalid_model"
        return "provider_unavailable"
    if 500 <= code < 600:
        return "provider_unavailable"
    return "unknown_error"


def _normalize_url_error(exc: urllib.error.URLError) -> str:
    """Map a URL/network error to a normalized reason string."""
    reason = str(exc.reason).lower()
    if "timed out" in reason or "timeout" in reason:
        return "timeout"
    return "provider_unavailable"


def _normalize_timeout_error() -> str:
    return "timeout"


def _pick_model(provider: "ModelProvider", model: str | None = None) -> str:
    """Choose the best model to use for a health-check call.

    Priority:
    1. provider.default_model (if set and non-empty)
    2. First entry in provider.models (if available)
    3. Empty string — for ACP providers that let the SDK choose the model.
    """
    if model is not None:
        return str(model)
    if provider.default_model:
        return provider.default_model
    if provider.models:
        return provider.models[0]
    return ""


# ---------------------------------------------------------------------------
# Core health-check implementation
# ---------------------------------------------------------------------------


def _build_ssl_context() -> ssl.SSLContext:
    """Return a default SSL context, falling back to unverified if needed."""
    try:
        return ssl.create_default_context()
    except Exception:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def run_health_check(
    provider: "ModelProvider",
    model: str | None = None,
    *,
    before_transport_contact: Callable[[], str | None] | None = None,
) -> ProviderTestResult:
    """Send a tiny prompt to *provider* and return a :class:`ProviderTestResult`.

    This function is intentionally **blocking** so it can be wrapped in
    ``asyncio.to_thread`` by the HTTP endpoint. It never:

    * creates oompah tasks
    * updates role round-robin usage
    * claims backlog work
    * mutates the provider config

    ACP providers (``mode == "acp"``) are session-based (Claude Agent SDK,
    OpenAI Agents SDK, or the ``opencode`` CLI subprocess depending on the
    backend) and cannot be probed over this synchronous OpenAI-compatible
    HTTP path. The endpoint routes them to :func:`run_acp_health_check`
    instead; this guard exists only for direct callers.
    """
    pid = provider.id
    pname = provider.name

    # ACP providers are driven by a backend session, not an HTTP request.
    # The async live probe (run_acp_health_check) is the supported path —
    # this sync function cannot drive an async session.
    if provider.mode == "acp":
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=_pick_model(provider, model),
            success=False,
            latency_ms=0.0,
            error_reason="provider_unavailable",
            error_detail=(
                "ACP providers must be tested via the live backend probe; "
                "the synchronous health-check path does not support ACP."
            ),
        )

    resolved_model = _pick_model(provider, model)
    if not resolved_model:
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=0.0,
            error_reason="invalid_model",
            error_detail=(
                "Provider has no models configured. "
                "Add at least one model to test it."
            ),
        )
    if provider.models and resolved_model not in provider.models:
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=0.0,
            error_reason="invalid_model",
            error_detail="The requested model is absent from the provider catalog.",
        )

    base_url_error = openai_base_url_error(getattr(provider, "base_url", ""))
    if base_url_error is not None:
        # Preserve the established health reason for a missing URL while
        # exposing malformed/relative URLs as a distinct actionable state.
        missing = not str(getattr(provider, "base_url", "") or "").strip()
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=0.0,
            error_reason="provider_unavailable" if missing else "invalid_base_url",
            error_detail=(
                "Provider has no base_url configured."
                if missing
                else base_url_error
            ),
        )

    api_key = provider.api_key or ""
    # Validation above and the guarded builder below are intentionally both
    # present: this function is a public integration boundary and should not
    # regress into constructing a relative URL if its checks are refactored.
    url = openai_chat_completions_url(provider.base_url)

    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "user", "content": _TEST_PROMPT},
        ],
        "max_tokens": 16,
        "temperature": 0,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "oompah-health-check/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    ssl_ctx = _build_ssl_context()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    t0 = time.monotonic()
    try:
        # The caller may have crossed an event-loop/thread boundary since it
        # snapshotted this provider. Revalidate live policy immediately before
        # opening the socket; a denied probe is not provider-health evidence.
        _require_probe_contact(before_transport_contact)
        with urllib.request.urlopen(
            req,
            context=ssl_ctx,
            timeout=HEALTH_CHECK_TIMEOUT,
        ) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        latency_ms = (time.monotonic() - t0) * 1000.0

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return ProviderTestResult(
                provider_id=pid,
                provider_name=pname,
                model=resolved_model,
                success=False,
                latency_ms=latency_ms,
                error_reason="unknown_error",
                error_detail=f"Non-JSON response: {raw[:200]}",
            )

        # Extract the assistant's reply from the standard OpenAI shape.
        response_text = ""
        try:
            choices = data.get("choices") or []
            if choices:
                response_text = (
                    choices[0].get("message", {}).get("content", "") or ""
                )
        except (KeyError, IndexError, TypeError):
            pass

        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=True,
            latency_ms=latency_ms,
            response_text=response_text.strip()[:MAX_RESPONSE_LENGTH],
        )

    except ProviderProbeAuthorityError:
        raise

    except urllib.error.HTTPError as exc:
        latency_ms = (time.monotonic() - t0) * 1000.0
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")[:1000]
        except Exception:
            pass
        reason = _normalize_http_error(exc, error_body)
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=latency_ms,
            error_reason=reason,
            error_detail=(
                f"HTTP {exc.code}: {redact_sensitive_text(error_body)[:300]}"
            ),
        )

    except urllib.error.URLError as exc:
        latency_ms = (time.monotonic() - t0) * 1000.0
        reason_str = str(exc.reason).lower()
        if "timed out" in reason_str or "timeout" in reason_str:
            reason = "timeout"
        else:
            reason = "provider_unavailable"
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=latency_ms,
            error_reason=reason,
            error_detail=redact_sensitive_text(str(exc)),
        )

    except TimeoutError:
        latency_ms = (time.monotonic() - t0) * 1000.0
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=latency_ms,
            error_reason="timeout",
            error_detail="Request timed out.",
        )

    except OSError as exc:
        latency_ms = (time.monotonic() - t0) * 1000.0
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=latency_ms,
            error_reason="provider_unavailable",
            error_detail=f"Network error: {redact_sensitive_text(exc)}",
        )

    except Exception as exc:  # noqa: BLE001
        latency_ms = (time.monotonic() - t0) * 1000.0
        logger.warning(
            "Provider health-check unexpected error for %s: %s",
            pname,
            redact_sensitive_text(exc),
        )
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=latency_ms,
            error_reason="unknown_error",
            error_detail=redact_sensitive_text(str(exc)[:300]),
        )


# ---------------------------------------------------------------------------
# ACP live probe
# ---------------------------------------------------------------------------


def _normalize_acp_error(status: str, last_error: str | None) -> tuple[str, str]:
    """Map a terminal ACP session status + last_error to (reason, detail).

    ACP backends don't expose HTTP status codes, so we sniff the error
    text for the well-known failure shapes (SDK/CLI not installed, auth
    not set up, rate limits) and otherwise fall back to a status-derived
    reason. Returns a (error_reason, error_detail) pair where
    error_reason is one of :data:`ERROR_REASONS`.
    """
    detail = (last_error or "").strip()
    low = detail.lower()

    # Backend not installed / not launchable.
    if (
        "modulenotfound" in low
        or "no module named" in low
        or "not installed" in low
        or ("command not found" in low)
        or ("executable" in low and "not found" in low)
    ):
        return "provider_unavailable", detail
    # Auth / subscription not configured.
    if any(
        k in low
        for k in (
            "unauthorized",
            "not logged in",
            "log in",
            "login",
            "authenticate",
            "auth failed",
            "subscription",
            "credential",
            "api key",
            "api_key",
            "401",
            "403",
        )
    ):
        return "auth_failed", detail
    if "rate" in low and "limit" in low:
        return "rate_limited", detail
    if "overloaded" in low or "529" in low:
        return "overloaded", detail

    # No usable hint in the error text — derive from the terminal status.
    if status == "stalled":
        return "timeout", detail or "ACP session stalled (turn timeout exceeded)."
    if status == "interrupted":
        return "unknown_error", detail or "ACP session was interrupted."
    if status == "errored":
        return "provider_unavailable", detail or "ACP backend session crashed."
    # "failed" or any unexpected status.
    return "unknown_error", detail or f"ACP session ended with status {status!r}."


async def run_pi_ai_health_check(
    provider: "ModelProvider",
    model: str | None = None,
    *,
    before_transport_contact: Callable[[], str | None] | None = None,
) -> ProviderTestResult:
    """Probe one exact model through the optional pi-ai transport."""

    from oompah.pi_ai_transport import PiAiTransport, PiAiTransportError

    resolved_model = _pick_model(provider, model)
    if not resolved_model:
        return ProviderTestResult(
            provider_id=provider.id,
            provider_name=provider.name,
            model="",
            success=False,
            latency_ms=0.0,
            error_reason="invalid_model",
            error_detail="Provider has no model configured.",
        )
    workspace = tempfile.mkdtemp(prefix="oompah-pi-ai-health-")
    transport = PiAiTransport(
        workspace_path=workspace,
        provider=(getattr(provider, "pi_provider_id", None) or provider.name),
        provider_name=provider.name,
        model=resolved_model,
        api_key=provider.api_key or "",
        base_url=provider.base_url or "",
        model_context=provider.get_model_context(resolved_model),
        model_capabilities=tuple(
            (getattr(provider, "model_capabilities", None) or {}).get(
                resolved_model, ("text",)
            )
        ),
        timeout_s=ACP_HEALTH_CHECK_TIMEOUT,
        before_transport_contact=before_transport_contact,
    )
    started = time.monotonic()
    parts: list[str] = []
    try:
        async for event in transport.complete(
            system_prompt="",
            messages=[
                {"role": "user", "content": _TEST_PROMPT, "timestamp": 0}
            ],
            tools=[],
            max_tokens=16,
        ):
            if event.get("type") == "text_delta":
                parts.append(str(event.get("delta") or ""))
        return ProviderTestResult(
            provider_id=provider.id,
            provider_name=provider.name,
            model=resolved_model,
            success=True,
            latency_ms=(time.monotonic() - started) * 1000.0,
            response_text="".join(parts)[:MAX_RESPONSE_LENGTH],
        )
    except PiAiTransportError as exc:
        if "configuration changed" in str(exc).lower():
            raise ProviderProbeAuthorityError(str(exc)) from exc
        reason, detail = _normalize_acp_error("errored", str(exc))
        return ProviderTestResult(
            provider_id=provider.id,
            provider_name=provider.name,
            model=resolved_model,
            success=False,
            latency_ms=(time.monotonic() - started) * 1000.0,
            error_reason=reason,
            error_detail=redact_sensitive_text(detail)[:500],
        )
    finally:
        await transport.close()
        shutil.rmtree(workspace, ignore_errors=True)


async def run_acp_health_check(
    provider: "ModelProvider",
    model: str | None = None,
    *,
    before_transport_contact: Callable[[], str | None] | None = None,
    isolate_remote_write: bool = False,
    provider_auth_kind: str | None = None,
) -> ProviderTestResult:
    """Live-probe an ACP provider by running one tiny turn through its backend.

    Resolves ``provider.backend`` (defaulting to ``"claude"``) against the
    ACP backend registry, runs the backend's cheap ``validate_provider``
    check, then spins up a real session in a throwaway workspace and sends
    the same :data:`_TEST_PROMPT` the HTTP path uses. The session is driven
    to completion (bounded by :data:`ACP_HEALTH_CHECK_TIMEOUT`) and the
    terminal ``status`` is mapped to a :class:`ProviderTestResult`.

    Like :func:`run_health_check`, this never creates oompah tasks, updates
    role usage, claims backlog work, or mutates provider config. It does
    spawn a real backend session (billing against the operator's
    subscription) and is therefore async + heavier than the HTTP probe.

    Imports of the ACP backend package are deferred to call time so that
    importing :mod:`oompah.provider_health` stays cheap and free of the
    orchestrator/tracker import graph.
    """
    from oompah.acp_backends import BACKENDS, get_backend
    from oompah.acp_backends.base import AcpBackendOptions

    pid = provider.id
    pname = provider.name
    resolved_model = _pick_model(provider, model)  # "" lets the backend choose
    backend_name = getattr(provider, "backend", None) or "claude"

    backend_cls = get_backend(backend_name)
    if backend_cls is None:
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=0.0,
            error_reason="provider_unavailable",
            error_detail=(
                f"Unknown ACP backend {backend_name!r}. "
                f"Registered backends: {sorted(BACKENDS)}"
            ),
        )

    backend = backend_cls()

    # Cheap, backend-specific config validation before spinning anything up.
    try:
        config_errors = backend.validate_provider(provider)
    except Exception as exc:  # noqa: BLE001 — surface validator bugs as a failure
        config_errors = [f"validate_provider raised: {exc}"]
    if config_errors:
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=0.0,
            error_reason="missing_credentials",
            error_detail="; ".join(config_errors)[:500],
        )

    if provider.models and resolved_model not in provider.models:
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=0.0,
            error_reason="invalid_model",
            error_detail="The requested model is absent from the provider catalog.",
        )
    permission_mode = getattr(provider, "acp_permission_mode", None) or "default"
    # Flow the billing tier so the probe exercises the SAME execution
    # path real dispatch would (e.g. codex: subscription -> CLI/OAuth,
    # per_token -> in-process SDK).
    billing_model = (getattr(provider, "billing_model", None) or "per_token")
    workspace = tempfile.mkdtemp(prefix="oompah-acp-health-")

    contact_denial: str | None = None

    def _begin_probe_transport() -> str | None:
        nonlocal contact_denial
        if before_transport_contact is None:
            return None
        denial = before_transport_contact()
        if denial is not None:
            contact_denial = str(denial)
        return contact_denial

    options = AcpBackendOptions(
        workspace_path=workspace,
        prompt=_TEST_PROMPT,
        model=resolved_model or None,
        max_turns=1,
        tool_catalog=[],  # the 2+2 probe needs no tools
        permission_mode=permission_mode,
        turn_timeout_s=ACP_HEALTH_CHECK_TIMEOUT,
        on_event=None,
        billing_model=billing_model,
        isolate_remote_write=isolate_remote_write,
        provider_auth_kind=provider_auth_kind,
        begin_transport_contact=_begin_probe_transport,
    )

    response_parts: list[str] = []
    t0 = time.monotonic()

    try:
        session = backend.start_session(options)
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(workspace, ignore_errors=True)
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=(time.monotonic() - t0) * 1000.0,
            error_reason="provider_unavailable",
            error_detail=(
                f"ACP backend {backend_name!r} failed to start a session: {exc}"
            )[:500],
        )

    async def _drive() -> None:
        async for ev in session.run_turn():
            if ev.kind == "text":
                txt = (ev.payload or {}).get("text") or ""
                if txt:
                    response_parts.append(txt)

    try:
        await asyncio.wait_for(_drive(), timeout=ACP_HEALTH_CHECK_TIMEOUT)
    except (asyncio.TimeoutError, TimeoutError):
        with contextlib.suppress(Exception):
            await session.close()
        if contact_denial is not None:
            raise ProviderProbeAuthorityError(contact_denial)
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=(time.monotonic() - t0) * 1000.0,
            error_reason="timeout",
            error_detail=(
                f"ACP session did not complete within "
                f"{int(ACP_HEALTH_CHECK_TIMEOUT)}s."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        with contextlib.suppress(Exception):
            await session.close()
        if contact_denial is not None:
            raise ProviderProbeAuthorityError(contact_denial) from exc
        logger.warning(
            "ACP health-check unexpected error for %s (%s): %s",
            pname,
            backend_name,
            exc,
        )
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=False,
            latency_ms=(time.monotonic() - t0) * 1000.0,
            error_reason="provider_unavailable",
            error_detail=(
                f"ACP backend {backend_name!r} session crashed: {exc}"
            )[:500],
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    if contact_denial is not None:
        raise ProviderProbeAuthorityError(contact_denial)

    latency_ms = (time.monotonic() - t0) * 1000.0
    status = session.status
    response_text = "".join(response_parts).strip()

    if status == "succeeded":
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=resolved_model,
            success=True,
            latency_ms=latency_ms,
            response_text=response_text[:MAX_RESPONSE_LENGTH],
        )

    reason, detail = _normalize_acp_error(status, session.last_error)
    return ProviderTestResult(
        provider_id=pid,
        provider_name=pname,
        model=resolved_model,
        success=False,
        latency_ms=latency_ms,
        response_text=response_text[:MAX_RESPONSE_LENGTH],
        error_reason=reason,
        error_detail=detail[:500],
    )
