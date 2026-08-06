"""Static regression for the dispatch timing Mapping test contract."""

from __future__ import annotations

import ast
from pathlib import Path


def _assigns_dispatch_handler(node: ast.Assign | ast.AnnAssign) -> bool:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return any(
        isinstance(target, ast.Attribute)
        and target.attr == "_handle_dispatch_needed"
        for target in targets
    )


def _is_async_mock_call(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "AsyncMock")
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "AsyncMock"
            )
        )
    )


def test_tick_dispatch_async_mocks_declare_mapping_return_value() -> None:
    """A bare AsyncMock returns a coroutine mock, not dispatch timings."""

    violations: list[str] = []
    tests_dir = Path(__file__).parent
    for path in sorted(tests_dir.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            if not _assigns_dispatch_handler(node) or not _is_async_mock_call(
                node.value
            ):
                continue
            call = node.value
            assert isinstance(call, ast.Call)
            if not any(keyword.arg == "return_value" for keyword in call.keywords):
                violations.append(f"{path.name}:{node.lineno}")

    assert violations == [], (
        "_handle_dispatch_needed AsyncMock assignments must declare an explicit "
        f"Mapping return_value; violations: {', '.join(violations)}"
    )
