"""End-to-end repository-map workflow regression tests.

These tests use a local managed-project-shaped checkout, its state-branch
checkout, and a bare remote.  They deliberately exercise the public generator
and prompt APIs together: no source checkout is used as a map artifact store.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from oompah.models import Issue
from oompah.prompt import render_prompt
from oompah.repo_map import (
    CURRENT_SCHEMA_VERSION,
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
from oompah.repo_map_prompt import build_repo_map_context


IDENTITY = "https://example.test/acme/managed-project.git"
STATE_BRANCH = "oompah/state/project-test"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    )


def _head(repo: Path, ref: str = "HEAD") -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _map_for(sha: str) -> RepoMap:
    return RepoMap(
        schema_version=CURRENT_SCHEMA_VERSION,
        repo_identity=IDENTITY,
        commit_sha=sha,
        generator_version="workflow-test",
        indexed_files=[IndexedFile(path="src/service.py", language="python")],
        symbol_tags=[
            SymbolTag(
                kind="function", name="dispatch_task", file_path="src/service.py", line=1
            )
        ],
        relationship_edges=[
            RelationshipEdge(kind="calls", source="dispatch_task", target="run")
        ],
        generated_at="2026-07-22T00:00:00Z",
        rendering_metadata=RenderingMetadata(total_files=1, total_symbols=1, total_edges=1),
    )


@pytest.fixture
def managed_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a source checkout and state checkout at the production path."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    source = tmp_path / "source"
    _git(tmp_path, "clone", str(remote), str(source))
    _git(source, "checkout", "-b", "main")
    _git(source, "config", "user.name", "Workflow Test")
    _git(source, "config", "user.email", "workflow@example.test")
    (source / "src").mkdir()
    # A sentinel ensures the generated prompt is tested as metadata-only rather
    # than a copy of repository source or credentials.
    (source / "src" / "service.py").write_text(
        "API_TOKEN = 'credential-must-not-leak'\n\ndef dispatch_task(): pass\n",
        encoding="utf-8",
    )
    _git(source, "add", "src/service.py")
    _git(source, "commit", "-m", "initial source")
    _git(source, "push", "-u", "origin", "main")
    _git(source, "branch", "release")
    _git(source, "push", "origin", "release")

    _git(source, "checkout", "--orphan", STATE_BRANCH)
    _git(source, "rm", "-rf", ".")
    (source / ".oompah").mkdir()
    (source / ".oompah" / ".gitkeep").write_text("", encoding="utf-8")
    _git(source, "add", ".oompah")
    _git(source, "commit", "-m", "state bootstrap")
    _git(source, "push", "-u", "origin", STATE_BRANCH)
    _git(source, "checkout", "main")

    common_dir = Path(_git(source, "rev-parse", "--git-common-dir").stdout.strip())
    if not common_dir.is_absolute():
        common_dir = (source / common_dir).resolve()
    state = common_dir / "oompah-state-worktrees" / STATE_BRANCH.replace("/", "__")
    state.parent.mkdir(parents=True)
    _git(source, "clone", "--branch", STATE_BRANCH, str(remote), str(state))
    _git(state, "config", "user.name", "Workflow Test")
    _git(state, "config", "user.email", "workflow@example.test")
    return source, state, remote


def _issue() -> Issue:
    return Issue(id="workflow-1", identifier="WORKFLOW-1", title="Fix dispatch_task", state="Open")


def _prompt_context(source: Path) -> str | None:
    context = build_repo_map_context(
        issue=_issue(),
        workspace_path=str(source),
        state_branch_name=STATE_BRANCH,
        repo_identity=IDENTITY,
    )
    return context.text if context else None


def test_managed_project_map_lifecycle_persists_only_to_state_branch_and_reaches_prompt(
    managed_project: tuple[Path, Path, Path],
) -> None:
    source, state, remote = managed_project
    main_before, release_before = _head(source, "main"), _head(source, "release")
    first_sha = _head(source)
    generator = RepoMapGenerator(state_branch_dir=state, repo_identity=IDENTITY)

    with patch(
        "oompah.repo_map_generator.index_repository",
        side_effect=lambda **kwargs: _map_for(kwargs["commit_sha"]),
    ) as index:
        first = generator.get_or_generate(source, first_sha)
        reused = generator.get_or_generate(source, first_sha)
        assert _prompt_context(source) is not None
        assert _head(source, "main") == main_before

        (source / "src" / "service.py").write_text("def dispatch_task(): return 'new'\n")
        _git(source, "commit", "-am", "source change")
        changed_sha = _head(source)
        changed_main_head = _head(source, "main")
        regenerated = generator.get_or_generate(source, changed_sha)
    generator.shutdown()

    assert (first.status, reused.status, regenerated.status) == (
        STATUS_GENERATED,
        STATUS_FRESH,
        STATUS_GENERATED,
    )
    assert reused.reused is True
    assert index.call_count == 2
    assert _head(source, "main") == changed_main_head
    assert _head(source, "release") == release_before
    assert _head(remote, "refs/heads/release") == release_before
    assert repo_map_path(IDENTITY, first_sha).as_posix() not in _git(
        source, "ls-tree", "-r", "--name-only", "release"
    ).stdout

    prompt_context = _prompt_context(source)
    assert prompt_context is not None
    prompt = render_prompt("Work on {{ issue.title }}", _issue(), repo_map_context=prompt_context)
    assert "dispatch_task" in prompt
    assert "credential-must-not-leak" not in prompt
    assert "API_TOKEN" not in prompt


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (SyntaxError("cannot parse source"), STATUS_FAILED),
        (OSError("state branch write failed"), STATUS_FAILED),
    ],
)
def test_index_or_state_write_failure_leaves_agent_prompt_runnable_without_map(
    managed_project: tuple[Path, Path, Path], failure: Exception, expected_status: str
) -> None:
    source, state, _ = managed_project
    generator = RepoMapGenerator(state_branch_dir=state, repo_identity=IDENTITY)
    target = "oompah.repo_map_generator.index_repository"
    kwargs = {"side_effect": failure}
    if isinstance(failure, OSError):
        target = "oompah.repo_map_generator.write_repo_map"
        kwargs = {"side_effect": failure}

    with patch(target, **kwargs):
        result = generator.get_or_generate(source, _head(source))
    generator.shutdown()

    assert result.status == expected_status
    assert result.repo_map is None
    assert _prompt_context(source) is None
    assert render_prompt("Work on {{ issue.title }}", _issue(), repo_map_context=None) == "Work on Fix dispatch_task"


def test_index_timeout_leaves_agent_prompt_runnable_without_map(
    managed_project: tuple[Path, Path, Path],
) -> None:
    source, state, _ = managed_project
    generator = RepoMapGenerator(state_branch_dir=state, repo_identity=IDENTITY, timeout_s=0.01)
    with patch(
        "oompah.repo_map_generator.index_repository",
        side_effect=lambda **_: (time.sleep(0.05), _map_for(_head(source)))[1],
    ):
        result = generator.get_or_generate(source, _head(source))
        # Check the dispatch-time contract before the timed-out background
        # worker is allowed to finish and persist a later artifact.
        assert result.status == STATUS_TIMEOUT
        assert result.repo_map is None
        assert _prompt_context(source) is None
        assert render_prompt("Agent startup", _issue(), repo_map_context=None) == "Agent startup"
    generator.shutdown()
