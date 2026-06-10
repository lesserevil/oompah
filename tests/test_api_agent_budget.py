"""Tests for the context-window budgeting helpers in oompah.api_agent.

Covers oompah-zlz_2-px3: chat-completions calls were 400ing because
``max_tokens`` was hardcoded at 32768 with no awareness of the model's
total window. The fix: estimate the outgoing payload, prune oldest
round-trips, and clamp ``max_tokens`` to the remaining headroom.
"""

from __future__ import annotations

import asyncio
import json
import os
import time

import pytest

from oompah.api_agent import (
    _DEFAULT_MAX_OUTPUT_TOKENS,
    _MIN_MAX_OUTPUT_TOKENS,
    _TOKENIZER_SAFETY_MARGIN,
    _estimate_tokens,
    _prune_messages_to_fit,
)


def _msg(role: str, content: str = "x", **extra) -> dict:
    m = {"role": role, "content": content}
    m.update(extra)
    return m


class TestEstimateTokens:
    def test_grows_with_content_size(self):
        small = _estimate_tokens([{"role": "user", "content": "hi"}])
        big = _estimate_tokens([{"role": "user", "content": "x" * 4000}])
        assert big > small
        # ~4 chars per token, with JSON serialization overhead.
        assert big >= 1000

    def test_minimum_one_token(self):
        assert _estimate_tokens({}) >= 1

    def test_handles_unjsonable_via_str(self):
        # Falls back to str() on TypeError; should still return a positive int.
        class Weird:
            pass
        assert _estimate_tokens(Weird()) >= 1


class TestPruneMessagesToFit:
    def _build_history(self, n_round_trips: int, content_size: int = 200) -> list[dict]:
        """system + initial user + n round-trips of (assistant + tool)."""
        msgs = [
            _msg("system", "You are a helpful agent."),
            _msg("user", "Initial task: " + "x" * content_size),
        ]
        for i in range(n_round_trips):
            msgs.append(_msg(
                "assistant",
                "thinking...",
                tool_calls=[{
                    "id": f"call_{i}",
                    "function": {"name": "run_command", "arguments": '{"cmd": "ls"}'},
                }],
            ))
            msgs.append({
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": "y" * content_size,
            })
        return msgs

    def test_no_pruning_when_already_fits(self):
        msgs = self._build_history(n_round_trips=2)
        snapshot = list(msgs)
        removed = _prune_messages_to_fit(msgs, [], max_input_tokens=10_000_000)
        assert removed == 0
        assert msgs == snapshot

    def test_prunes_until_fits(self):
        # Build a history that's too big to fit in a tiny budget.
        msgs = self._build_history(n_round_trips=20, content_size=500)
        original_len = len(msgs)
        # Force the budget to ~ the size of the head plus a tiny margin.
        head = [msgs[0], msgs[1]]
        target = _estimate_tokens({"messages": head, "tools": []}) + 100
        removed = _prune_messages_to_fit(msgs, [], max_input_tokens=target)
        assert removed > 0
        assert removed == original_len - len(msgs)
        # System and initial user are always preserved.
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_never_drops_system_or_initial_user(self):
        msgs = self._build_history(n_round_trips=5)
        # Even with an unsatisfiable budget, the head must survive.
        _prune_messages_to_fit(msgs, [], max_input_tokens=1)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_drops_assistant_with_its_tool_responses(self):
        """Pruning must remove an assistant + its tool responses together —
        otherwise we'd leave a tool message with a tool_call_id whose owning
        assistant is gone, which the API rejects."""
        msgs = self._build_history(n_round_trips=3)
        # Sanity: structure is system, user, [assistant, tool] x 3.
        assert [m["role"] for m in msgs] == [
            "system", "user",
            "assistant", "tool",
            "assistant", "tool",
            "assistant", "tool",
        ]
        head = [msgs[0], msgs[1]]
        # Ask for room that fits the head + exactly one round trip.
        budget = _estimate_tokens({
            "messages": head + [msgs[2], msgs[3]],
            "tools": [],
        }) + 50
        _prune_messages_to_fit(msgs, [], max_input_tokens=budget)
        # No orphaned tool message (every tool must follow an assistant).
        for i, m in enumerate(msgs):
            if m["role"] == "tool":
                assert i > 0 and msgs[i - 1]["role"] in ("assistant", "tool"), (
                    f"orphan tool message at index {i}: {msgs}"
                )

    def test_returns_zero_when_max_input_nonpositive(self):
        msgs = [_msg("system"), _msg("user")]
        assert _prune_messages_to_fit(msgs, [], max_input_tokens=0) == 0
        assert _prune_messages_to_fit(msgs, [], max_input_tokens=-5) == 0

    def test_assistant_without_tool_followers_drops_alone(self):
        """A plain assistant reply (no tool_calls, no following tool messages)
        is one droppable unit on its own."""
        msgs = [
            _msg("system"),
            _msg("user", "task"),
            _msg("assistant", "first reply"),
            _msg("user", "follow up"),
            _msg("assistant", "second reply"),
        ]
        head = [msgs[0], msgs[1]]
        budget = _estimate_tokens({"messages": head, "tools": []}) + 50
        _prune_messages_to_fit(msgs, [], max_input_tokens=budget)
        # Both assistants should have been dropped (and the orphan user with them
        # if pruning gets that aggressive). At minimum, system + initial user
        # remain.
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert msgs[1]["content"] == "task"


class TestSessionConstruction:
    """ApiAgentSession should accept and store ``model_max_context``."""

    def test_default_is_none(self, tmp_path):
        from oompah.api_agent import ApiAgentSession
        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        assert s.model_max_context is None

    def test_passes_through(self, tmp_path):
        from oompah.api_agent import ApiAgentSession
        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
            model_max_context=196608,
        )
        assert s.model_max_context == 196608


class TestCallApiBudget:
    """End-to-end check that _call_api budgets correctly. We patch the
    HTTP layer to capture the outgoing payload rather than actually
    calling a model."""

    def test_unbudgeted_session_uses_default_max_tokens(
        self, tmp_path, monkeypatch,
    ):
        captured = {}

        def fake_post(url, headers, body, ssl_ctx):
            captured["payload"] = json.loads(body)
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        from oompah.api_agent import ApiAgentSession
        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        asyncio.run(s._call_api([_msg("system"), _msg("user", "hi")]))
        assert captured["payload"]["max_tokens"] == _DEFAULT_MAX_OUTPUT_TOKENS

    def test_budgeted_session_clamps_max_tokens_when_history_is_huge(
        self, tmp_path, monkeypatch,
    ):
        captured = {}

        def fake_post(url, headers, body, ssl_ctx):
            captured["payload"] = json.loads(body)
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        from oompah.api_agent import ApiAgentSession
        # Tight 8K-token window: even with a small prompt, max_tokens
        # must be reduced from the default 32768 to fit the window minus
        # the prompt and safety margin.
        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
            model_max_context=8192,
        )
        msgs = [_msg("system", "agent"), _msg("user", "do a thing")]
        asyncio.run(s._call_api(msgs))
        mt = captured["payload"]["max_tokens"]
        assert mt < _DEFAULT_MAX_OUTPUT_TOKENS
        assert mt >= _MIN_MAX_OUTPUT_TOKENS

    def test_budgeted_session_prunes_oversized_history(
        self, tmp_path, monkeypatch,
    ):
        captured = {}

        def fake_post(url, headers, body, ssl_ctx):
            captured["payload"] = json.loads(body)
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        from oompah.api_agent import ApiAgentSession
        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
            model_max_context=4096,  # very tight
        )
        # Build history that overflows the window.
        msgs = [_msg("system", "agent"), _msg("user", "task")]
        for i in range(20):
            msgs.append(_msg(
                "assistant", "thinking",
                tool_calls=[{
                    "id": f"c{i}",
                    "function": {"name": "x", "arguments": "{}"},
                }],
            ))
            msgs.append({
                "role": "tool",
                "tool_call_id": f"c{i}",
                "content": "y" * 1000,
            })
        original_len = len(msgs)
        asyncio.run(s._call_api(msgs))
        # Pruning happened in place.
        assert len(msgs) < original_len
        # System + initial user preserved.
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        # max_tokens was clamped to fit.
        mt = captured["payload"]["max_tokens"]
        assert mt >= _MIN_MAX_OUTPUT_TOKENS


# ---------------------------------------------------------------------------
# Per-dispatch JSONL agent logging — captures every request, response,
# and activity event so users can audit exactly what each agent received
# and produced. One file per dispatch.
# ---------------------------------------------------------------------------

class TestAgentLogging:
    def test_no_log_when_log_path_none(self, tmp_path, monkeypatch):
        """Backwards-compat: a session without log_path writes no files."""
        captured = {}

        def fake_post(url, headers, body, ssl_ctx):
            captured["payload"] = json.loads(body)
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        from oompah.api_agent import ApiAgentSession
        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        asyncio.run(s._call_api([_msg("system"), _msg("user", "hi")]))
        # Nothing should have been written.
        files = list(tmp_path.iterdir())
        assert all(not f.name.endswith(".jsonl") for f in files), files

    def test_call_api_writes_request_and_response(self, tmp_path, monkeypatch):
        log_path = tmp_path / "agent.jsonl"

        def fake_post(url, headers, body, ssl_ctx):
            return {
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            }

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        from oompah.api_agent import ApiAgentSession
        s = ApiAgentSession(
            base_url="http://x", api_key="secret-redacted", model="m",
            workspace_path=str(tmp_path),
            log_path=str(log_path),
        )
        asyncio.run(s._call_api([_msg("system"), _msg("user", "hi")]))

        assert log_path.exists()
        records = [json.loads(l) for l in log_path.read_text().splitlines()]
        kinds = [r["kind"] for r in records]
        assert "request" in kinds
        assert "response" in kinds

        req = next(r for r in records if r["kind"] == "request")
        resp = next(r for r in records if r["kind"] == "response")
        # Request has the full payload — messages and model.
        assert req["payload"]["model"] == "m"
        assert req["payload"]["messages"][1]["content"] == "hi"
        # Response has the full body.
        assert resp["body"]["choices"][0]["message"]["content"] == "ok"
        assert resp["body"]["usage"]["total_tokens"] == 15

    def test_log_never_contains_api_key(self, tmp_path, monkeypatch):
        """API keys must never appear in the JSONL."""
        log_path = tmp_path / "agent.jsonl"

        def fake_post(url, headers, body, ssl_ctx):
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        from oompah.api_agent import ApiAgentSession
        sentinel_key = "should-never-appear-in-the-log-12345"
        s = ApiAgentSession(
            base_url="http://x", api_key=sentinel_key, model="m",
            workspace_path=str(tmp_path),
            log_path=str(log_path),
        )
        asyncio.run(s._call_api([_msg("system"), _msg("user", "hi")]))
        contents = log_path.read_text()
        assert sentinel_key not in contents, "api_key leaked to agent log"

    def test_empty_api_key_omits_authorization_header(self, tmp_path, monkeypatch):
        """No-auth OpenAI-compatible gateways should not receive Bearer ''."""
        captured = {}

        def fake_post(url, headers, body, ssl_ctx):
            captured["headers"] = headers
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        from oompah.api_agent import ApiAgentSession

        s = ApiAgentSession(
            base_url="http://x",
            api_key="",
            model="m",
            workspace_path=str(tmp_path),
        )
        asyncio.run(s._call_api([_msg("system"), _msg("user", "hi")]))

        assert "Authorization" not in captured["headers"]

    def test_nonempty_api_key_sends_authorization_header(self, tmp_path, monkeypatch):
        """Configured API keys are still sent to providers that require auth."""
        captured = {}

        def fake_post(url, headers, body, ssl_ctx):
            captured["headers"] = headers
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        from oompah.api_agent import ApiAgentSession

        s = ApiAgentSession(
            base_url="http://x",
            api_key="sk-present",
            model="m",
            workspace_path=str(tmp_path),
        )
        asyncio.run(s._call_api([_msg("system"), _msg("user", "hi")]))

        assert captured["headers"]["Authorization"] == "Bearer sk-present"

    def test_logging_failure_does_not_break_call(self, tmp_path, monkeypatch):
        """If the log file can't be written, the agent must still proceed."""

        def fake_post(url, headers, body, ssl_ctx):
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        from oompah.api_agent import ApiAgentSession
        # Point the log at a path where the parent doesn't exist AND can't
        # be created (use a path under an existing file). Use an unwritable
        # location instead to be portable.
        bad_path = "/dev/null/cannot/create/here.jsonl"
        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
            log_path=bad_path,
        )
        # Must not raise.
        result = asyncio.run(s._call_api([_msg("system"), _msg("user", "hi")]))
        assert result["choices"][0]["message"]["content"] == "ok"


# ---------------------------------------------------------------------------
# Transient-error retries: 5xx, connection refused, and other network blips
# should be retried inside _call_api rather than killing the worker, which
# would force the orchestrator's heavier-weight dispatch retry that
# rebuilds the whole conversation.
# ---------------------------------------------------------------------------

import urllib.error as _ue


class TestHttpPostClassification:
    """_http_post must distinguish retryable from permanent failures."""

    def test_5xx_raises_transient_server_error(self, monkeypatch):
        from oompah.api_agent import _http_post, TransientServerError

        class FakeReader:
            def read(self):
                return b"EngineCore boom"

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=500,
                msg="Internal Server Error",
                hdrs={}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert excinfo.value.status_code == 500

    def test_url_error_raises_transient_server_error(self, monkeypatch):
        from oompah.api_agent import _http_post, TransientServerError

        def fake_urlopen(*a, **kw):
            raise _ue.URLError(reason="[Errno 61] Connection refused")
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert excinfo.value.status_code is None
        assert "Connection refused" in str(excinfo.value)

    def test_timeout_error_raises_transient_server_error(self, monkeypatch):
        """A read/connect timeout is a URLError like connection refused —
        it must be wrapped in TransientServerError so _call_api retries it."""
        from oompah.api_agent import _http_post, TransientServerError

        def fake_urlopen(*a, **kw):
            raise _ue.URLError(reason="timed out")
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert excinfo.value.status_code is None
        assert "timed out" in str(excinfo.value)

    def test_429_still_raises_rate_limit_error(self, monkeypatch):
        from oompah.api_agent import _http_post, RateLimitError

        class FakeReader:
            def read(self):
                return b"slow down"

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=429, msg="Too Many",
                hdrs={"Retry-After": "5"}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(RateLimitError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert excinfo.value.retry_after == 5.0

    def test_4xx_other_than_429_is_permanent(self, monkeypatch):
        from oompah.api_agent import _http_post, RetryableError

        class FakeReader:
            def read(self):
                return b"bad request"

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=400, msg="Bad",
                hdrs={}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(Exception) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        # Must NOT be retryable — the request is wrong, retrying won't help.
        assert not isinstance(excinfo.value, RetryableError), (
            f"4xx must not be retryable: {excinfo.type}"
        )

    def test_socket_not_connected_raises_transient_server_error(self, monkeypatch):
        """oompah-zlz_2-ovt: macOS Errno 57 (ENOTCONN, "Socket is not
        connected") raised by the OS during ``resp.read()`` after
        ``urlopen`` returned must be wrapped as TransientServerError so
        the existing retry loop kicks in instead of failing the whole
        agent task on a transient socket blip."""
        from oompah.api_agent import _http_post, TransientServerError

        def fake_urlopen(*a, **kw):
            # Plain OSError, NOT urllib.error.URLError. URLError is a
            # subclass of OSError, but the bug is that a *raw* OSError
            # raised by the socket layer (e.g. during resp.read()) is
            # NOT wrapped in URLError and therefore escapes the URLError
            # handler.
            raise OSError(57, "Socket is not connected")
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert excinfo.value.status_code is None
        # Errno is preserved so operators can correlate logs with OS
        # errors. The full bug-report message is reconstructable.
        assert "Errno 57" in str(excinfo.value)
        assert "Socket is not connected" in str(excinfo.value)

    def test_connection_reset_raises_transient_server_error(self, monkeypatch):
        """ConnectionResetError (errno 104, ECONNRESET on Linux) is a
        subclass of OSError and is the Linux cousin of the macOS
        ENOTCONN bug. It must also be retryable."""
        from oompah.api_agent import _http_post, TransientServerError

        def fake_urlopen(*a, **kw):
            raise ConnectionResetError(104, "Connection reset by peer")
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert excinfo.value.status_code is None
        assert "Connection reset" in str(excinfo.value)

    def test_broken_pipe_raises_transient_server_error(self, monkeypatch):
        """BrokenPipeError (EPIPE, errno 32) is also an OSError subclass
        and must be retryable for the same reason."""
        from oompah.api_agent import _http_post, TransientServerError

        def fake_urlopen(*a, **kw):
            raise BrokenPipeError(32, "Broken pipe")
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError):
            _http_post("http://x", {}, b"{}", None)

    def test_url_error_still_wins_over_oserror_handler(self, monkeypatch):
        """URLError extends OSError, but the URLError handler must run
        first (more specific). The new OSError handler must NOT shadow
        the existing URLError contract — connection-refused failures
        should still surface 'URL error' phrasing for log-grep
        compatibility."""
        from oompah.api_agent import _http_post, TransientServerError

        def fake_urlopen(*a, **kw):
            raise _ue.URLError(reason="[Errno 61] Connection refused")
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        # The URLError branch tags the message with "URL error", not
        # "Socket error". Order-of-handlers regression guard.
        assert "URL error" in str(excinfo.value)
        assert "Socket error" not in str(excinfo.value)

    def test_oserror_during_resp_read_raises_transient_server_error(self, monkeypatch):
        """oompah-zlz_2-bsg: the actual production failure mode is OSError
        raised during ``resp.read()`` AFTER ``urlopen`` has already
        returned, not from ``urlopen`` itself. The previous test
        (``test_socket_not_connected_raises_transient_server_error``)
        only simulates ``urlopen`` raising — this test simulates a
        successful ``urlopen`` with a response object whose ``.read()``
        raises ENOTCONN, which is what happens when the remote tears
        down the TLS connection mid-stream on macOS. The OSError handler
        must catch it just the same."""
        from oompah.api_agent import _http_post, TransientServerError

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def read(self):
                # Real production scenario: urlopen returned, the with
                # block entered, then resp.read() blew up because the
                # peer closed the TLS connection mid-stream.
                raise OSError(57, "Socket is not connected")

        def fake_urlopen(*a, **kw):
            return FakeResponse()
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert excinfo.value.status_code is None
        assert "Errno 57" in str(excinfo.value)
        assert "Socket is not connected" in str(excinfo.value)
        # Must use the "Socket error" prefix from the OSError branch,
        # not "URL error" — proves the right handler caught it.
        assert "Socket error" in str(excinfo.value)

    def test_oserror_during_with_exit_raises_transient_server_error(self, monkeypatch):
        """Adjacent edge case: ``resp.read()`` succeeds and ``json.loads``
        succeeds, but the context manager's ``__exit__`` raises OSError
        when closing the connection (the peer already tore it down).
        This OSError ALSO must be caught and wrapped, otherwise it
        propagates raw out of ``_http_post`` and shows up as
        ``ApiAgentSession.run_task failed: [Errno 57] Socket is not
        connected`` — exactly the bug-report shape that triggered
        oompah-zlz_2-bsg."""
        from oompah.api_agent import _http_post, TransientServerError

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                # Connection close on a torn-down socket. macOS ENOTCONN.
                raise OSError(57, "Socket is not connected")
            def read(self):
                return b'{"choices": []}'

        def fake_urlopen(*a, **kw):
            return FakeResponse()
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert "Errno 57" in str(excinfo.value)


class TestHttpPost401AuthErrorClassifiedAsTransient:
    """oompah-zlz_2-e6t5: HTTP 401 (authentication error) must be
    treated as a retryable TransientServerError — not a non-retryable
    RuntimeError — so that _call_api's 5-attempt retry loop fires on
    transient auth failures (token expiry / identity-service glitch).
    This prevents error_watcher from filing a new bug bead every tick
    on what is typically an operator-fixable config issue."""

    def test_401_raises_transient_server_error(self, monkeypatch):
        """A 401 must be wrapped as TransientServerError so normal
        retry logic handles it, AND status_code must be 401 so callers
        can distinguish it from 5xx."""
        from oompah.api_agent import _http_post, TransientServerError

        class FakeReader:
            def read(self):
                return b'{"error":{"message":"Authentication Error","code":"401"}}'

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=401, msg="Unauthorized",
                hdrs={}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert excinfo.value.status_code == 401
        assert "401" in str(excinfo.value)
        assert "Authentication Error" in str(excinfo.value)

    def test_401_error_body_is_preserved(self, monkeypatch):
        """The full auth-error response body must be in the exception
        message so operators can diagnose what went wrong without
        digging through logs."""
        from oompah.api_agent import _http_post, TransientServerError

        class FakeReader:
            def read(self):
                return b'{"error":{"message":"Server disconnected without sending a response.","type":"auth_error","code":"401"}}'

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=401, msg="Unauthorized",
                hdrs={}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert "Server disconnected" in str(excinfo.value)

    def test_401_not_rate_limit_error(self, monkeypatch):
        """401 must NOT be routed as RateLimitError — they have different
        retry semantics (no Retry-After on 401)."""
        from oompah.api_agent import _http_post, RateLimitError

        class FakeReader:
            def read(self):
                return b"unauthorized"

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=401, msg="Unauthorized",
                hdrs={}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(Exception) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert not isinstance(excinfo.value, RateLimitError)

    def test_400_still_permanent(self, monkeypatch):
        """Ensure the 401 carve-out doesn't accidentally make ALL 4xx
        retryable. 400 is still a permanent RuntimeError."""
        from oompah.api_agent import _http_post, RetryableError

        class FakeReader:
            def read(self):
                return b'{"error":"bad request"}'

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=400, msg="Bad Request",
                hdrs={}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(Exception) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        # Must NOT be retryable — the request body is wrong.
        assert not isinstance(excinfo.value, RetryableError), (
            f"400 must not be retryable: {excinfo.type}"
        )


class TestHttpPost404LitellmNotFoundClassifiedAsTransient:
    """TASK-471: HTTP 404 from litellm's model router (``litellm.NotFoundError``
    with ``Received Model Group=``) must be classified as TransientServerError
    so the in-session retry loop can recover and run_task logs at WARNING rather
    than ERROR (which would trigger error_watcher to create a new bug task)."""

    _NVIDIA_NOT_FOUND_BODY = (
        '{"error":{"message":"litellm.NotFoundError: NotFoundError: OpenAIException'
        ' - . Received Model Group=nvidia/nvidia/nemotron-3-ultra\\n'
        'Available Model Group Fallbacks=None","type":null,"param":null,"code":"404"}}'
    )

    def test_litellm_not_found_404_raises_transient_server_error(self, monkeypatch):
        """A 404 whose body contains litellm.NotFoundError + Received Model Group=
        must be wrapped as TransientServerError so normal retry logic fires."""
        from oompah.api_agent import _http_post, TransientServerError

        class FakeReader:
            def read(self):
                return TestHttpPost404LitellmNotFoundClassifiedAsTransient._NVIDIA_NOT_FOUND_BODY.encode()

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=404, msg="Not Found",
                hdrs={}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert excinfo.value.status_code == 404
        assert "404" in str(excinfo.value)
        assert "litellm.NotFoundError" in str(excinfo.value)

    def test_litellm_not_found_404_status_code_is_preserved(self, monkeypatch):
        """status_code must be 404 so callers can distinguish it from 5xx."""
        from oompah.api_agent import _http_post, TransientServerError

        class FakeReader:
            def read(self):
                return TestHttpPost404LitellmNotFoundClassifiedAsTransient._NVIDIA_NOT_FOUND_BODY.encode()

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=404, msg="Not Found",
                hdrs={}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(TransientServerError) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert excinfo.value.status_code == 404

    def test_plain_404_without_litellm_signature_is_permanent(self, monkeypatch):
        """A plain 404 (e.g. wrong URL, missing resource) must still be a
        permanent RuntimeError — only the litellm model-router pattern is
        treated as transient."""
        from oompah.api_agent import _http_post, RetryableError

        class FakeReader:
            def read(self):
                return b'{"error":"Not Found"}'

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=404, msg="Not Found",
                hdrs={}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(Exception) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        # Plain 404 must NOT be retryable.
        assert not isinstance(excinfo.value, RetryableError), (
            f"plain 404 must not be retryable: {excinfo.type}"
        )

    def test_404_with_only_one_indicator_is_permanent(self, monkeypatch):
        """Both indicators must be present to trigger the transient path.
        A body with only 'litellm.NotFoundError' but no 'Received Model Group='
        is still a permanent error."""
        from oompah.api_agent import _http_post, RetryableError

        class FakeReader:
            def read(self):
                return b'{"error":{"message":"litellm.NotFoundError: something else"}}'

        def fake_urlopen(*a, **kw):
            err = _ue.HTTPError(
                url="http://x", code=404, msg="Not Found",
                hdrs={}, fp=FakeReader(),
            )
            raise err
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        with pytest.raises(Exception) as excinfo:
            _http_post("http://x", {}, b"{}", None)
        assert not isinstance(excinfo.value, RetryableError), (
            f"partial-match 404 must not be retryable: {excinfo.type}"
        )

    def test_is_litellm_not_found_error_true_for_nvidia_pattern(self):
        """_is_litellm_not_found_error must return True for the exact NVIDIA
        litellm error body seen in TASK-471."""
        from oompah.api_agent import _is_litellm_not_found_error

        body = TestHttpPost404LitellmNotFoundClassifiedAsTransient._NVIDIA_NOT_FOUND_BODY
        assert _is_litellm_not_found_error(body) is True

    def test_is_litellm_not_found_error_false_for_plain_404(self):
        """Plain 404 bodies without litellm signature must return False."""
        from oompah.api_agent import _is_litellm_not_found_error

        assert _is_litellm_not_found_error('{"error":"Not Found"}') is False
        assert _is_litellm_not_found_error("") is False

    def test_is_litellm_not_found_error_false_for_context_window_error(self):
        """Context-window error body must NOT be mistaken for a not-found error."""
        from oompah.api_agent import _is_litellm_not_found_error

        body = (
            '{"error":{"message":"litellm.BadRequestError: OpenAIException - '
            '{\\"error\\":{\\"message\\":\\"You passed 98305 input tokens and '
            'requested 32768 output tokens. However, the model\'s context length '
            'is only 131072 tokens\\",\\"code\\":400}}}.'
            ' Received Model Group=nvidia/nvidia/nemotron-3-super-v3\\n'
            'Available Model Group Fallbacks=None"}}'
        )
        assert _is_litellm_not_found_error(body) is False

    def test_is_litellm_not_found_error_false_for_500_with_model_group(self):
        """A 500 InternalServerError body that mentions Received Model Group=
        but no litellm.NotFoundError must return False."""
        from oompah.api_agent import _is_litellm_not_found_error

        body = (
            '{"error":{"message":"litellm.InternalServerError: InternalServerError:'
            ' OpenAIException - Cannot connect to host. Received Model Group='
            'nvidia/nvidia/nemotron-3-ultra\\nAvailable Model Group Fallbacks=None",'
            '"code":"500"}}'
        )
        assert _is_litellm_not_found_error(body) is False


class TestCallApiRetriesTransientErrors:
    def test_succeeds_after_one_5xx(self, tmp_path, monkeypatch):
        from oompah.api_agent import ApiAgentSession, TransientServerError

        # First call raises 5xx, second succeeds.
        responses = [
            TransientServerError("HTTP 500 from x", status_code=500),
            {"choices": [{"message": {"content": "ok"}}]},
        ]

        def fake_post(url, headers, body, ssl_ctx):
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        # Skip the real backoff sleeps to keep the test fast.
        async def _noop_sleep(*_a, **_k):
            return None
        monkeypatch.setattr("oompah.api_agent.asyncio.sleep", _noop_sleep)
        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        result = asyncio.run(s._call_api([_msg("system"), _msg("user")]))
        assert result["choices"][0]["message"]["content"] == "ok"
        # Must have consumed both responses (1 failure + 1 success).
        assert responses == []

    def test_logs_transient_error_event(self, tmp_path, monkeypatch):
        from oompah.api_agent import ApiAgentSession, TransientServerError

        responses = [
            TransientServerError("HTTP 502 from x", status_code=502),
            {"choices": [{"message": {"content": "ok"}}]},
        ]

        def fake_post(url, headers, body, ssl_ctx):
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        async def _noop_sleep(*_a, **_k):
            return None
        monkeypatch.setattr("oompah.api_agent.asyncio.sleep", _noop_sleep)
        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        log_path = tmp_path / "agent.jsonl"
        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
            log_path=str(log_path),
        )
        asyncio.run(s._call_api([_msg("system"), _msg("user")]))
        records = [json.loads(l) for l in log_path.read_text().splitlines()]
        kinds = [r["kind"] for r in records]
        assert "transient_error" in kinds
        te = next(r for r in records if r["kind"] == "transient_error")
        assert te["status_code"] == 502

    def test_raises_after_max_retries(self, tmp_path, monkeypatch):
        from oompah.api_agent import ApiAgentSession, TransientServerError

        # Always fail with 503.
        def fake_post(url, headers, body, ssl_ctx):
            raise TransientServerError("HTTP 503 from x", status_code=503)

        async def _noop_sleep(*_a, **_k):
            return None
        monkeypatch.setattr("oompah.api_agent.asyncio.sleep", _noop_sleep)
        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with pytest.raises(TransientServerError):
            asyncio.run(s._call_api([_msg("system"), _msg("user")]))

    def test_permanent_runtime_error_not_retried(self, tmp_path, monkeypatch):
        """4xx-other-than-429 (now bare RuntimeError) should propagate
        immediately — retrying a bad-request payload is wasteful."""
        from oompah.api_agent import ApiAgentSession

        call_count = {"n": 0}

        def fake_post(url, headers, body, ssl_ctx):
            call_count["n"] += 1
            raise RuntimeError("HTTP 400 from x: bad request")

        async def _noop_sleep(*_a, **_k):
            return None
        monkeypatch.setattr("oompah.api_agent.asyncio.sleep", _noop_sleep)
        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with pytest.raises(RuntimeError):
            asyncio.run(s._call_api([_msg("system"), _msg("user")]))
        # Exactly one call — no retries.
        assert call_count["n"] == 1

    def test_succeeds_after_one_401(self, tmp_path, monkeypatch):
        """A 401 must be retried by _call_api (like 5xx) — not propagate
        as a bare RuntimeError. oompah-zlz_2-e6t5."""
        from oompah.api_agent import ApiAgentSession, TransientServerError

        responses = [
            TransientServerError(
                'HTTP 401 from x: {"error":"Authentication Error"}',
                status_code=401,
            ),
            {"choices": [{"message": {"content": "ok"}}]},
        ]

        def fake_post(url, headers, body, ssl_ctx):
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        async def _noop_sleep(*_a, **_k):
            return None
        monkeypatch.setattr("oompah.api_agent.asyncio.sleep", _noop_sleep)
        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        result = asyncio.run(s._call_api([_msg("system"), _msg("user")]))
        assert result["choices"][0]["message"]["content"] == "ok"
        assert responses == []

    def test_401_gives_up_after_5_attempts(self, tmp_path, monkeypatch):
        """After 5 exhausted 401 attempts, _call_api raises so run_task
        can handle and log the failure cleanly."""
        from oompah.api_agent import ApiAgentSession, TransientServerError

        call_count = {"n": 0}

        def fake_post(url, headers, body, ssl_ctx):
            call_count["n"] += 1
            raise TransientServerError(
                'HTTP 401 from x: {"error":"Authentication Error"}',
                status_code=401,
            )

        async def _noop_sleep(*_a, **_k):
            return None
        monkeypatch.setattr("oompah.api_agent.asyncio.sleep", _noop_sleep)
        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with pytest.raises(TransientServerError) as excinfo:
            asyncio.run(s._call_api([_msg("system"), _msg("user")]))
        assert excinfo.value.status_code == 401
        assert call_count["n"] == 5  # 1 attempt + 4 retries

    def test_401_uses_fast_transient_backoff(self, tmp_path, monkeypatch):
        """401 retries use the FAST transient error backoff (1s, 2s, 4s,
        8s, capped at 30s) — not the slower RateLimitError backoff."""
        from oompah.api_agent import ApiAgentSession, TransientServerError

        sleep_deltas = []

        async def tracking_sleep(seconds):
            sleep_deltas.append(seconds)

        def fake_post(url, headers, body, ssl_ctx):
            raise TransientServerError(
                'HTTP 401 from x: {"error":"Authentication Error"}',
                status_code=401,
            )

        monkeypatch.setattr("oompah.api_agent.asyncio.sleep", tracking_sleep)
        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with pytest.raises(TransientServerError):
            asyncio.run(s._call_api([_msg("system"), _msg("user")]))
        # 4 sleeps between 5 attempts (fast backoff): 1, 2, 4, 8 (capped at 30).
        assert sleep_deltas == [1, 2, 4, 8]


# ---------------------------------------------------------------------------
# Workspace-escape protection: agents kept cd'ing into the main checkout
# (where their edits aren't), failing to verify their own work, and looping.
# Refuse `cd /abs/path` that leaves the worktree, with a clear error.
# Plus: helpful redirect when the model treats a shell command as a tool name.
# ---------------------------------------------------------------------------

class TestRunCommandRefusesCdOutsideWorkspace:
    def test_cd_to_absolute_path_outside_workspace_blocked(self, tmp_path):
        from oompah.api_agent import _exec_run_command
        # Worktree is at tmp_path; agent tries to cd to a sibling.
        elsewhere = tmp_path.parent / "elsewhere"
        elsewhere.mkdir(exist_ok=True)
        result = _exec_run_command(
            tmp_path, {"command": f"cd {elsewhere} && grep foo bar.py"},
        )
        assert result.startswith("Error:")
        assert "leaves your worktree" in result
        assert "relative paths" in result

    def test_cd_to_subdir_of_workspace_allowed(self, tmp_path):
        from oompah.api_agent import _exec_run_command
        sub = tmp_path / "subdir"
        sub.mkdir()
        # Should not be rejected by the cd guard. The actual command is
        # benign (we don't care about its result here, just that the guard
        # didn't intercept).
        result = _exec_run_command(
            tmp_path, {"command": f"cd {sub} && pwd"},
        )
        # Result is shell output, not the guard's "Error: refusing..." string.
        assert not result.startswith("Error: refusing")

    def test_relative_cd_allowed(self, tmp_path):
        from oompah.api_agent import _exec_run_command
        sub = tmp_path / "subdir"
        sub.mkdir()
        result = _exec_run_command(
            tmp_path, {"command": "cd subdir && pwd"},
        )
        assert not result.startswith("Error: refusing")

    def test_quoted_cd_target_handled(self, tmp_path):
        from oompah.api_agent import _exec_run_command
        elsewhere = tmp_path.parent / "elsewhere"
        elsewhere.mkdir(exist_ok=True)
        result = _exec_run_command(
            tmp_path, {"command": f'cd "{elsewhere}" && ls'},
        )
        assert "leaves your worktree" in result

    def test_pushd_outside_workspace_blocked(self, tmp_path):
        from oompah.api_agent import _exec_run_command
        elsewhere = tmp_path.parent / "elsewhere"
        elsewhere.mkdir(exist_ok=True)
        result = _exec_run_command(
            tmp_path, {"command": f"pushd {elsewhere}; ls"},
        )
        assert "leaves your worktree" in result

    def test_command_without_cd_unaffected(self, tmp_path):
        from oompah.api_agent import _exec_run_command
        result = _exec_run_command(tmp_path, {"command": "echo hello"})
        assert "Error: refusing" not in result
        assert "hello" in result


class TestRunCommandTimeoutCleanup:
    @pytest.mark.skipif(os.name != "posix", reason="requires POSIX process groups")
    def test_timeout_kills_child_process_tree(self, tmp_path):
        from oompah.api_agent import _exec_run_command

        pid_file = tmp_path / "child.pid"
        result = _exec_run_command(
            tmp_path,
            {"command": "sleep 60 & echo $! > child.pid; wait"},
            timeout=1,
        )

        assert "Error: command timed out after 1s" in result
        child_pid = int(pid_file.read_text().strip())
        try:
            for _ in range(30):
                if not self._pid_exists(child_pid):
                    break
                time.sleep(0.05)
            assert not self._pid_exists(child_pid)
        finally:
            if self._pid_exists(child_pid):
                try:
                    os.kill(child_pid, 9)
                except ProcessLookupError:
                    pass

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True


class TestUnknownToolHelpfulErrorWhenLooksShellish:
    def test_space_in_name_redirects_to_run_command(self, tmp_path):
        from oompah.api_agent import _execute_tool
        result = _execute_tool(tmp_path, "backlog task edit", {})
        assert "is not a tool" in result
        assert "run_command" in result
        # Must still preserve the original tool list for the model.
        assert "read_file" in result

    def test_backlog_prefix_no_space_still_redirects(self, tmp_path):
        from oompah.api_agent import _execute_tool
        result = _execute_tool(tmp_path, "backlog_edit", {})
        assert "is not a tool" in result
        assert "run_command" in result

    def test_git_prefix_redirects(self, tmp_path):
        from oompah.api_agent import _execute_tool
        result = _execute_tool(tmp_path, "git commit", {})
        assert "is not a tool" in result
        assert "run_command" in result

    def test_unrelated_unknown_tool_keeps_original_message(self, tmp_path):
        from oompah.api_agent import _execute_tool
        # Doesn't start with backlog/git/uv/make and has no spaces — should
        # use the original "unknown tool" wording without the shell hint.
        result = _execute_tool(tmp_path, "frobnicate", {})
        assert "unknown tool 'frobnicate'" in result
        assert "looks like a shell command" not in result


# ---------------------------------------------------------------------------
# Environment override plumbing for run_command.
# ---------------------------------------------------------------------------

class TestRunCommandEnvOverrides:
    def test_no_overrides_inherits_env(self, tmp_path, monkeypatch):
        from oompah.api_agent import _exec_run_command
        # Echoes whatever's in OOMPAH_TEST_OVERRIDE (or "unset" if missing) so we can
        # check whether the caller's env reached the subprocess.
        monkeypatch.setenv("OOMPAH_TEST_OVERRIDE", "/from/parent")
        result = _exec_run_command(
            tmp_path,
            {"command": "echo OOMPAH_TEST_OVERRIDE=${OOMPAH_TEST_OVERRIDE:-unset}"},
        )
        assert "OOMPAH_TEST_OVERRIDE=/from/parent" in result

    def test_overrides_replace_specific_keys(self, tmp_path):
        from oompah.api_agent import _exec_run_command
        # Caller specifies a value via env_overrides — child should see it.
        result = _exec_run_command(
            tmp_path,
            {"command": "echo OOMPAH_TEST_OVERRIDE=${OOMPAH_TEST_OVERRIDE:-unset}"},
            env_overrides={"OOMPAH_TEST_OVERRIDE": "/from/override"},
        )
        assert "OOMPAH_TEST_OVERRIDE=/from/override" in result

    def test_overrides_layer_on_existing_env(self, tmp_path, monkeypatch):
        """env_overrides should be additive — non-overridden keys still come
        from the parent process's env."""
        from oompah.api_agent import _exec_run_command
        monkeypatch.setenv("OOMPAH_TEST_FIXTURE", "fixture-from-parent")
        result = _exec_run_command(
            tmp_path,
            {
                "command": (
                    "echo PARENT=${OOMPAH_TEST_FIXTURE:-missing} "
                    "OVERRIDE=${OOMPAH_TEST_OVERRIDE:-unset}"
                )
            },
            env_overrides={"OOMPAH_TEST_OVERRIDE": "/x"},
        )
        assert "PARENT=fixture-from-parent" in result
        assert "OVERRIDE=/x" in result


class TestExecuteToolForwardsEnvOverrides:
    """When run_command goes through _execute_tool, env_overrides
    must reach the subprocess. File/edit tools don't
    spawn subprocesses, so the override has no effect there but must
    not crash either."""

    def test_run_command_receives_env_override(self, tmp_path):
        from oompah.api_agent import _execute_tool
        result = _execute_tool(
            tmp_path, "run_command",
            {"command": "echo OVERRIDE=${OOMPAH_TEST_OVERRIDE:-unset}"},
            env_overrides={"OOMPAH_TEST_OVERRIDE": "/sentinel/path"},
        )
        assert "OVERRIDE=/sentinel/path" in result

    def test_other_tools_unaffected_by_env_overrides(self, tmp_path):
        from oompah.api_agent import _execute_tool
        # list_files doesn't spawn a subprocess; passing env_overrides
        # must be a no-op (and definitely not a crash).
        (tmp_path / "f.txt").write_text("ok")
        result = _execute_tool(
            tmp_path, "list_files", {"path": "."},
            env_overrides={"OOMPAH_TEST_OVERRIDE": "/x"},
        )
        assert "f.txt" in result


# ---------------------------------------------------------------------------
# End-to-end transport-error coverage (oompah-zlz_2-bpa, follow-up to ovt).
#
# ovt fixed _http_post to wrap raw OSErrors as TransientServerError so the
# 5-attempt retry loop in _call_api can recover. These tests assert the
# *end-to-end* contract from run_task's perspective: no matter where a raw
# OSError leaks from, run_task must return an ApiAgentResult (never raise),
# and the error message must be a clearer "Socket error..." / "transport_error..."
# string instead of the bare "[Errno 57] Socket is not connected" repr that
# used to auto-trigger duplicate beads via the error_watcher fingerprint.
# ---------------------------------------------------------------------------

class TestRunTaskOSErrorRecovery:
    """Verifies the public contract of ApiAgentSession.run_task under raw
    socket-level errors. The historic failure (oompah-zlz_2-ovt) was that
    an OSError(57) leaked from _http_post -> _call_api -> run_task, where
    only the broad ``except Exception`` caught it — logging the bare
    ``[Errno 57] Socket is not connected`` string and tripping the
    error_watcher into filing a duplicate bead each time."""

    def test_oserror_from_http_post_retries_and_wraps(self, tmp_path, monkeypatch):
        """ovt-path end-to-end: when ``urllib.request.urlopen`` raises
        OSError(57) every time (the original bug pattern), the real
        ``_http_post`` wraps it as TransientServerError, ``_call_api``
        retries ``max_retries`` times with backoff, and ``run_task``
        ultimately returns a ``failed`` result whose error contains
        'Socket error' (NOT the bare '[Errno 57]' that originally
        slipped past the URLError handler)."""
        from oompah.api_agent import ApiAgentSession

        call_count = {"n": 0}

        def fake_urlopen(*a, **kw):
            call_count["n"] += 1
            # Plain OSError, not URLError — the macOS ENOTCONN pattern
            # that originally escaped _http_post's URLError handler.
            raise OSError(57, "Socket is not connected")

        async def _noop_sleep(*_a, **_k):
            return None

        # Keep the real _http_post so we exercise its OSError wrapper.
        monkeypatch.setattr("oompah.api_agent.asyncio.sleep", _noop_sleep)
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        # run_task should NEVER raise — always return a result.
        result = asyncio.run(s.run_task("hello"))

        # OSError -> _http_post's OSError wrapper -> TransientServerError
        # -> _call_api retries max_retries (=5) times.
        assert call_count["n"] == 5, (
            f"expected 5 retries, saw {call_count['n']}"
        )
        # Final result is a clean failure record, not an unhandled raise.
        assert result.status == "failed"
        # Error message uses the wrapped form ("Socket error for ...:
        # [Errno 57] Socket is not connected"), NOT the bare OSError repr
        # that the error_watcher historically fingerprinted into the
        # duplicate-bead loop.
        assert "Socket error" in (result.error or ""), result.error
        assert "Errno 57" in (result.error or ""), result.error

    def test_run_task_defense_in_depth_for_leaked_oserror(self, tmp_path, monkeypatch):
        """bpa-path defense-in-depth: if a raw OSError EVER reaches
        run_task's outer try/except (e.g. some new code path bypasses
        _http_post in the future), the dedicated ``except OSError``
        handler must produce a 'transport_error: ...' message instead of
        falling through to the broad ``except Exception`` and re-emitting
        the historic bare '[Errno 57] Socket is not connected' title."""
        from oompah.api_agent import ApiAgentSession

        async def fake_call_api(self_, messages):
            # Simulate an OSError that bypasses _http_post entirely
            # (the wrap-as-TransientServerError defense doesn't apply).
            raise OSError(57, "Socket is not connected")

        monkeypatch.setattr(
            "oompah.api_agent.ApiAgentSession._call_api", fake_call_api,
        )

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        result = asyncio.run(s.run_task("hello"))

        assert result.status == "failed"
        # The dedicated OSError handler tags the message with the
        # 'transport_error:' prefix so error_watcher fingerprints into a
        # *single* bead category instead of duplicating per-occurrence.
        assert result.error is not None
        assert result.error.startswith("transport_error:"), result.error
        assert "Errno 57" in result.error

    def test_run_task_oserror_logs_via_distinct_logger_signature(
        self, tmp_path, monkeypatch, caplog,
    ):
        """The new OSError handler must NOT use the historic
        'ApiAgentSession.run_task failed: [Errno 57]...' log signature
        that the error_watcher already filed beads for — otherwise
        production keeps duplicating the same bead. The 'transport_error'
        signature is intentionally distinct so the watcher fingerprints
        into a fresh, single bead."""
        import logging
        from oompah.api_agent import ApiAgentSession

        async def fake_call_api(self_, messages):
            raise OSError(57, "Socket is not connected")

        monkeypatch.setattr(
            "oompah.api_agent.ApiAgentSession._call_api", fake_call_api,
        )

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with caplog.at_level(logging.ERROR, logger="oompah.api_agent"):
            asyncio.run(s.run_task("hello"))

        api_records = [
            r for r in caplog.records if r.name == "oompah.api_agent"
            and r.levelno >= logging.ERROR
        ]
        # Exactly one error log line from the OSError branch.
        assert len(api_records) >= 1
        # The dedicated handler uses 'transport_error', not the historic
        # 'failed: [Errno 57] Socket is not connected' phrasing.
        assert any(
            "transport_error" in r.getMessage() for r in api_records
        ), [r.getMessage() for r in api_records]
        assert not any(
            r.getMessage().startswith(
                "ApiAgentSession.run_task failed: [Errno"
            )
            for r in api_records
        ), [r.getMessage() for r in api_records]

    def test_run_task_oserror_log_does_not_double_transport_error_prefix(
        self, tmp_path, monkeypatch, caplog,
    ):
        """hp2 regression guard (oompah-zlz_2-hp2): the OSError-handler
        log line must contain ``transport_error:`` exactly once. Before
        the cleanup, the format string ``"ApiAgentSession.run_task
        transport_error: %s"`` was paired with a ``msg`` argument that
        already started with ``transport_error: ...``, so the rendered
        record read ``"... transport_error: transport_error: [Errno 57]
        ..."``. The doubling didn't break fingerprinting (error_watcher
        normalisation strips numbers but keeps the prefix), but it was
        inconsistent with the rate_limited / transient_error log
        patterns and made grepping production logs ambiguous.

        Note: ``result.error`` (the user-facing field) intentionally
        keeps the ``transport_error:`` prefix — the cleanup only
        touches the log line."""
        import logging
        from oompah.api_agent import ApiAgentSession

        async def fake_call_api(self_, messages):
            raise OSError(57, "Socket is not connected")

        monkeypatch.setattr(
            "oompah.api_agent.ApiAgentSession._call_api", fake_call_api,
        )

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with caplog.at_level(logging.ERROR, logger="oompah.api_agent"):
            result = asyncio.run(s.run_task("hello"))

        # result.error keeps the prefix (descriptive for the dashboard).
        assert result.error is not None
        assert result.error.startswith("transport_error:"), result.error

        # Log line must contain 'transport_error' exactly once.
        api_error_records = [
            r for r in caplog.records
            if r.name == "oompah.api_agent" and r.levelno >= logging.ERROR
        ]
        oserror_records = [
            r for r in api_error_records
            if "transport_error" in r.getMessage()
        ]
        assert oserror_records, (
            f"expected at least one transport_error log record; got "
            f"{[r.getMessage() for r in api_error_records]}"
        )
        for r in oserror_records:
            occurrences = r.getMessage().count("transport_error")
            assert occurrences == 1, (
                f"transport_error must appear exactly once in the log "
                f"record; saw {occurrences} in {r.getMessage()!r}"
            )


# ---------------------------------------------------------------------------
# TransientServerError → WARNING coverage (oompah-zlz_2-amx).
#
# After ovt's fix, raw OSErrors hitting _http_post are wrapped as
# TransientServerError so _call_api's 5-retry loop can recover. When all
# 5 retries fail, the wrapped TransientServerError propagates up to
# run_task. Without a dedicated handler it falls through to the broad
# `except Exception` — logging at ERROR and tripping error_watcher into
# auto-filing a duplicate bug bead for what is, by definition, a
# known-transient network failure the orchestrator already retries.
#
# These tests assert the dedicated TransientServerError handler logs at
# WARNING (not ERROR), matching the RateLimitError precedent above it
# and the TrackerTimeoutError pattern in oompah/tracker.py.
# ---------------------------------------------------------------------------

class TestRunTaskTransientServerErrorHandler:
    """Verifies that TransientServerError (which is NOT a subclass of
    OSError, so bpa's OSError handler doesn't catch it) is downgraded
    to WARNING in run_task so error_watcher does not file beads."""

    def test_transient_server_error_returns_failed(self, tmp_path, monkeypatch):
        """Exhausted retries on a transient error must produce a clean
        'failed' result — never raise."""
        from oompah.api_agent import ApiAgentSession, TransientServerError

        async def fake_call_api(self_, messages):
            raise TransientServerError(
                "Socket error for http://x: [Errno 57] Socket is not connected",
                status_code=None,
            )

        monkeypatch.setattr(
            "oompah.api_agent.ApiAgentSession._call_api", fake_call_api,
        )

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        result = asyncio.run(s.run_task("hello"))
        assert result.status == "failed"
        assert "Errno 57" in (result.error or "")
        assert "Socket error" in (result.error or "")

    def test_transient_server_error_logs_warning_not_error(
        self, tmp_path, monkeypatch, caplog,
    ):
        """The dedicated TransientServerError handler must log at
        WARNING — not ERROR — so the error_watcher (which only files
        beads for ERROR+ records) does not auto-file duplicate bug
        beads on every exhausted-retry transient failure."""
        import logging
        from oompah.api_agent import ApiAgentSession, TransientServerError

        async def fake_call_api(self_, messages):
            raise TransientServerError(
                "Socket error for http://x: [Errno 57] Socket is not connected",
                status_code=None,
            )

        monkeypatch.setattr(
            "oompah.api_agent.ApiAgentSession._call_api", fake_call_api,
        )

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with caplog.at_level(logging.DEBUG, logger="oompah.api_agent"):
            asyncio.run(s.run_task("hello"))

        api_records = [
            r for r in caplog.records if r.name == "oompah.api_agent"
        ]
        # MUST NOT log the historic bead-triggering 'failed: ' phrasing
        # at ERROR — the catch-all `except Exception` would otherwise
        # match our new handler's logger record verbatim.
        bead_triggering = [
            r for r in api_records
            if r.levelno >= logging.ERROR
            and r.getMessage().startswith("ApiAgentSession.run_task failed: ")
        ]
        assert not bead_triggering, (
            f"transient errors must not log at ERROR with the historic "
            f"'run_task failed:' phrasing: {[r.getMessage() for r in bead_triggering]}"
        )
        # MUST log at WARNING with a transient-tagged signature.
        warning_records = [
            r for r in api_records
            if r.levelno == logging.WARNING
            and "transient_error" in r.getMessage()
        ]
        assert warning_records, (
            "TransientServerError must be logged at WARNING with a "
            "'transient_error' signature in run_task"
        )

    def test_transient_server_error_does_not_match_oserror_handler(
        self, tmp_path, monkeypatch, caplog,
    ):
        """Regression guard: TransientServerError doesn't inherit from
        OSError, so bpa's OSError handler must NOT swallow it. If it
        did, the message would carry the 'transport_error:' prefix
        (bpa's tag) instead of the 'transient_error' tag we want for
        retry-exhausted server failures."""
        import logging
        from oompah.api_agent import ApiAgentSession, TransientServerError

        async def fake_call_api(self_, messages):
            raise TransientServerError("HTTP 503 from x", status_code=503)

        monkeypatch.setattr(
            "oompah.api_agent.ApiAgentSession._call_api", fake_call_api,
        )

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with caplog.at_level(logging.DEBUG, logger="oompah.api_agent"):
            asyncio.run(s.run_task("hello"))

        api_records = [
            r for r in caplog.records if r.name == "oompah.api_agent"
        ]
        # Must NOT have the bpa OSError-handler 'transport_error:' tag.
        transport_records = [
            r for r in api_records
            if "transport_error" in r.getMessage()
        ]
        assert not transport_records, (
            f"TransientServerError must hit the dedicated handler, not bpa's "
            f"OSError handler: {[r.getMessage() for r in transport_records]}"
        )

    def test_rate_limit_error_unaffected(
        self, tmp_path, monkeypatch, caplog,
    ):
        """Regression guard: the existing RateLimitError handler still
        wins over the new TransientServerError handler (both are
        RetryableError subclasses)."""
        import logging
        from oompah.api_agent import ApiAgentSession, RateLimitError

        async def fake_call_api(self_, messages):
            raise RateLimitError("HTTP 429 from x", retry_after=10)

        monkeypatch.setattr(
            "oompah.api_agent.ApiAgentSession._call_api", fake_call_api,
        )

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with caplog.at_level(logging.DEBUG, logger="oompah.api_agent"):
            result = asyncio.run(s.run_task("hello"))

        # Status differentiates the two: RateLimitError → 'rate_limited',
        # TransientServerError → 'failed'. If the order were wrong, this
        # would surface as a 'failed' result.
        assert result.status == "rate_limited"
        api_records = [
            r for r in caplog.records if r.name == "oompah.api_agent"
        ]
        assert any(
            "rate limited" in r.getMessage().lower() for r in api_records
        ), [r.getMessage() for r in api_records]

    def test_auth_error_401_returns_failed(self, tmp_path, monkeypatch):
        """Exhausted retries on a 401 auth error must produce a 'failed'
        result — never raise. The 401 is a TransientServerError with
        status_code=401."""
        from oompah.api_agent import ApiAgentSession, TransientServerError

        async def fake_call_api(self_, messages):
            raise TransientServerError(
                'HTTP 401 from x: {"error":"Authentication Error"}',
                status_code=401,
            )

        monkeypatch.setattr(
            "oompah.api_agent.ApiAgentSession._call_api", fake_call_api,
        )

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        result = asyncio.run(s.run_task("hello"))
        assert result.status == "failed"
        assert "401" in (result.error or "")

    def test_auth_error_401_logs_warning_not_error(
        self, tmp_path, monkeypatch, caplog,
    ):
        """A 401 auth error must log at WARNING — not ERROR — so the
        error_watcher does not auto-file duplicate bug beads every tick
        on what is typically an operator-fixable config issue (expired
        key, wrong endpoint)."""
        import logging
        from oompah.api_agent import ApiAgentSession, TransientServerError

        async def fake_call_api(self_, messages):
            raise TransientServerError(
                'HTTP 401 from https://inference-api.nvidia.com/v1/chat/completions: '
                '{"error":{"message":"Authentication Error","code":"401"}}',
                status_code=401,
            )

        monkeypatch.setattr(
            "oompah.api_agent.ApiAgentSession._call_api", fake_call_api,
        )

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with caplog.at_level(logging.DEBUG, logger="oompah.api_agent"):
            asyncio.run(s.run_task("hello"))

        api_records = [
            r for r in caplog.records if r.name == "oompah.api_agent"
        ]
        # Must NOT log at ERROR level — that triggers error_watcher.
        bead_triggering = [
            r for r in api_records
            if r.levelno >= logging.ERROR
            and r.getMessage().startswith("ApiAgentSession.run_task failed: ")
        ]
        assert not bead_triggering, (
            f"401 auth error must not log at ERROR with 'run_task failed:' "
            f"phrasing: {[r.getMessage() for r in bead_triggering]}"
        )
        # Must log at WARNING with the 'auth_error' signature.
        warning_records = [
            r for r in api_records
            if r.levelno == logging.WARNING
            and ("auth_error" in r.getMessage() or "401" in r.getMessage())
        ]
        assert warning_records, (
            f"401 auth error must log at WARNING with 'auth_error' "
            f"signature. Records: {[r.getMessage() for r in api_records]}"
        )

    def test_auth_error_401_error_in_activity_log(
        self, tmp_path, monkeypatch,
    ):
        """The full auth-error message must appear in the activity log
        (result.error) so the operator can diagnose without digging
        through server logs. The full message is preserved, not
        truncated to the bare HTTP status code."""
        from oompah.api_agent import ApiAgentSession, TransientServerError

        async def fake_call_api(self_, messages):
            raise TransientServerError(
                'HTTP 401 from x: ending=Server disconnected without sending',
                status_code=401,
            )

        monkeypatch.setattr(
            "oompah.api_agent.ApiAgentSession._call_api", fake_call_api,
        )

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        result = asyncio.run(s.run_task("hello"))
        # The full error body — not just "401" — must be in result.error
        # The message preserves the distinctive NVIDIA error phrasing.
        assert "Server disconnected" in (result.error or "")


# ---------------------------------------------------------------------------
# Context-window recovery (oompah-zlz_2-vwrp).
#
# When provider.model_contexts has no entry for the active model,
# model_max_context is None and no pruning fires. The API then rejects
# the request with a 400 whose body contains the real limit. The fix:
# _extract_context_window_limit parses the limit from the error body,
# _is_context_window_error detects the pattern, and _call_api retries
# once with pruning enabled using the learned limit.
# ---------------------------------------------------------------------------

from oompah.api_agent import (
    _extract_context_window_limit,
    _is_context_window_error,
)


class TestExtractContextWindowLimit:
    def test_extracts_from_nvidia_litellm_error(self):
        # The exact production error format from NVIDIA inference API.
        body = json.dumps({
            "error": {
                "message": (
                    "litellm.ContextWindowExceededError: litellm.BadRequestError: "
                    "ContextWindowExceededError: OpenAIException - "
                    "{\"message\":\"This model's maximum context length is "
                    "131072 tokens. However, your messages resulted in 409823 tokens."
                    " Please reduce the length of the messages.\",\"type\":\"Bad Request\"}"
                ),
                "type": None,
                "param": None,
                "code": "400",
            }
        })
        assert _extract_context_window_limit(body) == 131072

    def test_extracts_from_plain_message(self):
        msg = (
            "litellm.ContextWindowExceededError: "
            "maximum context length is 2048 tokens. However, you sent 5000 tokens."
        )
        assert _extract_context_window_limit(msg) == 2048

    def test_extracts_from_simple_numeric_message(self):
        assert _extract_context_window_limit(
            "maximum context length is 8192 tokens."
        ) == 8192

    def test_returns_none_for_unparseable(self):
        assert _extract_context_window_limit("something went wrong") is None
        assert _extract_context_window_limit("") is None
        assert _extract_context_window_limit(
            "maximum context length tokens."  # no number
        ) is None
        assert _extract_context_window_limit("maximum tokens 1024 bytes") is None

    def test_returns_none_for_invalid_json(self):
        # JSON parse failure should fall back to raw string search.
        assert _extract_context_window_limit(
            "maximum context length is 4096 tokens."
        ) == 4096

    def test_extracts_from_nvidia_bad_request_error(self):
        # TASK-432: NVIDIA returns litellm.BadRequestError (not ContextWindowExceededError)
        # when input_tokens + max_tokens > context_window.
        # The raw RuntimeError string includes the "HTTP 400 from ..." prefix.
        error_str = (
            "HTTP 400 from https://inference-api.nvidia.com/v1/chat/completions: "
            '{"error":{"message":"litellm.BadRequestError: OpenAIException - '
            '{\\"error\\":{\\"message\\":\\"You passed 98305 input tokens and requested '
            "32768 output tokens. However, the model's context length is only "
            '131072 tokens, resulting in a maximum input length of 98304 tokens. '
            "Please reduce the length of the input prompt. "
            '(parameter=input_tokens, value=98305)\\",\\"type\\":\\"BadRequestError\\",'
            '\\"param\\":\\"input_tokens\\",\\"code\\":400}}. '
            "Received Model Group=nvidia/nvidia/nemotron-3-super-v3\\n"
            'Available Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}'
        )
        assert _extract_context_window_limit(error_str) == 131072


class TestIsContextWindowError:
    def test_detects_litellm_nvidia_pattern(self):
        body = json.dumps({
            "error": {
                "message": (
                    "litellm.ContextWindowExceededError: something. "
                    "Please reduce the length of the messages."
                ),
                "code": "400",
            }
        })
        assert _is_context_window_error(body) is True

    def test_detects_nvidia_bad_request_error_variant(self):
        # TASK-432: NVIDIA returns a BadRequestError (not ContextWindowExceededError)
        # when input_tokens + max_tokens > context_window. The error body
        # contains "context length is only N tokens" instead of "ContextWindowExceededError".
        error_str = (
            "HTTP 400 from https://inference-api.nvidia.com/v1/chat/completions: "
            '{"error":{"message":"litellm.BadRequestError: OpenAIException - '
            '{\\"error\\":{\\"message\\":\\"You passed 98305 input tokens and requested '
            "32768 output tokens. However, the model's context length is only "
            '131072 tokens, resulting in a maximum input length of 98304 tokens. '
            "Please reduce the length of the input prompt. "
            '(parameter=input_tokens, value=98305)\\",\\"type\\":\\"BadRequestError\\",'
            '\\"param\\":\\"input_tokens\\",\\"code\\":400}}. '
            "Received Model Group=nvidia/nvidia/nemotron-3-super-v3\\n"
            'Available Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}'
        )
        assert _is_context_window_error(error_str) is True

    def test_false_for_ordinary_400(self):
        assert _is_context_window_error('{"error":"bad request"}') is False
        assert _is_context_window_error('{"error":{"message":"Not Found","code":"404"}}') is False

    def test_false_for_transient_500(self):
        assert _is_context_window_error('{"error":"Internal Server Error"}') is False


class TestCallApiContextWindowRecovery:
    """oompah-zlz_2-vwrp: when model_max_context is None and the API
    returns a 400 with a ContextWindowExceededError body, _call_api must
    extract the limit, enable budgeting on the session, prune the
    messages, and retry once — all within the same worker turn."""

    def test_context_window_400_succeeds_on_retry_after_pruning(
        self, tmp_path, monkeypatch,
    ):
        """First attempt 400s with the litellm error; second attempt
        (with pruning) succeeds."""
        from oompah.api_agent import ApiAgentSession

        call_count = {"n": 0}
        captured = {}

        def fake_post(url, headers, body, ssl_ctx):
            call_count["n"] += 1
            captured["payload"] = json.loads(body)
            if call_count["n"] == 1:
                raise RuntimeError(
                    'HTTP 400 from https://api.x: '
                    '{"error":{"message":"litellm.ContextWindowExceededError: '
                    'OpenAIException - {\\"message\\":\\"maximum context length '
                    'is 8192 tokens. Your messages 10000 tokens.\\"}}'
                )
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
            # model_max_context intentionally None — the bug scenario.
        )
        # Build history that overflows 8192 tokens.
        msgs = [_msg("system", "agent"), _msg("user", "task")]
        for i in range(20):
            msgs.append(_msg(
                "assistant", "thinking",
                tool_calls=[{
                    "id": f"c{i}",
                    "function": {"name": "x", "arguments": "{}"},
                }],
            ))
            msgs.append({
                "role": "tool",
                "tool_call_id": f"c{i}",
                "content": "y" * 1000,
            })
        original_len = len(msgs)
        result = asyncio.run(s._call_api(msgs))

        # Must succeed on second attempt.
        assert result["choices"][0]["message"]["content"] == "ok"
        # Two calls: first 400'd, second succeeded.
        assert call_count["n"] == 2
        # Pruning happened on the retry.
        assert len(msgs) < original_len
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        # Context limit learned and stored on session.
        assert s.model_max_context == 8192
        # max_tokens clamped for the pruned history.
        mt = captured["payload"]["max_tokens"]
        assert _MIN_MAX_OUTPUT_TOKENS <= mt <= _DEFAULT_MAX_OUTPUT_TOKENS

    def test_context_window_400_propagates_after_one_retry(self, tmp_path, monkeypatch):
        """If the retry ALSO 400s (e.g. even pruning can't fit), raise
        after the single recovery attempt to avoid an infinite loop."""
        from oompah.api_agent import ApiAgentSession

        call_count = {"n": 0}

        def fake_post(url, headers, body, ssl_ctx):
            call_count["n"] += 1
            raise RuntimeError(
                'HTTP 400: {"error":{"message":"ContextWindowExceededError: '
                'maximum context length is 4096 tokens."}}'
            )

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        # Already have too much content.
        msgs = [_msg("system", "agent"), _msg("user", "task" + "x" * 5000)]
        with pytest.raises(RuntimeError):
            asyncio.run(s._call_api(msgs))

        # Exactly two calls: first attempt + one recovery attempt.
        assert call_count["n"] == 2, call_count

    def test_non_context_400_raises_immediately(self, tmp_path, monkeypatch):
        """A 400 that is NOT a ContextWindowExceededError (e.g. malformed
        JSON, wrong endpoint) must propagate immediately — not enter the
        recovery path."""
        from oompah.api_agent import ApiAgentSession

        call_count = {"n": 0}

        def fake_post(url, headers, body, ssl_ctx):
            call_count["n"] += 1
            raise RuntimeError(
                'HTTP 400 from x: {"error":"invalid request format"}'
            )

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        with pytest.raises(RuntimeError):
            asyncio.run(s._call_api([_msg("system"), _msg("user", "hi")]))
        # Exactly one call — no recovery retry for non-context 400s.
        assert call_count["n"] == 1

    def test_falls_back_to_conservative_limit_when_body_is_unparseable(
        self, tmp_path, monkeypatch,
    ):
        """If the 400 body is a ContextWindowExceededError but the limit
        can't be parsed (e.g. unusual format), use the hardcoded
        conservative fallback (131072) so pruning still fires."""
        from oompah.api_agent import ApiAgentSession

        call_count = {"n": 0}
        captured = {}

        def fake_post(url, headers, body, ssl_ctx):
            call_count["n"] += 1
            captured["payload"] = json.loads(body)
            if call_count["n"] == 1:
                raise RuntimeError(
                    'HTTP 400: {"error":{"message":"ContextWindowExceededError: '
                    'unknown reason (no limit given)"}}'
                )
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
        )
        msgs = [_msg("system", "agent"), _msg("user", "task")]
        for i in range(20):
            msgs.append(_msg(
                "assistant", "thinking",
                tool_calls=[{"id": f"c{i}", "function": {"name": "x", "arguments": "{}"}}],
            ))
            msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": "y" * 1000})
        result = asyncio.run(s._call_api(msgs))

        # Succeeded after the recovery attempt.
        assert result["choices"][0]["message"]["content"] == "ok"
        assert call_count["n"] == 2
        # Conservative fallback was learned and stored.
        assert s.model_max_context == 131072

    def test_logs_context_window_retry_event(self, tmp_path, monkeypatch):
        """The recovery retry must emit a 'context_window_retry' log event
        so operators can audit the recovery path from the JSONL."""
        from oompah.api_agent import ApiAgentSession

        def fake_post(url, headers, body, ssl_ctx):
            if json.loads(body)["max_tokens"] == _DEFAULT_MAX_OUTPUT_TOKENS:
                raise RuntimeError(
                    'HTTP 400: {"error":{"message":"ContextWindowExceededError: '
                    'maximum context length is 8192 tokens."}}'
                )
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        log_path = tmp_path / "agent.jsonl"
        s = ApiAgentSession(
            base_url="http://x", api_key="", model="m",
            workspace_path=str(tmp_path),
            log_path=str(log_path),
        )
        msgs = [_msg("system", "agent"), _msg("user", "task")]
        for i in range(10):
            msgs.append(_msg(
                "assistant", "thinking",
                tool_calls=[{"id": f"c{i}", "function": {"name": "x", "arguments": "{}"}}],
            ))
            msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": "y" * 500})
        asyncio.run(s._call_api(msgs))

        records = [json.loads(l) for l in log_path.read_text().splitlines()]
        kinds = [r["kind"] for r in records]
        assert "context_window_error" in kinds
        assert "context_window_retry" in kinds
        retry_event = next(
            r for r in records if r["kind"] == "context_window_retry"
        )
        assert "pruned" in retry_event
        assert "max_tokens" in retry_event

    def test_nvidia_bad_request_error_triggers_recovery(self, tmp_path, monkeypatch):
        """TASK-432: NVIDIA returns a ``litellm.BadRequestError`` (not
        ``ContextWindowExceededError``) when input_tokens + max_tokens exceeds
        the model's context window.  The error body contains the phrase
        "context length is only N tokens" instead of "ContextWindowExceededError".
        The recovery path must detect this variant and retry with pruning."""
        from oompah.api_agent import ApiAgentSession

        call_count = {"n": 0}
        captured = {}

        # Simulate the exact error body returned by NVIDIA inference API
        # via litellm for the nemotron-3-super-v3 model.
        nvidia_bad_request_error = (
            "HTTP 400 from https://inference-api.nvidia.com/v1/chat/completions: "
            '{"error":{"message":"litellm.BadRequestError: OpenAIException - '
            '{\\"error\\":{\\"message\\":\\"You passed 98305 input tokens and requested '
            "32768 output tokens. However, the model's context length is only "
            '8192 tokens, resulting in a maximum input length of 4096 tokens. '
            "Please reduce the length of the input prompt. "
            '(parameter=input_tokens, value=98305)\\",\\"type\\":\\"BadRequestError\\",'
            '\\"param\\":\\"input_tokens\\",\\"code\\":400}}. '
            "Received Model Group=nvidia/nvidia/nemotron-3-super-v3\\n"
            'Available Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}'
        )

        def fake_post(url, headers, body, ssl_ctx):
            call_count["n"] += 1
            captured["payload"] = json.loads(body)
            if call_count["n"] == 1:
                raise RuntimeError(nvidia_bad_request_error)
            return {"choices": [{"message": {"content": "done"}}]}

        monkeypatch.setattr("oompah.api_agent._http_post", fake_post)

        s = ApiAgentSession(
            base_url="http://x", api_key="", model="nvidia/nemotron-3-super-v3",
            workspace_path=str(tmp_path),
            # model_max_context is None — the production scenario when the limit
            # is first hit without prior knowledge of the context window.
        )
        # Build a long conversation history.
        msgs = [_msg("system", "agent"), _msg("user", "task")]
        for i in range(20):
            msgs.append(_msg(
                "assistant", "thinking",
                tool_calls=[{
                    "id": f"c{i}",
                    "function": {"name": "bash", "arguments": "{}"},
                }],
            ))
            msgs.append({
                "role": "tool",
                "tool_call_id": f"c{i}",
                "content": "output " * 200,
            })
        original_len = len(msgs)

        result = asyncio.run(s._call_api(msgs))

        # Succeeded on the second attempt after pruning.
        assert result["choices"][0]["message"]["content"] == "done"
        assert call_count["n"] == 2
        # Conversation was pruned.
        assert len(msgs) < original_len
        # Context limit was learned from the BadRequestError body.
        assert s.model_max_context == 8192
        # max_tokens was clamped to fit within the discovered context window.
        mt = captured["payload"]["max_tokens"]
        assert _MIN_MAX_OUTPUT_TOKENS <= mt <= _DEFAULT_MAX_OUTPUT_TOKENS
