"""Integration tests for repository-map generation on state branches.

The tests use only local temporary Git repositories.  The checked-out source
repository and the state-branch checkout are deliberately separate so a map
writer cannot accidentally put index artifacts on a code branch.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from oompah.repo_map import (
    IndexedFile,
    RelationshipEdge,
    RenderingMetadata,
    RepoMap,
    SymbolTag,
    repo_map_path,
)
from oompah.repo_map_generator import (
    STATUS_FAILED,
    STATUS_FRESH,
    STATUS_GENERATED,
    STATUS_TIMEOUT,
    RepoMapGenerator,
)


IDENTITY = "https://example.test/acme/widget.git"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    )


def _map_for(sha: str) -> RepoMap:
    return RepoMap(
        schema_version=1,
        repo_identity=IDENTITY,
        commit_sha=sha,
        generator_version="test",
        indexed_files=[
            IndexedFile(
                path="app.py",
                language="python",
            )
        ],
        symbol_tags=[
            SymbolTag(kind="function", name="run", file_path="app.py", line=1)
        ],
        relationship_edges=[],
        generated_at="2026-07-21T15:00:00Z",
        rendering_metadata=RenderingMetadata(
            total_files=1, total_symbols=1, total_edges=0
        ),
    )


@pytest.fixture
def git_repositories(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return source checkout, separate state checkout, and bare remote."""
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )

    source = tmp_path / "source"
    _git(tmp_path, "clone", str(remote), str(source))
    _git(source, "checkout", "-b", "main")
    _git(source, "config", "user.name", "Test Agent")
    _git(source, "config", "user.email", "test@example.test")
    (source / "app.py").write_text("def run(): pass\n", encoding="utf-8")
    _git(source, "add", "app.py")
    _git(source, "commit", "-m", "source")
    _git(source, "push", "-u", "origin", "main")

    state_branch = "oompah/state/project-test"
    _git(source, "checkout", "--orphan", state_branch)
    _git(source, "rm", "-rf", ".")
    (source / ".oompah").mkdir()
    (source / ".oompah" / ".gitkeep").write_text("", encoding="utf-8")
    _git(source, "add", ".oompah")
    _git(source, "commit", "-m", "state bootstrap")
    _git(source, "push", "-u", "origin", state_branch)
    _git(source, "checkout", "main")

    state = tmp_path / "state"
    _git(tmp_path, "clone", "--branch", state_branch, str(remote), str(state))
    _git(state, "config", "user.name", "Test Agent")
    _git(state, "config", "user.email", "test@example.test")
    return source, state, remote


def _head(repo: Path, ref: str = "HEAD") -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _remote_file(remote: Path, branch: str, path: Path) -> str:
    return subprocess.run(
        ["git", "--git-dir", str(remote), "show", f"{branch}:{path.as_posix()}"],
        check=True, text=True, capture_output=True,
    ).stdout


def test_generation_pushes_complete_map_only_to_state_branch(
    git_repositories: tuple[Path, Path, Path],
) -> None:
    source, state, remote = git_repositories
    sha = _head(source)
    generator = RepoMapGenerator(state_branch_dir=state, repo_identity=IDENTITY)

    with patch(
        "oompah.repo_map_generator.index_repository", return_value=_map_for(sha)
    ) as index:
        result = generator.get_or_generate(source, sha)
    generator.shutdown()

    assert result.status == STATUS_GENERATED
    assert index.call_count == 1
    relative_path = repo_map_path(IDENTITY, sha)
    payload = json.loads(
        _remote_file(remote, "oompah/state/project-test", relative_path)
    )
    assert payload["commit_sha"] == sha
    main_tree = _git(source, "ls-tree", "-r", "--name-only", "main").stdout
    assert relative_path.as_posix() not in main_tree


def test_exact_sha_is_reused_but_new_sha_is_regenerated(
    git_repositories: tuple[Path, Path, Path],
) -> None:
    source, state, _ = git_repositories
    first_sha = _head(source)
    generator = RepoMapGenerator(state_branch_dir=state, repo_identity=IDENTITY)

    with patch(
        "oompah.repo_map_generator.index_repository",
        side_effect=lambda **kwargs: _map_for(kwargs["commit_sha"]),
    ) as index:
        first = generator.get_or_generate(source, first_sha)
        again = generator.get_or_generate(source, first_sha)
        (source / "app.py").write_text("def newer(): pass\n", encoding="utf-8")
        _git(source, "commit", "-am", "new source")
        second = generator.get_or_generate(source, _head(source))
    generator.shutdown()

    assert (first.status, again.status, second.status) == (
        STATUS_GENERATED,
        STATUS_FRESH,
        STATUS_GENERATED,
    )
    assert index.call_count == 2


def test_concurrent_same_sha_requests_share_one_background_index(
    git_repositories: tuple[Path, Path, Path],
) -> None:
    source, state, _ = git_repositories
    sha = _head(source)
    started = threading.Event()
    release = threading.Event()
    generator = RepoMapGenerator(state_branch_dir=state, repo_identity=IDENTITY)

    def index(**kwargs: object) -> RepoMap:
        started.set()
        assert release.wait(2)
        return _map_for(str(kwargs["commit_sha"]))

    with patch("oompah.repo_map_generator.index_repository", side_effect=index) as mock_index:
        threads = [
            threading.Thread(target=generator.get_or_generate, args=(source, sha))
            for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        assert started.wait(1)
        release.set()
        for thread in threads:
            thread.join(2)
    generator.shutdown()

    assert mock_index.call_count == 1


def test_retention_prunes_old_complete_artifacts_on_remote_state_branch(
    git_repositories: tuple[Path, Path, Path],
) -> None:
    source, state, remote = git_repositories
    first_sha = _head(source)
    generator = RepoMapGenerator(
        state_branch_dir=state, repo_identity=IDENTITY, max_retained=1
    )

    with patch(
        "oompah.repo_map_generator.index_repository",
        side_effect=lambda **kwargs: _map_for(kwargs["commit_sha"]),
    ):
        assert generator.get_or_generate(source, first_sha).status == STATUS_GENERATED
        (source / "app.py").write_text("def later(): pass\n", encoding="utf-8")
        _git(source, "commit", "-am", "later source")
        second_sha = _head(source)
        assert generator.get_or_generate(source, second_sha).status == STATUS_GENERATED
    generator.shutdown()

    tree = subprocess.run(
        [
            "git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only",
            "oompah/state/project-test", "--", ".oompah/repo-maps",
        ],
        check=True, text=True, capture_output=True,
    ).stdout.splitlines()
    assert tree == [repo_map_path(IDENTITY, second_sha).as_posix()]
    assert (
        json.loads(_remote_file(remote, "oompah/state/project-test", Path(tree[0])))[
            "commit_sha"
        ]
        == second_sha
    )


def test_failure_and_timeout_return_diagnostics_without_raising(
    git_repositories: tuple[Path, Path, Path],
) -> None:
    source, state, _ = git_repositories
    sha = _head(source)
    generator = RepoMapGenerator(
        state_branch_dir=state, repo_identity=IDENTITY, timeout_s=0.01
    )

    with patch(
        "oompah.repo_map_generator.index_repository", side_effect=OSError("unavailable")
    ):
        failure = generator.get_or_generate(source, sha)
    assert failure.status == STATUS_FAILED
    assert failure.repo_map is None
    assert "unavailable" in (failure.error or "")

    with patch(
        "oompah.repo_map_generator.index_repository",
        side_effect=lambda **_: (time.sleep(0.05), _map_for(sha))[1],
    ):
        timeout = generator.get_or_generate(source, sha)
    generator.shutdown()
    assert timeout.status == STATUS_TIMEOUT
    assert timeout.repo_map is None
    assert timeout.error
