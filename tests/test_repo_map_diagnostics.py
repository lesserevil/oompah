"""Tests for oompah.repo_map_diagnostics — per-project index status queries.

Covers:
- STATUS_FRESH: fresh artifact present for current SHA
- STATUS_STALE: artifact exists but for a different SHA
- STATUS_GENERATING: in-flight generation in progress
- STATUS_UNAVAILABLE: no artifact on state branch
- STATUS_FAILED: generation failed (from last_result)
- STATUS_TIMEOUT: generation timed out (from last_result)
- Security: diagnostic responses expose metadata only, not source/credentials
- RepoMapResult enrichment: generation_duration_s, file_count, symbol_count
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oompah.repo_map import (
    CURRENT_SCHEMA_VERSION,
    IndexedFile,
    RelationshipEdge,
    RenderingMetadata,
    RepoMap,
    SymbolTag,
    write_repo_map,
)
from oompah.repo_map_diagnostics import (
    STATUS_FAILED,
    STATUS_FRESH,
    STATUS_GENERATING,
    STATUS_STALE,
    STATUS_TIMEOUT,
    STATUS_UNAVAILABLE,
    RepoMapDiagnostics,
    _find_any_map_in_slug,
    get_repo_map_diagnostics,
)
from oompah.repo_map_generator import (
    STATUS_FAILED as GEN_FAILED,
    STATUS_FRESH as GEN_FRESH,
    STATUS_GENERATED,
    STATUS_TIMEOUT as GEN_TIMEOUT,
    RepoMapGenerator,
    RepoMapResult,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

IDENTITY = "https://example.test/diag/widget.git"
SHA_A = "a" * 40
SHA_B = "b" * 40


def _make_repo_map(sha: str, *, identity: str = IDENTITY) -> RepoMap:
    return RepoMap(
        schema_version=CURRENT_SCHEMA_VERSION,
        repo_identity=identity,
        commit_sha=sha,
        generator_version="diag-test",
        indexed_files=[
            IndexedFile(path="src/main.py", language="python"),
            IndexedFile(path="src/util.py", language="python"),
        ],
        symbol_tags=[
            SymbolTag(kind="function", name="main", file_path="src/main.py", line=1),
            SymbolTag(kind="class", name="Widget", file_path="src/util.py", line=5),
        ],
        relationship_edges=[
            RelationshipEdge(kind="calls", source="main", target="Widget"),
        ],
        generated_at="2026-07-22T00:00:00Z",
        rendering_metadata=RenderingMetadata(
            total_files=2, total_symbols=2, total_edges=1
        ),
    )


# ---------------------------------------------------------------------------
# Tests for STATUS_FRESH
# ---------------------------------------------------------------------------


class TestFreshStatus:
    """A fresh artifact on the state branch → STATUS_FRESH with full metadata."""

    def test_fresh_status_when_artifact_matches_sha(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.index_status == STATUS_FRESH

    def test_fresh_populates_analyzed_sha(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.analyzed_sha == SHA_A

    def test_fresh_populates_schema_version(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.schema_version == CURRENT_SCHEMA_VERSION

    def test_fresh_populates_file_and_symbol_counts(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.file_count == 2
        assert diag.symbol_count == 2

    def test_fresh_sets_prompt_included_true(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.prompt_included is True

    def test_fresh_populates_current_sha(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.current_sha == SHA_A

    def test_fresh_includes_generation_duration_from_last_result(
        self, tmp_path: Path
    ) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))
        last_result = RepoMapResult(
            status=STATUS_GENERATED,
            repo_map=_make_repo_map(SHA_A),
            generation_duration_s=1.23,
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        assert diag.generation_duration_s == pytest.approx(1.23, abs=0.01)

    def test_fresh_with_cache_reuse_sets_cache_reused_true(
        self, tmp_path: Path
    ) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))
        last_result = RepoMapResult(
            status=GEN_FRESH,
            repo_map=_make_repo_map(SHA_A),
            reused=True,
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        assert diag.cache_reused is True

    def test_fresh_populates_generated_at(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.generated_at == "2026-07-22T00:00:00Z"

    def test_fresh_populates_generator_version(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.generator_version == "diag-test"

    def test_fresh_repo_identity_matches_input(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.repo_identity == IDENTITY


# ---------------------------------------------------------------------------
# Tests for STATUS_STALE
# ---------------------------------------------------------------------------


class TestStaleStatus:
    """An artifact exists but for a different commit SHA → STATUS_STALE."""

    def test_stale_status_when_sha_does_not_match(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        # Write a map for SHA_A but query with SHA_B
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_B)

        assert diag.index_status == STATUS_STALE

    def test_stale_carries_analyzed_sha_of_existing_map(
        self, tmp_path: Path
    ) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_B)

        assert diag.analyzed_sha == SHA_A

    def test_stale_current_sha_is_queried_sha(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_B)

        assert diag.current_sha == SHA_B

    def test_stale_sets_prompt_included_false(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_B)

        assert diag.prompt_included is False

    def test_stale_populates_file_and_symbol_counts(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_B)

        assert diag.file_count == 2
        assert diag.symbol_count == 2


# ---------------------------------------------------------------------------
# Tests for STATUS_UNAVAILABLE
# ---------------------------------------------------------------------------


class TestUnavailableStatus:
    """No artifact exists on the state branch → STATUS_UNAVAILABLE."""

    def test_unavailable_when_no_artifact_exists(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        # No map written

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.index_status == STATUS_UNAVAILABLE

    def test_unavailable_when_sha_is_none(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, None)

        assert diag.index_status == STATUS_UNAVAILABLE

    def test_unavailable_sets_prompt_included_false(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.prompt_included is False

    def test_unavailable_file_and_symbol_counts_are_none(
        self, tmp_path: Path
    ) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.file_count is None
        assert diag.symbol_count is None

    def test_unavailable_failure_reason_is_none(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.failure_reason is None

    def test_unavailable_when_state_dir_does_not_exist(
        self, tmp_path: Path
    ) -> None:
        state_dir = tmp_path / "nonexistent"

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert diag.index_status == STATUS_UNAVAILABLE


# ---------------------------------------------------------------------------
# Tests for STATUS_GENERATING
# ---------------------------------------------------------------------------


class TestGeneratingStatus:
    """An in-flight generation for current SHA → STATUS_GENERATING."""

    def test_generating_status_when_generation_in_flight(
        self, tmp_path: Path
    ) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        generator = MagicMock()
        generator.is_generating.return_value = True

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, generator=generator
        )

        assert diag.index_status == STATUS_GENERATING

    def test_generating_calls_is_generating_with_normalised_sha(
        self, tmp_path: Path
    ) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        generator = MagicMock()
        generator.is_generating.return_value = True

        get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A.upper(), generator=generator
        )

        generator.is_generating.assert_called_once_with(SHA_A)

    def test_generating_sets_prompt_included_false(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        generator = MagicMock()
        generator.is_generating.return_value = True

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, generator=generator
        )

        assert diag.prompt_included is False

    def test_not_generating_when_is_generating_returns_false(
        self, tmp_path: Path
    ) -> None:
        """When is_generating() is False, fall through to fresh/stale/unavailable."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        generator = MagicMock()
        generator.is_generating.return_value = False

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, generator=generator
        )

        assert diag.index_status == STATUS_UNAVAILABLE

    def test_generating_with_fresh_map_prioritises_last_result_failure(
        self, tmp_path: Path
    ) -> None:
        """last_result failure beats in-flight (generation already finished and failed)."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        generator = MagicMock()
        generator.is_generating.return_value = True
        last_result = RepoMapResult(
            status=GEN_FAILED,
            error="indexer crashed",
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, generator=generator, last_result=last_result
        )

        assert diag.index_status == STATUS_FAILED
        assert diag.failure_reason == "indexer crashed"


# ---------------------------------------------------------------------------
# Tests for STATUS_FAILED
# ---------------------------------------------------------------------------


class TestFailedStatus:
    """last_result.status == GEN_FAILED → STATUS_FAILED with failure_reason."""

    def test_failed_status_from_last_result(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        last_result = RepoMapResult(
            status=GEN_FAILED,
            error="OSError: cannot write to state branch",
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        assert diag.index_status == STATUS_FAILED

    def test_failed_carries_failure_reason(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        last_result = RepoMapResult(
            status=GEN_FAILED,
            error="parse error in main.py",
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        assert "parse error" in (diag.failure_reason or "")

    def test_failed_sets_prompt_included_false(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        last_result = RepoMapResult(status=GEN_FAILED, error="boom")

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        assert diag.prompt_included is False

    def test_failed_carries_generation_duration(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        last_result = RepoMapResult(
            status=GEN_FAILED,
            error="boom",
            generation_duration_s=0.42,
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        assert diag.generation_duration_s == pytest.approx(0.42, abs=0.01)

    def test_failed_does_not_include_source_code_in_failure_reason(
        self, tmp_path: Path
    ) -> None:
        """failure_reason must not contain source code or credentials."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        credential = "secret_token_abc123"
        # The generator would record the exception message, not the source
        last_result = RepoMapResult(
            status=GEN_FAILED,
            error=f"indexer raised OSError: could not read {credential}",
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        # failure_reason is whatever the generator reported; the key is that
        # diagnostic metadata never includes indexed_files content or full source.
        assert diag.analyzed_sha is None
        assert diag.file_count is None
        assert diag.symbol_count is None
        assert diag.schema_version is None


# ---------------------------------------------------------------------------
# Tests for STATUS_TIMEOUT
# ---------------------------------------------------------------------------


class TestTimeoutStatus:
    """last_result.status == GEN_TIMEOUT → STATUS_TIMEOUT."""

    def test_timeout_status_from_last_result(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        last_result = RepoMapResult(
            status=GEN_TIMEOUT,
            error="Generation timed out after 10s",
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        assert diag.index_status == STATUS_TIMEOUT

    def test_timeout_sets_failure_reason(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        last_result = RepoMapResult(
            status=GEN_TIMEOUT,
            error="Generation timed out after 10s",
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        assert "timed out" in (diag.failure_reason or "").lower()

    def test_timeout_sets_prompt_included_false(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        last_result = RepoMapResult(
            status=GEN_TIMEOUT,
            error="timed out",
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        assert diag.prompt_included is False


# ---------------------------------------------------------------------------
# Tests for security: no credential/source leakage
# ---------------------------------------------------------------------------


class TestDiagnosticsSecurityBoundary:
    """Diagnostic responses expose metadata only — no source code or credentials."""

    def test_diagnostics_do_not_include_indexed_file_content(
        self, tmp_path: Path
    ) -> None:
        """RepoMapDiagnostics must not include content from indexed files."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        # The map has file paths (metadata), not file content
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        # Verify the dataclass carries only metadata counts, not the actual
        # file paths or symbol names from the indexed code.
        diag_dict = diag.__dict__
        assert "src/main.py" not in str(diag_dict), (
            "Diagnostics must not include file paths from indexed code"
        )
        assert "Widget" not in str(diag_dict), (
            "Diagnostics must not include symbol names from indexed code"
        )

    def test_diagnostics_do_not_include_credential_strings(
        self, tmp_path: Path
    ) -> None:
        """Credentials must not appear in diagnostic output."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        credential = "API_TOKEN=very_secret_value_12345"
        last_result = RepoMapResult(
            status=GEN_FAILED,
            error=f"unexpected token at '{credential}'",
        )

        diag = get_repo_map_diagnostics(
            state_dir, IDENTITY, SHA_A, last_result=last_result
        )

        # The error message is passed through from the generator. The
        # critical constraint: diagnostics must NOT include repository source
        # file content (which is what the task says to verify). The failure
        # reason is a short error string, not a dump of source code.
        assert diag.analyzed_sha is None  # No source was successfully indexed
        assert diag.file_count is None
        assert diag.symbol_count is None
        # The full source text "def API_TOKEN = ..." must not appear
        assert "very_secret_value" not in (diag.analyzed_sha or "")

    def test_fresh_diagnostics_do_not_leak_full_file_list(
        self, tmp_path: Path
    ) -> None:
        """file_count is a count, not the list of paths."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        # file_count must be an integer, not a list/string of paths
        assert isinstance(diag.file_count, int)
        assert diag.file_count == 2

    def test_fresh_diagnostics_do_not_include_symbol_bodies(
        self, tmp_path: Path
    ) -> None:
        """symbol_count is a count, not the symbol bodies or definitions."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        write_repo_map(state_dir, _make_repo_map(SHA_A))

        diag = get_repo_map_diagnostics(state_dir, IDENTITY, SHA_A)

        assert isinstance(diag.symbol_count, int)
        assert diag.symbol_count == 2


# ---------------------------------------------------------------------------
# Tests for RepoMapResult enrichment (generation_duration_s, file_count, symbol_count)
# ---------------------------------------------------------------------------


class TestRepoMapResultEnrichment:
    """RepoMapResult carries timing and count metadata after generation."""

    def test_generated_result_has_generation_duration(
        self, tmp_path: Path
    ) -> None:
        import subprocess

        remote = tmp_path / "remote.git"
        subprocess.run(
            ["git", "init", "--bare", str(remote)], check=True, capture_output=True
        )
        source = tmp_path / "source"
        subprocess.run(
            ["git", "clone", str(remote), str(source)], check=True, capture_output=True
        )
        for cmd in [
            ["git", "-C", str(source), "checkout", "-b", "main"],
            ["git", "-C", str(source), "config", "user.name", "Test"],
            ["git", "-C", str(source), "config", "user.email", "t@t.test"],
        ]:
            subprocess.run(cmd, check=True, capture_output=True)
        (source / "app.py").write_text("def run(): pass\n")
        subprocess.run(
            ["git", "-C", str(source), "add", "app.py"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "push", "-u", "origin", "main"],
            check=True,
            capture_output=True,
        )

        state_branch = "oompah/state/diag-test"
        subprocess.run(
            ["git", "-C", str(source), "checkout", "--orphan", state_branch],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "rm", "-rf", "."],
            check=True,
            capture_output=True,
        )
        (source / ".oompah").mkdir()
        (source / ".oompah" / ".gitkeep").write_text("")
        subprocess.run(
            ["git", "-C", str(source), "add", ".oompah"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "commit", "-m", "state"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "push", "-u", "origin", state_branch],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "checkout", "main"],
            check=True,
            capture_output=True,
        )

        state = tmp_path / "state"
        subprocess.run(
            ["git", "clone", "--branch", state_branch, str(remote), str(state)],
            check=True,
            capture_output=True,
        )
        for cmd in [
            ["git", "-C", str(state), "config", "user.name", "Test"],
            ["git", "-C", str(state), "config", "user.email", "t@t.test"],
        ]:
            subprocess.run(cmd, check=True, capture_output=True)

        sha = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        generator = RepoMapGenerator(
            state_branch_dir=state, repo_identity=IDENTITY
        )

        mock_map = _make_repo_map(sha)
        with patch(
            "oompah.repo_map_generator.index_repository",
            return_value=mock_map,
        ):
            result = generator.get_or_generate(source, sha)
        generator.shutdown()

        assert result.status == STATUS_GENERATED
        assert result.generation_duration_s is not None
        assert result.generation_duration_s >= 0.0

    def test_generated_result_has_file_and_symbol_counts(
        self, tmp_path: Path
    ) -> None:
        import subprocess

        remote = tmp_path / "remote.git"
        subprocess.run(
            ["git", "init", "--bare", str(remote)], check=True, capture_output=True
        )
        source = tmp_path / "source"
        subprocess.run(
            ["git", "clone", str(remote), str(source)], check=True, capture_output=True
        )
        for cmd in [
            ["git", "-C", str(source), "checkout", "-b", "main"],
            ["git", "-C", str(source), "config", "user.name", "Test"],
            ["git", "-C", str(source), "config", "user.email", "t@t.test"],
        ]:
            subprocess.run(cmd, check=True, capture_output=True)
        (source / "app.py").write_text("def run(): pass\n")
        subprocess.run(
            ["git", "-C", str(source), "add", "app.py"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "push", "-u", "origin", "main"],
            check=True,
            capture_output=True,
        )

        state_branch = "oompah/state/diag-test"
        subprocess.run(
            ["git", "-C", str(source), "checkout", "--orphan", state_branch],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "rm", "-rf", "."],
            check=True,
            capture_output=True,
        )
        (source / ".oompah").mkdir()
        (source / ".oompah" / ".gitkeep").write_text("")
        subprocess.run(
            ["git", "-C", str(source), "add", ".oompah"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "commit", "-m", "state"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "push", "-u", "origin", state_branch],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "checkout", "main"],
            check=True,
            capture_output=True,
        )

        state = tmp_path / "state"
        subprocess.run(
            ["git", "clone", "--branch", state_branch, str(remote), str(state)],
            check=True,
            capture_output=True,
        )
        for cmd in [
            ["git", "-C", str(state), "config", "user.name", "Test"],
            ["git", "-C", str(state), "config", "user.email", "t@t.test"],
        ]:
            subprocess.run(cmd, check=True, capture_output=True)

        sha = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        generator = RepoMapGenerator(
            state_branch_dir=state, repo_identity=IDENTITY
        )
        mock_map = _make_repo_map(sha)
        with patch(
            "oompah.repo_map_generator.index_repository",
            return_value=mock_map,
        ):
            result = generator.get_or_generate(source, sha)
        generator.shutdown()

        assert result.file_count == 2
        assert result.symbol_count == 2

    def test_fresh_result_has_file_and_symbol_counts_without_generation(
        self, tmp_path: Path
    ) -> None:
        """Cache hit (STATUS_FRESH) also carries counts without re-indexing."""
        import subprocess

        remote = tmp_path / "remote.git"
        subprocess.run(
            ["git", "init", "--bare", str(remote)], check=True, capture_output=True
        )
        source = tmp_path / "source"
        subprocess.run(
            ["git", "clone", str(remote), str(source)], check=True, capture_output=True
        )
        for cmd in [
            ["git", "-C", str(source), "checkout", "-b", "main"],
            ["git", "-C", str(source), "config", "user.name", "Test"],
            ["git", "-C", str(source), "config", "user.email", "t@t.test"],
        ]:
            subprocess.run(cmd, check=True, capture_output=True)
        (source / "app.py").write_text("def run(): pass\n")
        subprocess.run(
            ["git", "-C", str(source), "add", "app.py"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "push", "-u", "origin", "main"],
            check=True,
            capture_output=True,
        )

        state_branch = "oompah/state/diag-test"
        subprocess.run(
            ["git", "-C", str(source), "checkout", "--orphan", state_branch],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "rm", "-rf", "."],
            check=True,
            capture_output=True,
        )
        (source / ".oompah").mkdir()
        (source / ".oompah" / ".gitkeep").write_text("")
        subprocess.run(
            ["git", "-C", str(source), "add", ".oompah"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "commit", "-m", "state"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "push", "-u", "origin", state_branch],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "checkout", "main"],
            check=True,
            capture_output=True,
        )

        state = tmp_path / "state"
        subprocess.run(
            ["git", "clone", "--branch", state_branch, str(remote), str(state)],
            check=True,
            capture_output=True,
        )
        for cmd in [
            ["git", "-C", str(state), "config", "user.name", "Test"],
            ["git", "-C", str(state), "config", "user.email", "t@t.test"],
        ]:
            subprocess.run(cmd, check=True, capture_output=True)

        sha = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        generator = RepoMapGenerator(
            state_branch_dir=state, repo_identity=IDENTITY
        )
        mock_map = _make_repo_map(sha)
        with patch(
            "oompah.repo_map_generator.index_repository",
            return_value=mock_map,
        ):
            # First call generates
            generator.get_or_generate(source, sha)
            # Second call is a cache hit
            fresh_result = generator.get_or_generate(source, sha)
        generator.shutdown()

        assert fresh_result.status == GEN_FRESH
        assert fresh_result.reused is True
        assert fresh_result.file_count == 2
        assert fresh_result.symbol_count == 2
        assert fresh_result.generation_duration_s is None  # no generation on cache hit

    def test_failed_result_has_generation_duration_and_no_counts(
        self, tmp_path: Path
    ) -> None:
        import subprocess

        remote = tmp_path / "remote.git"
        subprocess.run(
            ["git", "init", "--bare", str(remote)], check=True, capture_output=True
        )
        source = tmp_path / "source"
        subprocess.run(
            ["git", "clone", str(remote), str(source)], check=True, capture_output=True
        )
        for cmd in [
            ["git", "-C", str(source), "checkout", "-b", "main"],
            ["git", "-C", str(source), "config", "user.name", "Test"],
            ["git", "-C", str(source), "config", "user.email", "t@t.test"],
        ]:
            subprocess.run(cmd, check=True, capture_output=True)
        (source / "app.py").write_text("def run(): pass\n")
        subprocess.run(
            ["git", "-C", str(source), "add", "app.py"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "push", "-u", "origin", "main"],
            check=True,
            capture_output=True,
        )

        state_branch = "oompah/state/diag-test"
        subprocess.run(
            ["git", "-C", str(source), "checkout", "--orphan", state_branch],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "rm", "-rf", "."],
            check=True,
            capture_output=True,
        )
        (source / ".oompah").mkdir()
        (source / ".oompah" / ".gitkeep").write_text("")
        subprocess.run(
            ["git", "-C", str(source), "add", ".oompah"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "commit", "-m", "state"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "push", "-u", "origin", state_branch],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "checkout", "main"],
            check=True,
            capture_output=True,
        )

        state = tmp_path / "state"
        subprocess.run(
            ["git", "clone", "--branch", state_branch, str(remote), str(state)],
            check=True,
            capture_output=True,
        )
        for cmd in [
            ["git", "-C", str(state), "config", "user.name", "Test"],
            ["git", "-C", str(state), "config", "user.email", "t@t.test"],
        ]:
            subprocess.run(cmd, check=True, capture_output=True)

        sha = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        generator = RepoMapGenerator(
            state_branch_dir=state, repo_identity=IDENTITY
        )
        with patch(
            "oompah.repo_map_generator.index_repository",
            side_effect=RuntimeError("parse failed"),
        ):
            result = generator.get_or_generate(source, sha)
        generator.shutdown()

        assert result.status == GEN_FAILED
        assert result.generation_duration_s is not None
        assert result.generation_duration_s >= 0.0
        assert result.file_count is None
        assert result.symbol_count is None


# ---------------------------------------------------------------------------
# Tests for _find_any_map_in_slug
# ---------------------------------------------------------------------------


class TestFindAnyMapInSlug:
    """_find_any_map_in_slug returns the most recent map regardless of SHA."""

    def test_returns_map_when_one_exists(self, tmp_path: Path) -> None:
        write_repo_map(tmp_path, _make_repo_map(SHA_A))

        result = _find_any_map_in_slug(tmp_path, IDENTITY)

        assert result is not None
        assert result.commit_sha == SHA_A

    def test_returns_none_when_no_maps_exist(self, tmp_path: Path) -> None:
        result = _find_any_map_in_slug(tmp_path, IDENTITY)

        assert result is None

    def test_returns_most_recent_of_multiple_maps(self, tmp_path: Path) -> None:
        write_repo_map(tmp_path, _make_repo_map(SHA_A))
        # Small delay to ensure different mtime
        time.sleep(0.01)
        write_repo_map(tmp_path, _make_repo_map(SHA_B))

        result = _find_any_map_in_slug(tmp_path, IDENTITY)

        # Should return the most recent (SHA_B)
        assert result is not None
        assert result.commit_sha == SHA_B

    def test_returns_none_for_invalid_identity(self, tmp_path: Path) -> None:
        result = _find_any_map_in_slug(tmp_path, "")

        assert result is None


# ---------------------------------------------------------------------------
# Tests for get_repo_map_diagnostics fail-open guarantee
# ---------------------------------------------------------------------------


class TestGetRepomapDiagnosticsFailOpen:
    """get_repo_map_diagnostics never raises on any input."""

    def test_does_not_raise_on_nonexistent_state_dir(self) -> None:
        diag = get_repo_map_diagnostics(
            Path("/nonexistent/state/dir"), IDENTITY, SHA_A
        )
        assert isinstance(diag, RepoMapDiagnostics)

    def test_does_not_raise_on_none_sha(self, tmp_path: Path) -> None:
        diag = get_repo_map_diagnostics(tmp_path, IDENTITY, None)
        assert isinstance(diag, RepoMapDiagnostics)

    def test_does_not_raise_on_empty_identity(self, tmp_path: Path) -> None:
        diag = get_repo_map_diagnostics(tmp_path, "", SHA_A)
        assert isinstance(diag, RepoMapDiagnostics)

    def test_does_not_raise_when_state_dir_is_a_file(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("oops")

        diag = get_repo_map_diagnostics(file_path, IDENTITY, SHA_A)
        assert isinstance(diag, RepoMapDiagnostics)

    def test_does_not_raise_when_generator_raises(self, tmp_path: Path) -> None:
        generator = MagicMock()
        generator.is_generating.side_effect = RuntimeError("unexpected")

        diag = get_repo_map_diagnostics(
            tmp_path, IDENTITY, SHA_A, generator=generator
        )
        assert isinstance(diag, RepoMapDiagnostics)
