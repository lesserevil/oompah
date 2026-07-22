"""Repository-map observability: per-project index status and diagnostics.

This module provides API/UI-neutral diagnostics for the repository-map subsystem.
Operators can query the current index status of any managed project's repository
map and inspect metadata such as analyzed SHA, schema version, generation duration,
cache reuse, file/symbol counts, and failure reason.

**Security:** Diagnostic responses expose metadata only — never repository source
code or credentials.  The :class:`RepoMapDiagnostics` fields are derived from map
artifact metadata, not from raw file contents.

Public API
----------

``STATUS_FRESH``
    A fresh map exists for the current commit SHA.

``STATUS_STALE``
    A map exists on the state branch but for a different (older) commit SHA.

``STATUS_GENERATING``
    A background generation is currently in flight for the current SHA.

``STATUS_UNAVAILABLE``
    No map artifact exists on the state branch at all.

``STATUS_FAILED``
    The most recent generation attempt failed with an exception.

``STATUS_TIMEOUT``
    The most recent generation attempt timed out.

``RepoMapDiagnostics``
    Dataclass carrying the full diagnostic snapshot for one project.

``get_repo_map_diagnostics``
    Query the current index status for a project.  Fail-open: never raises.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from oompah.repo_map import (
    CURRENT_SCHEMA_VERSION,
    RepoMap,
    repo_map_slug,
    read_repo_map,
)

if TYPE_CHECKING:
    from oompah.repo_map_generator import RepoMapGenerator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Diagnostic status constants
# ---------------------------------------------------------------------------

STATUS_FRESH = "fresh"
"""A map exists on the state branch for the *current* commit SHA."""

STATUS_STALE = "stale"
"""A map exists on the state branch but for a different (older) commit SHA."""

STATUS_GENERATING = "generating"
"""A background generation task is currently in flight for the current SHA."""

STATUS_UNAVAILABLE = "unavailable"
"""No map artifact exists on the state branch at all."""

STATUS_FAILED = "failed"
"""The last generation attempt failed with an exception."""

STATUS_TIMEOUT = "timeout"
"""The last generation attempt did not complete within the configured timeout."""

# ---------------------------------------------------------------------------
# Diagnostics dataclass
# ---------------------------------------------------------------------------


@dataclass
class RepoMapDiagnostics:
    """Diagnostic snapshot for a managed project's repository map.

    Exposes metadata only.  No repository source code or credentials are
    included.

    Attributes
    ----------
    repo_identity:
        Canonical URL or opaque identifier for the repository.
    index_status:
        One of :data:`STATUS_FRESH`, :data:`STATUS_STALE`,
        :data:`STATUS_GENERATING`, :data:`STATUS_UNAVAILABLE`,
        :data:`STATUS_FAILED`, or :data:`STATUS_TIMEOUT`.
    current_sha:
        The commit SHA that was queried (usually the workspace HEAD).
        ``None`` if the SHA could not be resolved.
    analyzed_sha:
        The commit SHA actually indexed in the artifact.
        ``None`` when no artifact exists.
    schema_version:
        Integer schema version of the artifact.  ``None`` when unavailable.
    generator_version:
        Semantic version string of the generator used to produce the artifact.
        ``None`` when unavailable.
    generated_at:
        ISO 8601 UTC timestamp from the artifact.  ``None`` when unavailable.
    generation_duration_s:
        Wall-clock time in seconds for the last generation run.
        Populated from a :class:`~oompah.repo_map_generator.RepoMapResult`
        when the caller passes one in; otherwise ``None``.
    cache_reused:
        ``True`` when the last retrieval was a cache hit (STATUS_FRESH with
        no re-indexing).
    file_count:
        Number of files in the artifact's ``indexed_files`` list.
        ``None`` when no artifact is available.
    symbol_count:
        Number of tags in the artifact's ``symbol_tags`` list.
        ``None`` when no artifact is available.
    failure_reason:
        Human-readable description of the failure for STATUS_FAILED and
        STATUS_TIMEOUT.  ``None`` for successful or in-progress states.
    prompt_included:
        ``True`` when a fresh artifact was available and would be included
        in an agent startup prompt.  ``False`` when no fresh artifact is
        available (stale, generating, unavailable, failed, timeout).
        ``None`` when the status cannot be determined.
    """

    repo_identity: str
    index_status: str
    current_sha: str | None = None
    analyzed_sha: str | None = None
    schema_version: int | None = None
    generator_version: str | None = None
    generated_at: str | None = None
    generation_duration_s: float | None = None
    cache_reused: bool = False
    file_count: int | None = None
    symbol_count: int | None = None
    failure_reason: str | None = None
    prompt_included: bool | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_any_map_in_slug(state_dir: Path, repo_identity: str) -> RepoMap | None:
    """Return the most recently modified map for *repo_identity*, ignoring SHA.

    Used to detect the STALE state: a map exists on the state branch but its
    ``commit_sha`` does not match the current workspace HEAD.

    Returns ``None`` when no map files are found in the slug directory or
    when all candidate files fail to deserialise.
    """
    try:
        slug = repo_map_slug(repo_identity)
    except ValueError:
        return None

    slug_dir = state_dir / ".oompah" / "repo-maps" / slug
    if not slug_dir.is_dir():
        return None

    candidates = sorted(
        slug_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,  # newest first
    )
    for candidate in candidates:
        try:
            import json
            data = json.loads(candidate.read_text(encoding="utf-8"))
            return RepoMap.from_dict(data)
        except Exception:  # noqa: BLE001
            continue
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_repo_map_diagnostics(
    state_dir: Path,
    repo_identity: str,
    current_sha: str | None,
    *,
    generator: "RepoMapGenerator | None" = None,
    last_result: "RepoMapResult | None" = None,  # type: ignore[name-defined]
) -> RepoMapDiagnostics:
    """Query the current index status for a managed project's repository map.

    This function is **fail-open**: it never raises.  If any unexpected
    error occurs during status determination, :data:`STATUS_UNAVAILABLE` is
    returned.

    Status determination order
    --------------------------
    1. If ``last_result`` is supplied and its status is one of
       :data:`STATUS_FAILED` or :data:`STATUS_TIMEOUT`, return that failure
       status (the fresh read might have been wiped or never written).
    2. If ``generator`` is supplied and has a generation in flight for
       ``current_sha``, return :data:`STATUS_GENERATING`.
    3. If a fresh artifact exists on the state branch for ``current_sha``,
       return :data:`STATUS_FRESH`.
    4. If any artifact exists (but for a different SHA), return
       :data:`STATUS_STALE`.
    5. Otherwise return :data:`STATUS_UNAVAILABLE`.

    Parameters
    ----------
    state_dir:
        Root directory of the state-branch checkout.
    repo_identity:
        Canonical URL or opaque identifier for the managed repository.
    current_sha:
        The current workspace HEAD SHA to compare against.  ``None`` means
        the SHA could not be determined; :data:`STATUS_UNAVAILABLE` is
        returned.
    generator:
        Optional :class:`~oompah.repo_map_generator.RepoMapGenerator`
        instance for the project.  When supplied, an in-flight generation
        for ``current_sha`` is reported as :data:`STATUS_GENERATING`.
    last_result:
        Optional :class:`~oompah.repo_map_generator.RepoMapResult` from the
        most recent call to
        :meth:`~oompah.repo_map_generator.RepoMapGenerator.get_or_generate`.
        When supplied, ``generation_duration_s`` and failure details are
        included in the diagnostics.

    Returns
    -------
    RepoMapDiagnostics
        Diagnostic snapshot.  Metadata fields are ``None`` when not
        available.  No source code or credentials are included.
    """
    try:
        return _get_diagnostics_unsafe(
            state_dir=state_dir,
            repo_identity=repo_identity,
            current_sha=current_sha,
            generator=generator,
            last_result=last_result,
        )
    except Exception:  # noqa: BLE001
        logger.debug(
            "repo-map diagnostics failed unexpectedly for %s",
            repo_identity,
            exc_info=True,
        )
        return RepoMapDiagnostics(
            repo_identity=repo_identity,
            index_status=STATUS_UNAVAILABLE,
            current_sha=current_sha,
        )


def _get_diagnostics_unsafe(
    *,
    state_dir: Path,
    repo_identity: str,
    current_sha: str | None,
    generator: "RepoMapGenerator | None",
    last_result: "RepoMapResult | None",  # type: ignore[name-defined]
) -> RepoMapDiagnostics:
    """Inner implementation — wrapped by :func:`get_repo_map_diagnostics`."""
    # Normalise SHA for consistent lookups.
    sha = current_sha.lower().strip() if current_sha else None

    # Import here to avoid circular imports; repo_map_generator imports repo_map.
    from oompah.repo_map_generator import STATUS_FAILED as GEN_FAILED
    from oompah.repo_map_generator import STATUS_TIMEOUT as GEN_TIMEOUT

    # --- 1. Propagate failure information from last_result -----------------
    if last_result is not None and last_result.status in (GEN_FAILED, GEN_TIMEOUT):
        diag_status = (
            STATUS_FAILED if last_result.status == GEN_FAILED else STATUS_TIMEOUT
        )
        return RepoMapDiagnostics(
            repo_identity=repo_identity,
            index_status=diag_status,
            current_sha=sha,
            generation_duration_s=last_result.generation_duration_s,
            failure_reason=last_result.error,
            prompt_included=False,
        )

    # --- 2. In-flight generation -------------------------------------------
    if sha is not None and generator is not None and generator.is_generating(sha):
        return RepoMapDiagnostics(
            repo_identity=repo_identity,
            index_status=STATUS_GENERATING,
            current_sha=sha,
            prompt_included=False,
        )

    # --- 3. Fresh artifact on state branch ---------------------------------
    if sha is not None:
        fresh_map = read_repo_map(
            state_dir, repo_identity, sha, require_fresh=True
        )
        if fresh_map is not None:
            duration = None
            reused = False
            if last_result is not None:
                duration = last_result.generation_duration_s
                reused = last_result.reused
            return RepoMapDiagnostics(
                repo_identity=repo_identity,
                index_status=STATUS_FRESH,
                current_sha=sha,
                analyzed_sha=fresh_map.commit_sha,
                schema_version=fresh_map.schema_version,
                generator_version=fresh_map.generator_version,
                generated_at=fresh_map.generated_at,
                generation_duration_s=duration,
                cache_reused=reused,
                file_count=fresh_map.rendering_metadata.total_files,
                symbol_count=fresh_map.rendering_metadata.total_symbols,
                prompt_included=True,
            )

    # --- 4. Stale artifact -------------------------------------------------
    stale_map = _find_any_map_in_slug(state_dir, repo_identity)
    if stale_map is not None:
        return RepoMapDiagnostics(
            repo_identity=repo_identity,
            index_status=STATUS_STALE,
            current_sha=sha,
            analyzed_sha=stale_map.commit_sha,
            schema_version=stale_map.schema_version,
            generator_version=stale_map.generator_version,
            generated_at=stale_map.generated_at,
            file_count=stale_map.rendering_metadata.total_files,
            symbol_count=stale_map.rendering_metadata.total_symbols,
            prompt_included=False,
        )

    # --- 5. Unavailable ----------------------------------------------------
    return RepoMapDiagnostics(
        repo_identity=repo_identity,
        index_status=STATUS_UNAVAILABLE,
        current_sha=sha,
        prompt_included=False,
    )
