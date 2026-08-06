"""Static regression for the dispatch timing Mapping test contract."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from tests.tick_test_support import tick_dispatch_mock


_TARGET = "_handle_dispatch_needed"
_HELPER = "tick_dispatch_mock"
_HELPER_MODULE = "tests.tick_test_support"


def _contains_target(node: ast.AST) -> bool:
    return any(
        isinstance(candidate, ast.Attribute) and candidate.attr == _TARGET
        for candidate in ast.walk(node)
    )


def _helper_call(node: ast.AST | None) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _HELPER
    )


def _exact_helper_import(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.ImportFrom)
        and node.module == _HELPER_MODULE
        and any(alias.name == _HELPER and alias.asname is None for alias in node.names)
    )


def _helper_is_shadowed(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == _HELPER:
                return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = node.args
            if any(
                argument.arg == _HELPER
                for argument in (
                    *arguments.posonlyargs,
                    *arguments.args,
                    *arguments.kwonlyargs,
                )
            ):
                return True
            if arguments.vararg and arguments.vararg.arg == _HELPER:
                return True
            if arguments.kwarg and arguments.kwarg.arg == _HELPER:
                return True
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id == _HELPER:
                return True
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                if bound == _HELPER and not _exact_helper_import(node):
                    return True
    return False


def _call_argument(node: ast.Call, position: int, *names: str) -> ast.AST | None:
    if position < len(node.args):
        return node.args[position]
    return next(
        (keyword.value for keyword in node.keywords if keyword.arg in names),
        None,
    )


def _resolved_strings(
    node: ast.AST | None,
    bindings: dict[str, frozenset[str]],
) -> frozenset[str] | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return frozenset({node.value})
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolved_strings(node.left, bindings)
        right = _resolved_strings(node.right, bindings)
        if left is None or right is None or len(left) * len(right) > 256:
            return None
        return frozenset(
            left_value + right_value
            for left_value in left
            for right_value in right
        )
    return None


def _string_bindings(tree: ast.Module) -> dict[str, frozenset[str]]:
    """Resolve exact simple string assignments without guessing at builders."""

    assignments: dict[str, list[ast.AST]] = {}
    simple_target_ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                assignments.setdefault(target.id, []).append(node.value)
                simple_target_ids.add(id(target))

    # A second binding surface makes global static resolution ambiguous. This
    # includes augmented/destructuring/loop bindings, parameters, definitions,
    # and imports in any scope; ambiguity must not turn into a safe patch path.
    tainted = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, (ast.Store, ast.Del))
        and id(node) not in simple_target_ids
    }
    tainted.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            tainted.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            tainted.update(
                alias.asname or alias.name.split(".", 1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ExceptHandler) and node.name:
            tainted.add(node.name)
    for name in tainted:
        assignments.pop(name, None)

    bindings: dict[str, frozenset[str]] = {}
    changed = True
    while changed:
        changed = False
        for name, values in assignments.items():
            resolved = [_resolved_strings(value, bindings) for value in values]
            # One opaque assignment makes the name ambiguous. Keeping it out
            # of the binding map ensures patch targets using it fail closed.
            if any(value is None for value in resolved):
                continue
            combined = frozenset(
                item for possible in resolved if possible is not None for item in possible
            )
            if combined and bindings.get(name) != combined:
                bindings[name] = combined
                changed = True
    return bindings


def _mentions_target(node: ast.AST | None) -> bool:
    return node is not None and any(
        isinstance(candidate, ast.Constant)
        and isinstance(candidate.value, str)
        and _TARGET in candidate.value
        for candidate in ast.walk(node)
    )


def _dispatch_context(tree: ast.Module) -> tuple[set[str], set[str]]:
    receivers = {
        ast.dump(node.value, include_attributes=False)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == _TARGET
    }
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if node.value is not None and _contains_target(node.value):
            aliases.update(target.id for target in targets if isinstance(target, ast.Name))
    return receivers, aliases


def _attribute_path(node: ast.AST) -> tuple[str, ...] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return tuple(reversed(parts))


def _resolved_module_path(
    node: ast.AST,
    module_names: dict[str, tuple[str, ...]],
) -> tuple[str, ...] | None:
    path = _attribute_path(node)
    if path is None:
        return None
    module_path = module_names.get(path[0])
    return (*module_path, *path[1:]) if module_path is not None else None


def _patch_operation(
    function: ast.AST,
    operation_names: dict[str, str],
    module_names: dict[str, tuple[str, ...]],
) -> str | None:
    path = _attribute_path(function)
    if path is None:
        return None
    named_operation = operation_names.get(path[0])
    if named_operation is not None:
        if len(path) == 1:
            return named_operation
        if named_operation == "patch" and len(path) == 2:
            return path[1] if path[1] in {"object", "multiple"} else None
        return None

    resolved = _resolved_module_path(function, module_names)
    if resolved == ("unittest", "mock", "patch"):
        return "patch"
    if resolved in {
        ("unittest", "mock", "patch", "object"),
        ("unittest", "mock", "patch", "multiple"),
    }:
        return resolved[-1]
    return None


def _patch_bindings(
    tree: ast.Module,
) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """Resolve unittest.mock modules and patch operations to a fixed point."""

    operation_names: dict[str, str] = {}
    module_names: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "unittest.mock":
                operation_names.update(
                    {
                        alias.asname or alias.name: "patch"
                        for alias in node.names
                        if alias.name == "patch"
                    }
                )
            elif node.module == "unittest":
                module_names.update(
                    {
                        alias.asname or alias.name: ("unittest", "mock")
                        for alias in node.names
                        if alias.name == "mock"
                    }
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "unittest.mock":
                    module_names[alias.asname or "unittest"] = (
                        ("unittest", "mock")
                        if alias.asname
                        else ("unittest",)
                    )
                elif alias.name == "unittest":
                    module_names[alias.asname or "unittest"] = ("unittest",)

    # Follow module aliases (``m2 = mock``) and operation aliases
    # (``replace = patch.object``) together so arbitrary simple chains resolve.
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                resolved_module = _resolved_module_path(value, module_names)
                if (
                    resolved_module in {("unittest",), ("unittest", "mock")}
                    and module_names.get(target.id) != resolved_module
                ):
                    module_names[target.id] = resolved_module
                    changed = True
                operation = _patch_operation(
                    value, operation_names, module_names
                )
                if (
                    operation is not None
                    and operation_names.get(target.id) != operation
                ):
                    operation_names[target.id] = operation
                    changed = True
    return operation_names, module_names


def _helper_aliases(tree: ast.Module) -> set[str]:
    aliases: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is None or not (
                _helper_call(value)
                or (isinstance(value, ast.Name) and value.id in aliases)
            ):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases.add(target.id)
                    changed = True
    return aliases


def _uses_helper_value(node: ast.AST | None, helper_aliases: set[str]) -> bool:
    return node is not None and any(
        _helper_call(candidate)
        or (
            isinstance(candidate, ast.Name)
            and isinstance(candidate.ctx, ast.Load)
            and candidate.id in helper_aliases
        )
        for candidate in ast.walk(node)
    )


def _identifier_words(node: ast.AST | None) -> set[str]:
    words: set[str] = set()
    if node is None:
        return words
    for candidate in ast.walk(node):
        identifier = (
            candidate.id
            if isinstance(candidate, ast.Name)
            else candidate.attr if isinstance(candidate, ast.Attribute) else None
        )
        if identifier is not None:
            words.update(part for part in identifier.casefold().split("_") if part)
    return words


def _plausible_handler_receiver(
    owner: ast.AST | None,
    receivers: set[str],
) -> bool:
    if owner is None:
        return False
    if _contains_target(owner):
        return True
    if ast.dump(owner, include_attributes=False) in receivers:
        return True
    return bool(_identifier_words(owner) & {"orch", "orchestrator"})


def _provably_unrelated_receiver(owner: ast.AST | None) -> bool:
    path = _attribute_path(owner) if owner is not None else None
    if path is None:
        return False
    root = path[0].casefold().strip("_")
    return root in {"cfg", "config", "issue", "settings", "task"}


def _call_mutates_target(
    node: ast.Call,
    receivers: set[str],
    aliases: set[str],
    operation_names: dict[str, str],
    module_names: dict[str, tuple[str, ...]],
    helper_aliases: set[str],
    string_bindings: dict[str, frozenset[str]],
    *,
    module_exercises_target: bool,
) -> bool:
    function = node.func
    values = [*node.args, *(keyword.value for keyword in node.keywords)]
    if isinstance(function, ast.Attribute) and function.attr in {
        "configure_mock",
        "reset_mock",
    }:
        owner = function.value
        return (
            _contains_target(owner)
            or (isinstance(owner, ast.Name) and owner.id in aliases)
            or any(_contains_target(value) for value in values)
        )

    patch_operation = _patch_operation(function, operation_names, module_names)
    if patch_operation == "multiple":
        owner = _call_argument(node, 0, "target")
        return any(
            keyword.arg == _TARGET
            or (
                keyword.arg is None
                and (
                    _mentions_target(keyword.value)
                    or _uses_helper_value(keyword.value, helper_aliases)
                    or (
                        module_exercises_target
                        and not _provably_unrelated_receiver(owner)
                    )
                )
            )
            for keyword in node.keywords
        )

    direct_patch = patch_operation == "patch"
    keyword_names = {keyword.arg for keyword in node.keywords}
    string_setattr = (
        isinstance(function, ast.Attribute)
        and function.attr == "setattr"
        and (
            (len(node.args) == 2 and "name" not in keyword_names)
            or ("target" in keyword_names and "name" not in keyword_names)
        )
    )
    direct_patch = direct_patch or string_setattr
    object_mutator = (
        isinstance(function, ast.Name) and function.id in {"setattr", "delattr"}
    ) or (
        isinstance(function, ast.Attribute)
        and function.attr in {"setattr", "delattr"}
    )
    object_mutator = object_mutator or patch_operation == "object"
    if not direct_patch and not object_mutator:
        return False

    owner: ast.AST | None = None
    if direct_patch:
        attribute = _call_argument(node, 0, "target")
    else:
        owner = _call_argument(node, 0, "obj", "object", "target")
        attribute = _call_argument(node, 1, "name", "attribute")
        if owner is not None and _contains_target(owner):
            return True

    resolved_targets = _resolved_strings(attribute, string_bindings)
    if resolved_targets is not None:
        return any(
            value == _TARGET or value.endswith(f".{_TARGET}")
            for value in resolved_targets
        )
    if _mentions_target(attribute):
        return True
    if any(_uses_helper_value(value, helper_aliases) for value in values):
        return True
    if module_exercises_target:
        if direct_patch or _plausible_handler_receiver(owner, receivers):
            return True
        if not _provably_unrelated_receiver(owner):
            return True
    return False


def _other_binding_targets(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, (ast.AugAssign, ast.NamedExpr, ast.For, ast.AsyncFor)):
        return [node.target]
    if isinstance(node, ast.comprehension):
        return [node.target]
    if isinstance(node, ast.Delete):
        return list(node.targets)
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [item.optional_vars for item in node.items if item.optional_vars]
    return []


def _dispatch_replacement_violations(source: str, filename: str) -> list[str]:
    tree = ast.parse(source, filename=filename)
    receivers, aliases = _dispatch_context(tree)
    operation_names, module_names = _patch_bindings(tree)
    helper_aliases = _helper_aliases(tree)
    string_bindings = _string_bindings(tree)
    module_exercises_target = (
        bool(receivers)
        or any(_helper_call(node) for node in ast.walk(tree))
        or _mentions_target(tree)
    )
    violations: list[str] = []
    replacements = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not any(_contains_target(target) for target in targets):
                continue
            replacements += 1
            valid = (
                len(targets) == 1
                and isinstance(targets[0], ast.Attribute)
                and targets[0].attr == _TARGET
                and _helper_call(node.value)
            )
            if not valid:
                violations.append(f"{filename}:{node.lineno}:unsupported-assignment")
            continue
        binding_targets = _other_binding_targets(node)
        if any(_contains_target(target) for target in binding_targets):
            replacements += 1
            violations.append(f"{filename}:{node.lineno}:unsupported-assignment")
        elif isinstance(node, ast.Call) and _call_mutates_target(
            node,
            receivers,
            aliases,
            operation_names,
            module_names,
            helper_aliases,
            string_bindings,
            module_exercises_target=module_exercises_target,
        ):
            replacements += 1
            violations.append(f"{filename}:{node.lineno}:dynamic-replacement")

    if replacements and not any(_exact_helper_import(node) for node in tree.body):
        violations.append(f"{filename}:1:missing-helper-import")
    if replacements and _helper_is_shadowed(tree):
        violations.append(f"{filename}:1:shadowed-helper")
    return violations


def test_tick_dispatch_replacements_use_faithful_helper() -> None:
    violations = [
        violation
        for path in sorted(Path(__file__).parent.glob("test_*.py"))
        if path.name != Path(__file__).name
        for violation in _dispatch_replacement_violations(
            path.read_text(encoding="utf-8"), path.name
        )
    ]
    assert violations == [], (
        "_handle_dispatch_needed replacements must be direct tick_dispatch_mock "
        f"calls; violations: {', '.join(violations)}"
    )


def _source(body: str) -> str:
    return (
        "from unittest.mock import patch\n"
        f"from {_HELPER_MODULE} import {_HELPER}\n{body}"
    )


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (
            "replacement = tick_dispatch_mock()\n"
            "if enabled:\n    replacement = AsyncMock(return_value=None)\n"
            "orch._handle_dispatch_needed = replacement\n",
            "unsupported-assignment",
        ),
        (
            "replacement = AsyncMock(return_value=None)\n"
            "replacement = tick_dispatch_mock()\n"
            "orch._handle_dispatch_needed = replacement\n",
            "unsupported-assignment",
        ),
        (
            "tick_dispatch_mock = lambda: AsyncMock(return_value=None)\n"
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n",
            "shadowed-helper",
        ),
        (
            "def rebind():\n    global tick_dispatch_mock\n"
            "    tick_dispatch_mock = unsafe_factory\n"
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n",
            "shadowed-helper",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "orch._handle_dispatch_needed.return_value = None\n",
            "unsupported-assignment",
        ),
        (
            "AsyncMock = fake_factory\ndict = fake_mapping\n"
            "orch._handle_dispatch_needed = AsyncMock(return_value=dict())\n",
            "unsupported-assignment",
        ),
        (
            "setattr(orch, '_handle_dispatch_needed', tick_dispatch_mock())\n",
            "dynamic-replacement",
        ),
        (
            "monkeypatch.setattr(orch, '_handle_dispatch_needed', "
            "tick_dispatch_mock())\n",
            "dynamic-replacement",
        ),
        (
            "with patch.object(orch, '_handle_dispatch_needed', "
            "tick_dispatch_mock()):\n    pass\n",
            "dynamic-replacement",
        ),
        (
            "orch._handle_dispatch_needed, other = "
            "tick_dispatch_mock(), sentinel\n",
            "unsupported-assignment",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "suffix = choose_handler_suffix()\n"
            "setattr(orch, '_handle_' + suffix, AsyncMock(return_value=None))\n",
            "dynamic-replacement",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "patch_target = build_patch_target()\n"
            "with patch(patch_target, AsyncMock(return_value=None)):\n    pass\n",
            "dynamic-replacement",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "patch_target = build_patch_target()\n"
            "monkeypatch.setattr(patch_target, AsyncMock(return_value=None))\n",
            "dynamic-replacement",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "orch._handle_dispatch_needed.configure_mock(return_value=None)\n",
            "dynamic-replacement",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "orch._handle_dispatch_needed.configure_mock(side_effect=None)\n",
            "dynamic-replacement",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "orch._handle_dispatch_needed.reset_mock(side_effect=True)\n",
            "dynamic-replacement",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "setattr(orch._handle_dispatch_needed, 'side_effect', None)\n",
            "dynamic-replacement",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "with patch.object(orch._handle_dispatch_needed, 'return_value', None):\n"
            "    pass\n",
            "dynamic-replacement",
        ),
        (
            "from unittest.mock import patch as substitute\n"
            "replacement = tick_dispatch_mock()\n"
            "with substitute(build_target(), replacement):\n    pass\n",
            "dynamic-replacement",
        ),
        (
            "import unittest\n"
            "replacement = tick_dispatch_mock()\n"
            "with unittest.mock.patch(build_target(), replacement):\n    pass\n",
            "dynamic-replacement",
        ),
        (
            "patcher = patch\n"
            "replacement = tick_dispatch_mock()\n"
            "with patcher(build_target(), replacement):\n    pass\n",
            "dynamic-replacement",
        ),
        (
            "handler_target = "
            "'oompah.orchestrator._handle_dispatch_needed'\n"
            "with patch(handler_target, AsyncMock(return_value=None)):\n"
            "    pass\n",
            "dynamic-replacement",
        ),
        (
            "handler_suffix = '_handle_dispatch_' + 'needed'\n"
            "handler_target = 'oompah.orchestrator.' + handler_suffix\n"
            "handler_alias = handler_target\n"
            "with patch(handler_alias, AsyncMock(return_value=None)):\n"
            "    pass\n",
            "dynamic-replacement",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "with patch(build_target(), AsyncMock(return_value=None)):\n"
            "    pass\n",
            "dynamic-replacement",
        ),
        (
            "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
            "ambiguous_target = build_target()\n"
            "with patch(ambiguous_target, AsyncMock(return_value=None)):\n"
            "    pass\n",
            "dynamic-replacement",
        ),
        (
            "from unittest import mock\n"
            "m2 = mock\n"
            "m3 = m2\n"
            "replacement = tick_dispatch_mock()\n"
            "with m3.patch(build_target(), replacement):\n    pass\n",
            "dynamic-replacement",
        ),
        (
            "import unittest\n"
            "u2 = unittest\n"
            "u3 = u2\n"
            "replacement = tick_dispatch_mock()\n"
            "with u3.mock.patch(build_target(), replacement):\n    pass\n",
            "dynamic-replacement",
        ),
        (
            "replace = patch.object\n"
            "replace2 = replace\n"
            "replacement = tick_dispatch_mock()\n"
            "with replace2(orch, choose_handler_name(), replacement):\n"
            "    pass\n",
            "dynamic-replacement",
        ),
        (
            "multi = patch.multiple\n"
            "multi2 = multi\n"
            "with multi2(\n"
            "    orch, _handle_dispatch_needed=AsyncMock(return_value=None)\n"
            "):\n    pass\n",
            "dynamic-replacement",
        ),
        (
            "with patch.multiple(\n"
            "    orch, _handle_dispatch_needed=AsyncMock(return_value=None)\n"
            "):\n    pass\n",
            "dynamic-replacement",
        ),
        (
            "replacement = tick_dispatch_mock()\n"
            "with patch.multiple(orch, **build_replacements(replacement)):\n"
            "    pass\n",
            "dynamic-replacement",
        ),
        (
            "replacement = tick_dispatch_mock()\n"
            "handler_name = choose_handler_name()\n"
            "setattr(orch, handler_name, replacement)\n",
            "dynamic-replacement",
        ),
        (
            "replacement = tick_dispatch_mock()\n"
            "monkeypatch.setattr(build_target(), replacement)\n",
            "dynamic-replacement",
        ),
        (
            "replacement = tick_dispatch_mock()\n"
            "with patch.object(orch, choose_handler_name(), replacement):\n"
            "    pass\n",
            "dynamic-replacement",
        ),
    ],
)
def test_contract_rejects_unsafe_replacement_forms(body: str, reason: str) -> None:
    assert any(
        reason in violation
        for violation in _dispatch_replacement_violations(_source(body), "inline.py")
    )


def test_contract_accepts_direct_canonical_helper_calls() -> None:
    source = _source(
        "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
        "other._handle_dispatch_needed = "
        "tick_dispatch_mock({'candidate_fetch': 0.0}, on_call=callback)\n"
    )
    assert _dispatch_replacement_violations(source, "inline.py") == []


def test_contract_accepts_provably_unrelated_computed_mutations() -> None:
    source = _source(
        "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
        "for key, value in overrides.items():\n"
        "    setattr(cfg, key, value)\n"
        "setattr(task, metadata_attributes[key], value)\n"
        "safe_prefix = 'oompah.config.'\n"
        "safe_name = 'load_' + 'workflow'\n"
        "safe_target = safe_prefix + safe_name\n"
        "safe_alias = safe_target\n"
        "with patch(safe_alias, sentinel):\n"
        "    pass\n"
        "replace = patch.object\n"
        "with replace(settings, choose_field(), sentinel):\n"
        "    pass\n"
        "multi = patch.multiple\n"
        "with multi(settings, **build_fields()):\n"
        "    pass\n"
    )
    assert _dispatch_replacement_violations(source, "inline.py") == []


def test_contract_accepts_unrelated_targets_through_module_aliases() -> None:
    source = _source(
        "from unittest import mock\n"
        "m2 = mock\n"
        "import unittest\n"
        "u2 = unittest\n"
        "orch._handle_dispatch_needed = tick_dispatch_mock()\n"
        "safe_target = 'oompah.config.load_workflow'\n"
        "safe_alias = safe_target\n"
        "with m2.patch(safe_alias, sentinel):\n"
        "    pass\n"
        "with u2.mock.patch.object(settings, choose_field(), sentinel):\n"
        "    pass\n"
    )
    assert _dispatch_replacement_violations(source, "inline.py") == []


def test_tick_dispatch_mock_snapshots_and_copies_mapping() -> None:
    timings = {"candidate_fetch": 1.0}
    dispatch = tick_dispatch_mock(timings)
    timings["candidate_fetch"] = 99.0

    first = asyncio.run(dispatch())
    first["candidate_fetch"] = 42.0
    second = asyncio.run(dispatch())

    assert second == {"candidate_fetch": 1.0}
    assert first is not second


def test_tick_dispatch_mock_rejects_behavior_mutation() -> None:
    dispatch = tick_dispatch_mock({"candidate_fetch": 1.0})
    mutations = [
        lambda: setattr(dispatch, "return_value", None),
        lambda: setattr(dispatch, "side_effect", None),
        lambda: dispatch.configure_mock(return_value=None),
        lambda: dispatch.configure_mock(side_effect=None),
        lambda: dispatch.reset_mock(return_value=True),
        lambda: dispatch.reset_mock(side_effect=True),
    ]
    for mutate in mutations:
        with pytest.raises((AttributeError, TypeError)):
            mutate()
        assert asyncio.run(dispatch()) == {"candidate_fetch": 1.0}


def test_tick_dispatch_mock_preserves_await_assertions_and_safe_reset() -> None:
    dispatch = tick_dispatch_mock(on_call=lambda value: {"value": float(value)})

    assert asyncio.run(dispatch(3)) == {"value": 3.0}
    dispatch.assert_awaited_once_with(3)
    assert dispatch.await_count == 1
    dispatch.reset_mock()
    dispatch.assert_not_awaited()
    assert asyncio.run(dispatch(4)) == {"value": 4.0}


def test_tick_dispatch_mock_accepts_callbacks_and_rejects_non_mappings() -> None:
    async def async_callback() -> dict[str, float]:
        return {"async": 2.0}

    assert asyncio.run(tick_dispatch_mock(on_call=lambda: {"sync": 1.0})()) == {
        "sync": 1.0
    }
    assert asyncio.run(tick_dispatch_mock(on_call=async_callback)()) == {"async": 2.0}
    with pytest.raises(TypeError, match="timings must be a Mapping"):
        tick_dispatch_mock([])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="callback must return a Mapping"):
        asyncio.run(tick_dispatch_mock(on_call=lambda: None)())
