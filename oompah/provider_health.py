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
import contextlib
import json
import logging
import re
import shutil
import ssl
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING

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


# ---------------------------------------------------------------------------
# Normalized error reasons
# ---------------------------------------------------------------------------

#: All valid normalized error-reason strings.
ERROR_REASONS = frozenset(
    {
        "missing_credentials",
        "auth_failed",
        "rate_limited",
        "budget_blocked",
        "timeout",
        "overloaded",
        "invalid_model",
        "provider_unavailable",
        "unknown_error",
    }
)


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
            d["response_text"] = self.response_text[:MAX_RESPONSE_LENGTH]
        if self.error_reason:
            d["error_reason"] = self.error_reason
        if self.error_detail:
            d["error_detail"] = self.error_detail[:500]
        return d


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


def _pick_model(provider: "ModelProvider") -> str:
    """Choose the best model to use for a health-check call.

    Priority:
    1. provider.default_model (if set and non-empty)
    2. First entry in provider.models (if available)
    3. Empty string — for ACP providers that let the SDK choose the model.
    """
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


def run_health_check(provider: "ModelProvider") -> ProviderTestResult:
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
            model="",
            success=False,
            latency_ms=0.0,
            error_reason="provider_unavailable",
            error_detail=(
                "ACP providers must be tested via the live backend probe; "
                "the synchronous health-check path does not support ACP."
            ),
        )

    model = _pick_model(provider)
    if not model:
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model="",
            success=False,
            latency_ms=0.0,
            error_reason="invalid_model",
            error_detail=(
                "Provider has no models configured. "
                "Add at least one model to test it."
            ),
        )

    base_url = (provider.base_url or "").rstrip("/")
    if not base_url:
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=model,
            success=False,
            latency_ms=0.0,
            error_reason="provider_unavailable",
            error_detail="Provider has no base_url configured.",
        )

    api_key = provider.api_key or ""
    url = f"{base_url}/chat/completions"

    payload = {
        "model": model,
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
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=HEALTH_CHECK_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        latency_ms = (time.monotonic() - t0) * 1000.0

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return ProviderTestResult(
                provider_id=pid,
                provider_name=pname,
                model=model,
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
            model=model,
            success=True,
            latency_ms=latency_ms,
            response_text=response_text.strip()[:MAX_RESPONSE_LENGTH],
        )

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
            model=model,
            success=False,
            latency_ms=latency_ms,
            error_reason=reason,
            error_detail=f"HTTP {exc.code}: {error_body[:300]}",
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
            model=model,
            success=False,
            latency_ms=latency_ms,
            error_reason=reason,
            error_detail=str(exc),
        )

    except TimeoutError:
        latency_ms = (time.monotonic() - t0) * 1000.0
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=model,
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
            model=model,
            success=False,
            latency_ms=latency_ms,
            error_reason="provider_unavailable",
            error_detail=f"Network error: {exc}",
        )

    except Exception as exc:  # noqa: BLE001
        latency_ms = (time.monotonic() - t0) * 1000.0
        logger.warning("Provider health-check unexpected error for %s: %s", pname, exc)
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=model,
            success=False,
            latency_ms=latency_ms,
            error_reason="unknown_error",
            error_detail=str(exc)[:300],
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


async def run_acp_health_check(provider: "ModelProvider") -> ProviderTestResult:
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
    backend_name = getattr(provider, "backend", None) or "claude"

    backend_cls = get_backend(backend_name)
    if backend_cls is None:
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model="",
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
            model="",
            success=False,
            latency_ms=0.0,
            error_reason="missing_credentials",
            error_detail="; ".join(config_errors)[:500],
        )

    model = _pick_model(provider)  # "" lets the backend/SDK choose
    permission_mode = getattr(provider, "acp_permission_mode", None) or "default"
    # Flow the billing tier so the probe exercises the SAME execution
    # path real dispatch would (e.g. codex: subscription -> CLI/OAuth,
    # per_token -> in-process SDK).
    billing_model = (getattr(provider, "billing_model", None) or "per_token")
    workspace = tempfile.mkdtemp(prefix="oompah-acp-health-")

    options = AcpBackendOptions(
        workspace_path=workspace,
        prompt=_TEST_PROMPT,
        model=model or None,
        max_turns=1,
        tool_catalog=[],  # the 2+2 probe needs no tools
        permission_mode=permission_mode,
        turn_timeout_s=ACP_HEALTH_CHECK_TIMEOUT,
        on_event=None,
        billing_model=billing_model,
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
            model=model,
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
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=model,
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
        logger.warning(
            "ACP health-check unexpected error for %s (%s): %s",
            pname,
            backend_name,
            exc,
        )
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=model,
            success=False,
            latency_ms=(time.monotonic() - t0) * 1000.0,
            error_reason="provider_unavailable",
            error_detail=(
                f"ACP backend {backend_name!r} session crashed: {exc}"
            )[:500],
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    latency_ms = (time.monotonic() - t0) * 1000.0
    status = session.status
    response_text = "".join(response_parts).strip()

    if status == "succeeded":
        return ProviderTestResult(
            provider_id=pid,
            provider_name=pname,
            model=model,
            success=True,
            latency_ms=latency_ms,
            response_text=response_text[:MAX_RESPONSE_LENGTH],
        )

    reason, detail = _normalize_acp_error(status, session.last_error)
    return ProviderTestResult(
        provider_id=pid,
        provider_name=pname,
        model=model,
        success=False,
        latency_ms=latency_ms,
        response_text=response_text[:MAX_RESPONSE_LENGTH],
        error_reason=reason,
        error_detail=detail[:500],
    )
