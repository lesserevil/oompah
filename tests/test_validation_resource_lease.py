"""Focused coverage for the shared heavyweight-validation lane."""

from __future__ import annotations

import os
import shlex
import sqlite3
import subprocess
import sys
import threading
import time
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from oompah import validation_resource_lease as validation_lease_module
from oompah.acp_tools import _auditor_validation_success_handler
from oompah.api_agent import (
    _exec_run_command,
    _execute_tool,
    _validation_reuse_policy_decision,
)
from oompah.auditor import check_auditor_command
from oompah.terminal_audit_observability import TerminalAuditMetrics
from oompah.tool_liveness import ToolLivenessMonitor
from oompah.validation_resource_lease import (
    AUDITOR_PRIORITY,
    EXACT_GATE_PRIORITY,
    VALIDATION_KIND_AUDITOR,
    VALIDATION_KIND_WORKER,
    WORKER_PRIORITY,
    ValidationLeaseCancelled,
    ValidationLeaseOwner,
    ValidationResourceLease,
    classify_validation_command,
    contains_configured_validation_command,
    is_focused_validation_command,
    is_full_suite_validation_command,
    is_heavyweight_validation_command,
    managed_agent_validation_owner,
)


def _wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition did not become true")


def _gate_owner(project: str, task: str) -> ValidationLeaseOwner:
    return ValidationLeaseOwner.exact_gate(
        project_id=project,
        task_id=task,
        authority_generation=f"generation-{task}",
    )


def _audit_owner(project: str, task: str) -> ValidationLeaseOwner:
    return ValidationLeaseOwner.auditor(
        project_id=project,
        task_id=task,
        authority_generation=f"attempt-{task}",
    )


def _worker_owner(project: str, task: str) -> ValidationLeaseOwner:
    return ValidationLeaseOwner.worker(
        project_id=project,
        task_id=task,
        authority_generation=f"worker-{task}",
    )


def _reusable_gate_policy() -> dict[str, str]:
    return {
        "decision": "reuse_authoritative_gate",
        "command": "make test",
        "attempt_id": "attempt-1",
    }


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("make test", True),
        ("make", True),
        ("make -C . test-serial", True),
        ("make test-unit", True),
        ("make check-secrets", True),
        ("make help", True),
        ("make --help", False),
        ("pytest --help", False),
        ("pytest --version", False),
        ("python -m pytest --help", False),
        ("python -m unittest --help", False),
        ("make --eval='$(shell make test)' help", True),
        ("make --ev='$(shell make test)' help", True),
        ("make -E'$(shell make test)' help", True),
        ("make --eval=all: help", True),
        ("make -E all: help", True),
        ("make -f task.mk help", True),
        ("make --directory=/task help", True),
        ("make -j help", True),
        ("echo ready; make test", True),
        ("echo ready\nmake test", True),
        ("./ci/test.sh", True),
        (".venv/bin/python -m pytest tests/test_one.py", True),
        ("make test && git status --short", True),
        ("pytest", True),
        ("uv run pytest -q", True),
        ("uv run --python 3.12 pytest -q", True),
        ("PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q", True),
        ("timeout 10s python -m pytest tests/", True),
        ("bash -lc 'python -m pytest tests/'", True),
        ("exec pytest", True),
        ("exec -a validation pytest", True),
        ("time -p pytest", True),
        ("/usr/bin/time -f %E pytest", True),
        ("bash -ce 'pytest'", True),
        ("sh -ec 'pytest tests/'", True),
        ("bash --noprofile -O extglob -c 'make test'", True),
        ("bash -O extglob -c 'npm @(test)'", True),
        ("bash -o errexit -ce 'cargo test'", True),
        ("uv --directory . run pytest -q", True),
        ("uv --allow-insecure-host example.com run --group test pytest", True),
        ("uv --project=. run python -m pytest tests/", True),
        ("python -m pytest tests/", True),
        ("python -I -m pytest tests/", True),
        ("python3.12 -X dev -W error -m pytest -q", True),
        (
            "python -m pytest -q tests/test_acp_backends.py tests/test_providers.py "
            "tests/test_providers_ui.py tests/test_acp_agent.py "
            "tests/test_orchestrator_handlers.py",
            True,
        ),
        ("tox -q", True),
        ("pytest tests/test_one.py", True),
        ("pytest tests/test_*.py", True),
        ("pytest 'tests/test_{one,two}.py'", True),
        ("pytest 'tests/test_[ab].py'", True),
        ("pytest tests/test_one.py tests/test_two.py", True),
        ("pytest tests/test_one.py::test_case", True),
        ("pytest -k exact_case", True),
        ("pytest tests/test_one.py -k exact_case", True),
        ("pytest tests/test_one.py -n auto", True),
        ("pytest tests/test_one.py --numprocesses=4", True),
        ("pytest -p=task_plugin tests/test_one.py", True),
        ("pytest -ptask_plugin tests/test_one.py", True),
        ("pytest --override-ini=addopts=-n4 tests/test_one.py", True),
        ("pytest -oaddopts=-n4 tests/test_one.py", True),
        ("pytest --config-file=task.ini tests/test_one.py", True),
        ("pytest -ctask.ini tests/test_one.py", True),
        ("pytest --rootdir=/task tests/test_one.py", True),
        ("pytest --pdbcls=task:Debugger tests/test_one.py", True),
        ("pytest --collect-only", True),
        ("pytest --collect-only tests/test_one.py", True),
        (
            "pytest --collect-only tests/test_one.py tests/test_two.py",
            True,
        ),
        ("npm test", True),
        ("npm te*", True),
        ("npm $CMD", True),
        ('npm "$CMD"', True),
        ("npm $'test'", True),
        ("printf %s $'a\\'b'; npm $'test'", True),
        ("echo $'a\\'b'; npm test; echo \\'", True),
        ("npm te{st,}", True),
        ("npm --prefix web test -- --runInBand", True),
        ("npm --workspace web t", True),
        ("npm run test:unit", True),
        ("npm run build", True),
        ("npm run --silent test", True),
        ("npm exec -- make test", True),
        ("pnpm test", True),
        ("pnpm --filter web test", True),
        ("pnpm run test:unit", True),
        ("pnpm exec make test", True),
        ("pnpm arbitrary-script", True),
        ("yarn test", True),
        ("yarn run test", True),
        ("yarn dlx tool", True),
        ("yarn arbitrary-script", True),
        ("npm --script-shell=/task/sh run build", True),
        ("python -m unittest discover", True),
        ("python -I -m unittest discover -s tests", True),
        ("python -m unittest tests.test_one.TestCase.test_case", True),
        ("cargo test", True),
        ("cargo te*", True),
        ('cargo $"test"', True),
        ("cargo +nightly --color always test --workspace", True),
        ("cargo --config net.retry=2 test", True),
        ("cargo --config build.rustc-wrapper=/task/wrapper build", True),
        ("cargo build --config build.rustc-wrapper=/task/wrapper", True),
        ("cargo -C /task/worktree build", True),
        ("cargo nextest run", True),
        ("cargo task-alias", True),
        ("cargo build", False),
        ("npm 'te*'", True),
        ("printf %s \"a'b\"; npm 'build'", True),
        ("echo \"$'literal'\"; npm 'build'", True),
        ("echo \\$'literal'; npm 'build'", True),
        ("npm '$CMD'", True),
        ("npm \\$'test'", True),
        ("npm 'te{st,}'", True),
        ("cargo 'te*'", True),
        ('cargo \\$"test"', True),
        ("rg pytest tests", False),
        ("rg --hostname-bin=/task/hostname pytest tests", True),
        ("rg --hostname-bin /task/hostname pytest tests", True),
        ("rg --search-zip pytest tests", True),
        ("rg -z pytest tests", True),
        ("rg -nUz pytest tests", True),
        ("/usr/bin/rg pytest tests", False),
        ("./rg pytest tests", True),
        ("/workspace/bin/rg pytest tests", True),
        ("python ci/test.py", True),
        ("python ci/test", True),
        ("bash ci/test.sh", True),
        ("printf 'make test\\n' | bash", True),
        ("bash -s", True),
        ("printf 'make test\\n' | bash -h", True),
        ("python", True),
        ("node --input-type=module -", True),
        ("perl -", True),
        ("ruby -", True),
        ("ruby -v", False),
        ("ruby -v -e 'system %q(make test)'", True),
        ("ruby -v script.rb", True),
        ("python --version", False),
        ("bash --version", False),
        ("node --version", False),
        ("env -S 'python -m pytest'", True),
        ("env -S 'bash -c \"make test\"'", True),
        ("env --split-string='python -m pytest'", True),
        ("python -c \"__import__('pytest').main([])\"", True),
        ("python -c \"__import__('subprocess').run(['make','test'])\"", True),
        ("node -e \"require('child_process').execSync('npm test')\"", True),
        ("perl -e 'system q(make test)'", True),
        ("ruby -e 'system %q(make test)'", True),
        ("exec rg pytest tests", False),
        ("time git status --short", False),
        ("bash -ce 'echo pytest'", False),
        ("bash -O extglob -c \"npm '@(test)'\"", False),
        ("npm '@(test)'", False),
        ("eval \"$VALIDATION_COMMAND\"", True),
        ("$VALIDATION_COMMAND", True),
        ("source ./validation-command.sh", True),
        ("if true; then rg pytest tests; fi", True),
        ("echo $(printf make); test", True),
        ("echo `make test`", True),
        ("echo '`make test`'", False),
        ("unset BASH_ENV; rg pytest tests", True),
        ("PATH+=:/workspace/bin; rg pytest tests", True),
        ("unset OOMPAH_NATIVE_VALIDATION_BOUNDARY_GROUP", True),
        ("env -uBASH_ENV rg pytest tests", True),
        ("env --unset=BASH_ENV rg pytest tests", True),
        ("env -i rg pytest tests", True),
        ("env -iS 'rg pytest tests'", True),
        ("env -a -bash bash -c 'printf trusted'", True),
        ("env --argv0=-bash bash -c 'printf trusted'", True),
        ("exec -a -bash bash -c 'printf trusted'", True),
        ("exec -c rg pytest tests", True),
        ("exec -cl rg pytest tests", True),
        ("command -p rg pytest tests", True),
        ("command -pv rg pytest tests", True),
        ("typeset +x BASH_ENV; rg pytest tests", True),
        ("HOME=/task/worktree bash -lc 'printf trusted'", True),
        ("ZDOTDIR=/task/worktree zsh -c 'printf trusted'", True),
        ("ENV=/task/worktree/profile sh -c 'printf trusted'", True),
        ("LD_PRELOAD=/task/hook.so /usr/bin/printf trusted", True),
        ("LD_AUDIT=/task/audit.so /usr/bin/printf trusted", True),
        ("LD_LIBRARY_PATH=/task/lib /usr/bin/printf trusted", True),
        ("DYLD_INSERT_LIBRARIES=/task/hook.dylib printf trusted", True),
        ("LIBPATH=/task/lib printf trusted", True),
        ("bash -lc 'printf trusted'", True),
        ("bash -ic 'printf trusted'", True),
        ("bash --noprofile -lc 'printf trusted'", False),
        ("bash --norc -ic 'printf trusted'", False),
        ("bash -lc 'printf trusted' --noprofile", True),
        ("bash -ic 'printf trusted' --norc", True),
        ("zsh -c 'printf trusted'", True),
        ("zsh -fc 'printf trusted'", False),
        ("zsh +fc 'printf trusted'", True),
        (
            "PYTEST_ADDOPTS='-n auto' "
            "pytest tests/test_one.py::test_case",
            True,
        ),
        ("GNUMAKEFLAGS='--eval=all:;make test' make help", True),
        ("RUSTC=/task/rustc cargo build", True),
        ("CARGO_BUILD_RUSTC=/task/rustc cargo build", True),
        ("CARGO_HOME=/task/cargo cargo build", True),
        ("CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER=/task/cc cargo build", True),
        (
            "env 'BASH_FUNC_printf%%=() { make test; }' "
            "bash -c 'printf trusted'",
            True,
        ),
        ("printf -v PATH /workspace/bin; rg pytest tests", True),
        ("printf -v HOME %s /malicious-home; git status --short", True),
        ("printf -v LOCAL_VALUE %s harmless; git status --short", True),
        ('printf -v "$GUARD_NAME" value; rg pytest tests', True),
        ("printf '%s' HOME; git status --short", False),
        ("printf -- '-v %s' HOME; git status --short", False),
        ('unset "$GUARD_NAME"; rg pytest tests', True),
        ("PATH=/workspace/bin rg pytest tests", True),
        ("env -u OOMPAH_NATIVE_VALIDATION_GUARD rg pytest tests", True),
        ("ci-check", True),
        ("find . -exec make test {} +", True),
        ("git -c alias.verify='!make test' verify", True),
        ("git -c credential.helper=/workspace/helper credential fill", True),
        ("git --config-env=credential.helper=HELPER credential fill", True),
        ("git credential fill", True),
        ("git custom-inspector", True),
        ("git diff --ext-diff", True),
        ("git cat-file --filters HEAD:file", True),
        ("git log --format=%G? -1", True),
        ("git remote show origin", True),
        ("git branch --edit-description", True),
        ("git tag --list -v", True),
        ("git -c core.askPass=/workspace/helper status", True),
        ("git -c log.showSignature=true log -1", True),
        ("git -c format.pretty=%G? log -1", True),
        ("GIT_EXTERNAL_DIFF=/workspace/helper git diff", True),
        ("GIT_CONFIG_PARAMETERS=opaque git status", True),
        (
            "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.fsmonitor "
            "GIT_CONFIG_VALUE_0=/workspace/helper git status",
            True,
        ),
        ("git branch --show-current", False),
        ("git tag --list 'v*'", False),
        ("git grep validation", False),
        ("git rev-list -1 HEAD", False),
        ("git remote -v", False),
        ("git remote get-url origin", False),
        ("git reflog show -1", False),
        ("git worktree list --porcelain", False),
        ("git diff $OPTION", True),
        ("git diff '$OPTION'", False),
        ("git -c core.alternateRefsCommand=/workspace/helper rev-list --alternate-refs", True),
        ("sed -e '1e make test' file", True),
        ("sed -ne'1e make test' file", True),
        ("sed 'e;' file", True),
        ("sed '\\%foo%e make test' file", True),
        ("sed '/foo/Ie touch marker' file", True),
        ("sed '/foo/I!e touch marker' file", True),
        ("sed '\\%foo%Me touch marker' file", True),
        ("sed '\\%foo%iM ! e touch marker' file", True),
        ("sed '\\|foo|e make test' file", True),
        ("sed '\\xfooxe make test' file", True),
        ("sed '1,\\#foo#!e make test' file", True),
        ("sed '\\%foo%p' file", False),
        ("sed '/foo/Ip' file", False),
        ("sed '/foo/I!p' file", False),
        ("sed '\\%foo%Mp' file", False),
        ("sed 's/x/y/e' file", True),
        ("sed -f script.sed file", True),
        ("sed <commands.txt e", True),
        ('sed "$SCRIPT" file', True),
        ('sed -e "$SCRIPT" file', True),
        ('sed --expression="$SCRIPT" file', True),
        ("sed 'e'* file", True),
        ("sed * file", True),
        ("sed p *", True),
        ("sed p -- *", False),
        ("sed {e,} file", True),
        ("sed 1{e,} file", True),
        ("sed --e={e,} file", True),
        ("sed --e='e make test' file", True),
        ("sed --expr='e make test' file", True),
        ("sed --fi=commands.sed file", True),
        ("sed --fil=commands.sed file", True),
        ('sed -ne"$SCRIPT" file', True),
        ("sed 's/before/after/' file", False),
        ("sed 's/>/after/' file", False),
        ("sed 's/$/after/' file", False),
        ("sed 's/.*/after/' *.txt", True),
        ("sed 's/.*/after/' -- *.txt", False),
        ("sed 's/{before,after}/value/' file{1,2}", True),
        ("sed 's/{before,after}/value/' -- file{1,2}", False),
        ("sed --e='s/before/after/' file", False),
        ("sed --expr='s/before/after/' file", False),
        ("sed -e 's/before/after/' file", False),
        ("sed -n 's/before/after/p' file", False),
        ("awk 'BEGIN { system(\"make test\") }'", True),
        ("rg --pre 'make test' pattern .", True),
        ("echo make test", False),
        ("git status --short", False),
        ("npm >out test", True),
        ("npm '>' test", False),
        ("cargo test>out", True),
        ("cargo 'test>out'", True),
        ("pytest tests/test_one.py -$OPT", True),
        ("pytest tests/test_one.py '-$OPT'", False),
        ("npm 'unterminated", True),
    ],
)
def test_classifier_is_heavy_first_and_inspection_only_checks_bypass(command, expected):
    assert is_heavyweight_validation_command(command) is expected


def test_shell_line_continuation_is_removed_before_classification():
    assert is_heavyweight_validation_command(
        "cargo te\\" + "\n" + "st"
    ) is True
    assert is_heavyweight_validation_command(
        'cargo "te\\' + "\n" + 'st"'
    ) is True
    assert is_heavyweight_validation_command(
        "cargo 'te\\" + "\n" + "st'"
    ) is True


def test_sed_input_glob_cannot_inject_permuted_program_file(tmp_path):
    (tmp_path / "-fcommands.sed").write_text(
        "e touch marker\n",
        encoding="utf-8",
    )

    assert is_heavyweight_validation_command(
        "sed p *",
        working_directory=tmp_path,
    ) is True
    assert is_heavyweight_validation_command(
        "sed p -- *",
        working_directory=tmp_path,
    ) is False


def test_persisted_git_config_environment_fails_closed():
    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment={
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.fsmonitor",
            "GIT_CONFIG_VALUE_0": "/workspace/helper",
        },
    ) is True


def test_safe_complete_git_config_environment_preserves_inspection():
    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment={
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "url.file:///blocked/.insteadOf",
            "GIT_CONFIG_VALUE_0": "https://",
        },
    ) is False


def test_inherited_bash_function_state_fails_closed_before_command_resolution():
    assert is_heavyweight_validation_command(
        "printf trusted",
        command_environment={
            "BASH_FUNC_printf%%": "() { make test; }",
        },
    ) is True


@pytest.mark.parametrize(
    "name",
    [
        "LD_PRELOAD",
        "LD_AUDIT",
        "LD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        "_RLD_LIST",
        "LDR_CNTRL",
        "LDR_PRELOAD",
        "LIBPATH",
        "SHLIB_PATH",
    ],
)
def test_inherited_dynamic_loader_environment_fails_closed(name):
    assert is_heavyweight_validation_command(
        "printf trusted",
        command_environment={name: "/task/loader-hook"},
    ) is True


@pytest.mark.parametrize(
    ("config_name", "config_contents"),
    [
        (
            "config.toml",
            '[build]\nrustc-wrapper = "/task/wrapper"\n',
        ),
        (
            "config",
            '[alias]\nproject-check = "run --bin task-helper"\n',
        ),
    ],
)
def test_effective_workspace_cargo_configuration_fails_closed(
    tmp_path,
    config_name,
    config_contents,
):
    workspace = tmp_path / "workspace"
    invocation_directory = workspace / "crate"
    cargo_config = workspace / ".cargo"
    invocation_directory.mkdir(parents=True)
    cargo_config.mkdir()
    (cargo_config / config_name).write_text(config_contents, encoding="utf-8")

    assert is_heavyweight_validation_command(
        "cargo build",
        command_environment={"HOME": str(tmp_path / "isolated-home")},
        working_directory=invocation_directory,
    ) is True


@pytest.mark.parametrize(
    ("config_name", "config_contents"),
    [
        ("pyproject.toml", "[tool.pytest.ini_options]\naddopts = '-p task_plugin'\n"),
        ("pytest.ini", "[pytest]\naddopts = -p task_plugin\n"),
        (".pytest.ini", "[pytest]\naddopts = -p task_plugin\n"),
        ("tox.ini", "[pytest]\naddopts = -p task_plugin\n"),
        ("setup.cfg", "[tool:pytest]\naddopts = -p task_plugin\n"),
        ("conftest.py", "pytest_plugins = ['task_plugin']\n"),
    ],
)
def test_effective_pytest_configuration_fails_closed(
    tmp_path,
    config_name,
    config_contents,
):
    workspace = tmp_path / "workspace"
    invocation_directory = workspace / "tests" / "unit"
    invocation_directory.mkdir(parents=True)
    (workspace / config_name).write_text(config_contents, encoding="utf-8")

    assert is_heavyweight_validation_command(
        "pytest test_one.py::test_case",
        command_environment={},
        working_directory=invocation_directory,
    ) is True


def test_focused_pytest_without_persisted_configuration_remains_light(tmp_path):
    invocation_directory = tmp_path / "isolated" / "tests"
    invocation_directory.mkdir(parents=True)

    assert is_heavyweight_validation_command(
        "pytest test_one.py::test_case",
        command_environment={},
        working_directory=invocation_directory,
    ) is False
    assert is_heavyweight_validation_command(
        "pytest @payload.py",
        command_environment={},
        working_directory=invocation_directory,
    ) is True
    assert is_heavyweight_validation_command(
        "python -m pytest @payload.py",
        command_environment={},
        working_directory=invocation_directory,
    ) is True


def test_explicit_pytest_selector_ancestor_configuration_fails_closed(tmp_path):
    invocation_directory = tmp_path / "invocation"
    selector_directory = tmp_path / "project" / "tests"
    invocation_directory.mkdir()
    selector_directory.mkdir(parents=True)
    (tmp_path / "project" / "conftest.py").write_text(
        "pytest_plugins = ['task_plugin']\n",
        encoding="utf-8",
    )
    selector = selector_directory / "test_one.py"

    assert is_heavyweight_validation_command(
        f"pytest {selector}::test_case",
        command_environment={},
        working_directory=invocation_directory,
    ) is True


@pytest.mark.parametrize(
    ("command", "environment"),
    [
        (
            "pytest tests/test_one.py::test_case",
            {"PYTEST_ADDOPTS": "-n auto"},
        ),
        (
            "python -m pytest tests/test_one.py::test_case",
            {"PYTEST_PLUGINS": "task_plugin"},
        ),
        (
            "pytest tests/test_one.py::test_case",
            {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        ),
        ("make help", {"MAKEFLAGS": "--eval=$(shell make test)"}),
        ("make help", {"GNUMAKEFLAGS": "--eval=$(shell make test)"}),
        ("npm run build", {"NODE_OPTIONS": "--require=/task/hook.js"}),
        ("npm run build", {"npm_config_script_shell": "/task/sh"}),
        ("npm run build", {"NPM_CONFIG_SCRIPT_SHELL": "/task/sh"}),
        ("pnpm run build", {"PNPM_SCRIPT_SHELL": "/task/sh"}),
        ("yarn run build", {"YARN_SCRIPT_SHELL": "/task/sh"}),
        ("rg pytest tests", {"RIPGREP_CONFIG_PATH": "/task/ripgreprc"}),
        ("ruby --version", {"RUBYOPT": "-r/task/hook.rb"}),
        ("ruby --version", {"RUBYLIB": "/task/lib"}),
        ("cargo build", {"RUSTC_WRAPPER": "/task/wrapper"}),
        ("cargo build", {"RUSTC": "/task/rustc"}),
        ("cargo build", {"CARGO_BUILD_RUSTC": "/task/rustc"}),
        ("cargo build", {"CARGO_HOME": "/task/cargo"}),
        (
            "cargo build",
            {"CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER": "/task/wrapper"},
        ),
        (
            "cargo build",
            {"CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER": "/task/cc"},
        ),
    ],
)
def test_inherited_runner_environment_fails_closed(command, environment):
    assert is_heavyweight_validation_command(
        command,
        command_environment=environment,
    ) is True


@pytest.mark.parametrize(
    ("command", "environment_update"),
    [
        ("git diff --stat", {"GIT_EXTERNAL_DIFF": "/workspace/diff-helper"}),
        ("git status --short", {"GIT_CONFIG_PARAMETERS": "'alias.x'='!true'"}),
        ("git log -1", {"GIT_PAGER": "/workspace/pager-helper"}),
        ("git log -1", {"PAGER": "/workspace/pager-helper"}),
        ("git status --short", {"GIT_TRACE2_EVENT": "|/workspace/helper"}),
    ],
)
def test_git_executable_environment_surfaces_fail_closed(
    tmp_path,
    command,
    environment_update,
):
    invocation_directory = tmp_path / "invocation"
    invocation_directory.mkdir()
    environment = {
        **_isolated_git_config_environment(tmp_path),
        **environment_update,
    }

    assert is_heavyweight_validation_command(
        command,
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_non_executable_git_trace_environment_preserves_safe_inspection(tmp_path):
    invocation_directory = tmp_path / "invocation"
    invocation_directory.mkdir()
    environment = {
        **_isolated_git_config_environment(tmp_path),
        "GIT_TRACE2_EVENT": str(tmp_path / "trace.json"),
    }

    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False


@pytest.mark.parametrize(
    "command_environment",
    [
        {"GIT_CONFIG_COUNT": "invalid"},
        {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.fsmonitor"},
        {
            "GIT_CONFIG_COUNT": "0",
            "GIT_CONFIG_KEY_0": "safe.key",
            "GIT_CONFIG_VALUE_0": "safe-value",
        },
        {"GIT_CONFIG_KEY_0": "safe.key", "GIT_CONFIG_VALUE_0": "safe-value"},
    ],
)
def test_malformed_git_config_environment_fails_closed(command_environment):
    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=command_environment,
    ) is True


def test_persisted_repo_helper_config_fails_closed_but_safe_config_does_not(
    tmp_path,
):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    config = git_dir / "config"
    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "git status --short",
        working_directory=tmp_path,
    ) is False

    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "git status --short",
        working_directory=tmp_path,
    ) is True


@pytest.mark.parametrize(
    "executable_config",
    [
        "[log]\n\tshowSignature = true\n",
        "[format]\n\tpretty = %G?\n",
        "[pretty \"verified\"]\n\tformat = %G?\n",
    ],
)
def test_git_signature_config_surfaces_fail_closed(tmp_path, executable_config):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text(executable_config, encoding="utf-8")

    assert is_heavyweight_validation_command(
        "git log -1",
        command_environment=_isolated_git_config_environment(tmp_path),
        working_directory=tmp_path,
    ) is True


def test_git_alternate_refs_command_config_fences_rev_list(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    config = git_dir / "config"
    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n",
        encoding="utf-8",
    )
    environment = _isolated_git_config_environment(tmp_path)

    assert is_heavyweight_validation_command(
        "git rev-list --alternate-refs",
        command_environment=environment,
        working_directory=tmp_path,
    ) is False

    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n"
        "\talternateRefsCommand = /workspace/helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "git rev-list --alternate-refs",
        command_environment=environment,
        working_directory=tmp_path,
    ) is True


def _isolated_git_config_environment(tmp_path):
    home = tmp_path / "home"
    xdg_config = tmp_path / "xdg-config"
    home.mkdir()
    xdg_config.mkdir()
    return {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg_config),
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def test_git_c_inspects_the_selected_repository_config(tmp_path):
    invocation_directory = tmp_path / "invocation"
    alternate_repository = tmp_path / "alternate"
    invocation_directory.mkdir()
    git_dir = alternate_repository / ".git"
    git_dir.mkdir(parents=True)
    config = git_dir / "config"
    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n",
        encoding="utf-8",
    )
    environment = _isolated_git_config_environment(tmp_path)

    assert is_heavyweight_validation_command(
        "git -C ../alternate status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False

    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n"
        "\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "git -C ../alternate status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_env_chdir_inspects_the_selected_repository_config(tmp_path):
    invocation_directory = tmp_path / "invocation"
    alternate_repository = tmp_path / "alternate"
    invocation_directory.mkdir()
    git_dir = alternate_repository / ".git"
    git_dir.mkdir(parents=True)
    config = git_dir / "config"
    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n",
        encoding="utf-8",
    )
    environment = _isolated_git_config_environment(tmp_path)

    assert is_heavyweight_validation_command(
        "env --chdir=../alternate git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False

    config.write_text(
        "[core]\n\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "env -C ../alternate git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_env_unset_removes_inherited_git_execution_and_config_scope(tmp_path):
    invocation_directory = tmp_path / "invocation"
    inherited_home = tmp_path / "inherited-home"
    invocation_directory.mkdir()
    inherited_home.mkdir()
    (inherited_home / ".gitconfig").write_text(
        "[core]\n\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )
    environment = {
        "HOME": str(inherited_home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_EXTERNAL_DIFF": "/workspace/diff-helper",
    }

    assert is_heavyweight_validation_command(
        "env -u HOME --unset=GIT_EXTERNAL_DIFF git diff --stat",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False


def test_prior_cd_segment_updates_git_repository_scope(tmp_path):
    invocation_directory = tmp_path / "invocation"
    alternate_repository = tmp_path / "alternate"
    invocation_directory.mkdir()
    git_dir = alternate_repository / ".git"
    git_dir.mkdir(parents=True)
    config = git_dir / "config"
    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n",
        encoding="utf-8",
    )
    environment = _isolated_git_config_environment(tmp_path)

    assert is_heavyweight_validation_command(
        "cd ../alternate; git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False

    config.write_text(
        "[core]\n\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "cd ../alternate && git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_skipped_conditional_cd_does_not_change_later_git_scope(tmp_path):
    invocation_directory = tmp_path / "invocation"
    alternate_repository = tmp_path / "alternate"
    invocation_directory.mkdir()
    git_dir = alternate_repository / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "config").write_text(
        "[core]\n\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )

    assert is_heavyweight_validation_command(
        "false && cd ../alternate; git status --short",
        command_environment=_isolated_git_config_environment(tmp_path),
        working_directory=invocation_directory,
    ) is False


def test_conditional_chain_preserves_unknown_status_before_scope_mutation(
    tmp_path,
):
    invocation_directory = tmp_path / "invocation"
    alternate_repository = tmp_path / "alternate"
    invocation_directory.mkdir()
    git_dir = alternate_repository / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "config").write_text(
        "[core]\n\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )
    environment = _isolated_git_config_environment(tmp_path)

    assert is_heavyweight_validation_command(
        "test -e missing && true && cd ../alternate; git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


@pytest.mark.parametrize(
    "command",
    [
        "test -e missing && false && cd ../alternate; git status --short",
        "test -e missing || true || cd ../alternate; git status --short",
    ],
)
def test_conditional_chain_truth_table_proves_scope_mutation_is_skipped(
    tmp_path,
    command,
):
    invocation_directory = tmp_path / "invocation"
    alternate_repository = tmp_path / "alternate"
    invocation_directory.mkdir()
    git_dir = alternate_repository / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "config").write_text(
        "[core]\n\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )

    assert is_heavyweight_validation_command(
        command,
        command_environment=_isolated_git_config_environment(tmp_path),
        working_directory=invocation_directory,
    ) is False


def test_assignment_only_segment_updates_exported_git_scope(tmp_path):
    invocation_directory = tmp_path / "invocation"
    safe_home = tmp_path / "safe-home"
    helper_home = tmp_path / "helper-home"
    invocation_directory.mkdir()
    safe_home.mkdir()
    helper_home.mkdir()
    (safe_home / ".gitconfig").write_text(
        "[user]\n\tname = Safe Reader\n",
        encoding="utf-8",
    )
    (helper_home / ".gitconfig").write_text(
        "[core]\n\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )
    environment = {
        "HOME": str(safe_home),
        "GIT_CONFIG_NOSYSTEM": "1",
    }

    assert is_heavyweight_validation_command(
        f"HOME={helper_home}; git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_prior_export_and_unset_segments_update_git_environment_scope(tmp_path):
    invocation_directory = tmp_path / "invocation"
    safe_home = tmp_path / "safe-home"
    helper_home = tmp_path / "helper-home"
    invocation_directory.mkdir()
    safe_home.mkdir()
    helper_home.mkdir()
    (safe_home / ".gitconfig").write_text(
        "[user]\n\tname = Safe Reader\n",
        encoding="utf-8",
    )
    (helper_home / ".gitconfig").write_text(
        "[core]\n\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )
    environment = {
        "HOME": str(safe_home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_DIR": str(tmp_path / "missing-inherited-git-dir"),
    }

    assert is_heavyweight_validation_command(
        "unset GIT_DIR; export HOME=" + str(safe_home) + "; git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False
    assert is_heavyweight_validation_command(
        "unset GIT_DIR; export HOME=" + str(helper_home) + "; git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True
    assert is_heavyweight_validation_command(
        "unset GIT_DIR; export GIT_EXTERNAL_DIFF=/workspace/helper; git diff",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_ambiguous_shell_scope_control_flow_fails_closed(tmp_path):
    invocation_directory = tmp_path / "invocation"
    alternate_repository = tmp_path / "alternate"
    invocation_directory.mkdir()
    alternate_repository.mkdir()

    assert is_heavyweight_validation_command(
        "cd ../alternate || git status --short",
        command_environment=_isolated_git_config_environment(tmp_path),
        working_directory=invocation_directory,
    ) is True


def test_explicit_git_dir_and_work_tree_inspect_diff_helper_config(tmp_path):
    invocation_directory = tmp_path / "invocation"
    work_tree = tmp_path / "work-tree"
    git_dir = tmp_path / "alternate.git"
    invocation_directory.mkdir()
    work_tree.mkdir()
    git_dir.mkdir()
    config = git_dir / "config"
    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n",
        encoding="utf-8",
    )
    environment = _isolated_git_config_environment(tmp_path)
    command = (
        "git --git-dir=../alternate.git --work-tree=../work-tree diff --stat"
    )

    assert is_heavyweight_validation_command(
        command,
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False

    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n"
        "[diff \"external\"]\n\tcommand = /workspace/diff-helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        command,
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_explicit_work_tree_inspects_its_repository_config(tmp_path):
    invocation_directory = tmp_path / "invocation"
    work_tree = tmp_path / "work-tree"
    invocation_directory.mkdir()
    git_dir = work_tree / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "config").write_text(
        "[filter \"generated\"]\n\tprocess = /workspace/filter-helper\n",
        encoding="utf-8",
    )

    assert is_heavyweight_validation_command(
        "git --work-tree=../work-tree status --short",
        command_environment=_isolated_git_config_environment(tmp_path),
        working_directory=invocation_directory,
    ) is True


def test_linked_worktree_common_and_worktree_configs_are_inspected(tmp_path):
    work_tree = tmp_path / "work-tree"
    common_git_dir = tmp_path / "common.git"
    worktree_git_dir = common_git_dir / "worktrees" / "feature"
    work_tree.mkdir()
    worktree_git_dir.mkdir(parents=True)
    (work_tree / ".git").write_text(
        f"gitdir: {worktree_git_dir}\n",
        encoding="utf-8",
    )
    (worktree_git_dir / "commondir").write_text("../..\n", encoding="utf-8")
    (common_git_dir / "config").write_text(
        "[core]\n\trepositoryFormatVersion = 0\n",
        encoding="utf-8",
    )
    worktree_config = worktree_git_dir / "config.worktree"
    worktree_config.write_text(
        "[core]\n\tquotePath = false\n",
        encoding="utf-8",
    )
    environment = _isolated_git_config_environment(tmp_path)

    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=work_tree,
    ) is False

    worktree_config.write_text(
        "[core]\n\tfsmonitor = /workspace/worktree-helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=work_tree,
    ) is True


def test_git_dir_environment_inspects_filter_helper_config(tmp_path):
    invocation_directory = tmp_path / "invocation"
    work_tree = tmp_path / "work-tree"
    git_dir = tmp_path / "alternate.git"
    invocation_directory.mkdir()
    work_tree.mkdir()
    git_dir.mkdir()
    config = git_dir / "config"
    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n",
        encoding="utf-8",
    )
    environment = {
        **_isolated_git_config_environment(tmp_path),
        "GIT_DIR": "../alternate.git",
        "GIT_WORK_TREE": "../work-tree",
    }

    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False

    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n"
        "[filter \"generated\"]\n\tprocess = /workspace/filter-helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_git_common_dir_environment_inspects_selected_common_config(tmp_path):
    invocation_directory = tmp_path / "invocation"
    work_tree = tmp_path / "work-tree"
    git_dir = tmp_path / "worktree.git"
    common_dir = tmp_path / "common.git"
    invocation_directory.mkdir()
    work_tree.mkdir()
    git_dir.mkdir()
    common_dir.mkdir()
    config = common_dir / "config"
    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n",
        encoding="utf-8",
    )
    environment = {
        **_isolated_git_config_environment(tmp_path),
        "GIT_DIR": "../worktree.git",
        "GIT_COMMON_DIR": "../common.git",
        "GIT_WORK_TREE": "../work-tree",
    }

    assert is_heavyweight_validation_command(
        "git rev-list --alternate-refs",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False

    config.write_text(
        "[core]\n\trepositoryFormatVersion = 0\n"
        "\talternateRefsCommand = /workspace/helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "git rev-list --alternate-refs",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_inline_git_scope_environment_selects_alternate_repository(tmp_path):
    invocation_directory = tmp_path / "invocation"
    work_tree = tmp_path / "work-tree"
    git_dir = tmp_path / "alternate.git"
    invocation_directory.mkdir()
    work_tree.mkdir()
    git_dir.mkdir()
    (git_dir / "config").write_text(
        "[core]\n\tfsmonitor = /workspace/helper\n",
        encoding="utf-8",
    )

    assert is_heavyweight_validation_command(
        "GIT_DIR=../alternate.git GIT_WORK_TREE=../work-tree git status",
        command_environment=_isolated_git_config_environment(tmp_path),
        working_directory=invocation_directory,
    ) is True


def test_normal_home_and_xdg_git_configs_are_inspected(tmp_path):
    invocation_directory = tmp_path / "invocation"
    invocation_directory.mkdir()
    environment = _isolated_git_config_environment(tmp_path)
    home_config = Path(environment["HOME"]) / ".gitconfig"
    xdg_config = Path(environment["XDG_CONFIG_HOME"]) / "git" / "config"
    xdg_config.parent.mkdir()
    home_config.write_text(
        "[user]\n\tname = Safe Reader\n",
        encoding="utf-8",
    )
    xdg_config.write_text(
        "[core]\n\tquotePath = false\n",
        encoding="utf-8",
    )

    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False

    xdg_config.write_text(
        "[core]\n\tfsmonitor = /workspace/global-helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_normal_system_git_config_is_inspected_without_invoking_git(
    tmp_path,
    monkeypatch,
):
    invocation_directory = tmp_path / "invocation"
    invocation_directory.mkdir()
    environment = _isolated_git_config_environment(tmp_path)
    environment.pop("GIT_CONFIG_NOSYSTEM")
    system_config = tmp_path / "system-gitconfig"
    monkeypatch.setattr(
        validation_lease_module,
        "_GIT_SYSTEM_CONFIG_PATHS",
        (system_config,),
    )
    system_config.write_text(
        "[core]\n\tquotePath = false\n",
        encoding="utf-8",
    )

    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False

    system_config.write_text(
        "[diff \"external\"]\n\tcommand = /workspace/system-helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_selected_global_and_system_git_config_paths_are_inspected(tmp_path):
    invocation_directory = tmp_path / "invocation"
    invocation_directory.mkdir()
    global_config = tmp_path / "selected-global-config"
    system_config = tmp_path / "selected-system-config"
    global_config.write_text(
        "[user]\n\tname = Safe Reader\n",
        encoding="utf-8",
    )
    system_config.write_text(
        "[core]\n\tquotePath = false\n",
        encoding="utf-8",
    )
    environment = {
        "GIT_CONFIG_GLOBAL": str(global_config),
        "GIT_CONFIG_SYSTEM": str(system_config),
    }

    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is False

    global_config.write_text(
        "[core]\n\tfsmonitor = /workspace/global-helper\n",
        encoding="utf-8",
    )
    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_non_regular_or_oversized_git_config_fails_closed_without_reading(
    tmp_path,
):
    repository = tmp_path / "repository"
    git_dir = repository / ".git"
    git_dir.mkdir(parents=True)
    config = git_dir / "config"
    os.mkfifo(config)
    environment = _isolated_git_config_environment(tmp_path)

    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=repository,
    ) is True

    config.unlink()
    config.write_bytes(
        b"[core]\n" + (b"x" * (validation_lease_module._GIT_CONFIG_MAX_BYTES + 1))
    )
    assert is_heavyweight_validation_command(
        "git status --short",
        command_environment=environment,
        working_directory=repository,
    ) is True


@pytest.mark.parametrize(
    ("command", "environment_update"),
    [
        ("git -C ../missing status", {}),
        ("git --git-dir=$UNKNOWN_REPOSITORY status", {}),
        ("git --work-tree=../missing status", {}),
        ("git status", {"GIT_DIR": "../missing"}),
        ("git status", {"HOME": "relative-home"}),
    ],
)
def test_unresolvable_git_configuration_scope_fails_closed(
    tmp_path,
    command,
    environment_update,
):
    invocation_directory = tmp_path / "invocation"
    invocation_directory.mkdir()
    environment = {
        **_isolated_git_config_environment(tmp_path),
        **environment_update,
    }

    assert is_heavyweight_validation_command(
        command,
        command_environment=environment,
        working_directory=invocation_directory,
    ) is True


def test_task_controlled_path_lookalike_is_heavy(tmp_path):
    task_bin = tmp_path / "bin"
    task_bin.mkdir()
    fake_git = task_bin / "git"
    fake_git.write_text("#!/bin/sh\nexec make test\n", encoding="utf-8")
    fake_git.chmod(0o700)

    assert is_heavyweight_validation_command(
        "git status --short",
        executable_search_path=str(task_bin),
        untrusted_executable_roots=(tmp_path,),
    ) is True


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("pytest", True),
        ("pytest -q", True),
        ("pytest -p no:foo", True),
        ("python -m pytest -n auto", True),
        ("bash -lc 'python -m pytest -q -W error'", True),
        ("pytest tests/", True),
        ("python -m unittest", True),
        ("python -m unittest discover", True),
        ("python -m unittest discover -s tests -p 'test_*.py'", True),
        ("env -S 'make test'", True),
        ("echo ready && pytest", True),
        ("pytest $OOMPAH_TEST_SCOPE", True),
        ("npm test", True),
        ("cargo nextest run", True),
        ("npm run build", False),
        ("cargo build", False),
        ("pytest tests/test_one.py", False),
        ("pytest tests/test_one.py::test_case", False),
        ("python -m pytest -q tests/test_one.py", False),
        ("python -m unittest tests.test_one", False),
    ],
)
def test_full_suite_classifier_distinguishes_pytest_scope(command, expected):
    assert (
        is_full_suite_validation_command(
            command,
            configured_command="make test",
        )
        is expected
    )


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("pytest tests/test_one.py -q", True),
        ("bash -lc 'pytest tests/test_one.py -q'", True),
        ("echo ready && pytest tests/test_one.py -q", True),
        ("env -S 'pytest tests/test_one.py -q'", True),
        ("pytest $OOMPAH_TEST_SCOPE", False),
        ("pytest tests/test_one.py; npm test", False),
    ],
)
def test_focused_classifier_preserves_wrappers_and_syntax_provenance(
    command,
    expected,
):
    assert is_focused_validation_command(command) is expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("make test", True),
        ("timeout 30 bash -lc 'make test'", True),
        ("env -S 'make test'", True),
        ("echo ready && make test", True),
        ("$OOMPAH_RUNNER test", False),
        ("make $OOMPAH_TARGET", False),
    ],
)
def test_configured_command_match_preserves_wrappers_and_syntax_provenance(
    command,
    expected,
):
    assert (
        contains_configured_validation_command(
            command,
            configured_command="make test",
        )
        is expected
    )


@pytest.mark.parametrize(
    "command",
    [
        "make test",
        "make test-serial",
        "pytest",
        "pytest tests/test_one.py",
        "pytest tests/test_one.py::test_case",
        "py.test tests/test_*.py",
        "python -m pytest",
        "python -m pytest tests/test_one.py::test_case",
        "python -m unittest discover",
        "python -m unittest tests.test_one.TestCase.test_case",
        "npm test",
        "pnpm test",
        "yarn test",
    ],
)
def test_heavy_auditor_contract_commands_acquire_before_popen(
    tmp_path,
    monkeypatch,
    command,
):
    events: list[str] = []

    class FakeHandle:
        pass_fds: tuple[int, ...] = ()

        def attach_process(self, process, *, timeout_seconds):
            events.append("attach")

        def release(self):
            events.append("release")

    class FakeLease:
        def acquire(self, owner, *, is_cancelled=None):
            events.append("acquire")
            return FakeHandle()

    class FakeProcess:
        pid = os.getpid()
        returncode = 0

        def __init__(self, *_args, **_kwargs):
            events.append("popen")

        def communicate(self, timeout=None):
            return "", ""

    monkeypatch.setattr("oompah.api_agent.subprocess.Popen", FakeProcess)

    assert check_auditor_command(command) is None
    assert is_heavyweight_validation_command(command) is True
    result = _exec_run_command(
        tmp_path,
        {"command": command},
        timeout=2,
        validation_lease=FakeLease(),
        validation_owner=_audit_owner("project", "audit"),
        require_validation_lease=True,
    )

    assert result == "exit_code: 0"
    assert events == ["acquire", "popen", "attach", "release"]


def test_managed_owner_uses_audit_attempt_before_worker_scope():
    owner = managed_agent_validation_owner(
        types.SimpleNamespace(auditor_session=True),
        {
            "project_id": "audit-project",
            "task_id": "AUDIT-1",
            "attempt_id": "attempt-7",
        },
        project_id="worker-project",
        task_id="WORK-1",
        authority_generation="worker-generation",
    )

    assert owner is not None
    assert owner.kind == VALIDATION_KIND_AUDITOR
    assert owner.project_id == "audit-project"
    assert owner.task_id == "AUDIT-1"
    assert owner.authority_generation == "attempt-7"


def test_gate_and_auditor_never_overlap_and_wait_does_not_start_tool_timeout(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(_gate_owner("p1", "gate"))
    makefile = tmp_path / "Makefile"
    marker = tmp_path / "started"
    makefile.write_text(f"test:\n\t@touch {marker}\n", encoding="utf-8")
    monitor = ToolLivenessMonitor()
    result: list[str] = []
    worker = threading.Thread(
        target=lambda: result.append(
            _exec_run_command(
                tmp_path,
                {"command": "make test"},
                timeout=2,
                tool_liveness=monitor,
                validation_lease=lease,
                validation_owner=_audit_owner("p1", "audit"),
            )
        )
    )
    worker.start()
    _wait_for(lambda: lease.status().waiter_count == 1)

    assert not marker.exists()
    waiting = monitor.snapshot()
    assert waiting is not None
    assert waiting.phase == "waiting_for_capacity"
    assert waiting.protects_from_stall is True
    assert waiting.deadline_exceeded is False
    gate.release()
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert marker.exists()
    assert result and "exit_code: 0" in result[0]
    assert lease.status().owner_count == 0


def test_heavy_command_observes_cancellation_after_capacity_acquisition(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    makefile = tmp_path / "Makefile"
    started = tmp_path / "started"
    makefile.write_text(
        f"test:\n\t@touch {started}\n\t@sleep 30\n",
        encoding="utf-8",
    )
    cancelled = threading.Event()
    results: list[str] = []
    worker = threading.Thread(
        target=lambda: results.append(
            _exec_run_command(
                tmp_path,
                {"command": "make test"},
                timeout=60,
                validation_lease=lease,
                validation_owner=_audit_owner("p1", "audit"),
                lease_cancelled=cancelled.is_set,
            )
        )
    )
    worker.start()
    _wait_for(lambda: started.exists() and lease.status().owner_count == 1)

    cancelled.set()
    worker.join(timeout=3)

    assert worker.is_alive() is False
    assert results == [
        "Error: validation authority withdrawn while command was running"
    ]
    assert lease.status().owner_count == 0


def test_cancellation_between_acquire_and_popen_never_launches_command(
    tmp_path,
    monkeypatch,
):
    cancelled = threading.Event()
    released: list[bool] = []

    class FakeHandle:
        pass_fds: tuple[int, ...] = ()

        def release(self):
            released.append(True)

    class FakeLease:
        def acquire(self, _owner, *, is_cancelled=None):
            cancelled.set()
            return FakeHandle()

    def forbidden_popen(*_args, **_kwargs):
        raise AssertionError("cancelled command reached Popen")

    monkeypatch.setattr("oompah.api_agent.subprocess.Popen", forbidden_popen)

    result = _exec_run_command(
        tmp_path,
        {"command": "make test"},
        timeout=5,
        validation_lease=FakeLease(),
        validation_owner=_audit_owner("p1", "audit"),
        lease_cancelled=cancelled.is_set,
    )

    assert result == "Error: validation authority withdrawn before command launch"
    assert released == [True]


def test_release_metadata_failure_does_not_leak_flock_or_mask_result(
    tmp_path,
    monkeypatch,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    handle = lease.acquire(_gate_owner("p1", "first"))
    real_connect = lease._connect

    def fail_connect():
        raise sqlite3.OperationalError("transient release failure")

    monkeypatch.setattr(lease, "_connect", fail_connect)
    assert handle.release() is False
    monkeypatch.setattr(lease, "_connect", real_connect)

    with lease.acquire(
        _gate_owner("p2", "replacement"),
        wait_timeout_seconds=1,
    ):
        assert lease.status().owner_count == 1


def test_release_preserves_owner_while_background_descendant_holds_flock(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    handle = lease.acquire(_gate_owner("p1", "shell"))
    inherited_fd = handle.pass_fds[0]
    launcher = (
        "import os, subprocess, sys; "
        "fd=int(sys.argv[1]); "
        "subprocess.Popen(['sleep', '0.5'], pass_fds=(fd,)); "
        "os._exit(0)"
    )
    shell = subprocess.Popen(
        [sys.executable, "-c", launcher, str(inherited_fd)],
        pass_fds=handle.pass_fds,
        start_new_session=True,
    )
    handle.attach_process(shell, timeout_seconds=5)
    assert shell.wait(timeout=2) == 0

    assert handle.release() is False
    assert lease.status().owner_count == 1

    with lease.acquire(
        _gate_owner("p2", "after-descendant"),
        wait_timeout_seconds=2,
    ):
        assert lease.status().owner_count == 1


def test_expired_detached_descendant_is_not_killed_via_stale_group_id(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    handle = lease.acquire(_gate_owner("p1", "shell"))
    inherited_fd = handle.pass_fds[0]
    pid_path = tmp_path / "descendant.pid"
    launcher = (
        "import os, pathlib, subprocess, sys; "
        "fd=int(sys.argv[1]); "
        "child=subprocess.Popen(['sleep', '0.3'], pass_fds=(fd,), start_new_session=True); "
        "pathlib.Path(sys.argv[2]).write_text(str(child.pid)); "
        "os._exit(0)"
    )
    leader = subprocess.Popen(
        [sys.executable, "-c", launcher, str(inherited_fd), str(pid_path)],
        pass_fds=handle.pass_fds,
        start_new_session=True,
    )
    handle.attach_process(leader, timeout_seconds=0.05)
    assert leader.wait(timeout=2) == 0
    _wait_for(pid_path.exists)
    assert handle.release() is False
    time.sleep(0.06)

    descendant_pid = int(pid_path.read_text(encoding="utf-8"))
    # Once the recorded leader exits, neither its old PGID nor a locked slot
    # proves ownership of a detached descendant. Capacity remains fenced until
    # that descendant closes the inherited descriptor naturally.
    assert Path(f"/proc/{descendant_pid}").exists()

    with lease.acquire(
        _gate_owner("p2", "after-expiry"),
        wait_timeout_seconds=2,
    ):
        assert lease.status().owner_count == 1


def test_expired_stale_child_identity_never_signals_reused_pid(
    tmp_path,
    monkeypatch,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    handle = lease.acquire(_gate_owner("p1", "stale-child"))
    child = subprocess.Popen(["true"], start_new_session=True)
    handle.attach_process(child, timeout_seconds=0.05)
    assert child.wait(timeout=2) == 0
    time.sleep(0.06)

    monkeypatch.setattr(
        validation_lease_module,
        "_pidfd_send_signal",
        lambda *_args: pytest.fail("stale process identity was signaled"),
    )
    assert lease.status().owner_count == 1
    handle.release()


def test_group_empty_proof_rejects_member_forked_after_proc_snapshot(
    monkeypatch,
):
    observations: list[str] = []

    def empty_proc_snapshot(_pid):
        observations.append("proc-scan-complete")
        return ()

    def group_exists_after_fork(_pid):
        observations.append("kernel-group-probe")
        assert observations == ["proc-scan-complete", "kernel-group-probe"]
        return True

    monkeypatch.setattr(validation_lease_module, "_process_stat", lambda _pid: None)
    monkeypatch.setattr(
        validation_lease_module,
        "_process_group_members",
        empty_proc_snapshot,
    )
    monkeypatch.setattr(
        validation_lease_module,
        "_process_group_exists",
        group_exists_after_fork,
    )

    gone, members = validation_lease_module._original_process_group_snapshot(
        123,
        456,
    )

    assert gone is False
    assert members == ()
    assert observations == ["proc-scan-complete", "kernel-group-probe"]


def test_live_numeric_pid_with_stale_start_ticks_is_never_signaled(monkeypatch):
    previous = subprocess.Popen(["true"], start_new_session=True)
    previous_ticks = validation_lease_module._process_start_ticks(previous.pid)
    assert previous_ticks is not None
    assert previous.wait(timeout=2) == 0
    time.sleep(0.05)
    replacement = subprocess.Popen(["sleep", "30"], start_new_session=True)
    replacement_ticks = validation_lease_module._process_start_ticks(replacement.pid)
    assert replacement_ticks is not None
    assert replacement_ticks != previous_ticks
    assert os.getpgid(replacement.pid) == replacement.pid
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        validation_lease_module,
        "_pidfd_send_signal",
        lambda descriptor, signum: signals.append((descriptor, signum)),
    )
    try:
        assert validation_lease_module._terminate_exact_process_group(
            replacement.pid,
            previous_ticks,
        ) is True
        assert replacement.poll() is None
        assert signals == []
    finally:
        replacement.terminate()
        replacement.wait(timeout=2)


def test_cancel_owner_terminates_only_matching_attached_process_group(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = _audit_owner("p1", "audit")
    handle = lease.acquire(owner)
    process = subprocess.Popen(
        ["sleep", "30"],
        pass_fds=handle.pass_fds,
        start_new_session=True,
    )
    handle.attach_process(process, timeout_seconds=60)

    assert lease.cancel_owner(owner) == 1
    assert process.wait(timeout=3) != 0
    handle.release()
    assert lease.status().owner_count == 0


def test_cancel_owner_withdraws_matching_waiter_without_callback(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_gate_owner("p1", "gate"))
    owner = _audit_owner("p1", "audit")
    errors: list[str] = []

    def wait() -> None:
        try:
            lease.acquire(owner)
        except ValidationLeaseCancelled as exc:
            errors.append(str(exc))

    waiter = threading.Thread(target=wait)
    waiter.start()
    _wait_for(lambda: lease.status().waiter_count == 1)

    assert lease.cancel_owner(owner) == 1
    waiter.join(timeout=3)

    assert waiter.is_alive() is False
    assert errors == ["validation authority withdrawn while waiting for capacity"]
    held.release()


def test_cancel_owner_durably_fences_acquire_to_attach_race(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = _audit_owner("p1", "attach-race")
    handle = lease.acquire(owner)

    assert lease.cancel_owner(owner) == 1
    with pytest.raises(
        ValidationLeaseCancelled,
        match="withdrawn before process attachment",
    ):
        handle.attach_process(
            types.SimpleNamespace(pid=os.getpid()),
            timeout_seconds=5,
        )
    handle.release()

    restarted = ValidationResourceLease(
        tmp_path / "lease.sqlite3",
        poll_seconds=0.01,
    )
    with pytest.raises(
        ValidationLeaseCancelled,
        match="withdrawn before capacity acquisition",
    ):
        restarted.acquire(owner)


def test_cancel_pruning_never_removes_an_active_owner_tombstone(
    tmp_path,
    monkeypatch,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = _audit_owner("p1", "active-cancel")
    handle = lease.acquire(owner)
    assert lease.cancel_owner(owner) == 1
    monkeypatch.setattr(
        "oompah.validation_resource_lease._CANCELLED_OWNER_RETENTION_SECONDS",
        0,
    )
    monkeypatch.setattr(
        "oompah.validation_resource_lease._CANCELLED_OWNER_LIMIT",
        1,
    )
    for index in range(5):
        lease.cancel_owner(_audit_owner("other", f"cancel-{index}"))

    with pytest.raises(
        ValidationLeaseCancelled,
        match="withdrawn before process attachment",
    ):
        handle.attach_process(
            types.SimpleNamespace(pid=os.getpid()),
            timeout_seconds=5,
        )
    handle.release()


def test_slot_probe_descriptors_are_not_ambiently_inheritable(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    available = lease._try_lock_slots()
    try:
        assert available
        assert all(os.get_inheritable(fd) is False for fd in available.values())
    finally:
        lease._close_slot_locks(available.values())


@pytest.mark.parametrize(
    "command",
    [
        (
            "python -m pytest -q tests/test_acp_backends.py tests/test_providers.py "
            "tests/test_providers_ui.py tests/test_acp_agent.py "
            "tests/test_orchestrator_handlers.py"
        ),
        "pytest tests/test_one.py::test_case",
        "python -m pytest tests/test_one.py",
        "/usr/bin/python -m pytest tests/test_one.py::test_case",
        "python -m unittest tests.test_one.TestCase.test_case",
    ],
)
def test_worker_validation_queues_behind_gate_at_worker_priority(
    tmp_path,
    monkeypatch,
    command,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(_gate_owner("p1", "gate"))
    process_started = threading.Event()

    class FakeProcess:
        pid = os.getpid()
        returncode = 0

        def __init__(self, *_args, **_kwargs):
            process_started.set()

        def communicate(self, timeout=None):
            return "", ""

    monkeypatch.setattr("oompah.api_agent.subprocess.Popen", FakeProcess)
    results: list[str] = []
    worker = threading.Thread(
        target=lambda: results.append(
            _exec_run_command(
                tmp_path,
                {"command": command},
                timeout=2,
                validation_lease=lease,
                validation_owner=_worker_owner("p2", "worker"),
                require_validation_lease=True,
            )
        )
    )
    worker.start()
    _wait_for(lambda: lease.status().waiter_count == 1)

    status = lease.status()
    assert process_started.is_set() is False
    assert status.waiters[0]["kind"] == VALIDATION_KIND_WORKER
    assert status.waiters[0]["priority"] == WORKER_PRIORITY
    assert WORKER_PRIORITY < AUDITOR_PRIORITY < EXACT_GATE_PRIORITY

    gate.release()
    worker.join(timeout=3)
    assert worker.is_alive() is False
    assert process_started.is_set() is True
    assert results == ["exit_code: 0"]


def test_focused_pytest_waits_for_exact_gate_before_real_process_start(tmp_path):
    marker = tmp_path / "focused-test-started"
    target = tmp_path / "target_test.py"
    target.write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "def test_runs_once():\n"
        "    marker_path = Path(os.environ['OOMPAH_FOCUSED_MARKER'])\n"
        "    with marker_path.open('x', encoding='utf-8') as marker:\n"
        "        marker.write(str(os.getpid()))\n",
        encoding="utf-8",
    )
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(_gate_owner("p1", "exact-gate"))
    command = (
        f"{shlex.quote(sys.executable)} -m pytest {shlex.quote(target.name)} -q"
    )
    result: list[str] = []
    worker = threading.Thread(
        target=lambda: result.append(
            _exec_run_command(
                tmp_path,
                {"command": command},
                timeout=10,
                env_overrides={"OOMPAH_FOCUSED_MARKER": str(marker)},
                validation_lease=lease,
                validation_owner=_worker_owner("p2", "focused"),
            )
        )
    )
    worker.start()
    _wait_for(lambda: lease.status().waiter_count == 1)

    assert marker.exists() is False
    assert worker.is_alive() is True

    gate.release()
    worker.join(timeout=10)

    assert worker.is_alive() is False
    assert result and "exit_code: 0" in result[0]
    assert marker.read_text(encoding="utf-8").isdigit()
    assert lease.status().owner_count == 0


def test_non_test_inspection_runs_without_validation_capacity(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    gate = lease.acquire(_gate_owner("p1", "exact-gate"))

    result = _exec_run_command(
        tmp_path,
        {"command": "printf inspection"},
        timeout=2,
        validation_lease=lease,
        validation_owner=_worker_owner("p2", "inspection"),
    )

    assert "stdout:\ninspection" in result
    assert "exit_code: 0" in result
    assert lease.status().owner_count == 1
    assert lease.status().waiter_count == 0
    gate.release()


def test_capacity_is_process_safe_across_independent_instances(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    first = ValidationResourceLease(state_path, capacity=1, poll_seconds=0.01)
    second = ValidationResourceLease(state_path, capacity=1, poll_seconds=0.01)
    held = first.acquire(_gate_owner("p1", "one"))
    acquired = threading.Event()

    def waiter() -> None:
        with second.acquire(_gate_owner("p2", "two")):
            acquired.set()

    thread = threading.Thread(target=waiter)
    thread.start()
    _wait_for(lambda: first.status().waiter_count == 1)
    assert acquired.is_set() is False
    held.release()
    thread.join(timeout=3)
    assert acquired.is_set() is True


def test_status_is_authoritative_activity_not_an_alert(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_gate_owner("p1", "gate"))
    cancelled = threading.Event()

    def wait() -> None:
        with pytest.raises(ValidationLeaseCancelled):
            lease.acquire(
                _worker_owner("p2", "worker"),
                is_cancelled=cancelled.is_set,
            )

    thread = threading.Thread(target=wait)
    thread.start()
    _wait_for(lambda: lease.status().waiter_count == 1)

    snapshot = lease.status().to_dict()
    assert snapshot["status"] == "busy"
    assert snapshot["available_capacity"] == 0
    assert snapshot["owner_count"] == 1
    assert snapshot["waiter_count"] == 1
    assert "alert" not in snapshot

    cancelled.set()
    thread.join(timeout=3)
    held.release()


def test_status_marks_legacy_provider_root_and_safe_recovery_action(
    tmp_path,
    monkeypatch,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_worker_owner("project", "TASK-1"))
    held.attach_process(types.SimpleNamespace(pid=os.getpid()), timeout_seconds=30)
    monkeypatch.setattr(
        validation_lease_module,
        "_legacy_provider_bootstrap_process",
        lambda _pid, _ticks, _trusted, _parent: True,
    )

    snapshot = lease.status().to_dict()

    assert snapshot["status"] == "action_required"
    assert snapshot["legacy_provider_bootstrap_owner_count"] == 1
    assert snapshot["owners"][0]["process_role"] == "legacy_provider_bootstrap"
    assert snapshot["owners"][0]["recovery_action"] == "claim_task_directly"
    assert snapshot["owners"][0]["recovery_preserves_worktree"] is True
    recovery = snapshot["owners"][0]["recovery_request"]
    assert recovery["method"] == "POST"
    assert recovery["endpoint"] == (
        "/api/v1/projects/project/tasks/TASK-1/owner-claim"
    )
    expected = recovery["body"]["expected_validation_owner"]
    assert expected["kind"] == "worker"
    assert expected["project_id"] == "project"
    assert expected["task_id"] == "TASK-1"
    assert expected["authority_generation"] == "worker-TASK-1"
    assert expected["requester_pid"] == os.getpid()
    assert expected["child_pid"] == os.getpid()
    held.release()


def test_exact_owner_cancellation_rejects_same_generation_aba_replacement(
    tmp_path,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    owner = _worker_owner("project", "TASK-1")
    held = lease.acquire(owner)
    held.attach_process(types.SimpleNamespace(pid=os.getpid()), timeout_seconds=30)
    advertised = lease.status().owners[0]
    replacement_identity = {
        "requester_pid": int(advertised["requester_pid"]) + 101,
        "requester_start_ticks": int(advertised["requester_start_ticks"]) + 101,
        "child_pid": int(advertised["child_pid"]) + 101,
        "child_start_ticks": int(advertised["child_start_ticks"]) + 101,
    }
    with lease._connect() as connection:
        connection.execute(
            """UPDATE owners SET requester_pid = ?, requester_start_ticks = ?,
                      child_pid = ?, child_start_ticks = ?
               WHERE token = ?""",
            (*replacement_identity.values(), held.token),
        )

    cancelled = lease.cancel_exact_owner_process(
        owner,
        requester_pid=int(advertised["requester_pid"]),
        requester_start_ticks=int(advertised["requester_start_ticks"]),
        child_pid=int(advertised["child_pid"]),
        child_start_ticks=int(advertised["child_start_ticks"]),
    )

    assert cancelled is False
    with lease._connect() as connection:
        current = connection.execute(
            "SELECT requester_pid, child_pid FROM owners WHERE token = ?",
            (held.token,),
        ).fetchone()
        tombstones = connection.execute(
            "SELECT COUNT(*) FROM cancelled_owners"
        ).fetchone()[0]
    assert dict(current) == {
        "requester_pid": replacement_identity["requester_pid"],
        "child_pid": replacement_identity["child_pid"],
    }
    assert tombstones == 0
    held.release()


def test_legacy_auditor_owner_does_not_advertise_direct_claim_recovery(
    tmp_path,
    monkeypatch,
):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_audit_owner("project", "TASK-1"))
    held.attach_process(types.SimpleNamespace(pid=os.getpid()), timeout_seconds=30)
    monkeypatch.setattr(
        validation_lease_module,
        "_legacy_provider_bootstrap_process",
        lambda _pid, _ticks, _trusted, _parent: True,
    )

    owner = lease.status().to_dict()["owners"][0]

    assert owner["process_role"] == "legacy_provider_bootstrap"
    assert "recovery_action" not in owner
    assert "recovery_request" not in owner
    held.release()


@pytest.mark.parametrize(
    (
        "arguments",
        "environment",
        "prefix",
        "entrypoint_matches_operator",
        "interpreter_matches_operator",
        "parent_matches_operator",
        "bootstrap_is_task_writable",
        "expected",
    ),
    [
        (
            ("node", "/operator/codex", "exec", "--experimental-json"),
            {"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "codex_sdk_ts"},
            b"#!/usr/bin/env node\n",
            True,
            True,
            True,
            False,
            True,
        ),
        (
            ("node", "/workspace/test.js", "exec", "--experimental-json"),
            {"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "codex_sdk_ts"},
            b"#!/usr/bin/env node\n",
            False,
            True,
            True,
            True,
            False,
        ),
        (
            ("node", "/operator/codex", "exec", "--version"),
            {"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "codex_sdk_ts"},
            b"#!/usr/bin/env node\n",
            True,
            True,
            True,
            False,
            False,
        ),
        (
            ("node", "/workspace/codex", "exec", "--experimental-json"),
            {"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "codex_sdk_ts"},
            b"#!/usr/bin/env node\n",
            True,
            True,
            True,
            True,
            False,
        ),
        (
            ("node", "/operator/codex", "exec", "--experimental-json"),
            {"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "codex_sdk_ts"},
            b"#!/usr/bin/env node\n",
            True,
            True,
            False,
            False,
            False,
        ),
    ],
)
def test_legacy_provider_root_detection_is_specific(
    arguments,
    environment,
    prefix,
    entrypoint_matches_operator,
    interpreter_matches_operator,
    parent_matches_operator,
    bootstrap_is_task_writable,
    expected,
):
    assert (
        validation_lease_module._is_legacy_provider_bootstrap_snapshot(
            arguments,
            environment,
            prefix,
            entrypoint_matches_operator=entrypoint_matches_operator,
            interpreter_matches_operator=interpreter_matches_operator,
            parent_matches_operator=parent_matches_operator,
            bootstrap_is_task_writable=bootstrap_is_task_writable,
        )
        is expected
    )


def test_same_project_cannot_monopolize_equal_priority_queue(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_gate_owner("blocker", "held"))
    order: list[str] = []

    def run(project: str, task: str) -> None:
        with lease.acquire(_gate_owner(project, task)):
            order.append(task)
            time.sleep(0.02)

    threads = [
        threading.Thread(target=run, args=("p1", "p1-first")),
        threading.Thread(target=run, args=("p1", "p1-second")),
        threading.Thread(target=run, args=("p2", "p2-first")),
    ]
    for thread in threads:
        thread.start()
        _wait_for(lambda: lease.status().waiter_count == threads.index(thread) + 1)
    held.release()
    for thread in threads:
        thread.join(timeout=3)

    assert order == ["p1-first", "p2-first", "p1-second"]


def test_queue_prioritizes_exact_gate_then_auditor_then_worker(tmp_path):
    lease = ValidationResourceLease(
        tmp_path / "lease.sqlite3",
        aging_seconds=60,
        poll_seconds=0.01,
    )
    held = lease.acquire(_gate_owner("blocker", "held"))
    order: list[str] = []

    def run(owner: ValidationLeaseOwner, label: str) -> None:
        with lease.acquire(owner):
            order.append(label)

    requests = [
        (_worker_owner("worker-project", "worker"), "worker"),
        (_audit_owner("audit-project", "audit"), "audit"),
        (_gate_owner("gate-project", "gate"), "gate"),
    ]
    threads: list[threading.Thread] = []
    for owner, label in requests:
        thread = threading.Thread(target=run, args=(owner, label))
        threads.append(thread)
        thread.start()
        _wait_for(lambda: lease.status().waiter_count == len(threads))

    held.release()
    for thread in threads:
        thread.join(timeout=3)

    assert order == ["gate", "audit", "worker"]


def test_exact_gate_has_priority_but_aging_prevents_auditor_starvation(tmp_path):
    lease = ValidationResourceLease(
        tmp_path / "lease.sqlite3",
        aging_seconds=0.01,
        poll_seconds=0.005,
    )
    held = lease.acquire(_gate_owner("blocker", "held"))
    order: list[str] = []

    def run(owner: ValidationLeaseOwner, label: str) -> None:
        with lease.acquire(owner):
            order.append(label)

    auditor = threading.Thread(target=run, args=(_audit_owner("p1", "audit"), "audit"))
    auditor.start()
    _wait_for(lambda: lease.status().waiter_count == 1)
    # Ten aging intervals erase the exact gate's initial ten-point advantage.
    time.sleep(0.12)
    exact = threading.Thread(target=run, args=(_gate_owner("p2", "gate"), "gate"))
    exact.start()
    _wait_for(lambda: lease.status().waiter_count == 2)
    held.release()
    auditor.join(timeout=3)
    exact.join(timeout=3)

    assert order == ["audit", "gate"]


def test_wait_cancellation_removes_durable_waiter(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    held = lease.acquire(_gate_owner("p1", "held"))
    cancelled = threading.Event()
    errors: list[BaseException] = []

    def wait() -> None:
        try:
            lease.acquire(_audit_owner("p1", "audit"), is_cancelled=cancelled.is_set)
        except BaseException as exc:  # test captures the worker exception
            errors.append(exc)

    thread = threading.Thread(target=wait)
    thread.start()
    _wait_for(lambda: lease.status().waiter_count == 1)
    cancelled.set()
    thread.join(timeout=3)

    assert len(errors) == 1
    assert isinstance(errors[0], ValidationLeaseCancelled)
    assert lease.status().waiter_count == 0
    held.release()


def test_requester_crash_is_recovered_without_manual_state_edit(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    script = """
import os, sys
from oompah.validation_resource_lease import ValidationLeaseOwner, ValidationResourceLease
lease = ValidationResourceLease(sys.argv[1], poll_seconds=0.01)
lease.acquire(ValidationLeaseOwner.exact_gate(project_id='p', task_id='dead', authority_generation='g'))
os._exit(0)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
    subprocess.run(
        [sys.executable, "-c", script, str(state_path)],
        cwd=Path(__file__).parents[1],
        env=env,
        check=True,
        timeout=5,
    )

    restarted = ValidationResourceLease(state_path, poll_seconds=0.01)
    with restarted.acquire(
        _gate_owner("p", "replacement"),
        wait_timeout_seconds=1,
    ):
        assert restarted.status().owner_count == 1


def test_restart_observes_child_that_inherited_kernel_fence(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    script = """
import os, subprocess, sys
from oompah.validation_resource_lease import ValidationLeaseOwner, ValidationResourceLease
lease = ValidationResourceLease(sys.argv[1], poll_seconds=0.01)
handle = lease.acquire(ValidationLeaseOwner.exact_gate(project_id='p', task_id='old', authority_generation='g'))
child = subprocess.Popen(['sleep', '0.5'], pass_fds=handle.pass_fds, start_new_session=True)
handle.attach_process(child, timeout_seconds=5)
os._exit(0)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
    subprocess.run(
        [sys.executable, "-c", script, str(state_path)],
        cwd=Path(__file__).parents[1],
        env=env,
        check=True,
        timeout=5,
    )
    restarted = ValidationResourceLease(state_path, poll_seconds=0.01)

    assert restarted.status().owner_count == 1
    with pytest.raises(ValidationLeaseCancelled, match="timed out"):
        restarted.acquire(
            _gate_owner("p", "new"),
            wait_timeout_seconds=0.1,
        )
    time.sleep(0.5)
    with restarted.acquire(
        _gate_owner("p", "new"),
        wait_timeout_seconds=1,
    ):
        assert restarted.status().owner_count == 1


def test_corrupt_database_is_quarantined_before_fresh_initialization(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    state_path.write_bytes(b"not a sqlite database")

    lease = ValidationResourceLease(state_path, poll_seconds=0.01)

    quarantined = list(tmp_path.glob("lease.sqlite3.corrupt-*"))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == b"not a sqlite database"
    with lease.acquire(_gate_owner("p", "after-corruption")):
        assert lease.status().owner_count == 1


def test_capacity_greater_than_one_allows_exact_number_of_owners(tmp_path):
    lease = ValidationResourceLease(
        tmp_path / "lease.sqlite3",
        capacity=2,
        poll_seconds=0.01,
    )
    first = lease.acquire(_gate_owner("p1", "one"))
    second = lease.acquire(_gate_owner("p2", "two"))
    acquired = threading.Event()

    def take_third() -> None:
        with lease.acquire(_gate_owner("p3", "three")):
            acquired.set()

    waiter = threading.Thread(target=take_third)
    waiter.start()
    _wait_for(lambda: lease.status().waiter_count == 1)
    assert lease.status().owner_count == 2
    assert acquired.is_set() is False
    first.release()
    waiter.join(timeout=3)
    assert waiter.is_alive() is False
    assert acquired.is_set() is True
    second.release()


def test_expired_attached_process_group_is_terminated(tmp_path):
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    handle = lease.acquire(_gate_owner("p", "expiring"))
    child = subprocess.Popen(
        ["sleep", "30"],
        pass_fds=handle.pass_fds,
        start_new_session=True,
    )
    handle.attach_process(child, timeout_seconds=0.05)

    _wait_for(
        lambda: (
            lease.status().owner_count >= 0
            and child.poll() is not None
        ),
        timeout=3,
    )

    assert child.returncode is not None
    handle.release()


def test_simultaneous_multiprocess_acquisition_has_no_lost_owner_update(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    script = """
import sys, time
from oompah.validation_resource_lease import ValidationLeaseOwner, ValidationResourceLease
lease = ValidationResourceLease(sys.argv[1], poll_seconds=0.005)
owner = ValidationLeaseOwner.worker(project_id='p', task_id=sys.argv[2], authority_generation=sys.argv[2])
with lease.acquire(owner, wait_timeout_seconds=5):
    started = time.time()
    time.sleep(0.08)
    ended = time.time()
print(f'{started},{ended}', flush=True)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(state_path), f"worker-{index}"],
            cwd=Path(__file__).parents[1],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(4)
    ]
    intervals: list[tuple[float, float]] = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        start, end = stdout.strip().split(",")
        intervals.append((float(start), float(end)))

    ordered = sorted(intervals)
    assert all(
        current[1] <= following[0]
        for current, following in zip(ordered, ordered[1:])
    )
    assert ValidationResourceLease(state_path).status().owner_count == 0


def test_restart_observes_waiter_and_allows_it_to_continue(tmp_path):
    state_path = tmp_path / "lease.sqlite3"
    held = ValidationResourceLease(state_path, poll_seconds=0.01).acquire(
        _gate_owner("p1", "held")
    )
    script = """
import sys
from oompah.validation_resource_lease import ValidationLeaseOwner, ValidationResourceLease
lease = ValidationResourceLease(sys.argv[1], poll_seconds=0.01)
owner = ValidationLeaseOwner.worker(project_id='p2', task_id='waiting', authority_generation='waiting')
with lease.acquire(owner, wait_timeout_seconds=5):
    print('acquired', flush=True)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
    waiter = subprocess.Popen(
        [sys.executable, "-c", script, str(state_path)],
        cwd=Path(__file__).parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _wait_for(lambda: ValidationResourceLease(state_path).status().waiter_count == 1)

    restarted = ValidationResourceLease(state_path, poll_seconds=0.01)
    assert restarted.status().owner_count == 1
    assert restarted.status().waiter_count == 1
    held.release()
    stdout, stderr = waiter.communicate(timeout=5)
    assert waiter.returncode == 0, stderr
    assert stdout.strip() == "acquired"


def test_successful_heavy_command_reports_auditor_evidence(tmp_path):
    (tmp_path / "Makefile").write_text(
        "test:\n\t@true\nfail:\n\t@false\n",
        encoding="utf-8",
    )
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    observed: list[tuple[str, Path]] = []

    success = _exec_run_command(
        tmp_path,
        {"command": "make test"},
        timeout=5,
        validation_lease=lease,
        validation_owner=_audit_owner("p", "audit"),
        successful_validation_handler=lambda command, workspace: observed.append(
            (command, workspace)
        ),
    )
    failure = _exec_run_command(
        tmp_path,
        {"command": "make fail"},
        timeout=5,
        validation_lease=lease,
        validation_owner=_audit_owner("p", "audit"),
        successful_validation_handler=lambda command, workspace: observed.append(
            (command, workspace)
        ),
    )

    assert "exit_code: 0" in success
    assert "exit_code: 2" in failure
    assert observed == [("make test", tmp_path)]


def test_successful_heavy_command_reports_duration_to_auditor_observer(tmp_path):
    (tmp_path / "Makefile").write_text("test:\n\t@sleep 0.01\n", encoding="utf-8")
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    observed: list[tuple[str, Path, float]] = []

    result = _exec_run_command(
        tmp_path,
        {"command": "make test"},
        timeout=5,
        validation_lease=lease,
        validation_owner=_audit_owner("p", "duration"),
        successful_validation_handler=lambda command, workspace, *, duration_seconds: observed.append(
            (command, workspace, duration_seconds)
        ),
    )

    assert "exit_code: 0" in result
    assert observed[0][:2] == ("make test", tmp_path)
    assert observed[0][2] > 0


@pytest.mark.parametrize(
    ("target", "expected_outcome", "expected_success"),
    [
        ("test", "passed", True),
        ("fail", "failed", False),
        ("slow", "timed_out", False),
    ],
)
def test_api_command_runner_reports_complete_auditor_validation_lifecycle(
    tmp_path,
    target,
    expected_outcome,
    expected_success,
):
    (tmp_path / "Makefile").write_text(
        "test:\n\t@true\nfail:\n\t@false\nslow:\n\t@sleep 1\n",
        encoding="utf-8",
    )
    lease = ValidationResourceLease(tmp_path / "lease.sqlite3", poll_seconds=0.01)
    coordination = MagicMock()
    coordination.record_auditor_quality_evidence.return_value = True
    audit_target = types.SimpleNamespace(
        project_id="p",
        task_id="TASK-1",
        audit_id="audit-1",
    )
    observer = _auditor_validation_success_handler(
        coordination,
        auditor_mode=True,
        audit_target=audit_target,
    )

    result = _exec_run_command(
        tmp_path,
        {"command": f"make {target}"},
        timeout=0.05 if target == "slow" else 5,
        validation_lease=lease,
        validation_owner=_audit_owner("p", f"lifecycle-{target}"),
        successful_validation_handler=observer,
    )

    telemetry_calls = coordination.record_auditor_validation_command.call_args_list
    assert [call.kwargs["phase"] for call in telemetry_calls] == [
        "started",
        "completed",
    ]
    assert telemetry_calls[0].kwargs["outcome"] == "running"
    assert telemetry_calls[1].kwargs["outcome"] == expected_outcome
    assert telemetry_calls[1].kwargs["succeeded"] is expected_success
    assert telemetry_calls[0].kwargs["duration_seconds"] == 0
    assert telemetry_calls[1].kwargs["duration_seconds"] > 0
    assert all(
        call.kwargs["audit_target"] is audit_target for call in telemetry_calls
    )
    assert (
        telemetry_calls[0].kwargs["invocation_id"]
        == telemetry_calls[1].kwargs["invocation_id"]
    )
    if expected_success:
        assert "exit_code: 0" in result
        evidence_call = coordination.record_auditor_quality_evidence.call_args
        assert evidence_call.kwargs["audit_target"] is audit_target
        assert evidence_call.kwargs["workspace_path"] == tmp_path
        assert evidence_call.kwargs["command"] == "make test"
        assert evidence_call.kwargs["duration_seconds"] > 0
    else:
        coordination.record_auditor_quality_evidence.assert_not_called()


@pytest.mark.parametrize(
    ("args", "authority", "expected_decision", "denied"),
    [
        (
            {
                "command": "make test",
                "validation_mode": "task_required_distinct",
                "validation_justification": "still exact",
            },
            "reuse_authoritative_gate",
            "denied_reused_gate",
            True,
        ),
        (
            {
                "command": "bash -lc 'make test'",
                "validation_mode": "task_required_distinct",
                "validation_justification": "wrapped spelling",
            },
            "reuse_authoritative_gate",
            "denied_reused_gate",
            True,
        ),
        (
            {"command": "make test-serial"},
            "reuse_authoritative_gate",
            "denied_distinct_mode_required",
            True,
        ),
        (
            {
                "command": "env -S 'make test'",
                "validation_mode": "task_required_distinct",
                "validation_justification": "opaque spelling",
            },
            "reuse_authoritative_gate",
            "denied_reused_gate",
            True,
        ),
        (
            {"command": "./ci/test.sh"},
            "reuse_authoritative_gate",
            "denied_distinct_mode_required",
            True,
        ),
        (
            {
                "command": "./ci/test.sh",
                "validation_mode": "task_required_distinct",
                "validation_justification": "task-specific opaque suite",
            },
            "reuse_authoritative_gate",
            "allowed_distinct_mode",
            False,
        ),
        (
            {
                "command": "make test-serial",
                "validation_mode": "task_required_distinct",
                "validation_justification": "task requires serial race coverage",
            },
            "reuse_authoritative_gate",
            "allowed_distinct_mode",
            False,
        ),
        (
            {"command": "pytest tests/test_one.py -q"},
            "reuse_authoritative_gate",
            "",
            False,
        ),
        (
            {"command": "make test"},
            "stale_authority",
            "denied_stale_authority",
            True,
        ),
        (
            {"command": "make test"},
            "full_gate_required",
            "allowed_gate_now_required",
            False,
        ),
    ],
)
def test_validation_reuse_policy_decision_matrix(
    args,
    authority,
    expected_decision,
    denied,
):
    decision, denial, justification = _validation_reuse_policy_decision(
        args,
        _reusable_gate_policy(),
        lambda: authority,
        classification=classify_validation_command(
            args["command"],
            configured_command="make test",
        ),
    )

    assert decision == expected_decision
    assert (denial is not None) is denied
    if decision == "allowed_distinct_mode":
        assert justification == args["validation_justification"]
    else:
        assert justification == ""


@pytest.mark.parametrize("authority_surface", ["missing", "raises"])
def test_validation_reuse_policy_fails_closed_without_fresh_authority(
    authority_surface,
):
    def raise_authority_error():
        raise RuntimeError("authority unavailable")

    authority_check = (
        raise_authority_error if authority_surface == "raises" else None
    )

    decision, denial, _ = _validation_reuse_policy_decision(
        {"command": "pytest tests/test_one.py"},
        _reusable_gate_policy(),
        authority_check,
        classification=classify_validation_command(
            "pytest tests/test_one.py",
            configured_command="make test",
        ),
    )

    assert decision == "denied_stale_authority"
    assert denial is not None


def test_context_aware_classification_never_labels_runner_env_focused() -> None:
    classification = classify_validation_command(
        "pytest tests/test_one.py::test_case",
        command_environment={"PYTEST_ADDOPTS": "tests"},
    )

    assert classification.heavyweight is True
    assert classification.scope == "opaque"
    assert classification.focused is False


def test_context_aware_classification_never_labels_task_path_runner_focused(
    tmp_path: Path,
) -> None:
    task_bin = tmp_path / "bin"
    task_bin.mkdir()
    fake_pytest = task_bin / "pytest"
    fake_pytest.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_pytest.chmod(0o700)

    classification = classify_validation_command(
        "pytest tests/test_one.py::test_case",
        executable_search_path=f"{task_bin}{os.pathsep}/usr/bin:/bin",
        untrusted_executable_roots=(tmp_path,),
        working_directory=tmp_path,
    )

    assert classification.heavyweight is True
    assert classification.scope == "opaque"
    assert classification.focused is False


def test_exec_denies_reused_exact_gate_before_process_launch(tmp_path, monkeypatch):
    popen = MagicMock(side_effect=AssertionError("must not launch"))
    telemetry = MagicMock()
    monkeypatch.setattr("oompah.api_agent.subprocess.Popen", popen)

    result = _exec_run_command(
        tmp_path,
        {
            "command": "env -S 'make test'",
            "validation_mode": "task_required_distinct",
            "validation_justification": "wrapper must not bypass the exact denial",
        },
        validation_reuse_policy=_reusable_gate_policy(),
        validation_reuse_authority_check=lambda: "reuse_authoritative_gate",
        validation_reuse_policy_handler=telemetry,
    )

    assert "already passed" in result
    popen.assert_not_called()
    telemetry.assert_called_once()
    assert telemetry.call_args.kwargs["decision"] == "denied_reused_gate"
    assert telemetry.call_args.kwargs["invocation_id"]


def test_exec_reuse_policy_uses_context_aware_path_classification(
    tmp_path,
    monkeypatch,
):
    task_bin = tmp_path / "bin"
    task_bin.mkdir()
    fake_git = task_bin / "git"
    fake_git.write_text("#!/bin/sh\nexec make test\n", encoding="utf-8")
    fake_git.chmod(0o700)
    popen = MagicMock(side_effect=AssertionError("must not launch"))
    telemetry = MagicMock()
    monkeypatch.setattr("oompah.api_agent.subprocess.Popen", popen)

    result = _exec_run_command(
        tmp_path,
        {"command": "git status --short"},
        env_overrides={"PATH": f"{task_bin}{os.pathsep}/usr/bin:/bin"},
        validation_reuse_policy=_reusable_gate_policy(),
        validation_reuse_authority_check=lambda: "reuse_authoritative_gate",
        validation_reuse_policy_handler=telemetry,
    )

    assert "requires validation_mode" in result
    popen.assert_not_called()
    assert telemetry.call_args.kwargs["decision"] == (
        "denied_distinct_mode_required"
    )


def test_exec_rechecks_reuse_authority_after_capacity_queue(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    (tmp_path / "Makefile").write_text(
        f"test-serial:\n\t@touch {shlex.quote(str(marker))}\n",
        encoding="utf-8",
    )
    lease = ValidationResourceLease(
        tmp_path / "validation.sqlite3",
        capacity=1,
        poll_seconds=0.01,
    )
    exact_gate = lease.acquire(_gate_owner("p", "gate"))
    authority = {"state": "reuse_authoritative_gate"}
    authority_calls = 0
    final_sample_started = threading.Event()
    release_final_sample = threading.Event()
    metrics = TerminalAuditMetrics()
    result: list[str] = []

    def read_authority() -> str:
        nonlocal authority_calls
        authority_calls += 1
        if authority_calls == 3:
            final_sample_started.set()
            assert release_final_sample.wait(timeout=5)
        return authority["state"]

    def record_policy(**values) -> None:
        metrics.record_validation_reuse_policy(
            "p",
            "queued-auditor",
            "audit-1",
            attempt_id="attempt-1",
            **values,
        )

    worker = threading.Thread(
        target=lambda: result.append(
            _exec_run_command(
                tmp_path,
                {
                    "command": "make test-serial",
                    "validation_mode": "task_required_distinct",
                    "validation_justification": "serial race coverage",
                },
                timeout=5,
                validation_lease=lease,
                validation_owner=_audit_owner("p", "queued-auditor"),
                validation_reuse_policy=_reusable_gate_policy(),
                validation_reuse_authority_check=read_authority,
                validation_reuse_policy_handler=record_policy,
            )
        ),
    )
    worker.start()
    _wait_for(lambda: lease.status().waiter_count == 1)
    exact_gate.release()
    assert final_sample_started.wait(timeout=5)
    authority["state"] = "stale_authority"
    release_final_sample.set()
    worker.join(timeout=5)

    assert worker.is_alive() is False
    assert result and "authority is stale" in result[0]
    assert marker.exists() is False
    assert lease.status().owner_count == 0
    snapshot = metrics.snapshot()
    invocations = snapshot["validation"]["reuse_policy_invocations"]
    assert len(invocations) == 1
    assert next(iter(invocations.values()))["decision"] == (
        "denied_stale_authority"
    )
    assert snapshot["validation"]["last_reuse_policy"]["decision"] == (
        "denied_stale_authority"
    )
    assert snapshot["reused_gate_validation_denied"] == 1
    assert snapshot["reused_gate_distinct_mode_allowed"] == 0


def test_exec_allows_exact_gate_when_reusable_proof_disappears(tmp_path):
    (tmp_path / "Makefile").write_text("test:\n\t@true\n", encoding="utf-8")
    telemetry = MagicMock()

    result = _exec_run_command(
        tmp_path,
        {"command": "make test"},
        timeout=5,
        validation_reuse_policy=_reusable_gate_policy(),
        validation_reuse_authority_check=lambda: "full_gate_required",
        validation_reuse_policy_handler=telemetry,
    )

    assert "exit_code: 0" in result
    assert telemetry.call_args.kwargs["decision"] == "allowed_gate_now_required"


def test_api_tool_dispatch_threads_validation_reuse_policy(tmp_path, monkeypatch):
    popen = MagicMock(side_effect=AssertionError("must not launch"))
    monkeypatch.setattr("oompah.api_agent.subprocess.Popen", popen)

    result = _execute_tool(
        tmp_path,
        "run_command",
        {"command": "make test"},
        validation_reuse_policy=_reusable_gate_policy(),
        validation_reuse_authority_check=lambda: "reuse_authoritative_gate",
    )

    assert "already passed" in result
    popen.assert_not_called()


def test_acp_tool_dispatch_threads_validation_reuse_policy(
    tmp_path,
    monkeypatch,
):
    import asyncio

    class FakeTool:
        def __init__(self, name, handler, input_schema):
            self.name = name
            self.handler = handler
            self.input_schema = input_schema

    def tool(name, _description, input_schema):
        def decorate(handler):
            return FakeTool(name, handler, input_schema)

        return decorate

    monkeypatch.setitem(
        sys.modules,
        "claude_agent_sdk",
        types.SimpleNamespace(tool=tool),
    )
    popen = MagicMock(side_effect=AssertionError("must not launch"))
    monkeypatch.setattr("oompah.api_agent.subprocess.Popen", popen)
    from oompah.acp_tools import build_tool_catalog

    catalog = build_tool_catalog(
        str(tmp_path),
        validation_reuse_policy=_reusable_gate_policy(),
        validation_reuse_authority_check=lambda: "reuse_authoritative_gate",
    )
    run_command = next(item for item in catalog if item.name == "run_command")

    result = asyncio.run(run_command.handler({"command": "make test"}))

    assert "already passed" in result["content"][0]["text"]
    popen.assert_not_called()
