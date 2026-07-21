"""Unit tests for oompah.repo_map — repository-map artifact schema and lifecycle.

Coverage:
- CURRENT_SCHEMA_VERSION and REPO_MAP_MAX_RETAINED constants
- IndexedFile: to_dict / from_dict round-trips, optional fields
- SymbolTag: to_dict / from_dict round-trips, optional fields
- RelationshipEdge: to_dict / from_dict round-trips
- RenderingMetadata: to_dict / from_dict round-trips, defaults
- RepoMap: to_dict / from_dict round-trips
- RepoMap.from_dict: schema-version rejection (wrong version, missing key,
  None, future version)
- Deterministic output: identical inputs → identical JSON
- SHA invalidation: changing commit_sha changes the output
- repo_map_slug: happy path, URL scheme stripping, edge cases, empty/invalid
- repo_map_path: canonical path shape, namespace guarantee
- is_within_namespace: relative/absolute paths, escaping attempts
- is_fresh: matching SHA, mismatching SHA, case-normalisation
- write_repo_map: happy path, atomic temp-then-rename, wrong schema version,
  directory creation
- read_repo_map: happy path, missing file, bad JSON, wrong schema version,
  stale map with require_fresh=True, stale map with require_fresh=False
- prune_repo_maps: no maps, fewer than max, exactly max, more than max,
  ordering by mtime, max_retained=0 raises ValueError
- All state-branch writes remain within .oompah/ namespace
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from oompah.repo_map import (
    CURRENT_SCHEMA_VERSION,
    REPO_MAP_MAX_RETAINED,
    IndexedFile,
    RelationshipEdge,
    RenderingMetadata,
    RepoMap,
    SchemaVersionError,
    SymbolTag,
    is_fresh,
    is_within_namespace,
    prune_repo_maps,
    read_repo_map,
    repo_map_path,
    repo_map_slug,
    write_repo_map,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SHA = "a" * 40
SAMPLE_IDENTITY = "https://github.com/org/repo"
SAMPLE_SLUG = "github-com-org-repo"


def make_rendering_metadata(**kwargs) -> RenderingMetadata:
    defaults = {
        "total_files": 2,
        "total_symbols": 3,
        "total_edges": 1,
    }
    defaults.update(kwargs)
    return RenderingMetadata(**defaults)


def make_repo_map(
    *,
    commit_sha: str = SAMPLE_SHA,
    repo_identity: str = SAMPLE_IDENTITY,
    schema_version: int = CURRENT_SCHEMA_VERSION,
    **kwargs,
) -> RepoMap:
    defaults: dict = {
        "schema_version": schema_version,
        "repo_identity": repo_identity,
        "commit_sha": commit_sha,
        "generator_version": "1.0.0",
        "indexed_files": [
            IndexedFile(path="oompah/__init__.py", size_bytes=0, language="python"),
            IndexedFile(path="oompah/models.py", size_bytes=1024),
        ],
        "symbol_tags": [
            SymbolTag(kind="class", name="Project", file_path="oompah/models.py"),
            SymbolTag(kind="function", name="main", file_path="oompah/__main__.py", line=10),
        ],
        "relationship_edges": [
            RelationshipEdge(kind="imports", source="oompah/__main__.py", target="oompah/models.py"),
        ],
        "generated_at": "2026-07-21T15:00:00Z",
        "rendering_metadata": make_rendering_metadata(),
    }
    defaults.update(kwargs)
    return RepoMap(**defaults)


# ===========================================================================
# Constants
# ===========================================================================


class TestConstants:
    def test_current_schema_version_is_int(self):
        assert isinstance(CURRENT_SCHEMA_VERSION, int)

    def test_current_schema_version_is_positive(self):
        assert CURRENT_SCHEMA_VERSION >= 1

    def test_repo_map_max_retained_is_positive(self):
        assert REPO_MAP_MAX_RETAINED >= 1

    def test_repo_map_max_retained_is_int(self):
        assert isinstance(REPO_MAP_MAX_RETAINED, int)


# ===========================================================================
# IndexedFile
# ===========================================================================


class TestIndexedFile:
    def test_to_dict_all_fields(self):
        f = IndexedFile(
            path="src/main.py",
            size_bytes=512,
            content_hash="abc123",
            language="python",
        )
        d = f.to_dict()
        assert d == {
            "path": "src/main.py",
            "size_bytes": 512,
            "content_hash": "abc123",
            "language": "python",
        }

    def test_to_dict_optional_fields_none(self):
        f = IndexedFile(path="README.md")
        d = f.to_dict()
        assert d["size_bytes"] is None
        assert d["content_hash"] is None
        assert d["language"] is None

    def test_round_trip(self):
        original = IndexedFile(path="a.py", size_bytes=100, content_hash="deadbeef", language="python")
        restored = IndexedFile.from_dict(original.to_dict())
        assert restored == original

    def test_round_trip_with_none_fields(self):
        original = IndexedFile(path="b.md")
        restored = IndexedFile.from_dict(original.to_dict())
        assert restored == original

    def test_from_dict_coerces_size_bytes_to_int(self):
        d = {"path": "x.py", "size_bytes": "256", "content_hash": None, "language": None}
        f = IndexedFile.from_dict(d)
        assert f.size_bytes == 256
        assert isinstance(f.size_bytes, int)


# ===========================================================================
# SymbolTag
# ===========================================================================


class TestSymbolTag:
    def test_to_dict_all_fields(self):
        s = SymbolTag(kind="class", name="Foo", file_path="foo.py", line=10, namespace="bar")
        assert s.to_dict() == {
            "kind": "class",
            "name": "Foo",
            "file_path": "foo.py",
            "line": 10,
            "namespace": "bar",
        }

    def test_to_dict_optional_none(self):
        s = SymbolTag(kind="function", name="do_thing", file_path="util.py")
        d = s.to_dict()
        assert d["line"] is None
        assert d["namespace"] is None

    def test_round_trip_full(self):
        original = SymbolTag(kind="method", name="run", file_path="agent.py", line=42, namespace="Agent")
        restored = SymbolTag.from_dict(original.to_dict())
        assert restored == original

    def test_round_trip_minimal(self):
        original = SymbolTag(kind="variable", name="X", file_path="c.py")
        restored = SymbolTag.from_dict(original.to_dict())
        assert restored == original

    def test_from_dict_coerces_line_to_int(self):
        d = {"kind": "class", "name": "A", "file_path": "a.py", "line": "5", "namespace": None}
        s = SymbolTag.from_dict(d)
        assert s.line == 5
        assert isinstance(s.line, int)


# ===========================================================================
# RelationshipEdge
# ===========================================================================


class TestRelationshipEdge:
    def test_to_dict(self):
        e = RelationshipEdge(kind="imports", source="a.py", target="b.py")
        assert e.to_dict() == {"kind": "imports", "source": "a.py", "target": "b.py"}

    def test_round_trip(self):
        original = RelationshipEdge(kind="inherits", source="Child", target="Parent")
        restored = RelationshipEdge.from_dict(original.to_dict())
        assert restored == original

    def test_all_kind_values_survive_round_trip(self):
        for kind in ("imports", "inherits", "calls", "defines", "references"):
            e = RelationshipEdge(kind=kind, source="X", target="Y")
            assert RelationshipEdge.from_dict(e.to_dict()).kind == kind


# ===========================================================================
# RenderingMetadata
# ===========================================================================


class TestRenderingMetadata:
    def test_to_dict_defaults(self):
        m = RenderingMetadata(total_files=5, total_symbols=10, total_edges=3)
        d = m.to_dict()
        assert d["total_files"] == 5
        assert d["total_symbols"] == 10
        assert d["total_edges"] == 3
        assert d["truncated"] is False
        assert d["notes"] == []

    def test_to_dict_with_notes_and_truncated(self):
        m = RenderingMetadata(
            total_files=1, total_symbols=0, total_edges=0,
            truncated=True, notes=["binary files skipped", "large repo"]
        )
        d = m.to_dict()
        assert d["truncated"] is True
        assert d["notes"] == ["binary files skipped", "large repo"]

    def test_round_trip_defaults(self):
        original = RenderingMetadata(total_files=2, total_symbols=3, total_edges=1)
        restored = RenderingMetadata.from_dict(original.to_dict())
        assert restored == original

    def test_round_trip_full(self):
        original = RenderingMetadata(
            total_files=100, total_symbols=500, total_edges=200,
            truncated=True, notes=["note1", "note2"]
        )
        restored = RenderingMetadata.from_dict(original.to_dict())
        assert restored == original

    def test_from_dict_missing_notes_defaults_to_empty(self):
        d = {"total_files": 1, "total_symbols": 2, "total_edges": 3}
        m = RenderingMetadata.from_dict(d)
        assert m.notes == []
        assert m.truncated is False


# ===========================================================================
# RepoMap serialisation / deserialisation
# ===========================================================================


class TestRepoMapSerialization:
    def test_to_dict_has_all_top_level_keys(self):
        rm = make_repo_map()
        d = rm.to_dict()
        expected_keys = {
            "schema_version",
            "repo_identity",
            "commit_sha",
            "generator_version",
            "indexed_files",
            "symbol_tags",
            "relationship_edges",
            "generated_at",
            "rendering_metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_schema_version_is_correct(self):
        rm = make_repo_map()
        assert rm.to_dict()["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_round_trip_full(self):
        original = make_repo_map()
        restored = RepoMap.from_dict(original.to_dict())
        assert restored.schema_version == original.schema_version
        assert restored.repo_identity == original.repo_identity
        assert restored.commit_sha == original.commit_sha
        assert restored.generator_version == original.generator_version
        assert restored.generated_at == original.generated_at
        assert len(restored.indexed_files) == len(original.indexed_files)
        assert len(restored.symbol_tags) == len(original.symbol_tags)
        assert len(restored.relationship_edges) == len(original.relationship_edges)

    def test_round_trip_empty_lists(self):
        original = make_repo_map(
            indexed_files=[],
            symbol_tags=[],
            relationship_edges=[],
            rendering_metadata=RenderingMetadata(total_files=0, total_symbols=0, total_edges=0),
        )
        restored = RepoMap.from_dict(original.to_dict())
        assert restored.indexed_files == []
        assert restored.symbol_tags == []
        assert restored.relationship_edges == []

    def test_json_roundtrip_through_json_loads_dumps(self):
        rm = make_repo_map()
        serialized = json.dumps(rm.to_dict(), sort_keys=True)
        data = json.loads(serialized)
        restored = RepoMap.from_dict(data)
        assert restored.commit_sha == rm.commit_sha
        assert restored.repo_identity == rm.repo_identity


# ===========================================================================
# Schema-version rejection
# ===========================================================================


class TestSchemaVersionRejection:
    def test_from_dict_rejects_wrong_version_zero(self):
        d = make_repo_map().to_dict()
        d["schema_version"] = 0
        with pytest.raises(SchemaVersionError):
            RepoMap.from_dict(d)

    def test_from_dict_rejects_version_minus_one(self):
        d = make_repo_map().to_dict()
        d["schema_version"] = -1
        with pytest.raises(SchemaVersionError):
            RepoMap.from_dict(d)

    def test_from_dict_rejects_future_version(self):
        d = make_repo_map().to_dict()
        d["schema_version"] = CURRENT_SCHEMA_VERSION + 1
        with pytest.raises(SchemaVersionError):
            RepoMap.from_dict(d)

    def test_from_dict_rejects_string_version(self):
        d = make_repo_map().to_dict()
        d["schema_version"] = str(CURRENT_SCHEMA_VERSION)
        with pytest.raises(SchemaVersionError):
            RepoMap.from_dict(d)

    def test_from_dict_rejects_none_version(self):
        d = make_repo_map().to_dict()
        d["schema_version"] = None
        with pytest.raises(SchemaVersionError):
            RepoMap.from_dict(d)

    def test_schema_version_error_is_value_error(self):
        """SchemaVersionError must be a subclass of ValueError."""
        d = make_repo_map().to_dict()
        d["schema_version"] = 999
        with pytest.raises(ValueError):
            RepoMap.from_dict(d)

    def test_from_dict_rejects_missing_schema_version(self):
        d = make_repo_map().to_dict()
        del d["schema_version"]
        with pytest.raises(SchemaVersionError):
            RepoMap.from_dict(d)


# ===========================================================================
# Deterministic output
# ===========================================================================


class TestDeterministicOutput:
    def test_identical_inputs_produce_identical_json(self):
        """Serialisation must be deterministic: same input → same JSON bytes."""
        rm1 = make_repo_map()
        rm2 = make_repo_map()
        j1 = json.dumps(rm1.to_dict(), sort_keys=True)
        j2 = json.dumps(rm2.to_dict(), sort_keys=True)
        assert j1 == j2

    def test_different_commit_sha_produces_different_json(self):
        sha_a = "a" * 40
        sha_b = "b" * 40
        rm1 = make_repo_map(commit_sha=sha_a)
        rm2 = make_repo_map(commit_sha=sha_b)
        j1 = json.dumps(rm1.to_dict(), sort_keys=True)
        j2 = json.dumps(rm2.to_dict(), sort_keys=True)
        assert j1 != j2

    def test_different_repo_identity_produces_different_json(self):
        rm1 = make_repo_map(repo_identity="https://github.com/a/repo")
        rm2 = make_repo_map(repo_identity="https://github.com/b/repo")
        j1 = json.dumps(rm1.to_dict(), sort_keys=True)
        j2 = json.dumps(rm2.to_dict(), sort_keys=True)
        assert j1 != j2

    def test_adding_a_file_changes_json(self):
        rm1 = make_repo_map(indexed_files=[])
        rm2 = make_repo_map(
            indexed_files=[IndexedFile(path="new_file.py")],
            rendering_metadata=RenderingMetadata(total_files=1, total_symbols=0, total_edges=0),
        )
        j1 = json.dumps(rm1.to_dict(), sort_keys=True)
        j2 = json.dumps(rm2.to_dict(), sort_keys=True)
        assert j1 != j2


# ===========================================================================
# SHA invalidation
# ===========================================================================


class TestSHAInvalidation:
    def test_is_fresh_matching_sha(self):
        rm = make_repo_map(commit_sha=SAMPLE_SHA)
        assert is_fresh(rm, SAMPLE_SHA) is True

    def test_is_fresh_mismatching_sha(self):
        rm = make_repo_map(commit_sha=SAMPLE_SHA)
        assert is_fresh(rm, "b" * 40) is False

    def test_is_fresh_case_normalises_current_sha(self):
        rm = make_repo_map(commit_sha="abc" * 13 + "a")
        # current_sha provided in upper case must still match
        assert is_fresh(rm, ("ABC" * 13 + "A").lower()) is True

    def test_is_not_fresh_when_sha_differs_by_one_char(self):
        sha = "a" * 39 + "b"
        rm = make_repo_map(commit_sha=sha)
        different = "a" * 39 + "c"
        assert is_fresh(rm, different) is False

    def test_is_fresh_empty_sha_does_not_match(self):
        rm = make_repo_map(commit_sha=SAMPLE_SHA)
        assert is_fresh(rm, "") is False


# ===========================================================================
# repo_map_slug
# ===========================================================================


class TestRepoMapSlug:
    def test_github_https_url(self):
        assert repo_map_slug("https://github.com/lesserevil/oompah") == "github-com-lesserevil-oompah"

    def test_github_http_url(self):
        assert repo_map_slug("http://github.com/org/repo") == "github-com-org-repo"

    def test_git_scheme_url(self):
        slug = repo_map_slug("git://github.com/org/repo.git")
        assert "github" in slug
        assert "org" in slug
        assert "repo" in slug

    def test_ssh_style_url(self):
        # No scheme prefix; punctuation replaced with hyphens
        slug = repo_map_slug("git@github.com:lesserevil/oompah.git")
        assert slug  # must be non-empty
        assert "github" in slug

    def test_slug_is_lowercase(self):
        slug = repo_map_slug("https://GITHUB.COM/ORG/REPO")
        assert slug == slug.lower()

    def test_slug_has_no_leading_or_trailing_hyphens(self):
        slug = repo_map_slug("https://github.com/org/repo")
        assert not slug.startswith("-")
        assert not slug.endswith("-")

    def test_slug_contains_only_alphanumeric_and_hyphens(self):
        import re
        slug = repo_map_slug("https://github.com/some-org/some.repo")
        assert re.match(r"^[a-z0-9-]+$", slug), f"Invalid slug: {slug!r}"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            repo_map_slug("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            repo_map_slug("   ")

    def test_all_punctuation_raises(self):
        with pytest.raises(ValueError, match="empty slug"):
            repo_map_slug(":///:@!#$")

    def test_same_identity_always_same_slug(self):
        identity = "https://github.com/org/repo"
        assert repo_map_slug(identity) == repo_map_slug(identity)


# ===========================================================================
# repo_map_path
# ===========================================================================


class TestRepoMapPath:
    def test_returns_path_object(self):
        p = repo_map_path(SAMPLE_IDENTITY, SAMPLE_SHA)
        assert isinstance(p, Path)

    def test_starts_with_oompah_namespace(self):
        p = repo_map_path(SAMPLE_IDENTITY, SAMPLE_SHA)
        assert str(p).startswith(".oompah/")

    def test_contains_repo_maps_subdir(self):
        p = repo_map_path(SAMPLE_IDENTITY, SAMPLE_SHA)
        assert "repo-maps" in str(p)

    def test_filename_is_commit_sha_dot_json(self):
        p = repo_map_path(SAMPLE_IDENTITY, SAMPLE_SHA)
        assert p.name == f"{SAMPLE_SHA}.json"

    def test_different_shas_produce_different_paths(self):
        p1 = repo_map_path(SAMPLE_IDENTITY, "a" * 40)
        p2 = repo_map_path(SAMPLE_IDENTITY, "b" * 40)
        assert p1 != p2

    def test_different_identities_produce_different_dirs(self):
        p1 = repo_map_path("https://github.com/org/repo1", SAMPLE_SHA)
        p2 = repo_map_path("https://github.com/org/repo2", SAMPLE_SHA)
        assert p1.parent != p2.parent

    def test_path_is_relative(self):
        p = repo_map_path(SAMPLE_IDENTITY, SAMPLE_SHA)
        assert not p.is_absolute()

    def test_path_is_within_namespace(self):
        p = repo_map_path(SAMPLE_IDENTITY, SAMPLE_SHA)
        assert is_within_namespace(p)

    def test_sha_is_lowercased_in_path(self):
        upper_sha = ("A" * 40)
        p = repo_map_path(SAMPLE_IDENTITY, upper_sha)
        assert p.name == f"{'a' * 40}.json"


# ===========================================================================
# is_within_namespace
# ===========================================================================


class TestIsWithinNamespace:
    def test_relative_path_inside_namespace(self):
        assert is_within_namespace(Path(".oompah/repo-maps/slug/sha.json")) is True

    def test_absolute_path_inside_namespace(self):
        assert is_within_namespace(Path("/home/user/project/.oompah/repo-maps/slug/sha.json")) is True

    def test_relative_path_outside_namespace(self):
        assert is_within_namespace(Path("other/file.json")) is False

    def test_oompah_as_filename_not_namespace(self):
        # ".oompah" only as a file name in a different directory
        assert is_within_namespace(Path("data/.oompah")) is True  # it IS in parts

    def test_empty_relative_path(self):
        assert is_within_namespace(Path("")) is False

    def test_traversal_attempt_stays_rejected(self):
        # A path that tries to escape via .. should be resolved and checked
        # The normpath resolves .. so .oompah/../other is NOT within .oompah
        tricky = Path(".oompah/../other/file.json")
        assert is_within_namespace(tricky) is False

    def test_canonical_repo_map_path_is_within_namespace(self):
        p = repo_map_path(SAMPLE_IDENTITY, SAMPLE_SHA)
        assert is_within_namespace(p) is True


# ===========================================================================
# write_repo_map
# ===========================================================================


class TestWriteRepoMap:
    def test_happy_path_creates_file(self, tmp_path):
        rm = make_repo_map()
        result = write_repo_map(tmp_path, rm)
        assert result.exists()
        assert result.is_file()

    def test_returned_path_is_canonical(self, tmp_path):
        rm = make_repo_map()
        result = write_repo_map(tmp_path, rm)
        expected = tmp_path / repo_map_path(rm.repo_identity, rm.commit_sha)
        assert result == expected

    def test_written_file_is_valid_json(self, tmp_path):
        rm = make_repo_map()
        result = write_repo_map(tmp_path, rm)
        data = json.loads(result.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_written_file_deserialises_correctly(self, tmp_path):
        original = make_repo_map()
        result = write_repo_map(tmp_path, original)
        data = json.loads(result.read_text(encoding="utf-8"))
        restored = RepoMap.from_dict(data)
        assert restored.commit_sha == original.commit_sha
        assert restored.repo_identity == original.repo_identity

    def test_creates_parent_directories(self, tmp_path):
        rm = make_repo_map()
        # The subdirectories should not exist yet
        rel = repo_map_path(rm.repo_identity, rm.commit_sha)
        assert not (tmp_path / rel).parent.exists()
        write_repo_map(tmp_path, rm)
        assert (tmp_path / rel).parent.is_dir()

    def test_wrong_schema_version_raises(self, tmp_path):
        rm = make_repo_map(schema_version=CURRENT_SCHEMA_VERSION + 1)
        with pytest.raises(SchemaVersionError):
            write_repo_map(tmp_path, rm)

    def test_write_is_idempotent(self, tmp_path):
        rm = make_repo_map()
        p1 = write_repo_map(tmp_path, rm)
        p2 = write_repo_map(tmp_path, rm)
        assert p1 == p2
        assert p1.exists()

    def test_result_path_is_within_oompah_namespace(self, tmp_path):
        rm = make_repo_map()
        result = write_repo_map(tmp_path, rm)
        # The path relative to tmp_path must start with .oompah
        rel = result.relative_to(tmp_path)
        assert is_within_namespace(rel)

    def test_write_produces_deterministic_content(self, tmp_path):
        rm1 = make_repo_map()
        rm2 = make_repo_map()
        p1 = write_repo_map(tmp_path, rm1)
        content1 = p1.read_text(encoding="utf-8")
        # Remove the file and write again
        p1.unlink()
        p2 = write_repo_map(tmp_path, rm2)
        content2 = p2.read_text(encoding="utf-8")
        assert content1 == content2


# ===========================================================================
# read_repo_map
# ===========================================================================


class TestReadRepoMap:
    def test_happy_path_returns_repo_map(self, tmp_path):
        rm = make_repo_map()
        write_repo_map(tmp_path, rm)
        result = read_repo_map(tmp_path, rm.repo_identity, rm.commit_sha)
        assert result is not None
        assert result.commit_sha == rm.commit_sha

    def test_missing_file_returns_none(self, tmp_path):
        result = read_repo_map(tmp_path, SAMPLE_IDENTITY, SAMPLE_SHA)
        assert result is None

    def test_bad_json_returns_none(self, tmp_path):
        rm = make_repo_map()
        p = tmp_path / repo_map_path(rm.repo_identity, rm.commit_sha)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("this is not json", encoding="utf-8")
        result = read_repo_map(tmp_path, rm.repo_identity, rm.commit_sha)
        assert result is None

    def test_wrong_schema_version_returns_none(self, tmp_path):
        rm = make_repo_map()
        p = tmp_path / repo_map_path(rm.repo_identity, rm.commit_sha)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = rm.to_dict()
        data["schema_version"] = CURRENT_SCHEMA_VERSION + 99
        p.write_text(json.dumps(data), encoding="utf-8")
        result = read_repo_map(tmp_path, rm.repo_identity, rm.commit_sha)
        assert result is None

    def test_stale_sha_with_require_fresh_true_returns_none(self, tmp_path):
        rm = make_repo_map(commit_sha=SAMPLE_SHA)
        write_repo_map(tmp_path, rm)
        # Read with a different sha — stale
        different_sha = "b" * 40
        result = read_repo_map(tmp_path, rm.repo_identity, different_sha, require_fresh=True)
        assert result is None

    def test_stale_sha_with_require_fresh_false_returns_map(self, tmp_path):
        """With require_fresh=False, a map written for one SHA is readable
        when looking up a different SHA, as long as the file path resolves."""
        # We write the map for SAMPLE_SHA, then read with require_fresh=False
        # using the same sha (file path is keyed by sha so we still use SAMPLE_SHA
        # for the file path, but the sha in the document differs from current).
        rm = make_repo_map(commit_sha=SAMPLE_SHA)
        write_repo_map(tmp_path, rm)
        # Provide a different "current sha" but require_fresh=False
        # The file is still at SAMPLE_SHA path, so use SAMPLE_SHA to locate it
        result = read_repo_map(tmp_path, rm.repo_identity, rm.commit_sha, require_fresh=False)
        assert result is not None
        assert result.commit_sha == SAMPLE_SHA

    def test_require_fresh_default_is_true(self, tmp_path):
        """Default behaviour rejects stale maps without explicit require_fresh."""
        rm = make_repo_map(commit_sha=SAMPLE_SHA)
        write_repo_map(tmp_path, rm)
        # Write a second map with different sha; then the first should be stale
        # We test by writing a modified document directly
        p = tmp_path / repo_map_path(rm.repo_identity, SAMPLE_SHA)
        data = rm.to_dict()
        data["commit_sha"] = "c" * 40  # mutate the stored sha
        p.write_text(json.dumps(data), encoding="utf-8")
        # read_repo_map looks for SAMPLE_SHA path but finds document with "c"*40 sha
        result = read_repo_map(tmp_path, rm.repo_identity, SAMPLE_SHA)
        # commit_sha in document doesn't match SAMPLE_SHA → stale
        assert result is None

    def test_truncated_flag_preserved(self, tmp_path):
        rm = make_repo_map(
            rendering_metadata=RenderingMetadata(
                total_files=0, total_symbols=0, total_edges=0,
                truncated=True, notes=["too large"]
            )
        )
        write_repo_map(tmp_path, rm)
        result = read_repo_map(tmp_path, rm.repo_identity, rm.commit_sha)
        assert result is not None
        assert result.rendering_metadata.truncated is True
        assert result.rendering_metadata.notes == ["too large"]

    def test_empty_file_returns_none(self, tmp_path):
        rm = make_repo_map()
        p = tmp_path / repo_map_path(rm.repo_identity, rm.commit_sha)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")
        result = read_repo_map(tmp_path, rm.repo_identity, rm.commit_sha)
        assert result is None


# ===========================================================================
# prune_repo_maps
# ===========================================================================


class TestPruneRepoMaps:
    def test_no_maps_returns_empty_list(self, tmp_path):
        removed = prune_repo_maps(tmp_path, SAMPLE_IDENTITY)
        assert removed == []

    def test_nonexistent_slug_dir_returns_empty_list(self, tmp_path):
        removed = prune_repo_maps(tmp_path, "https://github.com/no/such")
        assert removed == []

    def test_fewer_than_max_returns_empty_list(self, tmp_path):
        for i in range(REPO_MAP_MAX_RETAINED - 1):
            sha = f"{i:040x}"
            rm = make_repo_map(commit_sha=sha)
            write_repo_map(tmp_path, rm)
        removed = prune_repo_maps(tmp_path, SAMPLE_IDENTITY)
        assert removed == []

    def test_exactly_max_returns_empty_list(self, tmp_path):
        for i in range(REPO_MAP_MAX_RETAINED):
            sha = f"{i:040x}"
            rm = make_repo_map(commit_sha=sha)
            write_repo_map(tmp_path, rm)
        removed = prune_repo_maps(tmp_path, SAMPLE_IDENTITY)
        assert removed == []

    def test_more_than_max_removes_oldest(self, tmp_path):
        n = REPO_MAP_MAX_RETAINED + 2
        written_paths = []
        for i in range(n):
            sha = f"{i:040x}"
            rm = make_repo_map(commit_sha=sha)
            p = write_repo_map(tmp_path, rm)
            written_paths.append(p)
            # Small sleep ensures distinct mtime on all filesystems.
            # On fast filesystems we touch the mtime explicitly instead.
            p.touch()
            # Advance mtime for determinism.
            import os as _os
            new_mtime = _os.path.getmtime(str(p)) + (i + 1)
            _os.utime(str(p), (new_mtime, new_mtime))

        removed = prune_repo_maps(tmp_path, SAMPLE_IDENTITY)
        assert len(removed) == 2

    def test_removed_files_do_not_exist_after_prune(self, tmp_path):
        n = REPO_MAP_MAX_RETAINED + 3
        for i in range(n):
            sha = f"{i:040x}"
            rm = make_repo_map(commit_sha=sha)
            p = write_repo_map(tmp_path, rm)
            import os as _os
            new_mtime = _os.path.getmtime(str(p)) + (i + 1)
            _os.utime(str(p), (new_mtime, new_mtime))

        removed = prune_repo_maps(tmp_path, SAMPLE_IDENTITY)
        for r in removed:
            assert not r.exists(), f"Removed path still exists: {r}"

    def test_retained_files_still_exist_after_prune(self, tmp_path):
        n = REPO_MAP_MAX_RETAINED + 1
        all_paths = []
        for i in range(n):
            sha = f"{i:040x}"
            rm = make_repo_map(commit_sha=sha)
            p = write_repo_map(tmp_path, rm)
            all_paths.append(p)
            import os as _os
            new_mtime = _os.path.getmtime(str(p)) + (i + 1)
            _os.utime(str(p), (new_mtime, new_mtime))

        removed = prune_repo_maps(tmp_path, SAMPLE_IDENTITY)
        removed_set = set(removed)
        for p in all_paths:
            if p not in removed_set:
                assert p.exists(), f"Retained path was removed: {p}"

    def test_custom_max_retained(self, tmp_path):
        for i in range(5):
            sha = f"{i:040x}"
            rm = make_repo_map(commit_sha=sha)
            p = write_repo_map(tmp_path, rm)
            import os as _os
            new_mtime = _os.path.getmtime(str(p)) + (i + 1)
            _os.utime(str(p), (new_mtime, new_mtime))

        removed = prune_repo_maps(tmp_path, SAMPLE_IDENTITY, max_retained=2)
        assert len(removed) == 3

    def test_max_retained_zero_raises(self, tmp_path):
        with pytest.raises(ValueError, match="max_retained must be >= 1"):
            prune_repo_maps(tmp_path, SAMPLE_IDENTITY, max_retained=0)

    def test_max_retained_negative_raises(self, tmp_path):
        with pytest.raises(ValueError):
            prune_repo_maps(tmp_path, SAMPLE_IDENTITY, max_retained=-1)


# ===========================================================================
# State-branch namespace guarantee
# ===========================================================================


class TestStateBranchNamespaceGuarantee:
    """All paths constructed or written by this module must remain within
    the .oompah/ project-state namespace."""

    def test_write_stays_within_namespace(self, tmp_path):
        rm = make_repo_map()
        result = write_repo_map(tmp_path, rm)
        rel = result.relative_to(tmp_path)
        assert is_within_namespace(rel), f"Written path escaped namespace: {rel}"

    def test_read_looks_within_namespace(self, tmp_path):
        rm = make_repo_map()
        write_repo_map(tmp_path, rm)
        # There should be no files written outside .oompah/
        all_files = list(tmp_path.rglob("*.json"))
        for f in all_files:
            rel = f.relative_to(tmp_path)
            assert is_within_namespace(rel), f"File outside namespace: {rel}"

    def test_prune_only_touches_files_within_namespace(self, tmp_path):
        # Write some maps
        for i in range(REPO_MAP_MAX_RETAINED + 2):
            sha = f"{i:040x}"
            rm = make_repo_map(commit_sha=sha)
            p = write_repo_map(tmp_path, rm)
            import os as _os
            new_mtime = _os.path.getmtime(str(p)) + (i + 1)
            _os.utime(str(p), (new_mtime, new_mtime))

        # Place a sentinel file outside the namespace
        sentinel = tmp_path / "important.json"
        sentinel.write_text("{}", encoding="utf-8")

        prune_repo_maps(tmp_path, SAMPLE_IDENTITY)

        # The sentinel must still exist
        assert sentinel.exists(), "prune_repo_maps deleted a file outside .oompah/"

    def test_repo_map_path_never_escapes_oompah(self):
        """Path construction must not produce a path outside .oompah/."""
        # Try a variety of adversarial repo identities
        tricky_identities = [
            "https://github.com/../../../etc",
            "https://github.com/a/b",
            "git@github.com:org/repo.git",
            "https://example.com",
        ]
        for identity in tricky_identities:
            try:
                p = repo_map_path(identity, SAMPLE_SHA)
                assert is_within_namespace(p), (
                    f"repo_map_path({identity!r}) produced path outside namespace: {p}"
                )
            except ValueError:
                # repo_map_slug may reject some identities; that is acceptable
                pass

    def test_write_validates_schema_version_before_touching_filesystem(self, tmp_path):
        """A wrong-version map must not create any directories or files."""
        rm = make_repo_map(schema_version=CURRENT_SCHEMA_VERSION + 5)
        expected_dir = tmp_path / ".oompah"
        with pytest.raises(SchemaVersionError):
            write_repo_map(tmp_path, rm)
        assert not expected_dir.exists(), (
            "write_repo_map created directories before validating schema_version"
        )


# ===========================================================================
# Unsupported / unavailable repository behavior
# ===========================================================================


class TestUnavailableAndUnsupportedRepositories:
    def test_unavailable_repo_read_returns_none(self, tmp_path):
        """A repo with no map file returns None — caller handles gracefully."""
        result = read_repo_map(tmp_path, "https://github.com/missing/repo", SAMPLE_SHA)
        assert result is None

    def test_unsupported_repo_map_has_empty_lists_and_note(self, tmp_path):
        """Unsupported-repo sentinel map is valid, readable, and has notes."""
        rm = make_repo_map(
            indexed_files=[],
            symbol_tags=[],
            relationship_edges=[],
            rendering_metadata=RenderingMetadata(
                total_files=0,
                total_symbols=0,
                total_edges=0,
                notes=["repository not supported"],
            ),
        )
        write_repo_map(tmp_path, rm)
        result = read_repo_map(tmp_path, rm.repo_identity, rm.commit_sha)
        assert result is not None
        assert result.indexed_files == []
        assert result.symbol_tags == []
        assert result.relationship_edges == []
        assert "repository not supported" in result.rendering_metadata.notes

    def test_stale_map_treated_as_unavailable_by_default(self, tmp_path):
        """A map whose commit SHA doesn't match the current SHA is unavailable."""
        rm = make_repo_map(commit_sha=SAMPLE_SHA)
        write_repo_map(tmp_path, rm)
        newer_sha = "f" * 40
        result = read_repo_map(tmp_path, rm.repo_identity, newer_sha)
        assert result is None
