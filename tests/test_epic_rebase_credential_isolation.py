"""Credential-boundary regressions for direct epic-rebase helpers."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from oompah.acp_agent import AcpAgentSession
from oompah.api_agent import _exec_run_command
from oompah.rebase_worker_sandbox import (
    RebaseWorkerHostPolicyUnavailable,
    RebaseWorkerSandboxUnavailable,
    _probe_bubblewrap_namespaces,
    restricted_rebase_command,
)


_HOST_POLICY_DENIAL = "nested bubblewrap namespaces are denied by host policy"
_HOST_POLICY_ERROR = f"Error: {_HOST_POLICY_DENIAL}"


def _skip_when_nested_bubblewrap_is_denied(text: str) -> None:
    """Never turn failure to launch the sandbox into a passing assertion."""
    if text.strip() == _HOST_POLICY_ERROR:
        pytest.skip(_HOST_POLICY_DENIAL)


def _init_rebase_workspace(path):
    """Create the linked-worktree layout required by direct rebase workers."""
    source = path / "source"
    workspace = path / "workspace"
    source.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "Oompah"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "oompah@example.test"], cwd=source, check=True)
    (source / "base.txt").write_text("base\n")
    subprocess.run(["git", "add", "base.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=source, check=True)
    subprocess.run(["git", "worktree", "add", "-q", "-b", "worker", str(workspace)], cwd=source, check=True)
    return workspace


def test_api_worker_shell_does_not_inherit_remote_write_credentials(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GITHUB_TOKEN", "forge-secret")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/run/ssh-agent.sock")
    monkeypatch.setenv("ARBITRARY_FORGE_ROUTE", "forge-secret")
    workspace = _init_rebase_workspace(tmp_path)

    result = _exec_run_command(
        workspace,
        {"command": "env"},
        isolate_remote_write=True,
    )

    _skip_when_nested_bubblewrap_is_denied(result)
    assert "exit_code: 0" in result
    assert "forge-secret" not in result
    assert "GITHUB_TOKEN=" not in result
    assert "SSH_AUTH_SOCK=" not in result
    assert "ARBITRARY_FORGE_ROUTE=" not in result
    assert "GIT_CONFIG_GLOBAL=/dev/null" in result
    assert "GIT_SSH_COMMAND=/bin/false" in result
    assert "OOMPAH_TASK_HANDOFF_TOKEN=" not in result
    assert "OPENAI_API_KEY=" not in result
    assert "OOMPAH_WORKER_RUNTIME_DIR=" not in result


@pytest.mark.parametrize(
    "command",
    [
        "test ! -e /home/shedwards/.ssh",
        "git send-pack https://example.test/repo HEAD:refs/heads/escape",
        "gh api https://example.test/user",
        "curl --max-time 2 https://example.test/",
        "python3 -c 'import urllib.request; urllib.request.urlopen(\"https://example.test\", timeout=2)'",
    ],
)
def test_rebase_executor_blocks_host_credentials_and_remote_write_routes(
    tmp_path, command
):
    """The MCP shell is a namespace boundary, not a command blacklist."""
    workspace = _init_rebase_workspace(tmp_path)
    result = _exec_run_command(
        workspace,
        {"command": command},
        isolate_remote_write=True,
    )

    _skip_when_nested_bubblewrap_is_denied(result)
    if command.startswith("test"):
        assert "exit_code: 0" in result
    else:
        assert "exit_code: 0" not in result


def test_rebase_executor_supports_a_real_linked_worktree_without_remote_config(
    tmp_path,
):
    """The namespace keeps the local Git data needed for a rebase/commit."""
    source = tmp_path / "source"
    linked = tmp_path / "linked"
    source.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "Oompah"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "oompah@example.test"], cwd=source, check=True)
    (source / "base.txt").write_text("base\n")
    subprocess.run(["git", "add", "base.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=source, check=True)
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "rebase-worker", str(linked)],
        cwd=source,
        check=True,
    )

    result = _exec_run_command(
        linked,
        {
            "command": (
                "printf 'worker\\n' > worker.txt && git add worker.txt && "
                "git commit -m worker && git rebase --onto HEAD HEAD && git status --porcelain"
            )
        },
        isolate_remote_write=True,
    )

    _skip_when_nested_bubblewrap_is_denied(result)
    assert "exit_code: 0" in result
    assert (linked / "worker.txt").read_text() == "worker\n"
    # The ordinary shared config remains unchanged; the sandbox receives only
    # a private, sanitized overlay.
    assert "remote" not in (source / ".git" / "config").read_text().lower()


def test_rebase_executor_never_mounts_provider_or_handoff_runtime(tmp_path, monkeypatch):
    provider_runtime = tmp_path / "provider-runtime"
    provider_runtime.mkdir()
    (provider_runtime / "auth.json").write_text("provider-secret")
    monkeypatch.setenv("OOMPAH_WORKER_RUNTIME_DIR", str(provider_runtime))
    monkeypatch.setenv("OOMPAH_TASK_HANDOFF_TOKEN", "handoff-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "provider-secret")
    workspace = _init_rebase_workspace(tmp_path)

    result = _exec_run_command(
        workspace,
        {
            "command": (
                f"test ! -e {provider_runtime} && "
                "test -z \"${OOMPAH_TASK_HANDOFF_TOKEN:-}\" && "
                "test -z \"${OPENAI_API_KEY:-}\""
            )
        },
        isolate_remote_write=True,
    )

    _skip_when_nested_bubblewrap_is_denied(result)
    assert "exit_code: 0" in result


@pytest.mark.parametrize(
    "detail",
    [
        "bwrap: setting up uid map: Permission denied",
        (
            "bwrap: No permissions to create a new namespace, likely because "
            "the kernel does not allow non-privileged user namespaces."
        ),
    ],
)
def test_nested_bubblewrap_probe_classifies_host_policy_denial(
    monkeypatch,
    detail,
):
    from oompah import rebase_worker_sandbox as sandbox_module

    monkeypatch.setattr(
        sandbox_module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, stderr=detail),
    )

    with pytest.raises(
        RebaseWorkerHostPolicyUnavailable,
        match=_HOST_POLICY_DENIAL,
    ):
        _probe_bubblewrap_namespaces("/usr/bin/bwrap")


@pytest.mark.parametrize(
    "detail",
    [
        "bwrap: malformed trusted invocation",
        "bwrap: failed to ro-bind /usr: Permission denied",
        "bwrap: execve /bin/true: Operation not permitted",
    ],
)
def test_nested_bubblewrap_probe_keeps_other_failures_distinct(
    monkeypatch,
    detail,
):
    from oompah import rebase_worker_sandbox as sandbox_module

    monkeypatch.setattr(
        sandbox_module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 1, stderr=detail
        ),
    )

    with pytest.raises(RebaseWorkerSandboxUnavailable) as caught:
        _probe_bubblewrap_namespaces("/usr/bin/bwrap")

    assert not isinstance(caught.value, RebaseWorkerHostPolicyUnavailable)
    assert detail in str(caught.value)


@pytest.mark.parametrize(
    "text",
    [
        _HOST_POLICY_DENIAL,
        f"exit_code: 1\nstderr: {_HOST_POLICY_DENIAL}",
        f"Error: unrelated failure: {_HOST_POLICY_DENIAL}",
        f"{_HOST_POLICY_ERROR}\nadditional failure",
    ],
)
def test_nested_bubblewrap_skip_requires_exact_canonical_error(
    monkeypatch,
    text,
):
    skip = MagicMock(side_effect=AssertionError("noncanonical output was skipped"))
    monkeypatch.setattr(pytest, "skip", skip)

    _skip_when_nested_bubblewrap_is_denied(text)

    skip.assert_not_called()


def test_nested_bubblewrap_skip_accepts_exact_canonical_error(monkeypatch):
    skip = MagicMock()
    monkeypatch.setattr(pytest, "skip", skip)

    _skip_when_nested_bubblewrap_is_denied(f"  {_HOST_POLICY_ERROR}\n")

    skip.assert_called_once_with(_HOST_POLICY_DENIAL)


def test_nested_bubblewrap_host_denial_fails_closed_before_candidate_launch(
    tmp_path,
    monkeypatch,
):
    from oompah import api_agent as api_agent_module
    from oompah import rebase_worker_sandbox as sandbox_module

    workspace = _init_rebase_workspace(tmp_path)
    launch = MagicMock(side_effect=AssertionError("candidate command launched"))
    monkeypatch.setattr(api_agent_module.subprocess, "Popen", launch)
    monkeypatch.setattr(
        sandbox_module,
        "_probe_bubblewrap_namespaces",
        lambda _bubblewrap: (_ for _ in ()).throw(
            RebaseWorkerHostPolicyUnavailable(_HOST_POLICY_DENIAL)
        ),
    )

    result = _exec_run_command(
        workspace,
        {"command": "printf candidate-ran"},
        isolate_remote_write=True,
    )

    assert result == f"Error: {_HOST_POLICY_DENIAL}"
    launch.assert_not_called()


def test_rebase_sandbox_static_boundary_survives_nested_host_denial(
    tmp_path,
    monkeypatch,
):
    """Static fencing remains asserted when the dynamic namespace is blocked."""
    from oompah import rebase_worker_sandbox as sandbox_module

    workspace = _init_rebase_workspace(tmp_path)
    monkeypatch.setattr(sandbox_module.shutil, "which", lambda _name: "/usr/bin/bwrap")
    monkeypatch.setattr(
        sandbox_module,
        "_probe_bubblewrap_namespaces",
        lambda _bubblewrap: None,
    )
    command = restricted_rebase_command(
        "env",
        workspace,
        {
            "GITHUB_TOKEN": "forge-secret",
            "SSH_AUTH_SOCK": "/run/ssh-agent.sock",
        },
    )
    try:
        assert "--unshare-net" in command
        assert ["--setenv", "GIT_CONFIG_GLOBAL", os.devnull] in [
            command[index : index + 3]
            for index in range(len(command) - 2)
        ]
        joined = "\0".join(command)
        assert "forge-secret" not in joined
        assert "GITHUB_TOKEN" not in joined
        assert "SSH_AUTH_SOCK" not in joined
    finally:
        command.cleanup()


def test_acp_session_forwards_remote_write_isolation_to_backend(tmp_path):
    captured = {}

    class FakeBackendSession:
        status = "succeeded"
        last_error = None
        permission_denials = []

        async def run_turn(self):
            if False:
                yield None

        async def terminate(self):
            return None

    class FakeBackend:
        name = "fake"

        def start_session(self, options):
            captured["isolate_remote_write"] = options.isolate_remote_write
            return FakeBackendSession()

    session = AcpAgentSession(
        workspace_path=str(tmp_path),
        prompt="work",
        isolate_remote_write=True,
    )
    session._backend = FakeBackend()

    assert asyncio.run(session.run_task()) == "succeeded"
    assert captured["isolate_remote_write"] is True


@pytest.mark.parametrize("authorized", [False, True])
def test_acp_session_threads_exact_publish_authority_to_backend(tmp_path, authorized):
    """The SDK-native backend rebuild receives the server admission bit."""

    captured = {}

    class FakeBackendSession:
        status = "succeeded"
        last_error = None
        permission_denials = []

        async def run_turn(self):
            if False:
                yield None

        async def terminate(self):
            return None

    class FakeBackend:
        name = "fake"

        def start_session(self, options):
            captured["publish_enabled"] = options.epic_rebase_publish_enabled
            return FakeBackendSession()

    session = AcpAgentSession(
        workspace_path=str(tmp_path),
        prompt="work",
        isolate_remote_write=True,
        epic_rebase_publish_enabled=authorized,
    )
    session._backend = FakeBackend()

    assert asyncio.run(session.run_task()) == "succeeded"
    assert captured["publish_enabled"] is authorized


@pytest.mark.parametrize("backend_name", ["codex", "opencode"])
@pytest.mark.parametrize("authorized", [False, True])
def test_rebuilding_backends_forward_exact_publish_authority(
    tmp_path, monkeypatch, backend_name, authorized
):
    """Catalog-rebuilding backends cannot silently drop the publish gate."""

    from oompah import acp_tools
    from oompah.acp_backends.base import AcpBackendOptions

    captured = {}

    def fake_builder(_workspace_path, **kwargs):
        captured.update(kwargs)
        return []

    if backend_name == "codex":
        from oompah.acp_backends.codex import CodexAcpBackendSession

        session_type = CodexAcpBackendSession
        monkeypatch.setattr(acp_tools, "build_codex_tool_catalog", fake_builder)
    else:
        from oompah.acp_backends.opencode import OpencodeAcpBackendSession

        session_type = OpencodeAcpBackendSession
        monkeypatch.setattr(acp_tools, "build_tool_catalog", fake_builder)

    session = session_type(
        AcpBackendOptions(
            workspace_path=str(tmp_path),
            prompt="work",
            isolate_remote_write=True,
            epic_rebase_publish_enabled=authorized,
        )
    )

    assert session._build_tool_catalog() == []
    assert captured["isolate_remote_write"] is True
    assert captured["epic_rebase_publish_enabled"] is authorized


def test_codex_subscription_cli_is_rejected_for_isolated_rebase_work(tmp_path):
    """Only the API/bridged path may combine provider access and tools."""
    from oompah.acp_backends.base import AcpBackendOptions
    from oompah.acp_backends.codex import CodexAcpBackendSession

    async def run() -> list[object]:
        session = CodexAcpBackendSession(
            AcpBackendOptions(
                workspace_path=str(tmp_path),
                prompt="work",
                billing_model="subscription",
                isolate_remote_write=True,
            )
        )
        events = [event async for event in session.run_turn()]
        assert session.status == "errored"
        assert "unavailable for shared-epic rebase" in (session.last_error or "")
        return events

    events = asyncio.run(run())
    assert events and events[0].kind == "session_error"


def test_opencode_is_rejected_for_isolated_rebase_work(tmp_path, monkeypatch):
    from oompah.acp_backends.base import AcpBackendOptions
    from oompah.acp_backends import opencode as opencode_module

    spawn = AsyncMock()
    monkeypatch.setattr(opencode_module.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(
        opencode_module,
        "agent_environment",
        lambda *_args, **_kwargs: pytest.fail("isolated OpenCode must not bootstrap auth"),
    )

    async def run() -> list[object]:
        session = opencode_module.OpencodeAcpBackendSession(
            AcpBackendOptions(
                workspace_path=str(tmp_path),
                prompt="work",
                isolate_remote_write=True,
            )
        )
        events = [event async for event in session.run_turn()]
        assert session.status == "errored"
        assert "unavailable for shared-epic rebase" in (session.last_error or "")
        return events

    events = asyncio.run(run())
    assert events and events[0].kind == "session_error"
    spawn.assert_not_awaited()


def test_rebase_routing_skips_cli_and_codex_subscription_profiles():
    from oompah.models import AgentProfile
    from oompah.orchestrator import Orchestrator

    cli = AgentProfile(name="cli", command="codex", mode="cli")
    subscription = AgentProfile(
        name="subscription", command="codex", mode="acp", provider_id="sub"
    )
    opencode = AgentProfile(
        name="opencode", command="opencode", mode="acp", provider_id="open"
    )
    unknown = AgentProfile(
        name="unknown", command="future-agent", mode="acp", provider_id="future"
    )
    missing_backend = AgentProfile(
        name="missing-backend", command="agent", mode="acp", provider_id="missing"
    )
    empty_backend = AgentProfile(
        name="empty-backend", command="agent", mode="acp", provider_id="empty"
    )
    codex_api = AgentProfile(
        name="codex-api", command="codex", mode="acp", provider_id="codex-api"
    )
    bridged = AgentProfile(
        name="bridged", command="claude", mode="acp", provider_id="bridge"
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.config = SimpleNamespace(
        agent_profiles=[
            cli,
            subscription,
            opencode,
            unknown,
            missing_backend,
            empty_backend,
            bridged,
            codex_api,
        ]
    )
    providers = {
        "sub": SimpleNamespace(backend="codex", billing_model="subscription"),
        "open": SimpleNamespace(backend="opencode", billing_model="per_token"),
        "future": SimpleNamespace(backend="future-acp", billing_model="per_token"),
        "missing": SimpleNamespace(billing_model="per_token"),
        "empty": SimpleNamespace(backend="", billing_model="per_token"),
        "codex-api": SimpleNamespace(backend="codex", billing_model="per_token"),
        "bridge": SimpleNamespace(backend="claude", billing_model="subscription"),
    }
    orchestrator._resolve_provider = lambda profile: providers[profile.provider_id]

    assert not orchestrator._profile_supports_isolated_rebase(opencode)
    assert not orchestrator._profile_supports_isolated_rebase(unknown)
    assert not orchestrator._profile_supports_isolated_rebase(missing_backend)
    assert not orchestrator._profile_supports_isolated_rebase(empty_backend)
    assert orchestrator._profile_supports_isolated_rebase(codex_api)
    assert orchestrator._profile_supports_isolated_rebase(bridged)
    assert orchestrator._find_rebase_acp_profile() is bridged


def test_embedded_http_remote_credentials_are_detected(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://token:secret@example.test/repo"],
        cwd=tmp_path,
        check=True,
    )

    from oompah.orchestrator import Orchestrator

    assert Orchestrator._epic_rebase_workspace_has_embedded_remote_credentials(
        str(tmp_path)
    )


def test_ssh_remote_identity_is_not_treated_as_embedded_secret(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@example.test:group/repo.git"],
        cwd=tmp_path,
        check=True,
    )

    from oompah.orchestrator import Orchestrator

    assert not Orchestrator._epic_rebase_workspace_has_embedded_remote_credentials(
        str(tmp_path)
    )


def test_credential_bearing_pushurl_is_detected_while_fetch_url_is_clean(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.test/repo"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "remote", "set-url", "--push", "origin", "https://token:secret@example.test/repo"],
        cwd=tmp_path,
        check=True,
    )

    from oompah.orchestrator import Orchestrator

    assert Orchestrator._epic_rebase_workspace_has_remote_write_route(str(tmp_path))


@pytest.mark.parametrize(
    "key,value",
    [
        ("credential.helper", "!/operator/credential-helper"),
        ("http.https://example.test/.extraheader", "Authorization: Bearer secret"),
    ],
)
def test_local_git_credential_routes_are_detected(tmp_path, key, value):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "--local", key, value], cwd=tmp_path, check=True)

    from oompah.orchestrator import Orchestrator

    assert Orchestrator._epic_rebase_workspace_has_remote_write_route(str(tmp_path))


def _assert_mcp_shell_is_isolated(text: str) -> None:
    _skip_when_nested_bubblewrap_is_denied(text)
    assert "GITHUB_TOKEN=" not in text
    assert "SSH_AUTH_SOCK=" not in text
    assert "ARBITRARY_FORGE_ROUTE=" not in text
    assert "GIT_CONFIG_GLOBAL=/dev/null" in text
    assert "GIT_SSH_COMMAND=/bin/false" in text


def test_claude_mcp_run_command_uses_rebase_credential_boundary(tmp_path, monkeypatch):
    pytest.importorskip("claude_agent_sdk")
    monkeypatch.setenv("GITHUB_TOKEN", "forge-secret")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/run/ssh-agent.sock")
    monkeypatch.setenv("ARBITRARY_FORGE_ROUTE", "forge-secret")
    workspace = _init_rebase_workspace(tmp_path)

    from oompah.acp_tools import build_tool_catalog

    catalog = build_tool_catalog(str(workspace), isolate_remote_write=True)
    tool = next(item for item in catalog if item.name == "run_command")
    result = asyncio.run(tool.handler({"command": "env"}))

    _assert_mcp_shell_is_isolated(result["content"][0]["text"])


def test_codex_mcp_run_command_uses_rebase_credential_boundary(tmp_path, monkeypatch):
    pytest.importorskip("agents")
    monkeypatch.setenv("GITHUB_TOKEN", "forge-secret")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/run/ssh-agent.sock")
    monkeypatch.setenv("ARBITRARY_FORGE_ROUTE", "forge-secret")
    workspace = _init_rebase_workspace(tmp_path)

    from oompah.acp_tools import build_codex_tool_catalog

    catalog = build_codex_tool_catalog(str(workspace), isolate_remote_write=True)
    tool = next(item for item in catalog if item.name == "run_command")
    result = asyncio.run(tool.on_invoke_tool(MagicMock(), '{"command":"env"}'))

    _assert_mcp_shell_is_isolated(result)


def test_opencode_mcp_run_command_uses_rebase_credential_boundary(
    tmp_path, monkeypatch
):
    def fake_tool(name, description, schema):
        del description, schema

        def decorate(handler):
            handler.name = name
            handler.handler = handler
            return handler

        return decorate

    monkeypatch.setitem(sys.modules, "opencode", types.SimpleNamespace(tool=fake_tool))
    monkeypatch.setenv("GITHUB_TOKEN", "forge-secret")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/run/ssh-agent.sock")
    monkeypatch.setenv("ARBITRARY_FORGE_ROUTE", "forge-secret")
    workspace = _init_rebase_workspace(tmp_path)

    from oompah.acp_tools import build_opencode_tool_catalog

    catalog = build_opencode_tool_catalog(str(workspace), isolate_remote_write=True)
    tool = next(item for item in catalog if item.name == "run_command")
    result = asyncio.run(tool.handler({"command": "env"}))

    _assert_mcp_shell_is_isolated(result["content"][0]["text"])


def test_publish_tool_binds_current_project_and_task_without_shell_token(
    tmp_path, monkeypatch
):
    def fake_tool(name, description, schema):
        del description, schema

        def decorate(handler):
            handler.name = name
            handler.handler = handler
            return handler

        return decorate

    calls = []

    class Coordinator:
        def publish_worker_epic_rebase_candidate(
            self, project_id, task_identifier, candidate
        ):
            calls.append((project_id, task_identifier, candidate))
            return {"published": True, "candidate": candidate}

    monkeypatch.setitem(sys.modules, "opencode", types.SimpleNamespace(tool=fake_tool))
    monkeypatch.delenv("OOMPAH_TASK_HANDOFF_TOKEN", raising=False)
    candidate = "a" * 40

    from oompah.acp_tools import build_opencode_tool_catalog

    catalog = build_opencode_tool_catalog(
        str(tmp_path),
        project_id="project-bound",
        task_identifier="REBASE-BOUND",
        coordination_service=Coordinator(),
        isolate_remote_write=True,
        epic_rebase_publish_enabled=True,
    )
    publish = next(item for item in catalog if item.name == "publish_epic_rebase")
    rejected = asyncio.run(
        publish.handler({"candidate": candidate, "remote": "attacker"})
    )
    result = asyncio.run(publish.handler({"candidate": candidate}))

    assert rejected["content"][0]["text"] == (
        "Error: publish_epic_rebase accepts only candidate"
    )
    assert calls == [("project-bound", "REBASE-BOUND", candidate)]
    assert result["content"][0]["text"] == (
        '{"candidate": "' + candidate + '", "published": true}'
    )
    assert "OOMPAH_TASK_HANDOFF_TOKEN" not in os.environ


def test_publish_tool_is_not_advertised_without_exact_session_authority(
    tmp_path, monkeypatch
):
    def fake_tool(name, description, schema):
        del description, schema

        def decorate(handler):
            handler.name = name
            return handler

        return decorate

    monkeypatch.setitem(sys.modules, "opencode", types.SimpleNamespace(tool=fake_tool))
    from oompah.acp_tools import build_opencode_tool_catalog

    ordinary = build_opencode_tool_catalog(str(tmp_path))
    disabled = build_opencode_tool_catalog(
        str(tmp_path),
        project_id="project-bound",
        task_identifier="REBASE-BOUND",
        coordination_service=MagicMock(
            publish_worker_epic_rebase_candidate=lambda *_args: None
        ),
        isolate_remote_write=True,
        epic_rebase_publish_enabled=False,
    )
    non_rebase = build_opencode_tool_catalog(
        str(tmp_path),
        project_id="project-bound",
        task_identifier="ORDINARY-1",
        coordination_service=MagicMock(
            publish_worker_epic_rebase_candidate=lambda *_args: None
        ),
        isolate_remote_write=False,
        epic_rebase_publish_enabled=True,
    )
    missing_task = build_opencode_tool_catalog(
        str(tmp_path),
        project_id="project-bound",
        coordination_service=MagicMock(
            publish_worker_epic_rebase_candidate=lambda *_args: None
        ),
        isolate_remote_write=True,
        epic_rebase_publish_enabled=True,
    )

    assert "publish_epic_rebase" not in {item.name for item in ordinary}
    assert "publish_epic_rebase" not in {item.name for item in disabled}
    assert "publish_epic_rebase" not in {item.name for item in non_rebase}
    assert "publish_epic_rebase" not in {item.name for item in missing_task}


def test_claude_publish_catalog_requires_all_authority_gates(tmp_path):
    pytest.importorskip("claude_agent_sdk")
    from oompah.acp_tools import build_tool_catalog

    coordinator = MagicMock()
    coordinator.publish_worker_epic_rebase_candidate = MagicMock()
    enabled = build_tool_catalog(
        str(tmp_path),
        project_id="project-bound",
        task_identifier="REBASE-BOUND",
        coordination_service=coordinator,
        isolate_remote_write=True,
        epic_rebase_publish_enabled=True,
    )
    disabled = build_tool_catalog(
        str(tmp_path),
        project_id="project-bound",
        task_identifier="REBASE-BOUND",
        coordination_service=coordinator,
        isolate_remote_write=True,
        epic_rebase_publish_enabled=False,
    )

    assert "publish_epic_rebase" in {item.name for item in enabled}
    assert "publish_epic_rebase" not in {item.name for item in disabled}


def test_codex_publish_catalog_requires_all_authority_gates(tmp_path):
    pytest.importorskip("agents")
    from oompah.acp_tools import build_codex_tool_catalog

    coordinator = MagicMock()
    coordinator.publish_worker_epic_rebase_candidate = MagicMock()
    enabled = build_codex_tool_catalog(
        str(tmp_path),
        project_id="project-bound",
        task_identifier="REBASE-BOUND",
        coordination_service=coordinator,
        isolate_remote_write=True,
        epic_rebase_publish_enabled=True,
    )
    missing_callback = build_codex_tool_catalog(
        str(tmp_path),
        project_id="project-bound",
        task_identifier="REBASE-BOUND",
        coordination_service=None,
        isolate_remote_write=True,
        epic_rebase_publish_enabled=True,
    )
    disabled = build_codex_tool_catalog(
        str(tmp_path),
        project_id="project-bound",
        task_identifier="REBASE-BOUND",
        coordination_service=coordinator,
        isolate_remote_write=True,
        epic_rebase_publish_enabled=False,
    )
    non_rebase = build_codex_tool_catalog(
        str(tmp_path),
        project_id="project-bound",
        task_identifier="ORDINARY-1",
        coordination_service=coordinator,
        isolate_remote_write=False,
        epic_rebase_publish_enabled=True,
    )

    assert "publish_epic_rebase" in {item.name for item in enabled}
    assert "publish_epic_rebase" not in {item.name for item in missing_callback}
    assert "publish_epic_rebase" not in {item.name for item in disabled}
    assert "publish_epic_rebase" not in {item.name for item in non_rebase}


def test_publish_tool_validates_full_candidate_before_callback():
    from oompah.acp_tools import _exec_publish_epic_rebase_candidate

    handler = MagicMock()
    result = _exec_publish_epic_rebase_candidate(
        "refs/heads/main",
        "project-bound",
        "REBASE-BOUND",
        publish_handler=handler,
    )

    assert result == "Error: candidate must be a full lowercase commit SHA"
    handler.assert_not_called()


def test_publish_tool_fails_closed_without_callback_or_bound_authority():
    from oompah.acp_tools import _exec_publish_epic_rebase_candidate

    candidate = "b" * 40
    assert "assigned managed task" in _exec_publish_epic_rebase_candidate(
        candidate,
        None,
        "REBASE-BOUND",
    )
    assert "service is unavailable" in _exec_publish_epic_rebase_candidate(
        candidate,
        "project-bound",
        "REBASE-BOUND",
    )


def test_publish_tool_redacts_callback_failure():
    from oompah.acp_tools import _exec_publish_epic_rebase_candidate
    from oompah.secrets import register_secret, retire_secret

    secret = "publish-capability-secret-value"
    register_secret(secret)

    def fail(*_args):
        raise RuntimeError(f"authority failed with bearer {secret}")

    try:
        result = _exec_publish_epic_rebase_candidate(
            "c" * 40,
            "project-bound",
            "REBASE-BOUND",
            publish_handler=fail,
        )
    finally:
        retire_secret(secret)

    assert result.startswith("Error:")
    assert secret not in result
    assert "[REDACTED]" in result


def test_isolated_api_publish_tool_reaches_server_capability_without_token(
    tmp_path, monkeypatch
):
    from oompah.api_agent import ApiAgentSession

    candidate = "d" * 40
    calls = []
    responses = iter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "publish-call",
                                    "type": "function",
                                    "function": {
                                        "name": "publish_epic_rebase",
                                        "arguments": '{"candidate":"' + candidate + '"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            {"choices": [{"message": {"content": "done"}}]},
        ]
    )

    async def fake_call_api(_self, _messages):
        return next(responses)

    def publish(project_id, task_identifier, received_candidate):
        assert "OOMPAH_TASK_HANDOFF_TOKEN" not in os.environ
        calls.append((project_id, task_identifier, received_candidate))
        return {"published": True, "candidate": received_candidate}

    monkeypatch.delenv("OOMPAH_TASK_HANDOFF_TOKEN", raising=False)
    monkeypatch.setattr(ApiAgentSession, "_call_api", fake_call_api)
    session = ApiAgentSession(
        base_url="http://example.invalid",
        api_key="test",
        model="test-model",
        workspace_path=str(tmp_path),
        project_id="project-api",
        task_identifier="REBASE-API",
        publish_rebase_handler=publish,
        isolate_remote_write=True,
    )

    definitions = session._tool_definitions
    tool_names = {tool["function"]["name"] for tool in definitions}
    publish_schema = next(
        tool["function"]["parameters"]
        for tool in definitions
        if tool["function"]["name"] == "publish_epic_rebase"
    )
    result = asyncio.run(session.run_task("publish the finished rebase"))

    assert "publish_epic_rebase" in tool_names
    assert publish_schema["required"] == ["candidate"]
    assert publish_schema["additionalProperties"] is False
    assert set(publish_schema["properties"]) == {"candidate"}
    assert result.status == "succeeded"
    assert calls == [("project-api", "REBASE-API", candidate)]
    assert "OOMPAH_TASK_HANDOFF_TOKEN" not in os.environ


def test_api_publish_tool_is_hidden_outside_isolated_rebase_session(tmp_path):
    from oompah.api_agent import ApiAgentSession

    session = ApiAgentSession(
        base_url="http://example.invalid",
        api_key="test",
        model="test-model",
        workspace_path=str(tmp_path),
        project_id="project-api",
        task_identifier="ORDINARY-1",
        publish_rebase_handler=MagicMock(),
        isolate_remote_write=False,
    )

    assert "publish_epic_rebase" not in {
        tool["function"]["name"] for tool in session._tool_definitions
    }


def test_codex_api_keys_are_scoped_per_session_not_process_global(monkeypatch, tmp_path):
    """Concurrent/rotated provider keys must not cross through os.environ."""
    from oompah.acp_backends import codex as codex_module
    from oompah.acp_backends.base import AcpBackendOptions
    from oompah.acp_backends.codex import CodexAcpBackendSession

    captured_keys = []

    class FakeAgent:
        def __init__(self, **_kwargs):
            pass

    class FakeProvider:
        def __init__(self, *, api_key):
            self.api_key = api_key

    class FakeRunConfig:
        def __init__(self, *, model_provider):
            self.model_provider = model_provider

    class FakeResult:
        usage = None

        async def _events(self):
            if False:
                yield None

        def stream_events(self):
            return self._events()

    class FakeRunner:
        @staticmethod
        def run_streamed(_agent, *, input, run_config=None):
            del input
            captured_keys.append(run_config.model_provider.api_key)
            return FakeResult()

    fake_sdk = types.SimpleNamespace(
        Agent=FakeAgent,
        Runner=FakeRunner,
        OpenAIProvider=FakeProvider,
        RunConfig=FakeRunConfig,
    )
    monkeypatch.setattr(codex_module, "_import_sdk", lambda: fake_sdk)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    async def run_one(key):
        session = CodexAcpBackendSession(
            AcpBackendOptions(
                workspace_path=str(tmp_path),
                prompt="work",
                env={"OPENAI_API_KEY": key},
            )
        )
        session._build_tool_catalog = lambda: []
        async for _event in session.run_turn():
            pass

    asyncio.run(run_one("key-one"))
    asyncio.run(run_one("key-two"))

    assert captured_keys == ["key-one", "key-two"]
    assert "OPENAI_API_KEY" not in os.environ
