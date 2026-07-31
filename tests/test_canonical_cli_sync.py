"""Safety tests for the canonical user-facing CLI installation."""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

import pytest

from scripts.sync_canonical_cli import (
    SyncError,
    activate_candidate,
    stage_candidate,
    synchronize,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True)
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "source.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "source.txt")
    subprocess.run(["git", "commit", "--quiet", "-m", "initial"], cwd=repo, check=True)
    _git(repo, "remote", "add", "origin", str(remote))
    subprocess.run(["git", "push", "--quiet", "-u", "origin", "main"], cwd=repo, check=True)
    return repo


def _push_change(repo: Path, content: str) -> str:
    (repo / "source.txt").write_text(content, encoding="utf-8")
    _git(repo, "add", "source.txt")
    subprocess.run(["git", "commit", "--quiet", "-m", "change"], cwd=repo, check=True)
    subprocess.run(["git", "push", "--quiet"], cwd=repo, check=True)
    return _git(repo, "rev-parse", "HEAD")


def _fake_uv(tmp_path: Path) -> Path:
    fake = tmp_path / "uv"
    fake.write_text(
        """#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path

if os.environ.get("FAKE_UV_FAILURE") == "1":
    print("simulated UV failure", file=sys.stderr)
    raise SystemExit(17)

tool_dir = Path(os.environ["UV_TOOL_DIR"])
bin_dir = Path(os.environ["UV_TOOL_BIN_DIR"])
tool = tool_dir / "oompah"
shutil.rmtree(tool, ignore_errors=True)
entrypoint = tool / "bin" / "oompah"
entrypoint.parent.mkdir(parents=True)
bin_dir.mkdir(parents=True, exist_ok=True)
revision = os.environ["FAKE_CLI_REVISION"]
entrypoint.write_text(
    "#!/bin/sh\\n"
    f"echo 'oompah 0.1.0 (revision {revision})'\\n",
    encoding="utf-8",
)
entrypoint.chmod(0o755)
launcher = bin_dir / "oompah"
launcher.write_text(
    "#!/bin/sh\\n"
    f"exec '{entrypoint}' \\\"$@\\\"\\n",
    encoding="utf-8",
)
launcher.chmod(0o755)
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def _paths(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    home = tmp_path / "home"
    bin_dir = home / ".local" / "bin"
    tool_dir = home / ".local" / "share" / "uv" / "tools"
    bin_dir.mkdir(parents=True)
    env = {
        "HOME": str(home),
        "PATH": os.pathsep.join((str(bin_dir), "/usr/bin")),
    }
    return home, bin_dir / "oompah", tool_dir, env


def _kwargs(repo, canonical, uv, tool_dir, env):
    return {
        "repo": repo,
        "canonical": canonical,
        "uv": str(uv),
        "tool_dir": tool_dir,
        "bin_dir": canonical.parent,
        "environ": env,
    }


def test_initial_install_and_upgrade_use_pushed_revision(tmp_path):
    repo = _repo(tmp_path)
    uv = _fake_uv(tmp_path)
    _, canonical, tool_dir, env = _paths(tmp_path)
    first = _git(repo, "rev-parse", "HEAD")
    env["FAKE_CLI_REVISION"] = first
    kwargs = _kwargs(repo, canonical, uv, tool_dir, env)

    assert synchronize(**kwargs) is True
    assert first in subprocess.check_output([str(canonical), "--version"], text=True)
    first_roots = set((tool_dir / ".oompah-revisions").iterdir())
    assert len(first_roots) == 1
    assert first in next(iter(first_roots)).name

    second = _push_change(repo, "two\n")
    env["FAKE_CLI_REVISION"] = second
    assert synchronize(**kwargs) is True
    assert second in subprocess.check_output([str(canonical), "--version"], text=True)
    published_roots = set((tool_dir / ".oompah-revisions").iterdir())
    assert first_roots < published_roots
    assert any(second in root.name for root in published_roots)


def test_already_current_is_a_noop(tmp_path):
    repo = _repo(tmp_path)
    uv = _fake_uv(tmp_path)
    _, canonical, tool_dir, env = _paths(tmp_path)
    revision = _git(repo, "rev-parse", "HEAD")
    env["FAKE_CLI_REVISION"] = revision
    kwargs = _kwargs(repo, canonical, uv, tool_dir, env)
    assert synchronize(**kwargs) is True
    env["FAKE_UV_FAILURE"] = "1"
    assert synchronize(**kwargs) is False


@pytest.mark.parametrize("failure_mode", ["install", "mismatch"])
def test_failed_install_or_mismatch_preserves_known_good_cli(tmp_path, failure_mode):
    repo = _repo(tmp_path)
    uv = _fake_uv(tmp_path)
    _, canonical, tool_dir, env = _paths(tmp_path)
    old_revision = _git(repo, "rev-parse", "HEAD")
    env["FAKE_CLI_REVISION"] = old_revision
    kwargs = _kwargs(repo, canonical, uv, tool_dir, env)
    assert synchronize(**kwargs) is True
    old_launcher = canonical.read_bytes()
    _push_change(repo, "two\n")
    env["FAKE_CLI_REVISION"] = "bad-revision" if failure_mode == "mismatch" else _git(repo, "rev-parse", "HEAD")
    if failure_mode == "install":
        env["FAKE_UV_FAILURE"] = "1"

    with pytest.raises(SyncError, match="preserved|mismatch"):
        synchronize(**kwargs)
    assert canonical.read_bytes() == old_launcher
    assert old_revision in subprocess.check_output([str(canonical), "--version"], text=True)


def test_dirty_and_unpushed_revisions_are_refused(tmp_path):
    repo = _repo(tmp_path)
    uv = _fake_uv(tmp_path)
    _, canonical, tool_dir, env = _paths(tmp_path)
    revision = _git(repo, "rev-parse", "HEAD")
    env["FAKE_CLI_REVISION"] = revision
    kwargs = _kwargs(repo, canonical, uv, tool_dir, env)
    (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(SyncError, match="dirty"):
        synchronize(**kwargs)
    (repo / "dirty.txt").unlink()
    (repo / "source.txt").write_text("unpushed\n", encoding="utf-8")
    _git(repo, "add", "source.txt")
    subprocess.run(["git", "commit", "--quiet", "-m", "unpushed"], cwd=repo, check=True)
    with pytest.raises(SyncError, match="pushed upstream"):
        synchronize(**kwargs)


def test_wrong_path_resolution_refuses_to_activate_new_cli(tmp_path):
    repo = _repo(tmp_path)
    uv = _fake_uv(tmp_path)
    _, canonical, tool_dir, env = _paths(tmp_path)
    old_revision = _git(repo, "rev-parse", "HEAD")
    env["FAKE_CLI_REVISION"] = old_revision
    kwargs = _kwargs(repo, canonical, uv, tool_dir, env)
    assert synchronize(**kwargs) is True
    old_launcher = canonical.read_bytes()
    new_revision = _push_change(repo, "two\n")
    env["FAKE_CLI_REVISION"] = new_revision
    env["PATH"] = "/usr/bin"
    with pytest.raises(SyncError, match="command -v"):
        synchronize(**kwargs)
    assert canonical.read_bytes() == old_launcher


def test_stage_does_not_replace_launcher_and_activation_can_roll_back(tmp_path):
    repo = _repo(tmp_path)
    uv = _fake_uv(tmp_path)
    _, canonical, tool_dir, env = _paths(tmp_path)
    old_revision = _git(repo, "rev-parse", "HEAD")
    env["FAKE_CLI_REVISION"] = old_revision
    kwargs = _kwargs(repo, canonical, uv, tool_dir, env)
    assert synchronize(**kwargs) is True
    old_launcher = canonical.read_bytes()
    old_roots = set((tool_dir / ".oompah-revisions").iterdir())

    new_revision = _push_change(repo, "two\n")
    env["FAKE_CLI_REVISION"] = new_revision
    staged = stage_candidate(repo=repo, uv=str(uv), environ=env)
    try:
        assert canonical.read_bytes() == old_launcher
        activation = activate_candidate(
            staged,
            canonical=canonical,
            tool_dir=tool_dir,
            bin_dir=canonical.parent,
            environ=env,
        )
        assert new_revision in subprocess.check_output([str(canonical), "--version"], text=True)
        assert activation.published_tool.is_dir()
        assert old_roots < set((tool_dir / ".oompah-revisions").iterdir())
        activation.rollback()
        assert canonical.read_bytes() == old_launcher
        assert all(root.is_dir() for root in old_roots)
        assert activation.published_tool.is_dir()
        assert old_revision in subprocess.check_output([str(canonical), "--version"], text=True)
    finally:
        staged.cleanup()


def test_activation_interruption_after_tool_publication_preserves_old_pair(
    tmp_path, monkeypatch
):
    """A published candidate root cannot disturb the live launcher/tool pair."""
    repo = _repo(tmp_path)
    uv = _fake_uv(tmp_path)
    _, canonical, tool_dir, env = _paths(tmp_path)
    old_revision = _git(repo, "rev-parse", "HEAD")
    env["FAKE_CLI_REVISION"] = old_revision
    kwargs = _kwargs(repo, canonical, uv, tool_dir, env)
    assert synchronize(**kwargs) is True
    old_launcher = canonical.read_bytes()
    old_roots = set((tool_dir / ".oompah-revisions").iterdir())

    new_revision = _push_change(repo, "two\n")
    env["FAKE_CLI_REVISION"] = new_revision
    staged = stage_candidate(repo=repo, uv=str(uv), environ=env)
    real_replace = os.replace

    def interrupted_replace(source, destination):
        source_path = Path(source)
        if Path(destination) == canonical and source_path.name.startswith(
            ".oompah-candidate-"
        ):
            raise OSError("simulated launcher activation interruption")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", interrupted_replace)
    try:
        with pytest.raises(SyncError, match="activation interruption"):
            activate_candidate(
                staged,
                canonical=canonical,
                tool_dir=tool_dir,
                bin_dir=canonical.parent,
                environ=env,
            )
        assert canonical.read_bytes() == old_launcher
        assert old_revision in subprocess.check_output(
            [str(canonical), "--version"], text=True
        )
        roots = set((tool_dir / ".oompah-revisions").iterdir())
        assert old_roots < roots
        assert any(new_revision in root.name for root in roots)
    finally:
        staged.cleanup()


def test_concurrent_invocations_see_complete_cli_during_atomic_activation(
    tmp_path, monkeypatch
):
    repo = _repo(tmp_path)
    uv = _fake_uv(tmp_path)
    _, canonical, tool_dir, env = _paths(tmp_path)
    old_revision = _git(repo, "rev-parse", "HEAD")
    env["FAKE_CLI_REVISION"] = old_revision
    kwargs = _kwargs(repo, canonical, uv, tool_dir, env)
    assert synchronize(**kwargs) is True

    new_revision = _push_change(repo, "two\n")
    env["FAKE_CLI_REVISION"] = new_revision
    staged = stage_candidate(repo=repo, uv=str(uv), environ=env)
    activation_ready = threading.Event()
    permit_activation = threading.Event()
    real_replace = os.replace
    result: dict[str, object] = {}

    def blocking_replace(source, destination):
        source_path = Path(source)
        if Path(destination) == canonical and source_path.name.startswith(
            ".oompah-candidate-"
        ):
            activation_ready.set()
            if not permit_activation.wait(timeout=5):
                raise TimeoutError("test did not release launcher activation")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", blocking_replace)

    def activate_in_thread():
        try:
            result["activation"] = activate_candidate(
                staged,
                canonical=canonical,
                tool_dir=tool_dir,
                bin_dir=canonical.parent,
                environ=env,
            )
        except BaseException as exc:  # pragma: no cover - assertion reports it
            result["error"] = exc

    worker = threading.Thread(target=activate_in_thread)
    worker.start()
    try:
        assert activation_ready.wait(timeout=5)
        for _ in range(20):
            output = subprocess.check_output([str(canonical), "--version"], text=True)
            assert old_revision in output
        permit_activation.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert "error" not in result
        assert new_revision in subprocess.check_output(
            [str(canonical), "--version"], text=True
        )
        activation = result["activation"]
        assert hasattr(activation, "commit")
        activation.commit()
    finally:
        permit_activation.set()
        worker.join(timeout=5)
        staged.cleanup()
