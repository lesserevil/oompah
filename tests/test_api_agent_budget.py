"""Tests for the context-window budgeting helpers in oompah.api_agent.

Covers oompah-zlz_2-px3: chat-completions calls were 400ing because
``max_tokens`` was hardcoded at 32768 with no awareness of the model's
total window. The fix: estimate the outgoing payload, prune oldest
round-trips, and clamp ``max_tokens`` to the remaining headroom.
"""

from __future__ import annotations

import asyncio
import json

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
