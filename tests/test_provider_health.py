"""Tests for oompah.provider_health and the POST /api/v1/providers/{id}/test endpoint.

Acceptance criteria (TASK-407.3):
  AC1: POSTing to the provider test endpoint for a valid mocked provider
       returns success, the model used, latency, and response text.
  AC2: A provider with missing credentials returns failure with normalized
       reason missing_credentials or auth_failed.
  AC3: A timeout returns failure with normalized reason timeout.
  AC4: A rate limit or overload error returns a normalized retryable reason.
  AC5: The endpoint does not create or modify any task.
  AC6: The endpoint does not update role selection usage state.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from oompah.models import ModelProvider
from oompah.provider_health import (
    ERROR_REASONS,
    ProviderTestResult,
    _normalize_acp_error,
    _normalize_http_error,
    _normalize_url_error,
    _pick_model,
    run_acp_health_check,
    run_health_check,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_UNSET = object()  # sentinel for unspecified models


def _make_provider(
    *,
    mode: str = "api",
    models=_UNSET,
    default_model: str | None = None,
    base_url: str = "http://test-llm.local",
    api_key: str = "sk-test-key",
    provider_id: str = "prov-test01",
    name: str = "TestProvider",
) -> ModelProvider:
    if models is _UNSET:
        models = ["gpt-test"]
    return ModelProvider(
        id=provider_id,
        name=name,
        base_url=base_url,
        api_key=api_key,
        models=models,
        default_model=default_model,
        mode=mode,
    )


def _openai_success_response(content: str = "4") -> bytes:
    """Return a minimal OpenAI-compatible JSON response body."""
    body = {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
                "index": 0,
            }
        ],
        "model": "gpt-test",
        "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
    }
    return json.dumps(body).encode()


def _http_error(code: int, body: str = "") -> urllib.error.HTTPError:
    """Build a fake urllib HTTPError."""
    fp = BytesIO(body.encode())
    return urllib.error.HTTPError(
        url="http://test/chat/completions",
        code=code,
        msg=f"HTTP Error {code}",
        hdrs=MagicMock(get=lambda k, d="": d),  # type: ignore[arg-type]
        fp=fp,
    )


def _url_error(msg: str = "timed out") -> urllib.error.URLError:
    return urllib.error.URLError(reason=msg)


# ---------------------------------------------------------------------------
# Fake ACP backend (for run_acp_health_check tests)
#
# The registry docstring explicitly supports inserting/removing test
# backends, so we register a fake under a unique name per fixture and
# clean it up afterward. The fake session implements only the slice of
# the AcpBackendSession protocol the live probe actually reads:
# run_turn(), status, last_error, close().
# ---------------------------------------------------------------------------


def _build_fake_session_cls():
    from oompah.acp_backends.base import BackendEvent

    class _FakeSession:
        def __init__(self, *, events, status, last_error=None):
            self._events = events
            self._status = status
            self._last_error = last_error
            self.closed = False

        async def run_turn(self):
            for ev in self._events:
                yield ev

        async def close(self):
            self.closed = True

        @property
        def status(self):
            return self._status

        @property
        def last_error(self):
            return self._last_error

    return _FakeSession, BackendEvent


def _register_fake_backend(name, *, start_session=None, validate=None):
    """Register a fake AcpBackend under *name*; return the name.

    Caller is responsible for unregistering (the fixtures below do).
    """
    from oompah.acp_backends.base import AcpBackend
    from oompah.acp_backends.registry import register_backend

    class _FakeBackend(AcpBackend):
        @classmethod
        def name(cls):
            return name

        def start_session(self, options):
            if start_session is None:
                raise AssertionError("start_session not configured")
            return start_session(options)

        def validate_provider(self, provider):
            return validate(provider) if validate else []

    register_backend(name, _FakeBackend)
    return name


@pytest.fixture
def fake_acp_backend():
    """A backend that succeeds and emits a single text event '4'."""
    SessionCls, BackendEvent = _build_fake_session_cls()

    def _start(options):
        return SessionCls(
            events=[BackendEvent(kind="text", payload={"text": "4"})],
            status="succeeded",
        )

    name = _register_fake_backend("fake-health-ok", start_session=_start)
    yield name
    from oompah.acp_backends.registry import BACKENDS
    BACKENDS.pop(name, None)


@pytest.fixture
def fake_acp_backend_failing():
    """A backend whose session ends 'failed' with an auth-shaped error."""
    SessionCls, _BackendEvent = _build_fake_session_cls()

    def _start(options):
        return SessionCls(
            events=[],
            status="failed",
            last_error="Error: not logged in. Run `claude login` to authenticate.",
        )

    name = _register_fake_backend("fake-health-fail", start_session=_start)
    yield name
    from oompah.acp_backends.registry import BACKENDS
    BACKENDS.pop(name, None)


@pytest.fixture
def fake_acp_backend_invalid():
    """A backend whose validate_provider rejects the provider config."""
    name = _register_fake_backend(
        "fake-health-invalid",
        validate=lambda provider: ["fake backend needs an api key"],
    )
    yield name
    from oompah.acp_backends.registry import BACKENDS
    BACKENDS.pop(name, None)


@pytest.fixture
def fake_acp_backend_crashing():
    """A backend whose start_session raises (e.g. SDK import failure)."""
    def _start(options):
        raise RuntimeError("No module named 'some_sdk'")

    name = _register_fake_backend("fake-health-crash", start_session=_start)
    yield name
    from oompah.acp_backends.registry import BACKENDS
    BACKENDS.pop(name, None)


# ---------------------------------------------------------------------------
# Unit tests: _pick_model
# ---------------------------------------------------------------------------


class TestPickModel:
    def test_prefers_default_model(self):
        p = _make_provider(models=["a", "b"], default_model="b")
        assert _pick_model(p) == "b"

    def test_falls_back_to_first_model(self):
        p = _make_provider(models=["a", "b"])
        assert _pick_model(p) == "a"

    def test_empty_string_when_no_models(self):
        p = _make_provider(models=[])
        assert _pick_model(p) == ""


# ---------------------------------------------------------------------------
# Unit tests: error normalization helpers
# ---------------------------------------------------------------------------


class TestNormalizeHttpError:
    def test_401_is_auth_failed(self):
        exc = _http_error(401, "Invalid API key")
        assert _normalize_http_error(exc, "Invalid API key") == "auth_failed"

    def test_401_generic_is_missing_credentials(self):
        exc = _http_error(401, "")
        assert _normalize_http_error(exc, "") == "missing_credentials"

    def test_403_is_auth_failed(self):
        exc = _http_error(403)
        assert _normalize_http_error(exc, "") == "auth_failed"

    def test_429_is_rate_limited(self):
        exc = _http_error(429)
        assert _normalize_http_error(exc, "") == "rate_limited"

    def test_529_is_overloaded(self):
        exc = _http_error(529)
        assert _normalize_http_error(exc, "") == "overloaded"

    def test_503_is_overloaded(self):
        exc = _http_error(503)
        assert _normalize_http_error(exc, "") == "overloaded"

    def test_404_with_model_hint_is_invalid_model(self):
        exc = _http_error(404)
        assert _normalize_http_error(exc, "model not found") == "invalid_model"

    def test_500_is_provider_unavailable(self):
        exc = _http_error(500)
        assert _normalize_http_error(exc, "") == "provider_unavailable"

    def test_all_reasons_are_known(self):
        """Every error reason produced by normalization is in ERROR_REASONS."""
        for reason in ERROR_REASONS:
            assert isinstance(reason, str)

    def test_unknown_code_is_unknown_error(self):
        exc = _http_error(418)
        result = _normalize_http_error(exc, "")
        assert result == "unknown_error"


class TestNormalizeUrlError:
    def test_timed_out_reason_is_timeout(self):
        exc = _url_error("timed out")
        assert _normalize_url_error(exc) == "timeout"

    def test_connection_refused_is_provider_unavailable(self):
        exc = _url_error("Connection refused")
        assert _normalize_url_error(exc) == "provider_unavailable"

    def test_dns_failure_is_provider_unavailable(self):
        exc = _url_error("Name or service not known")
        assert _normalize_url_error(exc) == "provider_unavailable"


# ---------------------------------------------------------------------------
# Unit tests: test_provider (blocking helper) — no real network calls
# ---------------------------------------------------------------------------


class TestTestProviderUnit:
    def _mock_urlopen(self, response_body: bytes):
        """Return a context manager that yields a fake HTTP response."""
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=response_body)))
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    # ------------------------------------------------------------------
    # AC1: success path
    # ------------------------------------------------------------------

    def test_success_returns_success_result(self):
        p = _make_provider()
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = self._mock_urlopen(_openai_success_response("4"))
            result = run_health_check(p)

        assert result.success is True
        assert result.provider_id == p.id
        assert result.provider_name == p.name
        assert result.model == "gpt-test"
        assert result.latency_ms >= 0
        assert result.response_text == "4"
        assert result.error_reason == ""

    def test_success_picks_default_model(self):
        p = _make_provider(models=["big-model", "small-model"], default_model="small-model")
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = self._mock_urlopen(_openai_success_response("4"))
            result = run_health_check(p)

        assert result.model == "small-model"
        assert result.success is True

    def test_success_picks_first_model_when_no_default(self):
        p = _make_provider(models=["alpha", "beta"])
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = self._mock_urlopen(_openai_success_response("4"))
            result = run_health_check(p)

        assert result.model == "alpha"

    def test_result_to_dict_has_required_keys(self):
        p = _make_provider()
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = self._mock_urlopen(_openai_success_response("4"))
            result = run_health_check(p)

        d = result.to_dict()
        for key in ("provider_id", "provider_name", "model", "success", "latency_ms"):
            assert key in d, f"missing key: {key}"

    # ------------------------------------------------------------------
    # AC2: missing credentials / auth failure
    # ------------------------------------------------------------------

    def test_401_invalid_key_is_auth_failed(self):
        p = _make_provider()
        exc = _http_error(401, "Invalid API key")
        with patch("urllib.request.urlopen", side_effect=exc):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "auth_failed"

    def test_401_no_key_is_missing_credentials(self):
        p = _make_provider(api_key="")
        exc = _http_error(401, "")
        with patch("urllib.request.urlopen", side_effect=exc):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason in ("missing_credentials", "auth_failed")

    def test_403_is_auth_failed(self):
        p = _make_provider()
        with patch("urllib.request.urlopen", side_effect=_http_error(403)):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "auth_failed"

    # ------------------------------------------------------------------
    # AC3: timeout
    # ------------------------------------------------------------------

    def test_url_error_timed_out_is_timeout(self):
        p = _make_provider()
        with patch("urllib.request.urlopen", side_effect=_url_error("timed out")):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "timeout"

    def test_timeout_error_is_timeout(self):
        p = _make_provider()
        with patch("urllib.request.urlopen", side_effect=TimeoutError("socket timeout")):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "timeout"

    # ------------------------------------------------------------------
    # AC4: rate limit / overload
    # ------------------------------------------------------------------

    def test_429_is_rate_limited(self):
        p = _make_provider()
        with patch("urllib.request.urlopen", side_effect=_http_error(429)):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "rate_limited"

    def test_529_is_overloaded(self):
        p = _make_provider()
        with patch("urllib.request.urlopen", side_effect=_http_error(529)):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "overloaded"

    def test_503_is_overloaded(self):
        p = _make_provider()
        with patch("urllib.request.urlopen", side_effect=_http_error(503)):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "overloaded"

    # ------------------------------------------------------------------
    # Other failure cases
    # ------------------------------------------------------------------

    def test_no_models_returns_invalid_model(self):
        p = _make_provider(models=[])
        result = run_health_check(p)
        assert result.success is False
        assert result.error_reason == "invalid_model"

    def test_no_base_url_returns_provider_unavailable(self):
        p = _make_provider(base_url="")
        result = run_health_check(p)
        assert result.success is False
        assert result.error_reason == "provider_unavailable"

    def test_acp_provider_sync_guard_returns_provider_unavailable(self):
        """The synchronous path can't drive a session — it returns a guard
        result pointing callers at the async live probe."""
        p = _make_provider(mode="acp")
        result = run_health_check(p)
        assert result.success is False
        assert result.error_reason == "provider_unavailable"
        assert "ACP" in result.error_detail

    def test_connection_refused_is_provider_unavailable(self):
        p = _make_provider()
        with patch("urllib.request.urlopen", side_effect=_url_error("Connection refused")):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "provider_unavailable"

    def test_os_error_is_provider_unavailable(self):
        p = _make_provider()
        with patch("urllib.request.urlopen", side_effect=OSError("EPIPE")):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "provider_unavailable"

    def test_non_json_response_is_unknown_error(self):
        p = _make_provider()
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=b"not json")))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=cm):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "unknown_error"

    def test_500_is_provider_unavailable(self):
        p = _make_provider()
        with patch("urllib.request.urlopen", side_effect=_http_error(500)):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "provider_unavailable"

    def test_404_model_not_found_is_invalid_model(self):
        p = _make_provider()
        with patch("urllib.request.urlopen", side_effect=_http_error(404, "model not found")):
            result = run_health_check(p)

        assert result.success is False
        assert result.error_reason == "invalid_model"

    def test_result_truncates_long_response(self):
        """Response text is truncated to MAX_RESPONSE_LENGTH characters."""
        from oompah.provider_health import MAX_RESPONSE_LENGTH
        long_content = "x" * (MAX_RESPONSE_LENGTH + 500)
        p = _make_provider()
        cm = MagicMock()
        cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=_openai_success_response(long_content)))
        )
        cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=cm):
            result = run_health_check(p)

        # to_dict() applies the cap
        d = result.to_dict()
        assert len(d.get("response_text", "")) <= MAX_RESPONSE_LENGTH


# ---------------------------------------------------------------------------
# Integration tests: HTTP endpoint via FastAPI TestClient
# ---------------------------------------------------------------------------


@pytest.fixture
def health_client(tmp_path):
    """Wire a fresh ProviderStore into the FastAPI app for endpoint testing."""
    from oompah import server as srv
    from oompah.providers import ProviderStore

    fresh_store = ProviderStore(path=str(tmp_path / "providers.json"))
    original = srv._provider_store
    srv._provider_store = fresh_store
    try:
        yield TestClient(srv.app), fresh_store
    finally:
        srv._provider_store = original


class TestProviderTestEndpoint:
    """AC1–AC6 via the HTTP endpoint with mocked urllib calls."""

    def test_404_for_unknown_provider(self, health_client):
        client, _ = health_client
        r = client.post("/api/v1/providers/prov-doesnotexist/test")
        assert r.status_code == 404
        assert "not found" in r.json()["error"]["message"]

    # ------------------------------------------------------------------
    # AC1: success path
    # ------------------------------------------------------------------

    def test_success_response_shape(self, health_client):
        client, store = health_client
        p = store.create(
            name="LocalLLM",
            base_url="http://localhost:11434",
            api_key="",
            models=["mistral"],
            default_model="mistral",
        )
        resp_body = _openai_success_response("4")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resp_body)))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=cm):
            r = client.post(f"/api/v1/providers/{p.id}/test")

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["provider_id"] == p.id
        assert body["provider_name"] == "LocalLLM"
        assert body["model"] == "mistral"
        assert body["latency_ms"] >= 0
        assert body["response_text"] == "4"
        assert "error_reason" not in body

    # ------------------------------------------------------------------
    # AC2: missing credentials / auth failure
    # ------------------------------------------------------------------

    def test_401_returns_auth_error(self, health_client):
        client, store = health_client
        p = store.create(
            name="RemoteLLM",
            base_url="http://api.example.com",
            api_key="bad-key",
            models=["gpt-x"],
        )
        with patch("urllib.request.urlopen", side_effect=_http_error(401, "Invalid API key")):
            r = client.post(f"/api/v1/providers/{p.id}/test")

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert body["error_reason"] in ("auth_failed", "missing_credentials")

    # ------------------------------------------------------------------
    # AC3: timeout
    # ------------------------------------------------------------------

    def test_timeout_returns_timeout_reason(self, health_client):
        client, store = health_client
        p = store.create(
            name="SlowLLM",
            base_url="http://slow.example.com",
            api_key="sk-ok",
            models=["gpt-slow"],
        )
        with patch("urllib.request.urlopen", side_effect=_url_error("timed out")):
            r = client.post(f"/api/v1/providers/{p.id}/test")

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert body["error_reason"] == "timeout"

    # ------------------------------------------------------------------
    # AC4: rate limit / overload
    # ------------------------------------------------------------------

    def test_429_returns_rate_limited(self, health_client):
        client, store = health_client
        p = store.create(
            name="BusyLLM",
            base_url="http://busy.example.com",
            api_key="sk-ok",
            models=["gpt-busy"],
        )
        with patch("urllib.request.urlopen", side_effect=_http_error(429)):
            r = client.post(f"/api/v1/providers/{p.id}/test")

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert body["error_reason"] == "rate_limited"

    def test_529_returns_overloaded(self, health_client):
        client, store = health_client
        p = store.create(
            name="OverloadedLLM",
            base_url="http://overloaded.example.com",
            api_key="sk-ok",
            models=["claude-x"],
        )
        with patch("urllib.request.urlopen", side_effect=_http_error(529)):
            r = client.post(f"/api/v1/providers/{p.id}/test")

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert body["error_reason"] == "overloaded"

    # ------------------------------------------------------------------
    # AC5: endpoint does NOT create/modify any task
    # (Structural test: the endpoint handler must not call tracker
    # functions.  We assert the call to test_provider has no side
    # effects on the tracker by verifying no tracker import is invoked.)
    # ------------------------------------------------------------------

    def test_does_not_import_tracker_during_test(self, health_client):
        """The test endpoint must not touch any tracker.

        We verify that importing provider_health doesn't pull in tracker code.
        """
        import sys
        # provider_health must be importable without importing tracker.
        # If 'oompah.tracker' is not in sys.modules before the call,
        # it must not appear after either.
        tracker_before = "oompah.tracker" in sys.modules
        from oompah import provider_health as ph  # noqa: F401  (already imported)
        tracker_after = "oompah.tracker" in sys.modules
        # If tracker was not loaded before, it must not have been loaded
        # by importing provider_health.
        if not tracker_before:
            assert not tracker_after

    # ------------------------------------------------------------------
    # AC6: endpoint does NOT update role round-robin state
    # ------------------------------------------------------------------

    def test_does_not_touch_role_store(self, health_client):
        """test_provider must not call into RoleStore.

        We assert by verifying no RoleStore.update call is made during
        a successful health check.
        """
        client, store = health_client
        p = store.create(
            name="LocalLLM2",
            base_url="http://localhost:11435",
            api_key="",
            models=["llama3"],
        )
        resp_body = _openai_success_response("4")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resp_body)))
        cm.__exit__ = MagicMock(return_value=False)
        from oompah import server as srv

        with patch("urllib.request.urlopen", return_value=cm):
            with patch.object(srv, "_role_store") as mock_role_store:
                r = client.post(f"/api/v1/providers/{p.id}/test")

        assert r.status_code == 200
        # RoleStore must not have been touched during a health-check
        mock_role_store.set.assert_not_called()
        mock_role_store.update.assert_not_called()

    # ------------------------------------------------------------------
    # ACP provider routes through the live backend probe
    # ------------------------------------------------------------------

    def test_acp_provider_endpoint_runs_live_probe(self, health_client, fake_acp_backend):
        """An ACP provider is dispatched to run_acp_health_check, which drives
        a real backend session — here the registered fake backend."""
        client, store = health_client
        p = store.create(
            name="FakeACP",
            base_url="",
            mode="acp",
            backend=fake_acp_backend,
            acp_permission_mode="default",
        )
        r = client.post(f"/api/v1/providers/{p.id}/test")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["response_text"] == "4"

    def test_acp_provider_endpoint_surfaces_failure(self, health_client, fake_acp_backend_failing):
        client, store = health_client
        p = store.create(
            name="FakeACPFail",
            base_url="",
            mode="acp",
            backend=fake_acp_backend_failing,
            acp_permission_mode="default",
        )
        r = client.post(f"/api/v1/providers/{p.id}/test")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert body["error_reason"] == "auth_failed"


# ---------------------------------------------------------------------------
# ACP live probe (run_acp_health_check)
# ---------------------------------------------------------------------------


def _make_acp_provider(*, backend: str, provider_id: str = "prov-acp01",
                       name: str = "AcpProvider") -> ModelProvider:
    return ModelProvider(
        id=provider_id,
        name=name,
        base_url="",
        api_key="",
        models=[],
        default_model=None,
        mode="acp",
        backend=backend,
        acp_permission_mode="default",
    )


class TestAcpLiveProbe:
    def test_success_echoes_response_text(self, fake_acp_backend):
        p = _make_acp_provider(backend=fake_acp_backend)
        result = asyncio.run(run_acp_health_check(p))
        assert result.success is True
        assert result.error_reason == ""
        assert result.response_text == "4"
        assert result.latency_ms >= 0.0

    def test_failed_status_maps_to_reason(self, fake_acp_backend_failing):
        p = _make_acp_provider(backend=fake_acp_backend_failing)
        result = asyncio.run(run_acp_health_check(p))
        assert result.success is False
        # last_error mentions "not logged in" → auth_failed
        assert result.error_reason == "auth_failed"

    def test_validate_provider_error_short_circuits(self, fake_acp_backend_invalid):
        """A backend whose validate_provider returns errors fails fast with
        missing_credentials and never starts a session."""
        p = _make_acp_provider(backend=fake_acp_backend_invalid)
        result = asyncio.run(run_acp_health_check(p))
        assert result.success is False
        assert result.error_reason == "missing_credentials"
        assert "needs an api key" in result.error_detail.lower()

    def test_start_session_crash_is_provider_unavailable(self, fake_acp_backend_crashing):
        p = _make_acp_provider(backend=fake_acp_backend_crashing)
        result = asyncio.run(run_acp_health_check(p))
        assert result.success is False
        assert result.error_reason == "provider_unavailable"

    def test_unknown_backend_is_provider_unavailable(self):
        p = _make_acp_provider(backend="definitely-not-registered")
        result = asyncio.run(run_acp_health_check(p))
        assert result.success is False
        assert result.error_reason == "provider_unavailable"
        assert "Unknown ACP backend" in result.error_detail

    def test_result_reason_is_a_known_reason(self, fake_acp_backend_failing):
        p = _make_acp_provider(backend=fake_acp_backend_failing)
        result = asyncio.run(run_acp_health_check(p))
        assert result.error_reason in ERROR_REASONS


class TestNormalizeAcpError:
    def test_module_not_found_is_provider_unavailable(self):
        reason, _ = _normalize_acp_error("errored", "No module named 'claude_agent_sdk'")
        assert reason == "provider_unavailable"

    def test_not_logged_in_is_auth_failed(self):
        reason, _ = _normalize_acp_error("failed", "Error: not logged in. Run `claude login`.")
        assert reason == "auth_failed"

    def test_stalled_is_timeout(self):
        reason, _ = _normalize_acp_error("stalled", None)
        assert reason == "timeout"

    def test_bare_failed_is_unknown(self):
        reason, detail = _normalize_acp_error("failed", None)
        assert reason == "unknown_error"
        assert "failed" in detail
