"""Safety tests for the canonical user-facing CLI installation."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import scripts.sync_canonical_cli as sync_cli
from scripts.sync_canonical_cli import (
    SyncError,
    activate_candidate,
    canonical_cli_lifecycle_lock,
    lifecycle_lock_path,
    prune_revision_roots,
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


def test_lifecycle_lock_is_stable_and_reentrant(tmp_path):
    _, canonical, _, _ = _paths(tmp_path)
    expected = canonical.parent / ".oompah-cli-lifecycle.lock"

    with canonical_cli_lifecycle_lock(canonical) as outer:
        with canonical_cli_lifecycle_lock(canonical) as inner:
            assert outer == expected
            assert inner == expected
            assert lifecycle_lock_path(canonical) == expected

    assert expected.is_file()
    assert expected.stat().st_mode & 0o777 == 0o600


def test_lifecycle_lock_serializes_separate_processes(tmp_path):
    _, canonical, _, _ = _paths(tmp_path)
    attempted = tmp_path / "child-attempted"
    acquired = tmp_path / "child-acquired"
    child_code = "\n".join(
        (
            "import sys",
            "from pathlib import Path",
            "from scripts.sync_canonical_cli import canonical_cli_lifecycle_lock",
            "canonical, attempted, acquired = map(Path, sys.argv[1:])",
            "attempted.write_text('ready', encoding='utf-8')",
            "with canonical_cli_lifecycle_lock(canonical):",
            "    acquired.write_text('acquired', encoding='utf-8')",
        )
    )

    with canonical_cli_lifecycle_lock(canonical):
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                child_code,
                str(canonical),
                str(attempted),
                str(acquired),
            ],
            cwd=Path(__file__).resolve().parents[1],
        )
        deadline = time.monotonic() + 5
        while not attempted.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert attempted.exists()
        assert not acquired.exists(), "the child process must block on flock"

    child.wait(timeout=5)
    assert child.returncode == 0
    assert acquired.read_text(encoding="utf-8") == "acquired"


def test_concurrent_synchronizations_serialize_the_full_transaction(
    tmp_path, monkeypatch
):
    repo = _repo(tmp_path)
    uv = _fake_uv(tmp_path)
    _, canonical, tool_dir, env = _paths(tmp_path)
    revision = _git(repo, "rev-parse", "HEAD")
    env["FAKE_CLI_REVISION"] = revision
    kwargs = _kwargs(repo, canonical, uv, tool_dir, env)
    first_staging = threading.Event()
    release_first = threading.Event()
    unexpected_second_stage = threading.Event()
    stage_calls = 0
    stage_calls_guard = threading.Lock()
    results: list[bool] = []
    errors: list[BaseException] = []
    real_stage = sync_cli.stage_candidate

    def blocking_stage(**stage_kwargs):
        nonlocal stage_calls
        with stage_calls_guard:
            stage_calls += 1
            call_number = stage_calls
        if call_number == 1:
            first_staging.set()
            if not release_first.wait(timeout=5):
                raise TimeoutError("test did not release the first synchronization")
        else:
            unexpected_second_stage.set()
        return real_stage(**stage_kwargs)

    monkeypatch.setattr(sync_cli, "stage_candidate", blocking_stage)

    def run_sync():
        try:
            results.append(synchronize(**kwargs))
        except BaseException as exc:  # pragma: no cover - assertion reports it
            errors.append(exc)

    first = threading.Thread(target=run_sync)
    second = threading.Thread(target=run_sync)
    first.start()
    assert first_staging.wait(timeout=5)
    second.start()
    try:
        assert not unexpected_second_stage.wait(timeout=0.2)
        assert second.is_alive(), "the second transaction must wait on the host lock"
    finally:
        release_first.set()
        first.join(timeout=5)
        second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert sorted(results) == [False, True]
    assert stage_calls == 1
    assert revision in subprocess.check_output([str(canonical), "--version"], text=True)
    assert not list(canonical.parent.glob(".oompah-cli-activation-*"))


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


def test_successive_upgrades_bound_obsolete_immutable_roots(tmp_path):
    repo = _repo(tmp_path)
    uv = _fake_uv(tmp_path)
    _, canonical, tool_dir, env = _paths(tmp_path)
    env["FAKE_CLI_REVISION"] = _git(repo, "rev-parse", "HEAD")
    kwargs = _kwargs(repo, canonical, uv, tool_dir, env)
    assert synchronize(**kwargs) is True

    for index in range(6):
        revision = _push_change(repo, f"upgrade-{index}\n")
        env["FAKE_CLI_REVISION"] = revision
        assert synchronize(**kwargs) is True

    roots = list((tool_dir / ".oompah-revisions").iterdir())
    assert len(roots) <= 4
    current_revision = _git(repo, "rev-parse", "HEAD")
    assert current_revision in subprocess.check_output(
        [str(canonical), "--version"], text=True
    )

    stale_roots = []
    for index in range(100, 103):
        stale = tool_dir / ".oompah-revisions" / f"{index:040x}-{index:032x}"
        stale.mkdir()
        os.utime(stale, (1, 1))
        stale_roots.append(stale)
    assert synchronize(**kwargs) is False
    assert all(not stale.exists() for stale in stale_roots)


def test_pruning_protects_live_backup_and_active_invocation_roots(tmp_path):
    revisions_dir = tmp_path / "tools" / ".oompah-revisions"
    revisions_dir.mkdir(parents=True)
    roots = []
    for index in range(6):
        root = revisions_dir / f"{index:040x}-{index:032x}"
        root.mkdir()
        roots.append(root)

    canonical = tmp_path / "bin" / "oompah"
    canonical.parent.mkdir()
    canonical.write_text(f"#!/bin/sh\n# {roots[5]}\n", encoding="utf-8")
    backup = tmp_path / "backup" / "oompah"
    backup.parent.mkdir()
    backup.write_text(f"#!/bin/sh\n# {roots[4]}\n", encoding="utf-8")

    active_script = roots[0] / "active.py"
    active_script.write_text(
        "#!/usr/bin/python3\nimport time\ntime.sleep(60)\n",
        encoding="utf-8",
    )
    active_script.chmod(0o755)
    process = subprocess.Popen([str(active_script)])
    try:
        removed = prune_revision_roots(
            revisions_dir,
            canonical=canonical,
            backup_launchers=(backup,),
            max_roots=1,
        )

        assert roots[5].is_dir(), "canonical launcher root must be retained"
        assert roots[4].is_dir(), "rollback launcher root must be retained"
        assert roots[0].is_dir(), "active invocation root must be retained"
        assert removed
        assert all(not root.exists() for root in removed)
    finally:
        process.terminate()
        process.wait(timeout=2)


def test_pruning_tolerates_launcher_replacement_and_ignores_partial_roots(
    tmp_path, monkeypatch
):
    revisions_dir = tmp_path / "tools" / ".oompah-revisions"
    revisions_dir.mkdir(parents=True)
    roots = []
    for index in range(6):
        root = revisions_dir / f"{index:040x}-{index:032x}"
        root.mkdir()
        os.utime(root, (index + 1, index + 1))
        roots.append(root)

    incomplete = revisions_dir / f".{7:040x}-{7:032x}.publishing"
    incomplete.mkdir()
    symlink_target = tmp_path / "external-root"
    symlink_target.mkdir()
    symlink_root = revisions_dir / f"{8:040x}-{8:032x}"
    symlink_root.symlink_to(symlink_target, target_is_directory=True)

    canonical = tmp_path / "bin" / "oompah"
    canonical.parent.mkdir()
    canonical.write_text(f"#!/bin/sh\n# {roots[0]}\n", encoding="utf-8")
    replacement = canonical.parent / ".replacement"
    replacement.write_text(f"#!/bin/sh\n# {roots[5]}\n", encoding="utf-8")
    real_read_bytes = Path.read_bytes
    replacement_done = False

    def read_during_replacement(path):
        nonlocal replacement_done
        payload = real_read_bytes(path)
        if path == canonical and not replacement_done:
            replacement_done = True
            os.replace(replacement, canonical)
        return payload

    monkeypatch.setattr(Path, "read_bytes", read_during_replacement)
    removed = prune_revision_roots(
        revisions_dir,
        canonical=canonical,
        max_roots=1,
        proc_root=tmp_path / "no-proc",
    )

    assert replacement_done
    assert roots[0].is_dir(), "the launcher observed before replacement stays protected"
    assert roots[5].is_dir(), "the newest replacement root stays protected"
    assert incomplete.is_dir(), "incomplete publications are never pruning candidates"
    assert symlink_root.is_symlink(), "symlink roots are never treated as publications"
    assert removed


def test_pruning_protects_an_invocation_that_crossed_launcher_activation(tmp_path):
    revisions_dir = tmp_path / "tools" / ".oompah-revisions"
    revisions_dir.mkdir(parents=True)
    roots = []
    for index in range(6):
        root = revisions_dir / f"{index:040x}-{index:032x}"
        root.mkdir()
        os.utime(root, (index + 1, index + 1))
        roots.append(root)

    ready = tmp_path / "invocation-ready"
    active_script = roots[0] / "active.py"
    active_script.write_text(
        "#!/usr/bin/python3\n"
        "from pathlib import Path\n"
        "import time\n"
        f"Path({str(ready)!r}).write_text('ready', encoding='utf-8')\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    active_script.chmod(0o755)
    canonical = tmp_path / "bin" / "oompah"
    canonical.parent.mkdir()
    canonical.write_text(f"#!/bin/sh\nexec '{active_script}'\n", encoding="utf-8")
    canonical.chmod(0o755)
    process = subprocess.Popen([str(canonical)])
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists()

        replacement = canonical.parent / ".candidate"
        replacement.write_text(f"#!/bin/sh\n# {roots[5]}\n", encoding="utf-8")
        replacement.chmod(0o755)
        os.replace(replacement, canonical)
        removed = prune_revision_roots(
            revisions_dir,
            canonical=canonical,
            max_roots=1,
        )

        assert roots[0].is_dir(), "the already-running old invocation must finish"
        assert roots[5].is_dir(), "the activated launcher root must remain"
        assert removed
    finally:
        process.terminate()
        process.wait(timeout=2)
