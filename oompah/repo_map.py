"""Repository-map artifact: versioned, deterministic JSON schema for code analysis.

This module defines the typed artifact contract for repository-map artifacts.
A repository map is a data-only snapshot of a repository's structure at a
specific commit.  It must NEVER be executed, evaluated, or interpreted as
instructions.  Every string field is untrusted data from the perspective of
the consuming code.

See ``plans/repo-map-artifact.md`` for the full schema specification, lifecycle
rules, and security invariants.

Public API
----------

``CURRENT_SCHEMA_VERSION``
    Integer constant.  Readers reject maps whose ``schema_version`` differs.

``IndexedFile``, ``SymbolTag``, ``RelationshipEdge``, ``RenderingMetadata``
    Typed dataclasses for the nested objects in the schema.

``RepoMap``
    The top-level artifact dataclass.  Serialise with ``RepoMap.to_dict()``
    and deserialise with ``RepoMap.from_dict()``.

``repo_map_slug(repo_identity)``
    Derive a filesystem-safe slug from a repository identity string.

``repo_map_path(repo_identity, commit_sha)``
    Return the canonical state-branch-relative ``Path`` for a map.

``is_within_namespace(path)``
    Return ``True`` if *path* is inside the ``.oompah/`` namespace.

``is_fresh(repo_map, current_sha)``
    Return ``True`` if the map's commit SHA matches *current_sha*.

``write_repo_map(base_dir, repo_map)``
    Atomically write a ``RepoMap`` to its canonical path under *base_dir*.

``read_repo_map(base_dir, repo_identity, commit_sha, *, require_fresh)``
    Read a ``RepoMap`` from the canonical path, or return ``None``.

``prune_repo_maps(base_dir, repo_identity, max_retained)``
    Remove old maps beyond *max_retained*, returning the list of removed paths.

``REPO_MAP_MAX_RETAINED``
    Default retention limit (5 maps per repository slug).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

#: Bump this integer when the JSON layout changes in a backward-incompatible
#: way.  Readers must reject maps whose schema_version differs.
CURRENT_SCHEMA_VERSION: int = 1

# ---------------------------------------------------------------------------
# Retention policy
# ---------------------------------------------------------------------------

#: Maximum number of maps to retain per repository slug.
REPO_MAP_MAX_RETAINED: int = 5

# ---------------------------------------------------------------------------
# State-branch namespace
# ---------------------------------------------------------------------------

#: Root directory within the state-branch checkout where all oompah-managed
#: files live.  Must never be changed without a schema-version bump.
_STATE_NAMESPACE = ".oompah"

#: Sub-directory under _STATE_NAMESPACE that holds repository-map artifacts.
_REPO_MAP_SUBDIR = "repo-maps"


# ---------------------------------------------------------------------------
# Nested schema dataclasses
# ---------------------------------------------------------------------------


@dataclass
class IndexedFile:
    """A single file included in the repository-map analysis.

    All fields are data-only; the ``path`` field must not be used for
    filesystem access by consumers.
    """

    #: Repository-relative path using forward slashes (e.g. "oompah/models.py").
    path: str

    #: File size in bytes at indexing time.  ``None`` if unavailable.
    size_bytes: int | None = None

    #: Lowercase hex SHA-256 of the file content.  ``None`` if not computed.
    content_hash: str | None = None

    #: Detected language (e.g. "python", "typescript").  ``None`` if undetected.
    language: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "content_hash": self.content_hash,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IndexedFile":
        return cls(
            path=str(d["path"]),
            size_bytes=int(d["size_bytes"]) if d.get("size_bytes") is not None else None,
            content_hash=str(d["content_hash"]) if d.get("content_hash") is not None else None,
            language=str(d["language"]) if d.get("language") is not None else None,
        )


@dataclass
class SymbolTag:
    """A named symbol declaration found in the repository.

    All fields are data-only.
    """

    #: Symbol kind — one of "class", "function", "method", "variable",
    #: "module", "constant", "type".
    kind: str

    #: Unqualified symbol name.
    name: str

    #: Repository-relative path of the file containing this symbol.
    file_path: str

    #: 1-based line number of the declaration.  ``None`` if unavailable.
    line: int | None = None

    #: Containing namespace, class, or module.  ``None`` for module-level symbols.
    namespace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "file_path": self.file_path,
            "line": self.line,
            "namespace": self.namespace,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SymbolTag":
        return cls(
            kind=str(d["kind"]),
            name=str(d["name"]),
            file_path=str(d["file_path"]),
            line=int(d["line"]) if d.get("line") is not None else None,
            namespace=str(d["namespace"]) if d.get("namespace") is not None else None,
        )


@dataclass
class RelationshipEdge:
    """A directed dependency edge between two entities in the repository.

    All fields are data-only.
    """

    #: Edge kind — one of "imports", "inherits", "calls", "defines", "references".
    kind: str

    #: Fully-qualified name or repo-relative file path of the source entity.
    source: str

    #: Fully-qualified name or repo-relative file path of the target entity.
    target: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source": self.source,
            "target": self.target,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RelationshipEdge":
        return cls(
            kind=str(d["kind"]),
            source=str(d["source"]),
            target=str(d["target"]),
        )


@dataclass
class RenderingMetadata:
    """Summary statistics about the analysis run.

    These fields are informational.  Consumers should verify them against
    the actual list lengths rather than trusting them as authoritative.
    """

    #: Number of entries in ``indexed_files``.
    total_files: int

    #: Number of entries in ``symbol_tags``.
    total_symbols: int

    #: Number of entries in ``relationship_edges``.
    total_edges: int

    #: ``True`` if the map was truncated because it exceeded a size limit.
    truncated: bool = False

    #: Human-readable notes about the analysis run.
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_files": self.total_files,
            "total_symbols": self.total_symbols,
            "total_edges": self.total_edges,
            "truncated": self.truncated,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RenderingMetadata":
        return cls(
            total_files=int(d["total_files"]),
            total_symbols=int(d["total_symbols"]),
            total_edges=int(d["total_edges"]),
            truncated=bool(d.get("truncated", False)),
            notes=[str(n) for n in (d.get("notes") or [])],
        )


# ---------------------------------------------------------------------------
# Top-level artifact
# ---------------------------------------------------------------------------


@dataclass
class RepoMap:
    """Top-level repository-map artifact.

    This is the typed contract for a versioned, deterministic snapshot of a
    repository's code structure at a specific commit.

    **Security:** All string fields are untrusted data.  Never pass them to
    ``eval()``, ``exec()``, ``subprocess``, or any template engine.

    Serialise with :meth:`to_dict` and deserialise with :meth:`from_dict`.
    Use :func:`write_repo_map` / :func:`read_repo_map` for filesystem I/O.
    """

    #: Must equal ``CURRENT_SCHEMA_VERSION``.  Readers reject mismatches.
    schema_version: int

    #: Canonical URL or unique opaque identifier for the repository.
    repo_identity: str

    #: 40-character lowercase hexadecimal SHA of the analyzed commit.
    commit_sha: str

    #: Semantic version string of the generator (e.g. "1.0.0").
    generator_version: str

    #: All files included in the analysis (lexicographically sorted by path).
    indexed_files: list[IndexedFile]

    #: Symbol declarations found across the indexed files.
    symbol_tags: list[SymbolTag]

    #: Directed dependency edges between symbols or files.
    relationship_edges: list[RelationshipEdge]

    #: ISO 8601 UTC timestamp of map generation (e.g. "2026-07-21T15:00:00Z").
    generated_at: str

    #: Summary statistics and notes from the analysis run.
    rendering_metadata: RenderingMetadata

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for ``json.dumps``.

        Keys are in a stable, documented order.  All nested objects are also
        converted to plain dicts.
        """
        return {
            "schema_version": self.schema_version,
            "repo_identity": self.repo_identity,
            "commit_sha": self.commit_sha,
            "generator_version": self.generator_version,
            "indexed_files": [f.to_dict() for f in self.indexed_files],
            "symbol_tags": [s.to_dict() for s in self.symbol_tags],
            "relationship_edges": [e.to_dict() for e in self.relationship_edges],
            "generated_at": self.generated_at,
            "rendering_metadata": self.rendering_metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RepoMap":
        """Deserialise from a plain dict (as produced by ``json.loads``).

        Raises :class:`SchemaVersionError` if ``schema_version`` does not
        equal ``CURRENT_SCHEMA_VERSION``.

        Raises :class:`ValueError` if required top-level keys are missing.
        """
        version = d.get("schema_version")
        if version != CURRENT_SCHEMA_VERSION:
            raise SchemaVersionError(
                f"Unsupported schema_version {version!r}; "
                f"expected {CURRENT_SCHEMA_VERSION}"
            )
        return cls(
            schema_version=int(d["schema_version"]),
            repo_identity=str(d["repo_identity"]),
            commit_sha=str(d["commit_sha"]),
            generator_version=str(d["generator_version"]),
            indexed_files=[IndexedFile.from_dict(f) for f in (d.get("indexed_files") or [])],
            symbol_tags=[SymbolTag.from_dict(s) for s in (d.get("symbol_tags") or [])],
            relationship_edges=[
                RelationshipEdge.from_dict(e) for e in (d.get("relationship_edges") or [])
            ],
            generated_at=str(d["generated_at"]),
            rendering_metadata=RenderingMetadata.from_dict(d["rendering_metadata"]),
        )


# ---------------------------------------------------------------------------
# Schema version error
# ---------------------------------------------------------------------------


class SchemaVersionError(ValueError):
    """Raised when a repo-map document has an unsupported schema_version.

    This is a subclass of :class:`ValueError` so callers that only care
    whether deserialization succeeded can catch ``ValueError``.
    """


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def repo_map_slug(repo_identity: str) -> str:
    """Derive a filesystem-safe slug from a repository identity string.

    The slug is used as a directory name under ``.oompah/repo-maps/``.

    Algorithm:
    1. Strip leading/trailing whitespace.
    2. Remove the URL scheme (``https://``, ``http://``, ``git://``).
    3. Lower-case the result.
    4. Replace any run of non-alphanumeric characters with a single hyphen.
    5. Strip leading and trailing hyphens.

    Raises :class:`ValueError` if *repo_identity* is empty or produces an
    empty slug (e.g. a string that is entirely punctuation).

    >>> repo_map_slug("https://github.com/lesserevil/oompah")
    'github-com-lesserevil-oompah'
    >>> repo_map_slug("git@github.com:lesserevil/oompah.git")
    'github-com-lesserevil-oompah-git'
    """
    identity = repo_identity.strip()
    if not identity:
        raise ValueError("repo_identity must not be empty")

    # Remove URL scheme
    cleaned = re.sub(r"^[a-z][a-z0-9+\-.]*://", "", identity, flags=re.IGNORECASE)
    # Lower-case
    cleaned = cleaned.lower()
    # Replace non-alphanumeric runs with a hyphen
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    # Strip leading/trailing hyphens
    cleaned = cleaned.strip("-")

    if not cleaned:
        raise ValueError(
            f"repo_identity {repo_identity!r} produces an empty slug after sanitization"
        )
    return cleaned


def repo_map_path(repo_identity: str, commit_sha: str) -> Path:
    """Return the canonical state-branch-relative path for a repo map.

    The returned path is always relative (no leading slash) and is guaranteed
    to be inside ``.oompah/``.

    >>> repo_map_path("https://github.com/org/repo", "a" * 40)
    PosixPath('.oompah/repo-maps/github-com-org-repo/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.json')
    """
    slug = repo_map_slug(repo_identity)
    sha = commit_sha.lower().strip()
    return Path(_STATE_NAMESPACE) / _REPO_MAP_SUBDIR / slug / f"{sha}.json"


def is_within_namespace(path: Path) -> bool:
    """Return ``True`` if *path* is inside the ``.oompah/`` namespace.

    Accepts both relative and absolute paths.  The check is purely
    string-based (no filesystem access).

    >>> is_within_namespace(Path(".oompah/repo-maps/slug/sha.json"))
    True
    >>> is_within_namespace(Path("/abs/.oompah/repo-maps/slug/sha.json"))
    True
    >>> is_within_namespace(Path("other/file.json"))
    False
    """
    # Normalise away ".." components without touching the filesystem.
    try:
        parts = Path(os.path.normpath(str(path))).parts
    except Exception:
        return False

    # Accept both relative (.oompah/…) and absolute (/…/.oompah/…) paths.
    return _STATE_NAMESPACE in parts


# ---------------------------------------------------------------------------
# Freshness rule
# ---------------------------------------------------------------------------


def is_fresh(repo_map: RepoMap, current_sha: str) -> bool:
    """Return ``True`` if the map's commit SHA matches *current_sha*.

    This is the **only** freshness check — a map is usable if and only if
    its ``commit_sha`` equals the current checkout HEAD SHA.

    >>> m = RepoMap(schema_version=1, repo_identity="https://example.com/r",
    ...     commit_sha="abc" * 13 + "a", generator_version="1.0.0",
    ...     indexed_files=[], symbol_tags=[], relationship_edges=[],
    ...     generated_at="2026-01-01T00:00:00Z",
    ...     rendering_metadata=RenderingMetadata(0, 0, 0))
    >>> is_fresh(m, "abc" * 13 + "a")
    True
    >>> is_fresh(m, "000" * 13 + "0")
    False
    """
    return repo_map.commit_sha == current_sha.lower().strip()


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _to_json(repo_map: RepoMap) -> str:
    """Serialise *repo_map* to a deterministic JSON string.

    Keys are always in the same order (``sort_keys=True`` on the
    ``json.dumps`` call).  The output is compact (no extra whitespace).
    """
    return json.dumps(repo_map.to_dict(), sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def write_repo_map(base_dir: Path, repo_map: RepoMap) -> Path:
    """Atomically write *repo_map* to its canonical path under *base_dir*.

    Procedure:
    1. Validate that ``repo_map.schema_version == CURRENT_SCHEMA_VERSION``.
    2. Compute the canonical path relative to *base_dir*.
    3. Verify the path is inside the ``.oompah/`` namespace.
    4. Create parent directories if necessary.
    5. Write to a temporary file in the same directory.
    6. ``os.replace()`` the temporary file to the canonical path (atomic on POSIX).
    7. Return the canonical path.

    Raises :class:`SchemaVersionError` if the schema version is not current.
    Raises :class:`ValueError` if the canonical path escapes the namespace.

    The caller is responsible for committing the written file to the state
    branch.
    """
    if repo_map.schema_version != CURRENT_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"Cannot write map with schema_version {repo_map.schema_version}; "
            f"current is {CURRENT_SCHEMA_VERSION}"
        )

    rel_path = repo_map_path(repo_map.repo_identity, repo_map.commit_sha)
    if not is_within_namespace(rel_path):
        raise ValueError(
            f"Computed path {rel_path} is outside the .oompah/ namespace"
        )

    canonical = base_dir / rel_path
    canonical.parent.mkdir(parents=True, exist_ok=True)

    payload = _to_json(repo_map)

    # Write to a temp file in the same directory then rename atomically.
    fd, tmp_path = tempfile.mkstemp(dir=canonical.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_path, canonical)
    except Exception:
        # Clean up the temp file if something went wrong.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return canonical


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def read_repo_map(
    base_dir: Path,
    repo_identity: str,
    commit_sha: str,
    *,
    require_fresh: bool = True,
) -> "RepoMap | None":
    """Read a repo map from the canonical path, or return ``None``.

    Returns ``None`` when:
    - The canonical file does not exist.
    - The file contains invalid JSON.
    - The file's ``schema_version`` does not equal ``CURRENT_SCHEMA_VERSION``.
    - ``require_fresh=True`` (the default) and the map's ``commit_sha``
      does not match *commit_sha*.

    The caller must treat a ``None`` result as "map unavailable; trigger
    regeneration or skip context injection".

    Parameters
    ----------
    base_dir:
        Root directory of the state-branch checkout.
    repo_identity:
        Canonical repository identity string (same as used when writing).
    commit_sha:
        Expected HEAD commit SHA.
    require_fresh:
        When ``True`` (default), stale maps are treated as unavailable and
        ``None`` is returned.  Pass ``False`` to read any map regardless of
        SHA.
    """
    rel_path = repo_map_path(repo_identity, commit_sha)
    canonical = base_dir / rel_path

    if not canonical.exists():
        return None

    try:
        text = canonical.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None

    try:
        repo_map = RepoMap.from_dict(data)
    except (SchemaVersionError, ValueError, KeyError, TypeError):
        return None

    if require_fresh and not is_fresh(repo_map, commit_sha):
        return None

    return repo_map


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------


def prune_repo_maps(
    base_dir: Path,
    repo_identity: str,
    max_retained: int = REPO_MAP_MAX_RETAINED,
) -> list[Path]:
    """Remove old repo maps beyond *max_retained*, keeping the most recently
    modified.

    Returns the list of removed paths.  A non-existent slug directory is not
    an error; the function returns an empty list.

    Parameters
    ----------
    base_dir:
        Root directory of the state-branch checkout.
    repo_identity:
        Canonical repository identity string.
    max_retained:
        Maximum number of maps to keep.  Must be >= 1.
    """
    if max_retained < 1:
        raise ValueError(f"max_retained must be >= 1, got {max_retained}")

    slug = repo_map_slug(repo_identity)
    slug_dir = base_dir / _STATE_NAMESPACE / _REPO_MAP_SUBDIR / slug

    if not slug_dir.is_dir():
        return []

    maps = sorted(
        slug_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,  # newest first
    )

    to_remove = maps[max_retained:]
    removed: list[Path] = []
    for p in to_remove:
        try:
            p.unlink()
            removed.append(p)
        except OSError:
            pass

    return removed
