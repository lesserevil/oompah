"""Aider-style ranking and bounded rendering for repository-map artifacts.

This module is the ranking and rendering layer over Tree-sitter extracted tags
(produced by OOMPAH-295).  It forms a directed relationship graph from
definitions and references, ranks important symbols/files using an in-degree
score with task-relevance and seed-file boosts, and renders a stable, compact
textual map within a caller-provided token budget.

Following Aider RepoMap principles:

* Symbols referenced by many other symbols (high in-degree) are ranked first.
* Task-mentioned symbol names and seed files receive explicit score boosts.
* Ties are broken deterministically by ``(file_path, line)`` in ascending
  lexicographic/numerical order.

**Security:** All paths and symbol names in the repo map are untrusted data.
This renderer never accesses the filesystem, never makes network calls, and
explicitly escapes untrusted strings before including them in output.  The
rendered header is labelled ``[UNTRUSTED]`` so consumers know the content
originated from repository source code.

Public API
----------

``RankedEntry``
    Dataclass pairing a :class:`~oompah.repo_map.SymbolTag` with its score.

``rank_symbols(repo_map, *, task_mentions, seed_files) → list[RankedEntry]``
    Return all symbols scored and sorted, highest first.

``render_repo_map(repo_map, token_budget, *, task_mentions, seed_files) → str``
    Return a token-budget-bounded text map of the repository.

``TASK_MENTION_BOOST``
    Score boost applied to task-mentioned symbol names.

``SEED_FILE_BOOST``
    Score boost applied to symbols in seed files.
"""

from __future__ import annotations

import html
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from oompah.repo_map import RepoMap, SymbolTag

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Score boost for symbols whose name appears in *task_mentions*.
TASK_MENTION_BOOST: float = 1000.0

#: Score boost for symbols whose ``file_path`` appears in *seed_files*.
SEED_FILE_BOOST: float = 100.0

# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------


@dataclass
class RankedEntry:
    """A symbol paired with its computed relevance score."""

    #: The symbol tag from the extraction artifact.
    symbol: SymbolTag

    #: Relevance score; higher is more important.
    score: float


# ---------------------------------------------------------------------------
# Helpers (internal)
# ---------------------------------------------------------------------------


def _escape_untrusted(text: str) -> str:
    """Escape *text* for safe inclusion in the rendered map.

    Transformations applied in order:

    1. ``\\r\\n``, standalone ``\\r``, and standalone ``\\n`` are replaced
       with the two-character literal sequence ``\\\\n`` so that injected
       line breaks cannot create new instruction-shaped lines in the output.
    2. HTML-unsafe characters (``<``, ``>``, ``&``) are entity-escaped, which
       prevents ``<script>``-style injection in downstream HTML renderers.
    """
    text = text.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
    return html.escape(text, quote=False)


def _count_tokens(text: str) -> int:
    """Return the number of whitespace-separated words in *text*.

    This is the same conservative token approximation that callers use to
    enforce the public token budget.
    """
    return len(re.findall(r"\S+", text))


# ---------------------------------------------------------------------------
# Rendering constants (computed once at import time)
# ---------------------------------------------------------------------------

#: Header line prepended to every rendered map.
_HEADER: str = "# [UNTRUSTED] repository map"

#: Pre-computed token count for the header line.
_HEADER_TOKENS: int = _count_tokens(_HEADER)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_symbols(
    repo_map: RepoMap,
    *,
    task_mentions: Sequence[str] | None = None,
    seed_files: Sequence[str] | None = None,
) -> list[RankedEntry]:
    """Rank all symbol tags in *repo_map* by relevance, highest score first.

    Scoring algorithm
    ~~~~~~~~~~~~~~~~~

    1. **Base score (in-degree):** Count the number of
       :class:`~oompah.repo_map.RelationshipEdge` records whose ``target``
       field matches the symbol's name.  Symbols referenced by many others
       are structurally more important.
    2. **Task-mention boost:** Add :data:`TASK_MENTION_BOOST` to any symbol
       whose ``name`` appears in *task_mentions* (exact string match).
    3. **Seed-file boost:** Add :data:`SEED_FILE_BOOST` to any symbol whose
       ``file_path`` appears in *seed_files* (exact string match).

    Tie-breaking
    ~~~~~~~~~~~~

    Symbols with identical scores are ordered deterministically by
    ``(file_path, line or 0)`` in ascending lexicographic / numerical order.
    This ensures stable, reproducible output across identical inputs.

    Parameters
    ----------
    repo_map:
        Extraction artifact produced by the Tree-sitter indexer (OOMPAH-295).
    task_mentions:
        Sequence of symbol names mentioned in the current task description.
        Compared with exact string equality.
    seed_files:
        Sequence of repository-relative file paths whose symbols should
        receive a relevance boost.  Compared with exact string equality.

    Returns
    -------
    list[RankedEntry]
        Entries sorted by descending score then ascending ``(file_path, line)``.
    """
    mention_set: set[str] = set(task_mentions) if task_mentions else set()
    seed_set: set[str] = set(seed_files) if seed_files else set()

    # Build in-degree map: count incoming relationship edges per target name.
    in_degree: dict[str, int] = {}
    for edge in repo_map.relationship_edges:
        in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

    entries: list[RankedEntry] = []
    for sym in repo_map.symbol_tags:
        score = float(in_degree.get(sym.name, 0))
        if sym.name in mention_set:
            score += TASK_MENTION_BOOST
        if sym.file_path in seed_set:
            score += SEED_FILE_BOOST
        entries.append(RankedEntry(symbol=sym, score=score))

    # Primary: descending score; secondary: ascending (path, line) for ties.
    entries.sort(
        key=lambda e: (-e.score, e.symbol.file_path, e.symbol.line or 0)
    )
    return entries


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_repo_map(
    repo_map: RepoMap,
    token_budget: int,
    *,
    task_mentions: Sequence[str] | None = None,
    seed_files: Sequence[str] | None = None,
) -> str:
    """Render a bounded, human-readable text map from *repo_map*.

    Format
    ~~~~~~

    ::

        # [UNTRUSTED] repository map
        src/core.py
          function my_function:10
          class MyClass:42

    Symbols within each file are listed in descending relevance order.
    Files are presented in the order of their highest-ranked symbol.

    Guarantees
    ~~~~~~~~~~

    * The rendered output contains at most *token_budget* whitespace-separated
      words (as measured by ``len(re.findall(r'\\S+', text))``).
    * Identical inputs produce identical outputs (deterministic).
    * The output header is labelled ``[UNTRUSTED]`` so consumers know the
      content originated from repository source code.
    * Angle brackets (``<`` / ``>``) and ampersands in file paths and symbol
      names are HTML-entity-escaped.
    * Embedded newlines in any string field are replaced with the two-character
      literal ``\\n`` rather than being emitted as real newlines.
    * No filesystem reads, no network calls, no code evaluation.

    Parameters
    ----------
    repo_map:
        The extraction artifact to render.
    token_budget:
        Maximum number of whitespace-separated tokens permitted in the output.
        Must be a positive integer.
    task_mentions:
        Passed through to :func:`rank_symbols`.
    seed_files:
        Passed through to :func:`rank_symbols`.

    Returns
    -------
    str
        The rendered map, always beginning with the ``[UNTRUSTED]`` header.
        The header alone is always included even if it is the only content.

    Raises
    ------
    ValueError
        If *token_budget* is not a positive integer (≤ 0).
    """
    if token_budget <= 0:
        raise ValueError(
            f"token_budget must be a positive integer, got {token_budget!r}"
        )

    ranked = rank_symbols(
        repo_map, task_mentions=task_mentions, seed_files=seed_files
    )

    # Start with the mandatory header (always emitted).
    lines: list[str] = [_HEADER]
    used_tokens: int = _HEADER_TOKENS

    # Group symbols by file path while preserving descending-score file order
    # (file order is determined by the first-ranked symbol per file).
    file_order: list[str] = []
    file_symbols: dict[str, list[RankedEntry]] = defaultdict(list)
    seen_files: set[str] = set()
    for entry in ranked:
        fp = entry.symbol.file_path
        if fp not in seen_files:
            file_order.append(fp)
            seen_files.add(fp)
        file_symbols[fp].append(entry)

    for file_path in file_order:
        escaped_path = _escape_untrusted(file_path)
        path_cost = _count_tokens(escaped_path)

        # Collect as many symbol lines as fit within the remaining budget.
        sym_lines: list[str] = []
        sym_cost_total: int = 0
        for entry in file_symbols[file_path]:
            sym = entry.symbol
            escaped_name = _escape_untrusted(sym.name)
            sym_line = f"  {sym.kind} {escaped_name}:{sym.line}"
            sym_cost = _count_tokens(sym_line)
            if used_tokens + path_cost + sym_cost_total + sym_cost > token_budget:
                break
            sym_lines.append(sym_line)
            sym_cost_total += sym_cost

        # Only emit a file section when at least one symbol fits.
        if sym_lines:
            lines.append(escaped_path)
            lines.extend(sym_lines)
            used_tokens += path_cost + sym_cost_total

    return "\n".join(lines)
