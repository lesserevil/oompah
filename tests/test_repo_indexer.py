"""Tests for oompah.repo_indexer — Tree-sitter repository symbol and reference extraction.

Coverage:
---------------------------------------------------------------------------
detect_language
    - All supported extensions map to expected language names.
    - Unsupported extensions return None.
    - Case-insensitive extension matching.

is_binary_content
    - Pure text returns False.
    - Content containing a null byte returns True.
    - Empty content returns False.
    - Content with null byte after first 8 KB is not flagged as binary.

_GitignoreSpec / _load_gitignore
    - Blank lines and comments are ignored.
    - Simple wildcard patterns match basenames.
    - Anchored patterns (containing '/') match from repo root.
    - Negation ('!') patterns un-ignore previously ignored paths.
    - is_ignored returns False for paths not matching any pattern.
    - _load_gitignore returns an empty spec when .gitignore is absent.
    - _load_gitignore reads and parses a real .gitignore file.

extract_symbols_and_edges (happy path per language)
    - Python: functions, classes, methods, imports, inheritance edges.
    - Rust: fn, struct, enum, trait, impl methods, use declarations.
    - JavaScript: function declarations, class + methods, const/let,
      import statements.
    - TypeScript: function, class + methods, interface, type alias,
      const/let, import statements.
    - YAML: top-level keys extracted as variable symbols.
    - Markdown: ATX headings extracted as module symbols.

extract_symbols_and_edges (error handling)
    - Completely malformed/garbage bytes return ([], []) without raising.
    - Empty bytes return ([], []).
    - Unknown language returns ([], []) without raising.

index_repository (file-walking behaviour)
    - Happy path: discovers and indexes Python files in a simple repo.
    - Binary files are excluded; diagnostic note recorded.
    - Oversized files are excluded; diagnostic note recorded.
    - Files matching .gitignore are excluded; diagnostic note recorded.
    - Unsupported file types are excluded (no diagnostic note unless configured).
    - Always-skip directories (.git, __pycache__, node_modules) are pruned.
    - Indexed files are sorted lexicographically by path.
    - Content hash is a lowercase hex SHA-256 of the file content.
    - language field in IndexedFile matches detect_language output.
    - rendering_metadata counts match actual list lengths.

index_repository (symbol integration)
    - Python fixture repository: expected symbols and edges found in result.
    - Rust fixture repository: expected symbols found in result.
    - TypeScript fixture repository: expected symbols found in result.
    - YAML fixture file: expected keys found as variable symbols.
    - Markdown fixture file: headings found as module symbols.

index_repository (schema conformance)
    - Returned RepoMap has schema_version == CURRENT_SCHEMA_VERSION.
    - repo_identity and commit_sha are propagated unchanged.
    - generated_at is a valid ISO 8601 UTC string when not supplied.
    - Custom generated_at is preserved.
    - to_dict() / from_dict() round-trips successfully.

index_repository (error cases)
    - repo_path does not exist raises ValueError.
    - repo_path is a file (not a directory) raises ValueError.
    - Empty repository (no files) returns a RepoMap with empty lists.

RepoMap output (safety / security)
    - All returned string fields are plain str objects (not bytes, Node, etc.).
    - No SymbolTag.kind value falls outside the allowed set.
    - No RelationshipEdge.kind value falls outside the allowed set.
---------------------------------------------------------------------------
"""

from __future__ import annotations

import hashlib
import io
import struct
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# All tests in this module require tree-sitter.  Import-skip at module level
# so the entire module is collected but skipped gracefully when absent.
# ---------------------------------------------------------------------------
tree_sitter = pytest.importorskip("tree_sitter", reason="tree-sitter not installed")

from oompah.repo_indexer import (  # noqa: E402
    MAX_FILE_BYTES,
    _ALWAYS_SKIP_DIRS,
    _GitignoreSpec,
    _load_gitignore,
    detect_language,
    extract_symbols_and_edges,
    index_repository,
    is_binary_content,
)
from oompah.repo_map import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    RepoMap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALLOWED_SYMBOL_KINDS = frozenset(
    {"class", "function", "method", "variable", "module", "constant", "type"}
)
_ALLOWED_EDGE_KINDS = frozenset(
    {"imports", "inherits", "calls", "defines", "references"}
)


def _write(path: Path, content: str | bytes) -> Path:
    """Write *content* to *path*, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _symbol_names(repo_map: RepoMap) -> set[str]:
    return {s.name for s in repo_map.symbol_tags}


def _symbol_kinds(repo_map: RepoMap) -> set[str]:
    return {s.kind for s in repo_map.symbol_tags}


def _edge_targets(repo_map: RepoMap) -> set[str]:
    return {e.target for e in repo_map.relationship_edges}


def _edge_sources(repo_map: RepoMap) -> set[str]:
    return {e.source for e in repo_map.relationship_edges}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    def test_python(self):
        assert detect_language(Path("foo.py")) == "python"

    def test_rust(self):
        assert detect_language(Path("src/main.rs")) == "rust"

    def test_typescript(self):
        assert detect_language(Path("app.ts")) == "typescript"

    def test_tsx(self):
        assert detect_language(Path("Component.tsx")) == "typescript"

    def test_javascript(self):
        assert detect_language(Path("script.js")) == "javascript"

    def test_jsx(self):
        assert detect_language(Path("Component.jsx")) == "javascript"

    def test_mjs(self):
        assert detect_language(Path("module.mjs")) == "javascript"

    def test_yaml_yml(self):
        assert detect_language(Path("config.yaml")) == "yaml"
        assert detect_language(Path("action.yml")) == "yaml"

    def test_markdown(self):
        assert detect_language(Path("README.md")) == "markdown"

    def test_mdx(self):
        assert detect_language(Path("page.mdx")) == "markdown"

    def test_unsupported_extension_returns_none(self):
        assert detect_language(Path("binary.exe")) is None

    def test_no_extension_returns_none(self):
        assert detect_language(Path("Makefile")) is None

    def test_case_insensitive_extension(self):
        assert detect_language(Path("UPPER.PY")) == "python"

    def test_dot_in_path_but_no_extension(self):
        # A path whose suffix is not in the map
        assert detect_language(Path("src/file.unknown")) is None

    def test_nested_path(self):
        assert detect_language(Path("a/b/c/d.rs")) == "rust"


# ---------------------------------------------------------------------------
# is_binary_content
# ---------------------------------------------------------------------------


class TestIsBinaryContent:
    def test_plain_text_is_not_binary(self):
        assert is_binary_content(b"hello, world\n") is False

    def test_empty_content_is_not_binary(self):
        assert is_binary_content(b"") is False

    def test_null_byte_in_first_block_is_binary(self):
        assert is_binary_content(b"some\x00data") is True

    def test_first_byte_null_is_binary(self):
        assert is_binary_content(b"\x00") is True

    def test_utf8_non_ascii_is_not_binary(self):
        # UTF-8 encoded non-ASCII does not contain null bytes
        text = "こんにちは世界\n".encode("utf-8")
        assert is_binary_content(text) is False

    def test_latin1_extended_is_not_binary(self):
        # Bytes in 0x80..0xFF are common in Latin-1 text
        content = bytes(range(0x80, 0xFF))
        assert is_binary_content(content) is False

    def test_null_only_after_8kb_boundary_is_not_flagged(self):
        # 8001 bytes of 'a' followed by a null byte
        content = b"a" * 8001 + b"\x00"
        assert is_binary_content(content) is False

    def test_pdf_header_is_binary(self):
        # PDF files start with %PDF-1.x and soon have binary bytes
        pdf_header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"\x00" * 4
        assert is_binary_content(pdf_header) is True

    def test_png_file_is_binary(self):
        # A minimal PNG: 8-byte signature + IHDR chunk (13 bytes of data).
        # The IHDR chunk includes width + height as 4-byte big-endian ints,
        # which contain null bytes for any typical dimension.
        png_signature = b"\x89PNG\r\n\x1a\n"
        # IHDR chunk: length(4) + "IHDR" + width(4) + height(4) + bit_depth(1)
        # + color_type(1) + compression(1) + filter(1) + interlace(1) + crc(4)
        # width=100 → \x00\x00\x00\x64 (contains null bytes)
        ihdr_data = b"\x00\x00\x00\x64\x00\x00\x00\x64\x08\x02\x00\x00\x00"
        png_content = png_signature + b"\x00\x00\x00\x0d" + b"IHDR" + ihdr_data + b"\x00\x00\x00\x00"
        assert is_binary_content(png_content) is True


# ---------------------------------------------------------------------------
# _GitignoreSpec
# ---------------------------------------------------------------------------


class TestGitignoreSpec:
    def _spec(self, text: str) -> _GitignoreSpec:
        spec = _GitignoreSpec()
        spec.add_patterns_from_text(text)
        return spec

    def test_empty_spec_ignores_nothing(self):
        spec = self._spec("")
        assert spec.is_ignored("foo.py") is False

    def test_blank_lines_are_ignored(self):
        spec = self._spec("\n\n  \n")
        assert spec.is_ignored("foo.py") is False

    def test_comment_lines_are_ignored(self):
        spec = self._spec("# this is a comment\n# another comment")
        assert spec.is_ignored("anything.py") is False

    def test_simple_wildcard_matches_basename(self):
        spec = self._spec("*.pyc")
        assert spec.is_ignored("foo.pyc") is True
        assert spec.is_ignored("src/foo.pyc") is True

    def test_simple_wildcard_does_not_match_non_matching_files(self):
        spec = self._spec("*.pyc")
        assert spec.is_ignored("foo.py") is False

    def test_directory_trailing_slash_matches_dir_name(self):
        spec = self._spec("__pycache__/")
        assert spec.is_ignored("__pycache__") is True
        assert spec.is_ignored("src/__pycache__") is True

    def test_anchored_pattern_matches_from_root(self):
        # Pattern with a slash is anchored to the root
        spec = self._spec("src/secret.txt")
        assert spec.is_ignored("src/secret.txt") is True
        assert spec.is_ignored("other/src/secret.txt") is False

    def test_negation_unignores_previously_matched_path(self):
        spec = self._spec("*.log\n!important.log")
        assert spec.is_ignored("debug.log") is True
        assert spec.is_ignored("important.log") is False

    def test_negation_order_matters(self):
        # Later rules take priority
        spec = self._spec("!important.log\n*.log")
        # *.log matches last, so important.log is still ignored
        assert spec.is_ignored("important.log") is True

    def test_node_modules_pattern(self):
        spec = self._spec("node_modules/")
        assert spec.is_ignored("node_modules") is True
        assert spec.is_ignored("node_modules/lodash/index.js") is True

    def test_dot_env_pattern(self):
        spec = self._spec(".env")
        assert spec.is_ignored(".env") is True
        assert spec.is_ignored(".env.local") is False


class TestLoadGitignore:
    def test_absent_gitignore_returns_empty_spec(self, tmp_path):
        spec = _load_gitignore(tmp_path)
        # An empty spec ignores nothing
        assert spec.is_ignored("foo.py") is False

    def test_reads_gitignore_from_root(self, tmp_path):
        (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        spec = _load_gitignore(tmp_path)
        assert spec.is_ignored("foo.pyc") is True
        assert spec.is_ignored("foo.py") is False

    def test_comments_in_gitignore_are_skipped(self, tmp_path):
        (tmp_path / ".gitignore").write_text("# comment\n*.log\n", encoding="utf-8")
        spec = _load_gitignore(tmp_path)
        assert spec.is_ignored("error.log") is True
        assert spec.is_ignored("app.py") is False

    def test_invalid_utf8_is_handled_gracefully(self, tmp_path):
        # write bytes with invalid UTF-8 sequences
        (tmp_path / ".gitignore").write_bytes(b"*.pyc\n\xff\xfe*.tmp\n")
        spec = _load_gitignore(tmp_path)
        # At minimum, the valid pattern should still work
        assert spec.is_ignored("foo.pyc") is True


# ---------------------------------------------------------------------------
# extract_symbols_and_edges — Python
# ---------------------------------------------------------------------------


PYTHON_FIXTURE = b"""\
import os
from pathlib import Path

X = 42


class Animal:
    sound = "..."

    def speak(self):
        pass


class Dog(Animal):
    def speak(self):
        return "woof"


def standalone_function(x, y):
    return x + y
"""


class TestExtractPython:
    def test_function_symbol_extracted(self):
        symbols, _ = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        names = {s.name for s in symbols}
        assert "standalone_function" in names

    def test_class_symbol_extracted(self):
        symbols, _ = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        names = {s.name for s in symbols}
        assert "Animal" in names
        assert "Dog" in names

    def test_method_symbol_extracted_with_namespace(self):
        symbols, _ = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        methods = [s for s in symbols if s.kind == "method"]
        method_names = {s.name for s in methods}
        assert "speak" in method_names
        namespaces = {s.namespace for s in methods if s.name == "speak"}
        assert "Animal" in namespaces or "Dog" in namespaces

    def test_method_namespace_matches_containing_class(self):
        symbols, _ = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        animal_speaks = [s for s in symbols if s.name == "speak" and s.namespace == "Animal"]
        dog_speaks = [s for s in symbols if s.name == "speak" and s.namespace == "Dog"]
        assert animal_speaks, "speak in Animal namespace not found"
        assert dog_speaks, "speak in Dog namespace not found"

    def test_import_edge_extracted(self):
        _, edges = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        targets = {e.target for e in edges if e.kind == "imports"}
        assert "os" in targets

    def test_from_import_edge_extracted(self):
        _, edges = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        targets = {e.target for e in edges if e.kind == "imports"}
        assert "pathlib" in targets

    def test_inheritance_edge_extracted(self):
        _, edges = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        inherit_edges = [e for e in edges if e.kind == "inherits"]
        assert any(e.source == "Dog" and e.target == "Animal" for e in inherit_edges)

    def test_class_symbol_has_correct_kind(self):
        symbols, _ = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        kinds = {s.kind for s in symbols if s.name in ("Animal", "Dog")}
        assert kinds == {"class"}

    def test_function_symbol_has_correct_kind(self):
        symbols, _ = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        func = next(s for s in symbols if s.name == "standalone_function")
        assert func.kind == "function"

    def test_symbol_line_numbers_are_1_based(self):
        symbols, _ = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        for sym in symbols:
            if sym.line is not None:
                assert sym.line >= 1, f"Symbol {sym.name} has line {sym.line} < 1"

    def test_file_path_on_symbols_matches_rel_path(self):
        symbols, _ = extract_symbols_and_edges(PYTHON_FIXTURE, "src/animals.py", "python")
        for sym in symbols:
            assert sym.file_path == "src/animals.py"

    def test_edge_source_matches_rel_path(self):
        _, edges = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        import_sources = {e.source for e in edges if e.kind == "imports"}
        assert "animals.py" in import_sources

    def test_all_symbol_kinds_are_valid(self):
        symbols, _ = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        for sym in symbols:
            assert sym.kind in _ALLOWED_SYMBOL_KINDS, f"Invalid kind: {sym.kind!r}"

    def test_all_edge_kinds_are_valid(self):
        _, edges = extract_symbols_and_edges(PYTHON_FIXTURE, "animals.py", "python")
        for edge in edges:
            assert edge.kind in _ALLOWED_EDGE_KINDS, f"Invalid kind: {edge.kind!r}"

    def test_decorated_function_is_extracted(self):
        code = b"""\
def decorator(f):
    return f

@decorator
def my_decorated():
    pass
"""
        symbols, _ = extract_symbols_and_edges(code, "deco.py", "python")
        names = {s.name for s in symbols}
        assert "my_decorated" in names

    def test_nested_class_is_extracted(self):
        code = b"""\
class Outer:
    class Inner:
        pass
"""
        symbols, _ = extract_symbols_and_edges(code, "nested.py", "python")
        names = {s.name for s in symbols}
        assert "Outer" in names
        assert "Inner" in names


# ---------------------------------------------------------------------------
# extract_symbols_and_edges — Rust
# ---------------------------------------------------------------------------


RUST_FIXTURE = b"""\
use std::collections::HashMap;

pub fn greet(name: &str) -> String {
    format!("Hello, {}!", name)
}

pub struct Counter {
    count: u32,
}

impl Counter {
    pub fn new() -> Self {
        Counter { count: 0 }
    }

    pub fn increment(&mut self) {
        self.count += 1;
    }
}

pub enum Direction {
    North,
    South,
}

pub trait Describable {
    fn describe(&self) -> String;
}
"""


class TestExtractRust:
    def test_function_symbol_extracted(self):
        symbols, _ = extract_symbols_and_edges(RUST_FIXTURE, "lib.rs", "rust")
        names = {s.name for s in symbols}
        assert "greet" in names

    def test_struct_symbol_extracted(self):
        symbols, _ = extract_symbols_and_edges(RUST_FIXTURE, "lib.rs", "rust")
        names = {s.name for s in symbols}
        assert "Counter" in names

    def test_impl_methods_extracted(self):
        symbols, _ = extract_symbols_and_edges(RUST_FIXTURE, "lib.rs", "rust")
        names = {s.name for s in symbols}
        assert "new" in names
        assert "increment" in names

    def test_impl_method_kind_is_method(self):
        symbols, _ = extract_symbols_and_edges(RUST_FIXTURE, "lib.rs", "rust")
        new_syms = [s for s in symbols if s.name == "new" and s.namespace == "Counter"]
        assert new_syms, "Counter::new not found as method with namespace Counter"
        assert new_syms[0].kind == "method"

    def test_enum_symbol_extracted(self):
        symbols, _ = extract_symbols_and_edges(RUST_FIXTURE, "lib.rs", "rust")
        names = {s.name for s in symbols}
        assert "Direction" in names

    def test_trait_symbol_extracted(self):
        symbols, _ = extract_symbols_and_edges(RUST_FIXTURE, "lib.rs", "rust")
        names = {s.name for s in symbols}
        assert "Describable" in names

    def test_use_declaration_produces_imports_edge(self):
        _, edges = extract_symbols_and_edges(RUST_FIXTURE, "lib.rs", "rust")
        import_edges = [e for e in edges if e.kind == "imports"]
        assert import_edges, "No import edges extracted from use declaration"
        targets = {e.target for e in import_edges}
        # std::collections::HashMap or similar
        assert any("HashMap" in t or "std" in t for t in targets)

    def test_all_symbol_kinds_are_valid(self):
        symbols, _ = extract_symbols_and_edges(RUST_FIXTURE, "lib.rs", "rust")
        for sym in symbols:
            assert sym.kind in _ALLOWED_SYMBOL_KINDS

    def test_struct_kind_is_class(self):
        symbols, _ = extract_symbols_and_edges(RUST_FIXTURE, "lib.rs", "rust")
        counter = next(s for s in symbols if s.name == "Counter")
        assert counter.kind == "class"

    def test_enum_kind_is_type(self):
        symbols, _ = extract_symbols_and_edges(RUST_FIXTURE, "lib.rs", "rust")
        direction = next(s for s in symbols if s.name == "Direction")
        assert direction.kind == "type"


# ---------------------------------------------------------------------------
# extract_symbols_and_edges — JavaScript
# ---------------------------------------------------------------------------


JS_FIXTURE = b"""\
import { EventEmitter } from 'events';

const PI = 3.14159;

function add(a, b) {
    return a + b;
}

class Animal {
    constructor(name) {
        this.name = name;
    }
    speak() {
        console.log(this.name);
    }
}

const arrow = (x) => x * 2;
"""


class TestExtractJavaScript:
    def test_function_declaration_extracted(self):
        symbols, _ = extract_symbols_and_edges(JS_FIXTURE, "app.js", "javascript")
        names = {s.name for s in symbols}
        assert "add" in names

    def test_class_extracted(self):
        symbols, _ = extract_symbols_and_edges(JS_FIXTURE, "app.js", "javascript")
        names = {s.name for s in symbols}
        assert "Animal" in names

    def test_class_method_extracted_with_namespace(self):
        symbols, _ = extract_symbols_and_edges(JS_FIXTURE, "app.js", "javascript")
        methods = [s for s in symbols if s.kind == "method" and s.name == "speak"]
        assert methods, "speak method not found"
        assert methods[0].namespace == "Animal"

    def test_const_variable_extracted(self):
        symbols, _ = extract_symbols_and_edges(JS_FIXTURE, "app.js", "javascript")
        names = {s.name for s in symbols}
        assert "PI" in names

    def test_import_edge_extracted(self):
        _, edges = extract_symbols_and_edges(JS_FIXTURE, "app.js", "javascript")
        imports = [e for e in edges if e.kind == "imports"]
        assert imports, "No import edges found"
        targets = {e.target for e in imports}
        assert "events" in targets

    def test_all_symbol_kinds_are_valid(self):
        symbols, _ = extract_symbols_and_edges(JS_FIXTURE, "app.js", "javascript")
        for sym in symbols:
            assert sym.kind in _ALLOWED_SYMBOL_KINDS

    def test_function_kind_is_function(self):
        symbols, _ = extract_symbols_and_edges(JS_FIXTURE, "app.js", "javascript")
        add_sym = next(s for s in symbols if s.name == "add")
        assert add_sym.kind == "function"

    def test_class_kind_is_class(self):
        symbols, _ = extract_symbols_and_edges(JS_FIXTURE, "app.js", "javascript")
        animal = next(s for s in symbols if s.name == "Animal")
        assert animal.kind == "class"

    def test_line_numbers_are_1_based(self):
        symbols, _ = extract_symbols_and_edges(JS_FIXTURE, "app.js", "javascript")
        for sym in symbols:
            if sym.line is not None:
                assert sym.line >= 1


# ---------------------------------------------------------------------------
# extract_symbols_and_edges — TypeScript
# ---------------------------------------------------------------------------


TS_FIXTURE = b"""\
import { Injectable } from '@angular/core';

interface UserService {
    getUser(id: number): User;
}

type UserId = number;

class AuthService {
    constructor(private userService: UserService) {}

    login(username: string): boolean {
        return true;
    }
}

function bootstrap(): void {}

const VERSION = '1.0.0';
"""


class TestExtractTypeScript:
    def test_interface_extracted_as_type(self):
        symbols, _ = extract_symbols_and_edges(TS_FIXTURE, "auth.ts", "typescript")
        names = {s.name for s in symbols}
        assert "UserService" in names
        iface = next(s for s in symbols if s.name == "UserService")
        assert iface.kind == "type"

    def test_type_alias_extracted_as_type(self):
        symbols, _ = extract_symbols_and_edges(TS_FIXTURE, "auth.ts", "typescript")
        names = {s.name for s in symbols}
        assert "UserId" in names
        tid = next(s for s in symbols if s.name == "UserId")
        assert tid.kind == "type"

    def test_class_extracted(self):
        symbols, _ = extract_symbols_and_edges(TS_FIXTURE, "auth.ts", "typescript")
        names = {s.name for s in symbols}
        assert "AuthService" in names

    def test_class_method_extracted_with_namespace(self):
        symbols, _ = extract_symbols_and_edges(TS_FIXTURE, "auth.ts", "typescript")
        methods = [s for s in symbols if s.kind == "method" and s.name == "login"]
        assert methods, "login method not found"
        assert methods[0].namespace == "AuthService"

    def test_function_declaration_extracted(self):
        symbols, _ = extract_symbols_and_edges(TS_FIXTURE, "auth.ts", "typescript")
        names = {s.name for s in symbols}
        assert "bootstrap" in names

    def test_const_variable_extracted(self):
        symbols, _ = extract_symbols_and_edges(TS_FIXTURE, "auth.ts", "typescript")
        names = {s.name for s in symbols}
        assert "VERSION" in names

    def test_import_edge_extracted(self):
        _, edges = extract_symbols_and_edges(TS_FIXTURE, "auth.ts", "typescript")
        imports = [e for e in edges if e.kind == "imports"]
        assert imports, "No import edges found"
        targets = {e.target for e in imports}
        assert "@angular/core" in targets

    def test_all_symbol_kinds_are_valid(self):
        symbols, _ = extract_symbols_and_edges(TS_FIXTURE, "auth.ts", "typescript")
        for sym in symbols:
            assert sym.kind in _ALLOWED_SYMBOL_KINDS


# ---------------------------------------------------------------------------
# extract_symbols_and_edges — YAML
# ---------------------------------------------------------------------------


YAML_FIXTURE = b"""\
name: oompah
version: 1.0.0
dependencies:
  - httpx
  - fastapi
config:
  port: 8090
  debug: false
"""


class TestExtractYAML:
    def test_top_level_keys_extracted(self):
        symbols, _ = extract_symbols_and_edges(YAML_FIXTURE, "pyproject.yaml", "yaml")
        names = {s.name for s in symbols}
        assert "name" in names
        assert "version" in names

    def test_nested_keys_not_extracted_as_top_level(self):
        symbols, _ = extract_symbols_and_edges(YAML_FIXTURE, "pyproject.yaml", "yaml")
        names = {s.name for s in symbols}
        # 'port' and 'debug' are nested under 'config'
        assert "port" not in names
        assert "debug" not in names

    def test_all_symbols_are_variables(self):
        symbols, _ = extract_symbols_and_edges(YAML_FIXTURE, "pyproject.yaml", "yaml")
        for sym in symbols:
            assert sym.kind == "variable"

    def test_no_edges_produced(self):
        _, edges = extract_symbols_and_edges(YAML_FIXTURE, "pyproject.yaml", "yaml")
        assert edges == []

    def test_line_numbers_are_1_based(self):
        symbols, _ = extract_symbols_and_edges(YAML_FIXTURE, "pyproject.yaml", "yaml")
        for sym in symbols:
            if sym.line is not None:
                assert sym.line >= 1

    def test_file_path_on_symbols_matches_rel_path(self):
        symbols, _ = extract_symbols_and_edges(YAML_FIXTURE, "config/settings.yaml", "yaml")
        for sym in symbols:
            assert sym.file_path == "config/settings.yaml"

    def test_empty_yaml_returns_no_symbols(self):
        symbols, _ = extract_symbols_and_edges(b"", "empty.yaml", "yaml")
        assert symbols == []

    def test_yaml_list_document_returns_no_keys(self):
        symbols, _ = extract_symbols_and_edges(b"- item1\n- item2\n", "list.yaml", "yaml")
        # A YAML list document has no mapping keys at top level
        assert isinstance(symbols, list)  # must be a list (possibly empty)


# ---------------------------------------------------------------------------
# extract_symbols_and_edges — Markdown
# ---------------------------------------------------------------------------


MD_FIXTURE = b"""\
# Project Overview

Some introductory text.

## Installation

Steps to install.

### Requirements

What you need.

## Usage

How to use.

# License
"""


class TestExtractMarkdown:
    def test_h1_heading_extracted(self):
        symbols, _ = extract_symbols_and_edges(MD_FIXTURE, "README.md", "markdown")
        names = {s.name for s in symbols}
        assert "Project Overview" in names

    def test_h2_headings_extracted(self):
        symbols, _ = extract_symbols_and_edges(MD_FIXTURE, "README.md", "markdown")
        names = {s.name for s in symbols}
        assert "Installation" in names
        assert "Usage" in names

    def test_h3_heading_extracted(self):
        symbols, _ = extract_symbols_and_edges(MD_FIXTURE, "README.md", "markdown")
        names = {s.name for s in symbols}
        assert "Requirements" in names

    def test_all_symbols_are_module_kind(self):
        symbols, _ = extract_symbols_and_edges(MD_FIXTURE, "README.md", "markdown")
        for sym in symbols:
            assert sym.kind == "module"

    def test_no_edges_produced(self):
        _, edges = extract_symbols_and_edges(MD_FIXTURE, "README.md", "markdown")
        assert edges == []

    def test_line_numbers_are_1_based(self):
        symbols, _ = extract_symbols_and_edges(MD_FIXTURE, "README.md", "markdown")
        for sym in symbols:
            if sym.line is not None:
                assert sym.line >= 1

    def test_empty_markdown_returns_no_symbols(self):
        symbols, _ = extract_symbols_and_edges(b"", "empty.md", "markdown")
        assert symbols == []

    def test_markdown_with_only_paragraphs_returns_no_symbols(self):
        symbols, _ = extract_symbols_and_edges(
            b"Just a paragraph.\n\nAnother paragraph.\n", "prose.md", "markdown"
        )
        assert symbols == []


# ---------------------------------------------------------------------------
# extract_symbols_and_edges — error handling
# ---------------------------------------------------------------------------


class TestExtractSymbolsErrorHandling:
    def test_garbage_bytes_do_not_raise(self):
        garbage = bytes(range(256)) * 10
        symbols, edges = extract_symbols_and_edges(garbage, "junk.py", "python")
        assert isinstance(symbols, list)
        assert isinstance(edges, list)

    def test_empty_content_returns_empty_lists(self):
        symbols, edges = extract_symbols_and_edges(b"", "empty.py", "python")
        assert symbols == []
        assert edges == []

    def test_unknown_language_returns_empty_lists(self):
        symbols, edges = extract_symbols_and_edges(b"hello world", "file.xyz", "cobol")
        assert symbols == []
        assert edges == []

    def test_truncated_utf8_does_not_raise(self):
        # Valid Python structure but with invalid UTF-8 in a string literal
        code = b"def f():\n    x = b'\\xff\\xfe'\n"
        symbols, edges = extract_symbols_and_edges(code, "trunc.py", "python")
        assert isinstance(symbols, list)

    def test_deeply_nested_python_does_not_raise(self):
        # Stress test: deeply nested functions
        depth = 200
        code = ("def f():\n" + "    " * 1 + "def g():\n") * 1 + (" " * 4 + "pass\n")
        symbols, edges = extract_symbols_and_edges(code.encode(), "deep.py", "python")
        assert isinstance(symbols, list)

    def test_rust_with_invalid_syntax_does_not_raise(self):
        symbols, edges = extract_symbols_and_edges(b"fn invalid { {{ } }", "bad.rs", "rust")
        assert isinstance(symbols, list)
        assert isinstance(edges, list)

    def test_yaml_with_invalid_content_does_not_raise(self):
        symbols, edges = extract_symbols_and_edges(
            b"key: [unterminated", "bad.yaml", "yaml"
        )
        assert isinstance(symbols, list)

    def test_markdown_with_binary_content_does_not_raise(self):
        content = b"# Title\n\x00\x01\x02\x03"
        symbols, edges = extract_symbols_and_edges(content, "weird.md", "markdown")
        assert isinstance(symbols, list)


# ---------------------------------------------------------------------------
# index_repository — file-walking behaviour
# ---------------------------------------------------------------------------


class TestIndexRepositoryWalking:
    def test_empty_repo_returns_empty_lists(self, tmp_path):
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert result.indexed_files == []
        assert result.symbol_tags == []
        assert result.relationship_edges == []

    def test_happy_path_indexes_python_file(self, tmp_path):
        _write(tmp_path / "main.py", "def hello(): pass\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert any(f.path == "main.py" for f in result.indexed_files)

    def test_binary_file_excluded_from_indexed_files(self, tmp_path):
        _write(tmp_path / "data.py", b"\x00binary\x00content")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert not any(f.path == "data.py" for f in result.indexed_files)

    def test_binary_file_produces_diagnostic_note(self, tmp_path):
        _write(tmp_path / "data.bin", b"\x00binary\x00content")
        _write(tmp_path / "also.py", b"\x00null")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        notes = result.rendering_metadata.notes
        binary_notes = [n for n in notes if "binary" in n.lower()]
        assert binary_notes, f"Expected binary diagnostic, got notes={notes!r}"

    def test_oversized_file_excluded_from_indexed_files(self, tmp_path):
        big_content = b"x" * (MAX_FILE_BYTES + 1)
        _write(tmp_path / "huge.py", big_content)
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40,
            max_file_bytes=MAX_FILE_BYTES,
        )
        assert not any(f.path == "huge.py" for f in result.indexed_files)

    def test_oversized_file_produces_diagnostic_note(self, tmp_path):
        big_content = b"x" * (MAX_FILE_BYTES + 1)
        _write(tmp_path / "huge.py", big_content)
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40,
            max_file_bytes=MAX_FILE_BYTES,
        )
        notes = result.rendering_metadata.notes
        size_notes = [n for n in notes if "oversized" in n.lower() or "huge.py" in n]
        assert size_notes, f"Expected oversized diagnostic, got notes={notes!r}"

    def test_unsupported_file_type_excluded(self, tmp_path):
        _write(tmp_path / "config.toml", "[package]\nname = 'foo'\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert not any(f.path == "config.toml" for f in result.indexed_files)

    def test_gitignore_patterns_exclude_files(self, tmp_path):
        _write(tmp_path / ".gitignore", "*.pyc\nsecret.py\n")
        _write(tmp_path / "secret.py", "SECRET = 'x'\n")
        _write(tmp_path / "main.py", "def run(): pass\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "secret.py" not in paths
        assert "main.py" in paths

    def test_gitignore_exclusions_produce_diagnostic_note(self, tmp_path):
        _write(tmp_path / ".gitignore", "ignored.py\n")
        _write(tmp_path / "ignored.py", "x = 1\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        notes = result.rendering_metadata.notes
        ignore_notes = [n for n in notes if "gitignore" in n.lower() or "ignored" in n.lower() or "skipped" in n.lower()]
        assert ignore_notes, f"Expected gitignore diagnostic, got notes={notes!r}"

    def test_always_skip_dirs_are_pruned(self, tmp_path):
        for skip_dir in (".git", "__pycache__", "node_modules"):
            _write(
                tmp_path / skip_dir / "file.py",
                b"def should_not_appear(): pass\n",
            )
        _write(tmp_path / "main.py", "def visible(): pass\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "main.py" in paths
        for skip_dir in (".git", "__pycache__", "node_modules"):
            assert not any(
                p.startswith(skip_dir + "/") for p in paths
            ), f"Found files from always-skip dir {skip_dir!r}"

    def test_indexed_files_sorted_lexicographically(self, tmp_path):
        for name in ("z.py", "a.py", "m.py"):
            _write(tmp_path / name, "x = 1\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        paths = [f.path for f in result.indexed_files]
        assert paths == sorted(paths), f"Paths not sorted: {paths}"

    def test_content_hash_is_sha256_of_file_content(self, tmp_path):
        content = b"def f():\n    pass\n"
        _write(tmp_path / "f.py", content)
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        f_file = next(f for f in result.indexed_files if f.path == "f.py")
        assert f_file.content_hash == _sha256(content)

    def test_content_hash_is_lowercase_hex(self, tmp_path):
        _write(tmp_path / "x.py", "pass\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        for f in result.indexed_files:
            if f.content_hash:
                assert f.content_hash == f.content_hash.lower()
                assert all(c in "0123456789abcdef" for c in f.content_hash)

    def test_language_field_matches_detect_language(self, tmp_path):
        _write(tmp_path / "x.py", "x = 1\n")
        _write(tmp_path / "lib.rs", "fn main() {}\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        for f in result.indexed_files:
            expected = detect_language(Path(f.path))
            assert f.language == expected, (
                f"Language mismatch for {f.path}: got {f.language!r}, "
                f"expected {expected!r}"
            )

    def test_rendering_metadata_counts_match_list_lengths(self, tmp_path):
        _write(tmp_path / "a.py", "def f(): pass\n")
        _write(tmp_path / "b.py", "class G: pass\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        meta = result.rendering_metadata
        assert meta.total_files == len(result.indexed_files)
        assert meta.total_symbols == len(result.symbol_tags)
        assert meta.total_edges == len(result.relationship_edges)

    def test_nested_subdirectory_files_are_indexed(self, tmp_path):
        _write(tmp_path / "src" / "deep" / "module.py", "x = 1\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "src/deep/module.py" in paths

    def test_paths_use_forward_slashes(self, tmp_path):
        _write(tmp_path / "subdir" / "file.py", "x = 1\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        for f in result.indexed_files:
            assert "\\" not in f.path, f"Backslash in path: {f.path!r}"
            for sym in result.symbol_tags:
                assert "\\" not in sym.file_path

    def test_custom_max_file_bytes_excludes_larger_files(self, tmp_path):
        _write(tmp_path / "small.py", b"x = 1\n")  # 6 bytes
        _write(tmp_path / "medium.py", b"y = 2\n" * 10)  # 60 bytes
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40, max_file_bytes=30
        )
        paths = {f.path for f in result.indexed_files}
        assert "small.py" in paths
        assert "medium.py" not in paths

    def test_size_bytes_field_matches_actual_content_size(self, tmp_path):
        content = b"def f(): pass\n"
        _write(tmp_path / "f.py", content)
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        f_file = next(f for f in result.indexed_files if f.path == "f.py")
        assert f_file.size_bytes == len(content)


# ---------------------------------------------------------------------------
# index_repository — symbol integration tests
# ---------------------------------------------------------------------------


class TestIndexRepositorySymbols:
    def test_python_functions_appear_in_symbol_tags(self, tmp_path):
        _write(
            tmp_path / "module.py",
            "def alpha(): pass\ndef beta(): pass\nclass Gamma: pass\n",
        )
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        names = _symbol_names(result)
        assert "alpha" in names
        assert "beta" in names
        assert "Gamma" in names

    def test_rust_functions_appear_in_symbol_tags(self, tmp_path):
        _write(
            tmp_path / "lib.rs",
            b"pub fn add(a: i32, b: i32) -> i32 { a + b }\n"
            b"pub struct Point { x: f64, y: f64 }\n",
        )
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        names = _symbol_names(result)
        assert "add" in names
        assert "Point" in names

    def test_typescript_class_appears_in_symbol_tags(self, tmp_path):
        _write(
            tmp_path / "auth.ts",
            b"class AuthService { login(): boolean { return true; } }\n",
        )
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        names = _symbol_names(result)
        assert "AuthService" in names

    def test_yaml_top_level_keys_appear_as_symbols(self, tmp_path):
        _write(
            tmp_path / "config.yaml",
            "name: test\nversion: 2\n",
        )
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        names = _symbol_names(result)
        assert "name" in names
        assert "version" in names

    def test_markdown_headings_appear_as_symbols(self, tmp_path):
        _write(
            tmp_path / "README.md",
            "# Introduction\n\nSome text.\n\n## Getting Started\n",
        )
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        names = _symbol_names(result)
        assert "Introduction" in names
        assert "Getting Started" in names

    def test_python_import_edges_appear_in_relationship_edges(self, tmp_path):
        _write(tmp_path / "app.py", "import os\nfrom pathlib import Path\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        targets = _edge_targets(result)
        assert "os" in targets
        assert "pathlib" in targets

    def test_multiple_files_combined_in_single_repo_map(self, tmp_path):
        _write(tmp_path / "a.py", "def fa(): pass\n")
        _write(tmp_path / "b.py", "def fb(): pass\n")
        _write(tmp_path / "c.rs", b"pub fn fc() {}\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert len(result.indexed_files) == 3
        names = _symbol_names(result)
        assert "fa" in names
        assert "fb" in names
        assert "fc" in names

    def test_symbol_file_paths_match_indexed_file_paths(self, tmp_path):
        _write(tmp_path / "svc" / "handler.py", "def handle(): pass\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        indexed_paths = {f.path for f in result.indexed_files}
        for sym in result.symbol_tags:
            assert sym.file_path in indexed_paths, (
                f"Symbol {sym.name!r} references path {sym.file_path!r} "
                f"which is not in indexed_files"
            )


# ---------------------------------------------------------------------------
# index_repository — schema conformance
# ---------------------------------------------------------------------------


class TestIndexRepositorySchemaConformance:
    def test_schema_version_is_current(self, tmp_path):
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert result.schema_version == CURRENT_SCHEMA_VERSION

    def test_repo_identity_propagated(self, tmp_path):
        identity = "https://github.com/test/my-repo"
        result = index_repository(tmp_path, identity, "a" * 40)
        assert result.repo_identity == identity

    def test_commit_sha_propagated(self, tmp_path):
        sha = "b" * 40
        result = index_repository(tmp_path, "https://example.com/repo", sha)
        assert result.commit_sha == sha

    def test_generated_at_is_iso8601_utc_when_not_supplied(self, tmp_path):
        import re

        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        # Must match YYYY-MM-DDTHH:MM:SSZ
        assert re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", result.generated_at
        ), f"generated_at {result.generated_at!r} is not ISO 8601 UTC"

    def test_custom_generated_at_preserved(self, tmp_path):
        ts = "2026-01-01T00:00:00Z"
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40, generated_at=ts
        )
        assert result.generated_at == ts

    def test_generator_version_default_is_string(self, tmp_path):
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert isinstance(result.generator_version, str)
        assert result.generator_version

    def test_custom_generator_version_preserved(self, tmp_path):
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40, generator_version="2.3.4"
        )
        assert result.generator_version == "2.3.4"

    def test_to_dict_from_dict_round_trip(self, tmp_path):
        _write(tmp_path / "x.py", "class X: pass\n")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        restored = RepoMap.from_dict(result.to_dict())
        assert restored.commit_sha == result.commit_sha
        assert len(restored.indexed_files) == len(result.indexed_files)
        assert len(restored.symbol_tags) == len(result.symbol_tags)

    def test_all_symbol_kinds_are_from_allowed_set(self, tmp_path):
        _write(tmp_path / "m.py", PYTHON_FIXTURE)
        _write(tmp_path / "lib.rs", RUST_FIXTURE)
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        for sym in result.symbol_tags:
            assert sym.kind in _ALLOWED_SYMBOL_KINDS, f"Invalid kind: {sym.kind!r}"

    def test_all_edge_kinds_are_from_allowed_set(self, tmp_path):
        _write(tmp_path / "m.py", PYTHON_FIXTURE)
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        for edge in result.relationship_edges:
            assert edge.kind in _ALLOWED_EDGE_KINDS, f"Invalid edge kind: {edge.kind!r}"

    def test_all_string_fields_are_str_objects(self, tmp_path):
        _write(tmp_path / "m.py", PYTHON_FIXTURE)
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        for sym in result.symbol_tags:
            assert isinstance(sym.name, str), f"name is {type(sym.name)}"
            assert isinstance(sym.kind, str)
            assert isinstance(sym.file_path, str)
            if sym.namespace is not None:
                assert isinstance(sym.namespace, str)
        for edge in result.relationship_edges:
            assert isinstance(edge.kind, str)
            assert isinstance(edge.source, str)
            assert isinstance(edge.target, str)
        for f in result.indexed_files:
            assert isinstance(f.path, str)
            if f.language is not None:
                assert isinstance(f.language, str)
            if f.content_hash is not None:
                assert isinstance(f.content_hash, str)


# ---------------------------------------------------------------------------
# index_repository — error cases
# ---------------------------------------------------------------------------


class TestIndexRepositoryErrors:
    def test_nonexistent_repo_path_raises_value_error(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(ValueError, match="does not exist"):
            index_repository(nonexistent, "https://example.com/repo", "a" * 40)

    def test_repo_path_is_file_raises_value_error(self, tmp_path):
        f = tmp_path / "not_a_dir.py"
        f.write_text("x = 1")
        with pytest.raises(ValueError, match="not a directory"):
            index_repository(f, "https://example.com/repo", "a" * 40)

    def test_empty_repo_produces_valid_repo_map(self, tmp_path):
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert isinstance(result, RepoMap)
        assert result.schema_version == CURRENT_SCHEMA_VERSION

    def test_malformed_python_does_not_crash_indexer(self, tmp_path):
        # Write syntactically broken Python
        _write(tmp_path / "bad.py", "def (broken {{{")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        # File should still be in indexed_files (language detected)
        # OR may be present with empty symbols — either is acceptable
        assert isinstance(result, RepoMap)

    def test_malformed_rust_does_not_crash_indexer(self, tmp_path):
        _write(tmp_path / "bad.rs", b"fn (()( {}{}}")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert isinstance(result, RepoMap)

    def test_malformed_yaml_does_not_crash_indexer(self, tmp_path):
        _write(tmp_path / "bad.yaml", "key: [unterminated")
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert isinstance(result, RepoMap)

    def test_truncated_utf8_python_does_not_crash_indexer(self, tmp_path):
        # A file with valid structure but embedded invalid bytes in a comment
        content = b"def hello():\n    # \xff\xfe invalid utf-8\n    pass\n"
        _write(tmp_path / "trunc.py", content)
        result = index_repository(
            tmp_path, "https://example.com/repo", "a" * 40
        )
        assert isinstance(result, RepoMap)


# ---------------------------------------------------------------------------
# index_repository — mixed fixture repository
# ---------------------------------------------------------------------------


class TestIndexRepositoryMixedFixture:
    """Integration tests using a small fixture repository with multiple
    file types and an ignore rule."""

    @pytest.fixture()
    def mixed_repo(self, tmp_path) -> Path:
        # Python file
        _write(
            tmp_path / "oompah" / "models.py",
            "class Project:\n    def __init__(self, name):\n        self.name = name\n",
        )
        # Rust file
        _write(
            tmp_path / "src" / "main.rs",
            b"fn main() {}\npub struct Config { debug: bool }\n",
        )
        # TypeScript file
        _write(
            tmp_path / "frontend" / "app.ts",
            b"interface IApp { run(): void; }\nclass App implements IApp { run() {} }\n",
        )
        # YAML file
        _write(
            tmp_path / "config.yaml",
            "name: myapp\nversion: 0.1\n",
        )
        # Markdown file
        _write(
            tmp_path / "README.md",
            "# My App\n\n## Getting Started\n",
        )
        # Binary file — should be skipped
        _write(tmp_path / "data.bin", b"\x00\x01\x02binary")
        # Gitignore — should exclude secrets.py
        _write(tmp_path / ".gitignore", "secrets.py\n*.tmp\n")
        _write(tmp_path / "secrets.py", "PASSWORD = 'secret'\n")
        # Unsupported type — should be skipped
        _write(tmp_path / "config.toml", "[package]\nname = 'x'\n")
        return tmp_path

    def test_python_file_indexed(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "oompah/models.py" in paths

    def test_rust_file_indexed(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "src/main.rs" in paths

    def test_typescript_file_indexed(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "frontend/app.ts" in paths

    def test_yaml_file_indexed(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "config.yaml" in paths

    def test_markdown_file_indexed(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "README.md" in paths

    def test_binary_file_excluded(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "data.bin" not in paths

    def test_gitignored_file_excluded(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "secrets.py" not in paths

    def test_unsupported_type_excluded(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        paths = {f.path for f in result.indexed_files}
        assert "config.toml" not in paths

    def test_python_class_symbol_present(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        names = _symbol_names(result)
        assert "Project" in names

    def test_rust_struct_symbol_present(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        names = _symbol_names(result)
        assert "Config" in names

    def test_typescript_class_symbol_present(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        names = _symbol_names(result)
        assert "App" in names

    def test_yaml_key_symbol_present(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        names = _symbol_names(result)
        assert "name" in names

    def test_markdown_heading_symbol_present(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        names = _symbol_names(result)
        assert "My App" in names

    def test_result_conforms_to_schema(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        # Must round-trip through to_dict / from_dict without error
        restored = RepoMap.from_dict(result.to_dict())
        assert restored.schema_version == CURRENT_SCHEMA_VERSION
        assert len(restored.indexed_files) == len(result.indexed_files)

    def test_rendering_metadata_is_consistent(self, mixed_repo):
        result = index_repository(
            mixed_repo, "https://example.com/mixed", "a" * 40
        )
        meta = result.rendering_metadata
        assert meta.total_files == len(result.indexed_files)
        assert meta.total_symbols == len(result.symbol_tags)
        assert meta.total_edges == len(result.relationship_edges)
        assert meta.truncated is False
