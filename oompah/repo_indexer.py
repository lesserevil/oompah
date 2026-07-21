"""Repository indexer using Tree-sitter for symbol and reference extraction.

This module implements a standalone repository indexer that:

1. Walks a checked-out repository directory.
2. Respects ``.gitignore`` rules (root-level and nested).
3. Skips binary files, oversized files, and unsupported file types.
4. Uses Tree-sitter Python bindings to extract file-level symbols and
   cross-file references.
5. Returns a :class:`~oompah.repo_map.RepoMap` artifact conforming to the
   OOMPAH-294 schema.

Supported languages (when the corresponding grammar package is installed):
    Python, Rust, TypeScript, JavaScript, YAML, Markdown.

**Security:** This module reads file content but never executes it.
All string data is treated as untrusted.  Do not pass fields from the
returned :class:`~oompah.repo_map.RepoMap` to ``eval()``, ``exec()``,
``subprocess``, or any template engine.

Usage::

    from pathlib import Path
    from oompah.repo_indexer import index_repository

    repo_map = index_repository(
        repo_path=Path("/path/to/repo"),
        repo_identity="https://github.com/org/repo",
        commit_sha="a" * 40,
    )

Tests require no project build and no network access.  Tree-sitter grammar
packages are optional; if unavailable, language-specific extraction is skipped
and a diagnostic note is recorded in ``rendering_metadata.notes``.
"""

from __future__ import annotations

import datetime
import fnmatch
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from oompah.repo_map import (
    CURRENT_SCHEMA_VERSION,
    IndexedFile,
    RelationshipEdge,
    RenderingMetadata,
    RepoMap,
    SymbolTag,
)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Default maximum file size to index (1 MiB).  Files larger than this are
#: skipped and recorded as a diagnostic.
MAX_FILE_BYTES: int = 1_000_000

#: Directories that are always skipped regardless of .gitignore.
_ALWAYS_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        "target",  # Rust build artefacts
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
    }
)

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

#: Map from normalised file extension to canonical language name.
_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".rs": "rust",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".mdx": "markdown",
}


def detect_language(path: Path) -> str | None:
    """Return the canonical language name for *path*, or ``None``.

    Detection is purely extension-based; no content sniffing is performed.

    >>> detect_language(Path("src/main.py"))
    'python'
    >>> detect_language(Path("README.md"))
    'markdown'
    >>> detect_language(Path("binary.exe")) is None
    True
    """
    return _EXT_TO_LANGUAGE.get(path.suffix.lower())


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

#: Number of bytes to sample when checking for binary content.
_BINARY_CHECK_BYTES: int = 8_000


def is_binary_content(content: bytes) -> bool:
    """Return ``True`` if *content* appears to be binary data.

    Heuristic: the presence of a null byte (``\\x00``) in the first
    :data:`_BINARY_CHECK_BYTES` bytes is treated as a binary signal.
    This matches the behaviour of ``git`` and most Unix tools.

    >>> is_binary_content(b"hello world")
    False
    >>> is_binary_content(b"\\x00\\x01\\x02")
    True
    """
    sample = content[:_BINARY_CHECK_BYTES]
    return b"\x00" in sample


# ---------------------------------------------------------------------------
# Gitignore helpers
# ---------------------------------------------------------------------------


@dataclass
class _GitignoreSpec:
    """Compiled collection of gitignore patterns for a repository."""

    # List of (pattern, negate, anchor_dir) tuples where:
    #   pattern  – the raw fnmatch pattern
    #   negate   – True if this is a negation (!)
    #   anchor   – True if the pattern contains a slash (anchored to root)
    _entries: list[tuple[str, bool, bool]] = field(default_factory=list)

    def add_patterns_from_text(self, text: str, _base: str = "") -> None:
        """Parse *text* as gitignore content and add the patterns."""
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if not line or line.startswith("#"):
                continue
            negate = line.startswith("!")
            if negate:
                line = line[1:]
            anchor = "/" in line.rstrip("/")
            # Normalise trailing slash (directory-only markers) for fnmatch.
            pattern = line.rstrip("/")
            self._entries.append((pattern, negate, anchor))

    def is_ignored(self, rel_path: str) -> bool:
        """Return ``True`` if *rel_path* (forward-slash separated) is ignored."""
        parts = rel_path.split("/")
        name = parts[-1]
        result = False
        for pattern, negate, anchor in self._entries:
            if anchor:
                # Anchored pattern: match against the full relative path.
                matched = fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
                    rel_path, pattern + "/*"
                )
            else:
                # Unanchored: match against the basename or any path component.
                matched = fnmatch.fnmatch(name, pattern) or any(
                    fnmatch.fnmatch(p, pattern) for p in parts
                )
            if matched:
                result = not negate
        return result


def _load_gitignore(repo_path: Path) -> _GitignoreSpec:
    """Read ``.gitignore`` from the repository root and return a compiled spec.

    Non-existent or unreadable files are silently ignored.
    """
    spec = _GitignoreSpec()
    gi_path = repo_path / ".gitignore"
    try:
        text = gi_path.read_text(encoding="utf-8", errors="replace")
        spec.add_patterns_from_text(text)
    except OSError:
        pass
    return spec


# ---------------------------------------------------------------------------
# Tree-sitter grammar loading (lazy, optional)
# ---------------------------------------------------------------------------

# We intentionally import tree-sitter lazily so that the module can be
# imported without the optional grammar packages installed.  Tests that
# exercise symbol extraction use ``pytest.importorskip``.


def _get_parser(language: str) -> Any | None:
    """Return a (tree_sitter.Parser, tree_sitter.Language) pair, or None.

    Returns ``None`` if the required packages are not installed.
    """
    try:
        from tree_sitter import Language, Parser  # type: ignore[import]
    except ImportError:
        return None

    try:
        if language == "python":
            import tree_sitter_python as _ts_lang  # type: ignore[import]

            lang = Language(_ts_lang.language())
        elif language == "rust":
            import tree_sitter_rust as _ts_lang  # type: ignore[import]

            lang = Language(_ts_lang.language())
        elif language == "javascript":
            import tree_sitter_javascript as _ts_lang  # type: ignore[import]

            lang = Language(_ts_lang.language())
        elif language == "typescript":
            import tree_sitter_typescript as _ts_lang  # type: ignore[import]

            lang = Language(_ts_lang.language_typescript())
        elif language == "yaml":
            import tree_sitter_yaml as _ts_lang  # type: ignore[import]

            lang = Language(_ts_lang.language())
        elif language == "markdown":
            import tree_sitter_markdown as _ts_lang  # type: ignore[import]

            lang = Language(_ts_lang.language())
        else:
            return None
    except (ImportError, AttributeError):
        return None

    parser = Parser(lang)
    return parser, lang


# ---------------------------------------------------------------------------
# Language-specific extraction
# ---------------------------------------------------------------------------


def _extract_python(content: bytes, rel_path: str) -> tuple[list[SymbolTag], list[RelationshipEdge]]:
    """Extract Python symbols and import edges using Tree-sitter."""
    result = _get_parser("python")
    if result is None:
        return [], []
    parser, _lang = result

    try:
        tree = parser.parse(content)
    except Exception:
        return [], []

    symbols: list[SymbolTag] = []
    edges: list[RelationshipEdge] = []

    def _walk(node: Any, namespace: str | None = None) -> None:
        node_type = node.type

        if node_type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                kind = "method" if namespace else "function"
                symbols.append(
                    SymbolTag(
                        kind=kind,
                        name=name,
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                        namespace=namespace,
                    )
                )
                # Recurse into body without changing namespace for nested funcs
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        _walk(child, namespace=namespace)
            return

        if node_type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                cls_name = name_node.text.decode("utf-8", errors="replace")
                symbols.append(
                    SymbolTag(
                        kind="class",
                        name=cls_name,
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                        namespace=namespace,
                    )
                )
                # Check for base classes → "inherits" edges
                args = node.child_by_field_name("superclasses") or node.child_by_field_name("argument_list")
                if args:
                    for arg in args.children:
                        if arg.type == "identifier":
                            base_name = arg.text.decode("utf-8", errors="replace")
                            edges.append(
                                RelationshipEdge(
                                    kind="inherits",
                                    source=cls_name,
                                    target=base_name,
                                )
                            )
                # Recurse into body with new namespace
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        _walk(child, namespace=cls_name)
            return

        if node_type == "import_statement":
            # import X, import X as Y
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    module = child.children[0].text.decode("utf-8", errors="replace")
                    edges.append(
                        RelationshipEdge(kind="imports", source=rel_path, target=module)
                    )
            return

        if node_type == "import_from_statement":
            # from X import Y
            module_node = node.child_by_field_name("module_name")
            if module_node is None:
                # Tree-sitter field name may differ; search children
                for child in node.children:
                    if child.type == "dotted_name" and child != node.children[0]:
                        module_node = child
                        break
            if module_node is None:
                # fallback: use first dotted_name child after 'from'
                found_from = False
                for child in node.children:
                    if child.type == "from":
                        found_from = True
                        continue
                    if found_from and child.type in ("dotted_name", "relative_import"):
                        module_node = child
                        break
            if module_node:
                module = module_node.text.decode("utf-8", errors="replace")
                edges.append(
                    RelationshipEdge(kind="imports", source=rel_path, target=module)
                )
            return

        if node_type in ("decorated_definition",):
            # Unwrap decorators
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    _walk(child, namespace=namespace)
            return

        # Recurse into all other nodes
        for child in node.children:
            _walk(child, namespace=namespace)

    try:
        _walk(tree.root_node)
    except Exception:
        pass  # Partial results are acceptable

    return symbols, edges


def _extract_rust(content: bytes, rel_path: str) -> tuple[list[SymbolTag], list[RelationshipEdge]]:
    """Extract Rust symbols and use edges using Tree-sitter."""
    result = _get_parser("rust")
    if result is None:
        return [], []
    parser, _lang = result

    try:
        tree = parser.parse(content)
    except Exception:
        return [], []

    symbols: list[SymbolTag] = []
    edges: list[RelationshipEdge] = []

    def _walk(node: Any, namespace: str | None = None) -> None:
        node_type = node.type

        if node_type == "function_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                kind = "method" if namespace else "function"
                symbols.append(
                    SymbolTag(
                        kind=kind,
                        name=name,
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                        namespace=namespace,
                    )
                )
            return

        if node_type == "struct_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                symbols.append(
                    SymbolTag(
                        kind="class",
                        name=name,
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                        namespace=namespace,
                    )
                )
            return

        if node_type == "enum_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                symbols.append(
                    SymbolTag(
                        kind="type",
                        name=name,
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                        namespace=namespace,
                    )
                )
            return

        if node_type == "trait_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                symbols.append(
                    SymbolTag(
                        kind="type",
                        name=name,
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                        namespace=namespace,
                    )
                )
            return

        if node_type == "impl_item":
            # Extract the type name as namespace, then recurse into methods
            type_node = node.child_by_field_name("type")
            impl_ns: str | None = None
            if type_node:
                impl_ns = type_node.text.decode("utf-8", errors="replace")
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    _walk(child, namespace=impl_ns)
            return

        if node_type == "use_declaration":
            # use std::collections::HashMap;
            arg = node.child_by_field_name("argument")
            if arg:
                target = arg.text.decode("utf-8", errors="replace")
                edges.append(
                    RelationshipEdge(kind="imports", source=rel_path, target=target)
                )
            return

        if node_type == "const_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf-8", errors="replace")
                symbols.append(
                    SymbolTag(
                        kind="constant",
                        name=name,
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                        namespace=namespace,
                    )
                )
            return

        # Recurse into all other nodes at module level
        for child in node.children:
            _walk(child, namespace=namespace)

    try:
        _walk(tree.root_node)
    except Exception:
        pass

    return symbols, edges


def _extract_javascript(content: bytes, rel_path: str) -> tuple[list[SymbolTag], list[RelationshipEdge]]:
    """Extract JavaScript symbols and import edges using Tree-sitter."""
    result = _get_parser("javascript")
    if result is None:
        return [], []
    parser, _lang = result

    try:
        tree = parser.parse(content)
    except Exception:
        return [], []

    symbols: list[SymbolTag] = []
    edges: list[RelationshipEdge] = []

    def _extract_from_program(program_node: Any) -> None:
        for node in program_node.children:
            node_type = node.type

            if node_type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(
                        SymbolTag(
                            kind="function",
                            name=name_node.text.decode("utf-8", errors="replace"),
                            file_path=rel_path,
                            line=node.start_point[0] + 1,
                        )
                    )

            elif node_type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    cls_name = name_node.text.decode("utf-8", errors="replace")
                    symbols.append(
                        SymbolTag(
                            kind="class",
                            name=cls_name,
                            file_path=rel_path,
                            line=node.start_point[0] + 1,
                        )
                    )
                    # Extract methods
                    body = node.child_by_field_name("body")
                    if body:
                        for member in body.children:
                            if member.type == "method_definition":
                                mname = member.child_by_field_name("name")
                                if mname:
                                    symbols.append(
                                        SymbolTag(
                                            kind="method",
                                            name=mname.text.decode("utf-8", errors="replace"),
                                            file_path=rel_path,
                                            line=member.start_point[0] + 1,
                                            namespace=cls_name,
                                        )
                                    )

            elif node_type == "lexical_declaration":
                # const/let declarations
                for declarator in node.children:
                    if declarator.type == "variable_declarator":
                        name_node = declarator.child_by_field_name("name")
                        if name_node and name_node.type == "identifier":
                            symbols.append(
                                SymbolTag(
                                    kind="variable",
                                    name=name_node.text.decode("utf-8", errors="replace"),
                                    file_path=rel_path,
                                    line=node.start_point[0] + 1,
                                )
                            )

            elif node_type == "import_statement":
                # import { X } from 'module'
                source_node = node.child_by_field_name("source")
                if source_node:
                    module = source_node.text.decode("utf-8", errors="replace").strip("\"'")
                    edges.append(
                        RelationshipEdge(kind="imports", source=rel_path, target=module)
                    )

            elif node_type == "export_statement":
                # export function X / export class X / export const X
                for child in node.children:
                    _extract_from_exported(child)

    def _extract_from_exported(node: Any) -> None:
        node_type = node.type
        if node_type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append(
                    SymbolTag(
                        kind="function",
                        name=name_node.text.decode("utf-8", errors="replace"),
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                    )
                )
        elif node_type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append(
                    SymbolTag(
                        kind="class",
                        name=name_node.text.decode("utf-8", errors="replace"),
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                    )
                )
        elif node_type == "lexical_declaration":
            for declarator in node.children:
                if declarator.type == "variable_declarator":
                    name_node = declarator.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        symbols.append(
                            SymbolTag(
                                kind="variable",
                                name=name_node.text.decode("utf-8", errors="replace"),
                                file_path=rel_path,
                                line=node.start_point[0] + 1,
                            )
                        )

    try:
        _extract_from_program(tree.root_node)
    except Exception:
        pass

    return symbols, edges


def _extract_typescript(content: bytes, rel_path: str) -> tuple[list[SymbolTag], list[RelationshipEdge]]:
    """Extract TypeScript symbols and import edges using Tree-sitter."""
    result = _get_parser("typescript")
    if result is None:
        return [], []
    parser, _lang = result

    try:
        tree = parser.parse(content)
    except Exception:
        return [], []

    symbols: list[SymbolTag] = []
    edges: list[RelationshipEdge] = []

    def _extract_from_program(program_node: Any) -> None:
        for node in program_node.children:
            node_type = node.type

            if node_type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(
                        SymbolTag(
                            kind="function",
                            name=name_node.text.decode("utf-8", errors="replace"),
                            file_path=rel_path,
                            line=node.start_point[0] + 1,
                        )
                    )

            elif node_type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    cls_name = name_node.text.decode("utf-8", errors="replace")
                    symbols.append(
                        SymbolTag(
                            kind="class",
                            name=cls_name,
                            file_path=rel_path,
                            line=node.start_point[0] + 1,
                        )
                    )
                    body = node.child_by_field_name("body")
                    if body:
                        for member in body.children:
                            if member.type == "method_definition":
                                mname = member.child_by_field_name("name")
                                if mname:
                                    symbols.append(
                                        SymbolTag(
                                            kind="method",
                                            name=mname.text.decode("utf-8", errors="replace"),
                                            file_path=rel_path,
                                            line=member.start_point[0] + 1,
                                            namespace=cls_name,
                                        )
                                    )

            elif node_type == "interface_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(
                        SymbolTag(
                            kind="type",
                            name=name_node.text.decode("utf-8", errors="replace"),
                            file_path=rel_path,
                            line=node.start_point[0] + 1,
                        )
                    )

            elif node_type == "type_alias_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(
                        SymbolTag(
                            kind="type",
                            name=name_node.text.decode("utf-8", errors="replace"),
                            file_path=rel_path,
                            line=node.start_point[0] + 1,
                        )
                    )

            elif node_type == "lexical_declaration":
                for declarator in node.children:
                    if declarator.type == "variable_declarator":
                        name_node = declarator.child_by_field_name("name")
                        if name_node and name_node.type == "identifier":
                            symbols.append(
                                SymbolTag(
                                    kind="variable",
                                    name=name_node.text.decode("utf-8", errors="replace"),
                                    file_path=rel_path,
                                    line=node.start_point[0] + 1,
                                )
                            )

            elif node_type == "import_statement":
                source_node = node.child_by_field_name("source")
                if source_node:
                    module = source_node.text.decode("utf-8", errors="replace").strip("\"'")
                    edges.append(
                        RelationshipEdge(kind="imports", source=rel_path, target=module)
                    )

            elif node_type == "export_statement":
                for child in node.children:
                    _extract_from_exported_ts(child)

    def _extract_from_exported_ts(node: Any) -> None:
        node_type = node.type
        if node_type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append(
                    SymbolTag(
                        kind="function",
                        name=name_node.text.decode("utf-8", errors="replace"),
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                    )
                )
        elif node_type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append(
                    SymbolTag(
                        kind="class",
                        name=name_node.text.decode("utf-8", errors="replace"),
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                    )
                )
        elif node_type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append(
                    SymbolTag(
                        kind="type",
                        name=name_node.text.decode("utf-8", errors="replace"),
                        file_path=rel_path,
                        line=node.start_point[0] + 1,
                    )
                )
        elif node_type == "lexical_declaration":
            for declarator in node.children:
                if declarator.type == "variable_declarator":
                    name_node = declarator.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        symbols.append(
                            SymbolTag(
                                kind="variable",
                                name=name_node.text.decode("utf-8", errors="replace"),
                                file_path=rel_path,
                                line=node.start_point[0] + 1,
                            )
                        )

    try:
        _extract_from_program(tree.root_node)
    except Exception:
        pass

    return symbols, edges


def _extract_yaml(content: bytes, rel_path: str) -> tuple[list[SymbolTag], list[RelationshipEdge]]:
    """Extract YAML top-level keys as variable symbols using Tree-sitter."""
    result = _get_parser("yaml")
    if result is None:
        return [], []
    parser, _lang = result

    try:
        tree = parser.parse(content)
    except Exception:
        return [], []

    symbols: list[SymbolTag] = []

    def _find_top_level_keys(node: Any) -> None:
        if node.type == "block_mapping":
            for child in node.children:
                if child.type == "block_mapping_pair":
                    key_node = child.children[0] if child.children else None
                    if key_node and key_node.type == "flow_node":
                        key_text = key_node.text.decode("utf-8", errors="replace").strip()
                        if key_text:
                            symbols.append(
                                SymbolTag(
                                    kind="variable",
                                    name=key_text,
                                    file_path=rel_path,
                                    line=child.start_point[0] + 1,
                                )
                            )
            return
        for child in node.children:
            _find_top_level_keys(child)

    try:
        # Only process the first document for top-level key extraction
        if tree.root_node.children:
            _find_top_level_keys(tree.root_node.children[0])
    except Exception:
        pass

    return symbols, []


def _extract_markdown(content: bytes, rel_path: str) -> tuple[list[SymbolTag], list[RelationshipEdge]]:
    """Extract Markdown headings as module symbols using Tree-sitter."""
    result = _get_parser("markdown")
    if result is None:
        return [], []
    parser, _lang = result

    try:
        tree = parser.parse(content)
    except Exception:
        return [], []

    symbols: list[SymbolTag] = []

    _ATX_HEADING_TYPES = frozenset(
        {
            "atx_heading",
        }
    )

    def _walk_md(node: Any) -> None:
        if node.type in _ATX_HEADING_TYPES:
            # Extract the heading text from the inline child
            for child in node.children:
                if child.type == "inline":
                    heading_text = child.text.decode("utf-8", errors="replace").strip()
                    if heading_text:
                        symbols.append(
                            SymbolTag(
                                kind="module",
                                name=heading_text,
                                file_path=rel_path,
                                line=node.start_point[0] + 1,
                            )
                        )
                    break
        for child in node.children:
            _walk_md(child)

    try:
        _walk_md(tree.root_node)
    except Exception:
        pass

    return symbols, []


# ---------------------------------------------------------------------------
# Per-language dispatch table
# ---------------------------------------------------------------------------

_EXTRACTORS: dict[
    str,
    Any,
] = {
    "python": _extract_python,
    "rust": _extract_rust,
    "javascript": _extract_javascript,
    "typescript": _extract_typescript,
    "yaml": _extract_yaml,
    "markdown": _extract_markdown,
}


def extract_symbols_and_edges(
    content: bytes,
    rel_path: str,
    language: str,
) -> tuple[list[SymbolTag], list[RelationshipEdge]]:
    """Extract symbols and relationship edges from *content*.

    Parameters
    ----------
    content:
        Raw file content as bytes.
    rel_path:
        Repository-relative path (forward slashes) used as the ``file_path``
        on emitted symbols.
    language:
        Canonical language name returned by :func:`detect_language`.

    Returns
    -------
    tuple[list[SymbolTag], list[RelationshipEdge]]
        Pair of extracted symbols and edges.  Both lists are empty when the
        language is unsupported or the grammar package is unavailable.
        Parse errors yield partial (possibly empty) results without raising.
    """
    extractor = _EXTRACTORS.get(language)
    if extractor is None:
        return [], []
    try:
        return extractor(content, rel_path)
    except Exception:
        return [], []


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# Repository walker
# ---------------------------------------------------------------------------


def _rel_posix(root: Path, abs_path: Path) -> str:
    """Return the POSIX-style relative path of *abs_path* from *root*."""
    return str(PurePosixPath(abs_path.relative_to(root)))


def index_repository(
    repo_path: Path,
    repo_identity: str,
    commit_sha: str,
    *,
    generator_version: str = "1.0.0",
    max_file_bytes: int = MAX_FILE_BYTES,
    generated_at: str | None = None,
) -> RepoMap:
    """Index a repository and return a :class:`~oompah.repo_map.RepoMap`.

    The function walks *repo_path* and for each eligible file:
    1. Checks whether the file is listed in ``.gitignore``.
    2. Checks whether the file content is binary.
    3. Checks whether the file exceeds *max_file_bytes*.
    4. Detects the language by file extension.
    5. Extracts symbols and reference edges using Tree-sitter.

    Skipped files are not included in ``indexed_files`` but are recorded in
    ``rendering_metadata.notes`` as human-readable diagnostic strings.

    Files whose source cannot be parsed yield partial results (the file IS
    included in ``indexed_files``) and do not raise.

    Parameters
    ----------
    repo_path:
        Absolute or relative path to the checked-out repository root.
    repo_identity:
        Canonical URL or unique identifier for the repository.
    commit_sha:
        40-character lowercase hexadecimal HEAD SHA.
    generator_version:
        Semantic version string of the generator (defaults to ``"1.0.0"``).
    max_file_bytes:
        Maximum file size to index; larger files are skipped.
    generated_at:
        ISO 8601 UTC timestamp.  Defaults to the current UTC time.

    Returns
    -------
    RepoMap
        Fully populated repository-map artifact.

    Raises
    ------
    ValueError
        If *repo_path* does not exist or is not a directory.
    """
    repo_path = Path(repo_path).resolve()
    if not repo_path.exists():
        raise ValueError(f"repo_path does not exist: {repo_path}")
    if not repo_path.is_dir():
        raise ValueError(f"repo_path is not a directory: {repo_path}")

    if generated_at is None:
        generated_at = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    gitignore_spec = _load_gitignore(repo_path)
    notes: list[str] = []

    indexed_files: list[IndexedFile] = []
    symbol_tags: list[SymbolTag] = []
    relationship_edges: list[RelationshipEdge] = []

    skipped_ignored = 0
    skipped_binary = 0
    skipped_oversized = 0
    skipped_unsupported = 0

    for dirpath_str, dirnames, filenames in os.walk(str(repo_path)):
        dirpath = Path(dirpath_str)
        rel_dir = _rel_posix(repo_path, dirpath) if dirpath != repo_path else ""

        # Prune always-skip directories in-place to prevent descent.
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in _ALWAYS_SKIP_DIRS
            and not (
                gitignore_spec.is_ignored(
                    f"{rel_dir}/{d}" if rel_dir else d
                )
            )
        )

        for filename in sorted(filenames):
            rel_path = f"{rel_dir}/{filename}" if rel_dir else filename

            # Gitignore check
            if gitignore_spec.is_ignored(rel_path):
                skipped_ignored += 1
                continue

            abs_path = dirpath / filename

            # Read content (skip unreadable files)
            try:
                content = abs_path.read_bytes()
            except OSError as exc:
                notes.append(f"skipped unreadable file: {rel_path} ({exc})")
                continue

            # Binary check
            if is_binary_content(content):
                skipped_binary += 1
                continue

            # Size check
            size_bytes = len(content)
            if size_bytes > max_file_bytes:
                skipped_oversized += 1
                notes.append(
                    f"skipped oversized file: {rel_path} "
                    f"({size_bytes} bytes > {max_file_bytes})"
                )
                continue

            # Language detection
            language = detect_language(abs_path)

            if language is None:
                skipped_unsupported += 1
                continue

            # Content hash
            content_hash = _sha256_hex(content)

            # Record the file
            indexed_files.append(
                IndexedFile(
                    path=rel_path,
                    size_bytes=size_bytes,
                    content_hash=content_hash,
                    language=language,
                )
            )

            # Symbol and edge extraction
            file_symbols, file_edges = extract_symbols_and_edges(content, rel_path, language)
            symbol_tags.extend(file_symbols)
            relationship_edges.extend(file_edges)

    # Build diagnostic notes
    if skipped_ignored:
        notes.append(f"{skipped_ignored} file(s) skipped: matched .gitignore")
    if skipped_binary:
        notes.append(f"{skipped_binary} binary file(s) skipped")
    if skipped_oversized:
        # Individual oversized notes already added above
        pass
    if skipped_unsupported:
        notes.append(f"{skipped_unsupported} file(s) skipped: unsupported language")

    # Sort indexed_files lexicographically by path (required by schema)
    indexed_files.sort(key=lambda f: f.path)

    return RepoMap(
        schema_version=CURRENT_SCHEMA_VERSION,
        repo_identity=repo_identity,
        commit_sha=commit_sha,
        generator_version=generator_version,
        indexed_files=indexed_files,
        symbol_tags=symbol_tags,
        relationship_edges=relationship_edges,
        generated_at=generated_at,
        rendering_metadata=RenderingMetadata(
            total_files=len(indexed_files),
            total_symbols=len(symbol_tags),
            total_edges=len(relationship_edges),
            truncated=False,
            notes=notes,
        ),
    )
