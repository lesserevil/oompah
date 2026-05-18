"""Tests for the SDK import guards and install-hint error messages.

Verifies that every lazy SDK import in the ACP backends surfaces a
clear ``uv pip install 'oompah[<extra>]'`` hint when the SDK is absent
or incomplete, rather than an obscure ModuleNotFoundError.

Covers (oompah-zlz_2-jrkz.2):
* ``build_tool_catalog`` raises ImportError with ``oompah[claude]`` hint
  when claude-agent-sdk is missing (acp_tools.py guard).
* ``ClaudeAcpBackendSession.run_turn`` sets status=errored with
  ``oompah[claude]`` hint when the full SDK import fails.
* ``ClaudeAcpBackendSession.run_turn`` sets status=errored with
  ``oompah[claude]`` hint when ``PermissionResultAllow/Deny`` are missing
  (second SDK import guard).
* ``ClaudeAcpBackendSession.run_turn`` sets status=errored with
  ``oompah[claude]`` hint when ``create_sdk_mcp_server`` is missing.
* ``_import_sdk`` (codex backend) raises ImportError with ``oompah[codex]``
  hint when openai-agents is missing.
* ``build_codex_tool_catalog`` raises ImportError with ``oompah[codex]``
  hint when openai-agents is missing.
"""

from __future__ import annotations

import asyncio
import builtins
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.acp_backends.base import AcpBackendOptions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _block_module(monkeypatch, *module_names: str):
    """Monkeypatch builtins.__import__ so the named modules raise
    ImportError instead of resolving, regardless of whether they are
    already cached in sys.modules."""
    for name in module_names:
        monkeypatch.delitem(sys.modules, name, raising=False)

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name in module_names:
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)


def _make_partial_claude_sdk(*, include_permission_results: bool = True,
                              include_mcp_server: bool = True) -> types.ModuleType:
    """Build a fake ``claude_agent_sdk`` module with a configurable
    subset of attributes — so we can test guards that fire when specific
    symbols are missing from an otherwise importable SDK."""
    sdk = types.ModuleType("claude_agent_sdk")
    # Always include first-import-block symbols.
    sdk.ClaudeAgentOptions = MagicMock()
    sdk.ClaudeSDKClient = MagicMock()
    sdk.AssistantMessage = MagicMock()
    sdk.ResultMessage = MagicMock()
    sdk.UserMessage = MagicMock()
    sdk.TextBlock = MagicMock()
    sdk.ToolUseBlock = MagicMock()
    sdk.ToolResultBlock = MagicMock()
    sdk.ThinkingBlock = MagicMock()

    if include_permission_results:
        sdk.PermissionResultAllow = MagicMock()
        sdk.PermissionResultDeny = MagicMock()
    if include_mcp_server:
        sdk.create_sdk_mcp_server = MagicMock()

    return sdk


# ---------------------------------------------------------------------------
# acp_tools.build_tool_catalog — claude guard
# ---------------------------------------------------------------------------


class TestBuildToolCatalogClaudeGuard:
    def test_missing_sdk_raises_import_error(self, monkeypatch, tmp_path):
        """build_tool_catalog must raise ImportError with a clear
        oompah[claude] install hint when claude-agent-sdk is not installed."""
        _block_module(monkeypatch, "claude_agent_sdk")

        from oompah.acp_tools import build_tool_catalog

        with pytest.raises(ImportError) as exc_info:
            build_tool_catalog(str(tmp_path))
        msg = str(exc_info.value)
        assert "oompah[claude]" in msg

    def test_error_message_includes_uv_command(self, monkeypatch, tmp_path):
        """The install hint must use uv pip install (not bare pip install)."""
        _block_module(monkeypatch, "claude_agent_sdk")

        from oompah.acp_tools import build_tool_catalog

        with pytest.raises(ImportError) as exc_info:
            build_tool_catalog(str(tmp_path))
        assert "uv pip install" in str(exc_info.value)


# ---------------------------------------------------------------------------
# acp_tools.build_codex_tool_catalog — codex guard (updated hint)
# ---------------------------------------------------------------------------


class TestBuildCodexToolCatalogCodexGuard:
    def test_missing_sdk_raises_import_error(self, monkeypatch, tmp_path):
        """build_codex_tool_catalog raises ImportError with a clear
        oompah[codex] install hint when openai-agents is missing."""
        _block_module(monkeypatch, "agents", "openai_agents")

        from oompah.acp_tools import build_codex_tool_catalog

        with pytest.raises(ImportError) as exc_info:
            build_codex_tool_catalog(str(tmp_path))
        msg = str(exc_info.value)
        assert "openai-agents" in msg
        assert "oompah[codex]" in msg

    def test_error_message_includes_uv_command(self, monkeypatch, tmp_path):
        _block_module(monkeypatch, "agents", "openai_agents")

        from oompah.acp_tools import build_codex_tool_catalog

        with pytest.raises(ImportError) as exc_info:
            build_codex_tool_catalog(str(tmp_path))
        assert "uv pip install" in str(exc_info.value)


# ---------------------------------------------------------------------------
# codex._import_sdk — updated install hint
# ---------------------------------------------------------------------------


class TestImportSdkCodexGuard:
    def test_missing_sdk_error_mentions_oompah_codex(self, monkeypatch):
        """_import_sdk raises ImportError with oompah[codex] hint when
        neither 'agents' nor 'openai_agents' resolve."""
        _block_module(monkeypatch, "agents", "openai_agents")

        from oompah.acp_backends.codex import _import_sdk

        with pytest.raises(ImportError) as exc_info:
            _import_sdk()
        msg = str(exc_info.value)
        assert "oompah[codex]" in msg
        assert "uv pip install" in msg


# ---------------------------------------------------------------------------
# ClaudeAcpBackendSession.run_turn — full-SDK-import guard (updated hint)
# ---------------------------------------------------------------------------


class TestClaudeSessionFullSdkGuard:
    def test_missing_full_sdk_sets_errored_with_claude_hint(self, monkeypatch):
        """When the first claude_agent_sdk import fails (ClaudeSDKClient
        etc.), run_turn must set status=errored and include oompah[claude]
        in last_error."""
        _block_module(monkeypatch, "claude_agent_sdk")

        from oompah.acp_backends.claude import ClaudeAcpBackendSession

        async def run():
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            sess = ClaudeAcpBackendSession(opt)
            collected = []
            async for ev in sess.run_turn():
                collected.append(ev)
            return sess

        sess = asyncio.run(run())
        assert sess.status == "errored"
        assert sess.last_error is not None
        assert "oompah[claude]" in sess.last_error
        assert "uv pip install" in sess.last_error


# ---------------------------------------------------------------------------
# ClaudeAcpBackendSession.run_turn — PermissionResultAllow/Deny guard
# ---------------------------------------------------------------------------


class TestClaudeSessionPermissionGuard:
    """Exercises the second claude_agent_sdk import guard.

    The guard fires when the first import (ClaudeAgentOptions etc.)
    succeeds but the second one (PermissionResultAllow/Deny) fails.
    This can happen with a partial or older claude-agent-sdk install.

    We test this by installing a fake SDK module that has all the
    first-import-block symbols but NOT PermissionResultAllow/Deny.
    Python's ``from module import X`` raises ImportError when X is
    absent from the module object.
    """

    def test_missing_permission_symbols_sets_errored(self, monkeypatch):
        """When PermissionResultAllow/Deny are absent (partial install),
        run_turn sets status=errored with an oompah[claude] hint."""
        partial_sdk = _make_partial_claude_sdk(
            include_permission_results=False,
            include_mcp_server=True,
        )
        monkeypatch.setitem(sys.modules, "claude_agent_sdk", partial_sdk)

        from oompah.acp_backends.claude import ClaudeAcpBackendSession

        async def run():
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            sess = ClaudeAcpBackendSession(opt)
            collected = []
            async for ev in sess.run_turn():
                collected.append(ev)
            return sess

        sess = asyncio.run(run())
        assert sess.status == "errored"
        assert sess.last_error is not None
        assert "oompah[claude]" in sess.last_error

    def test_missing_permission_symbols_error_mentions_uv(self, monkeypatch):
        """The install hint in the PermissionResultAllow/Deny guard must
        use 'uv pip install' (not bare pip install)."""
        partial_sdk = _make_partial_claude_sdk(
            include_permission_results=False,
            include_mcp_server=True,
        )
        monkeypatch.setitem(sys.modules, "claude_agent_sdk", partial_sdk)

        from oompah.acp_backends.claude import ClaudeAcpBackendSession

        async def run():
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            sess = ClaudeAcpBackendSession(opt)
            collected = []
            async for ev in sess.run_turn():
                collected.append(ev)
            return sess

        sess = asyncio.run(run())
        assert "uv pip install" in (sess.last_error or "")


# ---------------------------------------------------------------------------
# ClaudeAcpBackendSession.run_turn — create_sdk_mcp_server guard
# ---------------------------------------------------------------------------


class TestClaudeSessionMcpServerGuard:
    """Exercises the create_sdk_mcp_server import guard.

    This guard fires when tool_catalog is non-empty but
    create_sdk_mcp_server is not available in the installed SDK
    (older SDK version).
    """

    def test_missing_mcp_server_symbol_sets_errored(self, monkeypatch):
        """When tool_catalog is set but create_sdk_mcp_server is absent,
        run_turn sets status=errored with an oompah[claude] hint."""
        partial_sdk = _make_partial_claude_sdk(
            include_permission_results=True,
            include_mcp_server=False,
        )
        monkeypatch.setitem(sys.modules, "claude_agent_sdk", partial_sdk)

        from oompah.acp_backends.claude import ClaudeAcpBackendSession

        fake_tool = MagicMock()
        fake_tool.name = "fake_tool"

        async def run():
            opt = AcpBackendOptions(
                workspace_path="/tmp/ws",
                prompt="x",
                tool_catalog=[fake_tool],
            )
            sess = ClaudeAcpBackendSession(opt)
            collected = []
            async for ev in sess.run_turn():
                collected.append(ev)
            return sess

        sess = asyncio.run(run())
        assert sess.status == "errored"
        assert sess.last_error is not None
        assert "oompah[claude]" in sess.last_error

    def test_missing_mcp_server_hint_uses_uv(self, monkeypatch):
        """The install hint in the create_sdk_mcp_server guard uses
        'uv pip install'."""
        partial_sdk = _make_partial_claude_sdk(
            include_permission_results=True,
            include_mcp_server=False,
        )
        monkeypatch.setitem(sys.modules, "claude_agent_sdk", partial_sdk)

        from oompah.acp_backends.claude import ClaudeAcpBackendSession

        fake_tool = MagicMock()
        fake_tool.name = "fake_tool"

        async def run():
            opt = AcpBackendOptions(
                workspace_path="/tmp/ws",
                prompt="x",
                tool_catalog=[fake_tool],
            )
            sess = ClaudeAcpBackendSession(opt)
            collected = []
            async for ev in sess.run_turn():
                collected.append(ev)
            return sess

        sess = asyncio.run(run())
        assert "uv pip install" in (sess.last_error or "")

    def test_no_tool_catalog_skips_mcp_server_path(self, monkeypatch):
        """When tool_catalog is absent (None), the create_sdk_mcp_server
        branch is never reached — even if the symbol is missing."""
        partial_sdk = _make_partial_claude_sdk(
            include_permission_results=True,
            include_mcp_server=False,
        )
        monkeypatch.setitem(sys.modules, "claude_agent_sdk", partial_sdk)

        from oompah.acp_backends.claude import ClaudeAcpBackendSession

        # We need a good enough mock to not crash on ClaudeSDKClient.
        # Just verify status is NOT errored due to the mcp_server symbol.
        # (It will still error on ClaudeSDKClient since the mock is a
        # MagicMock, not a real async context manager — that's expected
        # and unrelated to our guard.)
        async def run():
            opt = AcpBackendOptions(
                workspace_path="/tmp/ws",
                prompt="x",
                tool_catalog=None,  # no catalog → skip mcp_server path
            )
            sess = ClaudeAcpBackendSession(opt)
            collected = []
            try:
                async for ev in sess.run_turn():
                    collected.append(ev)
            except Exception:
                pass
            return sess

        sess = asyncio.run(run())
        # Error (if any) must NOT mention missing create_sdk_mcp_server.
        assert "create_sdk_mcp_server" not in (sess.last_error or "")


# ---------------------------------------------------------------------------
# Verify updated error message strings
# ---------------------------------------------------------------------------


class TestInstallHintStrings:
    """Smoke-check the exact install hint strings in each error path."""

    def test_claude_full_sdk_error_oompah_extra(self, monkeypatch):
        _block_module(monkeypatch, "claude_agent_sdk")

        from oompah.acp_backends.claude import ClaudeAcpBackendSession

        async def run():
            opt = AcpBackendOptions(workspace_path="/tmp/ws", prompt="x")
            sess = ClaudeAcpBackendSession(opt)
            async for _ in sess.run_turn():
                pass
            return sess

        sess = asyncio.run(run())
        assert "oompah[claude]" in (sess.last_error or "")
        assert "uv pip install" in (sess.last_error or "")

    def test_codex_import_sdk_error_oompah_extra(self, monkeypatch):
        _block_module(monkeypatch, "agents", "openai_agents")

        from oompah.acp_backends.codex import _import_sdk

        with pytest.raises(ImportError) as exc_info:
            _import_sdk()
        assert "oompah[codex]" in str(exc_info.value)

    def test_build_tool_catalog_error_oompah_extra(self, monkeypatch, tmp_path):
        _block_module(monkeypatch, "claude_agent_sdk")

        from oompah.acp_tools import build_tool_catalog

        with pytest.raises(ImportError) as exc_info:
            build_tool_catalog(str(tmp_path))
        assert "oompah[claude]" in str(exc_info.value)

    def test_build_codex_tool_catalog_error_oompah_extra(
        self, monkeypatch, tmp_path
    ):
        _block_module(monkeypatch, "agents", "openai_agents")

        from oompah.acp_tools import build_codex_tool_catalog

        with pytest.raises(ImportError) as exc_info:
            build_codex_tool_catalog(str(tmp_path))
        assert "oompah[codex]" in str(exc_info.value)
