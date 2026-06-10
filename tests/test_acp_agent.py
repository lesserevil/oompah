"""Tests for ACP-mode agent execution.

Covers:
- AcpAgentSession lifecycle (init, run_task, terminate, counters)
- Tool catalog bridging (cd-guard, tracker-safe shell routing)
- Permission auto-accept emits acp_session_start with the bypass flag
- Profile mode validation (auto/api/cli/acp + invalid → auto fallback)
- Orchestrator dispatch routing by profile.mode
- Budget gate bypasses ACP profiles entirely

These tests use mocks for ClaudeSDKClient — they don't spawn the real
claude CLI. Real-claude integration is left to a separate
@pytest.mark.skipif test that's only meaningful in dev environments
where the binary is installed.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import pytest

from oompah.acp_agent import AcpAgentSession, _SessionCounters, _truncate_for_log
from oompah.agent import AgentEvent
from oompah.config import _parse_profile_mode
from oompah.models import AgentProfile, Issue


# ----------------------------------------------------------------------
# Profile mode parsing
# ----------------------------------------------------------------------


class TestParseProfileMode:
    def test_default_is_auto(self):
        assert _parse_profile_mode(None) == "auto"
        assert _parse_profile_mode("") == "auto"

    def test_valid_values_pass_through(self):
        for v in ("auto", "api", "cli", "acp"):
            assert _parse_profile_mode(v) == v

    def test_case_insensitive(self):
        assert _parse_profile_mode("ACP") == "acp"
        assert _parse_profile_mode("Cli") == "cli"

    def test_whitespace_tolerated(self):
        assert _parse_profile_mode("  acp  ") == "acp"

    def test_invalid_falls_back_to_auto(self):
        # Typo in WORKFLOW.md must not silently change dispatch routing.
        assert _parse_profile_mode("acpx") == "auto"
        assert _parse_profile_mode("subscription") == "auto"
        assert _parse_profile_mode("123") == "auto"


class TestAgentProfileMode:
    def test_default_field_is_auto(self):
        p = AgentProfile(name="x", command="y")
        assert p.mode == "auto"

    def test_explicit_mode_settable(self):
        p = AgentProfile(name="x", command="y", mode="acp")
        assert p.mode == "acp"


# ----------------------------------------------------------------------
# Session counters
# ----------------------------------------------------------------------


class TestSessionCounters:
    def test_absorbs_assistant_usage(self):
        c = _SessionCounters()
        c.absorb_assistant_usage({"input_tokens": 10, "output_tokens": 5})
        c.absorb_assistant_usage({"input_tokens": 7, "output_tokens": 3})
        assert c.input_tokens == 17
        assert c.output_tokens == 8
        assert c.total_tokens == 25

    def test_handles_missing_keys(self):
        c = _SessionCounters()
        c.absorb_assistant_usage({"input_tokens": 4})  # no output
        assert c.input_tokens == 4
        assert c.output_tokens == 0

    def test_handles_none(self):
        c = _SessionCounters()
        c.absorb_assistant_usage(None)
        c.absorb_assistant_usage("not a dict")  # type: ignore
        assert c.total_tokens == 0

    def test_cache_tokens_tracked_separately(self):
        c = _SessionCounters()
        c.absorb_assistant_usage(
            {
                "input_tokens": 1,
                "output_tokens": 2,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 200,
            }
        )
        # total_tokens uses input + output, not cache.
        assert c.total_tokens == 3
        assert c.cache_creation_input_tokens == 100
        assert c.cache_read_input_tokens == 200


# ----------------------------------------------------------------------
# Truncation helper
# ----------------------------------------------------------------------


class TestTruncateForLog:
    def test_short_string_passes_through(self):
        assert _truncate_for_log("hello", 100) == "hello"

    def test_long_string_gets_ellipsis(self):
        v = _truncate_for_log("x" * 100, limit=10)
        assert v == "xxxxxxxxxx" + " …[truncated]"

    def test_dict_recursively_truncated(self):
        v = _truncate_for_log({"k": "y" * 100}, limit=5)
        assert v["k"].startswith("yyyyy")
        assert "[truncated]" in v["k"]

    def test_list_recursively_truncated(self):
        v = _truncate_for_log(["a", "b" * 100], limit=3)
        assert v[0] == "a"
        assert "[truncated]" in v[1]

    def test_nondict_nonstring_passes_through(self):
        assert _truncate_for_log(42) == 42
        assert _truncate_for_log(None) is None
        assert _truncate_for_log(True) is True


# ----------------------------------------------------------------------
# AcpAgentSession behavior with a mocked SDK
# ----------------------------------------------------------------------


class TestAcpAgentSession:
    """Drive AcpAgentSession with a fully-mocked ClaudeSDKClient. The
    SDK's real subprocess + claude CLI never run."""

    def _run_session_sync(self, mock_messages, *, on_event=None):
        return asyncio.run(self._run_with_mocked_sdk(mock_messages, on_event=on_event))

    async def _run_with_mocked_sdk(self, mock_messages, *, on_event=None):
        """Helper: patch the SDK to yield mock_messages from
        receive_response, then run the session."""
        events = []

        def collector(ev):
            events.append(ev)
            if on_event:
                on_event(ev)

        # Build a fake async-context-manager mock for ClaudeSDKClient
        client_mock = AsyncMock()
        client_mock.query = AsyncMock()

        async def _yield():
            for m in mock_messages:
                yield m

        client_mock.receive_response = MagicMock(return_value=_yield())
        client_mock.interrupt = AsyncMock()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client_mock)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch("claude_agent_sdk.ClaudeSDKClient", return_value=cm):
            session = AcpAgentSession(
                workspace_path="/tmp/ws",
                prompt="do the thing",
                model="claude-opus-4",
                on_event=collector,
            )
            status = await session.run_task()
        return status, session, events

    def test_succeeded_path(self):
        pytest.importorskip('claude_agent_sdk')
        from claude_agent_sdk import ResultMessage
        result = ResultMessage(
            subtype="success",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=2,
            session_id="sess-1",
            stop_reason="end_turn",
            total_cost_usd=0.0,
            usage={"input_tokens": 50, "output_tokens": 25},
            result="done",
            structured_output=None,
            model_usage=None,
            permission_denials=None,
            errors=None,
            uuid="u1",
        )
        status, session, events = self._run_session_sync([result])
        assert status == "succeeded"
        assert session.session_id == "sess-1"
        assert session.input_tokens == 50
        assert session.output_tokens == 25
        # Session start + result events emitted to on_event.
        kinds = [e.event for e in events]
        assert "acp_session_start" in kinds
        assert "acp_result" in kinds

    def test_failed_path(self):
        pytest.importorskip('claude_agent_sdk')
        from claude_agent_sdk import ResultMessage
        result = ResultMessage(
            subtype="error",
            duration_ms=10, duration_api_ms=5, is_error=True,
            num_turns=1, session_id="sess-2",
            stop_reason=None, total_cost_usd=None,
            usage=None, result=None, structured_output=None,
            model_usage=None, permission_denials=None,
            errors=["something went wrong"], uuid="u2",
        )
        status, session, _ = self._run_session_sync([result])
        assert status == "failed"
        assert session.last_error == "something went wrong"

    def test_interrupt_returns_interrupted(self):
        # Drive an empty response stream after a terminate(), which
        # sets _stop_requested=True so the next yield breaks out.
        # Easiest: patch ClaudeSDKClient with a never-yielding stream
        # and call terminate() before it starts.
        from claude_agent_sdk import AssistantMessage, TextBlock

        async def slow_stream():
            # Never yield anything synchronously; the session loop will
            # check _stop_requested first.
            await asyncio.sleep(0.01)
            yield AssistantMessage(
                content=[TextBlock(text="never seen")],
                model="x", parent_tool_use_id=None, error=None,
                usage=None, message_id="m", stop_reason=None,
                session_id="s", uuid="u",
            )

        client_mock = AsyncMock()
        client_mock.query = AsyncMock()
        client_mock.receive_response = MagicMock(return_value=slow_stream())
        client_mock.interrupt = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client_mock)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def runner():
            with patch("claude_agent_sdk.ClaudeSDKClient", return_value=cm):
                session = AcpAgentSession(
                    workspace_path="/tmp/ws", prompt="x", model="m",
                )
                await session.terminate()  # set _stop_requested before run
                return await session.run_task()
        status = asyncio.run(runner())
        assert status == "interrupted"

    def test_emits_session_start_with_bypass_permissions(self):
        pytest.importorskip('claude_agent_sdk')
        from claude_agent_sdk import ResultMessage
        result = ResultMessage(
            subtype="success", duration_ms=1, duration_api_ms=1,
            is_error=False, num_turns=0, session_id="s",
            stop_reason=None, total_cost_usd=None,
            usage=None, result=None, structured_output=None,
            model_usage=None, permission_denials=None,
            errors=None, uuid="u",
        )
        _, _, events = self._run_session_sync([result])
        starts = [e for e in events if e.event == "acp_session_start"]
        assert len(starts) == 1
        # Permission mode is "default" (not bypassPermissions) so
        # can_use_tool fires and oompah's catalog is the only allowed
        # surface. The strict-allowlist policy is recorded for audit.
        assert starts[0].payload["permission_mode"] == "default"
        assert starts[0].payload["tool_policy"] == (
            "strict_allowlist:mcp__oompah__*"
        )
        # The native-tool denylist is recorded too — Bash et al. are
        # hard-blocked at the SDK config layer because can_use_tool
        # alone doesn't gate built-ins.
        denied = starts[0].payload["disallowed_native_tools"]
        for builtin in ("Bash", "Read", "Write", "Edit", "Glob", "Grep"):
            assert builtin in denied, f"missing {builtin!r} in denylist"

    def test_errored_when_sdk_raises(self):
        async def boom():
            raise RuntimeError("subprocess crashed")
            yield  # unreachable but makes this an async generator

        client_mock = AsyncMock()
        client_mock.query = AsyncMock()
        client_mock.receive_response = MagicMock(return_value=boom())
        client_mock.interrupt = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client_mock)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def runner():
            with patch("claude_agent_sdk.ClaudeSDKClient", return_value=cm):
                session = AcpAgentSession(
                    workspace_path="/tmp/ws", prompt="x", model="m",
                )
                return await session.run_task(), session
        status, session = asyncio.run(runner())
        assert status == "errored"
        assert "subprocess crashed" in (session.last_error or "")


# ----------------------------------------------------------------------
# can_use_tool strict allowlist (oompah-zlz_2-bcl.6)
# ----------------------------------------------------------------------


class TestCanUseToolStrictAllowlist:
    """Verifies the can_use_tool callback installed in AcpAgentSession:

    * Allows tools whose name starts with ``mcp__oompah__`` (our
      MCP-bridged catalog).
    * Denies every claude built-in (Bash, Read, Write, Edit, Glob,
      Grep, WebFetch, Task, etc.) so the cd-out-of-worktree guard
      and shell-redirect stay in force.
    * Emits an `acp_permission_grant` event for allows and an
      `acp_permission_deny` event for denies, both with the tool
      name and a truncated copy of the input args so the
      agent_watcher (planned, plans/agent-watcher.md) can audit
      retroactively.
    """

    def _capture_callback(self):
        """Extract the can_use_tool callback the session installs.

        We can't easily run a real ClaudeSDKClient here, so capture
        the callback by intercepting ClaudeAgentOptions construction
        inside run_task() and short-circuit the session loop.
        """
        captured = {}

        from claude_agent_sdk import ClaudeAgentOptions as _Real

        def _spy(*args, **kwargs):
            captured["kwargs"] = kwargs
            return _Real(*args, **kwargs)

        events: list[AgentEvent] = []

        async def _stream():
            from claude_agent_sdk import ResultMessage
            yield ResultMessage(
                subtype="success", duration_ms=1, duration_api_ms=1,
                is_error=False, num_turns=0, session_id="s",
                stop_reason=None, total_cost_usd=None,
                usage=None, result=None, structured_output=None,
                model_usage=None, permission_denials=None,
                errors=None, uuid="u",
            )

        client_mock = AsyncMock()
        client_mock.query = AsyncMock()
        client_mock.receive_response = MagicMock(return_value=_stream())
        client_mock.interrupt = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client_mock)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def runner():
            with patch("claude_agent_sdk.ClaudeAgentOptions", _spy):
                with patch("claude_agent_sdk.ClaudeSDKClient",
                           return_value=cm):
                    session = AcpAgentSession(
                        workspace_path="/tmp/ws",
                        prompt="x",
                        model="claude-opus-4-7",
                        on_event=events.append,
                    )
                    await session.run_task()

        asyncio.run(runner())
        return captured["kwargs"]["can_use_tool"], events

    def test_session_installs_can_use_tool(self):
        callback, _ = self._capture_callback()
        assert callable(callback)

    def test_session_passes_disallowed_native_tools(self):
        # Verifies the SDK gets a disallowed_tools list covering
        # claude's native built-ins, so they're hard-blocked at config
        # load and never reach the can_use_tool callback. Without this
        # the SDK auto-allows native tools — the bug we observed live
        # before the fix.
        from claude_agent_sdk import ClaudeAgentOptions as _Real

        captured: dict = {}

        def _spy(*args, **kwargs):
            captured["kwargs"] = kwargs
            return _Real(*args, **kwargs)

        async def _stream():
            from claude_agent_sdk import ResultMessage
            yield ResultMessage(
                subtype="success", duration_ms=1, duration_api_ms=1,
                is_error=False, num_turns=0, session_id="s",
                stop_reason=None, total_cost_usd=None, usage=None,
                result=None, structured_output=None, model_usage=None,
                permission_denials=None, errors=None, uuid="u",
            )

        client_mock = AsyncMock()
        client_mock.query = AsyncMock()
        client_mock.receive_response = MagicMock(return_value=_stream())
        client_mock.interrupt = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client_mock)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def runner():
            with patch("claude_agent_sdk.ClaudeAgentOptions", _spy), \
                 patch("claude_agent_sdk.ClaudeSDKClient", return_value=cm):
                session = AcpAgentSession(
                    workspace_path="/tmp/ws", prompt="x",
                    model="claude-opus-4-7",
                )
                await session.run_task()

        asyncio.run(runner())
        denied = captured["kwargs"]["disallowed_tools"]
        # Claude's full built-in surface (as of this writing) must be
        # blocked. New entries Anthropic adds will need explicit
        # additions — that's the point of the test, to surface drift.
        for builtin in ("Bash", "BashOutput", "Edit", "Glob", "Grep",
                        "KillShell", "NotebookEdit", "Read", "Task",
                        "TodoWrite", "ToolSearch", "WebFetch",
                        "WebSearch", "Write"):
            assert builtin in denied, f"missing {builtin!r} in disallowed_tools"

    def test_oompah_tool_allowed(self):
        pytest.importorskip('claude_agent_sdk')
        from claude_agent_sdk import PermissionResultAllow
        callback, events = self._capture_callback()
        result = asyncio.run(callback(
            "mcp__oompah__read_file", {"path": "x.py"}, MagicMock(),
        ))
        assert isinstance(result, PermissionResultAllow)

    def test_native_bash_denied(self):
        pytest.importorskip('claude_agent_sdk')
        from claude_agent_sdk import PermissionResultDeny
        callback, _ = self._capture_callback()
        result = asyncio.run(callback("Bash", {"command": "ls"}, MagicMock()))
        assert isinstance(result, PermissionResultDeny)
        assert "not in oompah's allowed catalog" in result.message
        # `interrupt=False` lets claude see the deny and continue —
        # important so a single misuse doesn't terminate the whole turn.
        assert result.interrupt is False

    def test_native_read_denied(self):
        pytest.importorskip('claude_agent_sdk')
        from claude_agent_sdk import PermissionResultDeny
        callback, _ = self._capture_callback()
        result = asyncio.run(callback("Read", {"file_path": "/etc/passwd"}, MagicMock()))
        assert isinstance(result, PermissionResultDeny)

    def test_native_write_denied(self):
        pytest.importorskip('claude_agent_sdk')
        from claude_agent_sdk import PermissionResultDeny
        callback, _ = self._capture_callback()
        result = asyncio.run(callback("Write", {"file_path": "x", "content": "y"}, MagicMock()))
        assert isinstance(result, PermissionResultDeny)

    def test_other_mcp_server_denied(self):
        # Even another MCP server's tools (mcp__some_other__*) are
        # denied — strict allowlist means oompah's catalog only.
        from claude_agent_sdk import PermissionResultDeny
        callback, _ = self._capture_callback()
        result = asyncio.run(callback("mcp__rogue__do_thing", {}, MagicMock()))
        assert isinstance(result, PermissionResultDeny)

    def test_grant_emits_jsonl_event(self):
        callback, _ = self._capture_callback()
        captured: list[AgentEvent] = []

        # Re-run capture but with fresh on_event we can introspect.
        from claude_agent_sdk import ClaudeAgentOptions as _Real

        async def runner():
            kwargs = {}

            def _spy(*args, **kw):
                kwargs.update(kw)
                return _Real(*args, **kw)

            async def _stream():
                from claude_agent_sdk import ResultMessage
                yield ResultMessage(
                    subtype="success", duration_ms=1, duration_api_ms=1,
                    is_error=False, num_turns=0, session_id="s",
                    stop_reason=None, total_cost_usd=None, usage=None,
                    result=None, structured_output=None, model_usage=None,
                    permission_denials=None, errors=None, uuid="u",
                )

            client_mock = AsyncMock()
            client_mock.query = AsyncMock()
            client_mock.receive_response = MagicMock(return_value=_stream())
            client_mock.interrupt = AsyncMock()
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=client_mock)
            cm.__aexit__ = AsyncMock(return_value=None)

            with patch("claude_agent_sdk.ClaudeAgentOptions", _spy), \
                 patch("claude_agent_sdk.ClaudeSDKClient", return_value=cm):
                session = AcpAgentSession(
                    workspace_path="/tmp/ws", prompt="x",
                    model="claude-opus-4-7",
                    on_event=captured.append,
                )
                await session.run_task()
            return kwargs["can_use_tool"]

        cb = asyncio.run(runner())
        # Now drive the callback once and observe the emitted event.
        captured.clear()
        asyncio.run(cb("mcp__oompah__read_file", {"path": "x"}, MagicMock()))
        kinds = [e.event for e in captured]
        assert "acp_permission_grant" in kinds
        grant = next(e for e in captured if e.event == "acp_permission_grant")
        assert grant.payload["tool"] == "mcp__oompah__read_file"
        # input is recorded for audit
        assert grant.payload["input"] == {"path": "x"}

    def test_deny_emits_jsonl_event(self):
        captured: list[AgentEvent] = []
        from claude_agent_sdk import ClaudeAgentOptions as _Real

        async def runner():
            kwargs = {}

            def _spy(*args, **kw):
                kwargs.update(kw)
                return _Real(*args, **kw)

            async def _stream():
                from claude_agent_sdk import ResultMessage
                yield ResultMessage(
                    subtype="success", duration_ms=1, duration_api_ms=1,
                    is_error=False, num_turns=0, session_id="s",
                    stop_reason=None, total_cost_usd=None, usage=None,
                    result=None, structured_output=None, model_usage=None,
                    permission_denials=None, errors=None, uuid="u",
                )

            client_mock = AsyncMock()
            client_mock.query = AsyncMock()
            client_mock.receive_response = MagicMock(return_value=_stream())
            client_mock.interrupt = AsyncMock()
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=client_mock)
            cm.__aexit__ = AsyncMock(return_value=None)

            with patch("claude_agent_sdk.ClaudeAgentOptions", _spy), \
                 patch("claude_agent_sdk.ClaudeSDKClient", return_value=cm):
                session = AcpAgentSession(
                    workspace_path="/tmp/ws", prompt="x",
                    model="claude-opus-4-7",
                    on_event=captured.append,
                )
                await session.run_task()
            return kwargs["can_use_tool"]

        cb = asyncio.run(runner())
        captured.clear()
        asyncio.run(cb("Bash", {"command": "rm -rf /"}, MagicMock()))
        denies = [e for e in captured if e.event == "acp_permission_deny"]
        assert len(denies) == 1
        assert denies[0].payload["tool"] == "Bash"


# ----------------------------------------------------------------------
# Tool catalog bridging
# ----------------------------------------------------------------------


# TestToolCatalogBridging calls build_tool_catalog() which requires
# claude_agent_sdk. Skip when it is not installed (base install without
# [claude] extra).
try:
    import claude_agent_sdk
except ImportError:
    pytest.skip("claude_agent_sdk not installed; install with uv pip install 'oompah[claude]'", allow_module_level=True)


class TestSystemPromptFileTransport:
    """The (possibly large) rendered prompt must reach the CLI via a
    --system-prompt-file (file dict), not an inline --system-prompt
    string, so the SDK doesn't exec the bundled binary with an oversized
    argv ("Argument list too long")."""

    def _run_and_capture(self, prompt):
        from claude_agent_sdk import ClaudeAgentOptions as _Real

        captured: dict = {}

        def _spy(*args, **kwargs):
            captured["kwargs"] = kwargs
            # Snapshot the system_prompt file contents while the temp file
            # still exists (run_task removes it in its finally).
            sp = kwargs.get("system_prompt")
            if isinstance(sp, dict) and sp.get("type") == "file":
                try:
                    with open(sp["path"], encoding="utf-8") as f:
                        captured["file_contents"] = f.read()
                except OSError:
                    captured["file_contents"] = None
            return _Real(*args, **kwargs)

        async def _stream():
            from claude_agent_sdk import ResultMessage
            yield ResultMessage(
                subtype="success", duration_ms=1, duration_api_ms=1,
                is_error=False, num_turns=0, session_id="s",
                stop_reason=None, total_cost_usd=None, usage=None,
                result=None, structured_output=None, model_usage=None,
                permission_denials=None, errors=None, uuid="u",
            )

        client_mock = AsyncMock()
        client_mock.query = AsyncMock()
        client_mock.receive_response = MagicMock(return_value=_stream())
        client_mock.interrupt = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client_mock)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def runner():
            with patch("claude_agent_sdk.ClaudeAgentOptions", _spy), \
                 patch("claude_agent_sdk.ClaudeSDKClient", return_value=cm):
                session = AcpAgentSession(
                    workspace_path="/tmp/ws", prompt=prompt,
                    model="claude-opus-4-7",
                )
                await session.run_task()
                return session

        session = asyncio.run(runner())
        return captured, session

    def test_system_prompt_passed_as_file(self):
        big = "X" * 500_000  # would blow the OS arg limit if passed inline
        captured, _session = self._run_and_capture(big)
        sp = captured["kwargs"]["system_prompt"]
        assert isinstance(sp, dict) and sp.get("type") == "file"
        assert sp.get("path")
        # The file carried the full prompt verbatim.
        assert captured.get("file_contents") == big

    def test_temp_prompt_file_cleaned_up(self):
        captured, _session = self._run_and_capture("hello")
        path = captured["kwargs"]["system_prompt"]["path"]
        # run_turn's finally removed the temp file.
        assert not os.path.exists(path)


class TestToolCatalogBridging:
    """The catalog must declare oompah's tools (so claude doesn't
    use its native ones) and route through the existing _exec_*
    implementations (preserving cd-guard + shell-redirect)."""

    def test_catalog_includes_oompah_tools(self, tmp_path):
        from oompah.acp_tools import build_tool_catalog
        cat = build_tool_catalog(str(tmp_path))
        names = [t.name for t in cat]
        # Q2 acceptance — full set of tools claude should be able to call.
        for expected in ("read_file", "write_file", "edit_file",
                         "list_files", "search_files", "run_command",
                         "get_project", "update_project"):
            assert expected in names, f"missing {expected!r} in catalog"

    def test_catalog_size_reflects_locked_set(self, tmp_path):
        # Adding new tools is a deliberate change — this test surfaces it.
        # Now 8: the original 6 + get_project + update_project (TASK-464.8).
        from oompah.acp_tools import build_tool_catalog
        cat = build_tool_catalog(str(tmp_path))
        assert len(cat) == 8


# ----------------------------------------------------------------------
# Orchestrator dispatch routing by profile.mode
# ----------------------------------------------------------------------


class TestRunWorkerRouting:
    """_run_worker must dispatch based on profile.mode. Mocks all three
    workers so we can observe which one fires."""

    def _make_orch_with_mocks(self, tmp_path):
        from unittest.mock import MagicMock
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator
        from oompah.providers import ProviderStore

        cfg = ServiceConfig()
        provider_store = ProviderStore(path=str(tmp_path / "providers.json"))
        project_store = MagicMock()
        project_store.list_all.return_value = []
        orch = Orchestrator(
            config=cfg, workflow_path="WORKFLOW.md",
            provider_store=provider_store, project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        orch._run_acp_worker = AsyncMock()
        orch._run_api_worker = AsyncMock()
        orch._run_cli_worker = AsyncMock()
        return orch

    def test_mode_acp_routes_to_acp_worker(self, tmp_path):
        orch = self._make_orch_with_mocks(tmp_path)
        profile = AgentProfile(name="claude-sub", command="claude --acp", mode="acp")
        issue = Issue(id="i", identifier="i", title="t", description="b", state="open")
        asyncio.run(orch._run_worker(issue, attempt=None, profile=profile))
        orch._run_acp_worker.assert_called_once()
        orch._run_api_worker.assert_not_called()
        orch._run_cli_worker.assert_not_called()

    def test_mode_cli_routes_to_cli_worker(self, tmp_path):
        orch = self._make_orch_with_mocks(tmp_path)
        profile = AgentProfile(name="legacy", command="claude", mode="cli")
        issue = Issue(id="i", identifier="i", title="t", description="b", state="open")
        asyncio.run(orch._run_worker(issue, attempt=None, profile=profile))
        orch._run_cli_worker.assert_called_once()
        orch._run_acp_worker.assert_not_called()
        orch._run_api_worker.assert_not_called()

    def test_mode_auto_with_no_provider_routes_to_cli(self, tmp_path):
        orch = self._make_orch_with_mocks(tmp_path)
        profile = AgentProfile(name="x", command="claude")  # mode=auto default
        issue = Issue(id="i", identifier="i", title="t", description="b", state="open")
        # No provider configured → cli fallback.
        asyncio.run(orch._run_worker(issue, attempt=None, profile=profile))
        orch._run_cli_worker.assert_called_once()
        orch._run_acp_worker.assert_not_called()


# ----------------------------------------------------------------------
# Budget gate bypass for ACP profiles
# ----------------------------------------------------------------------


class TestBudgetBypassForAcpProfiles:
    """ACP profiles bypass the budget gate even when over limit. The
    cost is billed against the operator's claude subscription, not the
    per-token API meter the budget tracks."""

    def _make_orch(self, tmp_path, profile_mode: str):
        from unittest.mock import MagicMock
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator
        from oompah.providers import ProviderStore

        cfg = ServiceConfig()
        cfg.budget_limit = 10.0
        cfg.agent_profiles = [
            AgentProfile(name="default", command="claude", mode=profile_mode),
        ]
        provider_store = ProviderStore(path=str(tmp_path / "providers.json"))
        project_store = MagicMock()
        project_store.list_all.return_value = []
        return Orchestrator(
            config=cfg, workflow_path="WORKFLOW.md",
            provider_store=provider_store, project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

    def _force_over_budget(self, orch):
        import time
        orch.state.agent_totals.estimated_cost = 999.0
        orch.state.budget_window_start = time.time()
        orch.state.budget_window_kind = "day"

    def test_acp_profile_dispatches_when_over_budget(self, tmp_path):
        orch = self._make_orch(tmp_path, "acp")
        issue = Issue(id="i", identifier="i", title="t", description="b", state="open")
        self._force_over_budget(orch)
        # ACP profiles bypass the budget cap entirely.
        assert orch._should_dispatch(issue) is True
        # Free-tier counter NOT incremented (this isn't a free-tier
        # bypass; it's an ACP-mode bypass).
        assert orch.state.free_tier_dispatches_this_window == 0

    def test_non_acp_paid_profile_rejected_when_over_budget(self, tmp_path):
        orch = self._make_orch(tmp_path, "auto")
        issue = Issue(id="i", identifier="i", title="t", description="b", state="open")
        self._force_over_budget(orch)
        # No provider configured + no model_costs → free model resolution
        # fails → reject.
        assert orch._should_dispatch(issue) is False

    def test_would_dispatch_via_acp_returns_false_for_non_acp(self, tmp_path):
        orch = self._make_orch(tmp_path, "auto")
        issue = Issue(id="i", identifier="i", title="t", description="b", state="open")
        assert orch._would_dispatch_via_acp(issue) is False

    def test_would_dispatch_via_acp_returns_true_for_acp(self, tmp_path):
        orch = self._make_orch(tmp_path, "acp")
        issue = Issue(id="i", identifier="i", title="t", description="b", state="open")
        assert orch._would_dispatch_via_acp(issue) is True
