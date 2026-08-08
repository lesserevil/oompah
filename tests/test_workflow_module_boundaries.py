"""Dependency and compatibility fences for cohesive workflow modules."""

from __future__ import annotations

import ast
import importlib
import inspect
import textwrap
from pathlib import Path

import pytest

from oompah.orchestrator import Orchestrator
from oompah.workflow_decision_projection import WorkDecisionProjectionCoordinator


_PACKAGE_ROOT = Path(__file__).parents[1] / "oompah"
_OWNED_WORKFLOW_MODULES = frozenset(
    {
        "epic_workflow",
        "epic_workflow_adapter",
        "implementation_workflow",
        "implementation_workflow_adapter",
        "integration_workflow",
        "review_workflow",
        "review_workflow_adapter",
        "work_decision",
        "workflow_contract",
        "workflow_controller",
        "workflow_decision_projection",
        "workflow_event_intake",
        "workflow_fact_model",
        "workflow_jobs",
        "workflow_reasons",
        "workflow_runtime",
        "workflow_scheduler",
        "workflow_worker",
    }
)
_PURE_MODULES = frozenset(
    {
        "work_decision",
        "workflow_contract",
        "workflow_fact_model",
        "workflow_reasons",
    }
)
_IO_BOUNDARIES = frozenset(
    {
        "bootstrap",
        "orchestrator",
        "projects",
        "scm",
        "server",
        "tracker",
        "workflow_facts",
        "workflow_jobs",
    }
)


def _tree(module_name: str) -> ast.Module:
    return ast.parse((_PACKAGE_ROOT / f"{module_name}.py").read_text())


def _oompah_imports(module_name: str) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(_tree(module_name)):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module and node.module.startswith("oompah."):
            imports.add(node.module.partition(".")[2].partition(".")[0])
    return imports


def _owned_graph() -> dict[str, set[str]]:
    return {
        module: _oompah_imports(module) & _OWNED_WORKFLOW_MODULES
        for module in _OWNED_WORKFLOW_MODULES
    }


def _reachable(graph: dict[str, set[str]], root: str) -> set[str]:
    found: set[str] = set()
    pending = list(graph.get(root, ()))
    while pending:
        module = pending.pop()
        if module in found:
            continue
        found.add(module)
        pending.extend(graph.get(module, ()))
    return found


def _method_metrics(method: object) -> tuple[int, int]:
    source = textwrap.dedent(inspect.getsource(method))
    tree = ast.parse(source)
    function = tree.body[0]
    assert isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
    branches = sum(
        isinstance(
            node,
            (
                ast.If,
                ast.IfExp,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.Match,
            ),
        )
        for node in ast.walk(function)
    )
    assert function.end_lineno is not None
    return function.end_lineno - function.lineno + 1, branches


def test_owned_workflow_modules_have_no_import_cycle() -> None:
    graph = _owned_graph()

    for root in sorted(graph):
        assert root not in _reachable(graph, root), f"workflow import cycle at {root}"


@pytest.mark.parametrize("module", sorted(_OWNED_WORKFLOW_MODULES))
def test_owned_workflow_modules_do_not_import_composition_roots(module: str) -> None:
    assert _oompah_imports(module).isdisjoint(
        {"bootstrap", "orchestrator", "server"}
    )


@pytest.mark.parametrize("module", sorted(_PURE_MODULES))
def test_pure_evaluator_graph_cannot_reach_io_boundaries(module: str) -> None:
    graph = {
        name: _oompah_imports(name)
        for name in _PURE_MODULES | {"models", "statuses"}
    }
    reached = _reachable(graph, module)

    assert reached.isdisjoint(_IO_BOUNDARIES)


def test_workflow_facts_preserves_model_import_compatibility() -> None:
    compatibility = importlib.import_module("oompah.workflow_facts")
    model = importlib.import_module("oompah.workflow_fact_model")

    for name in (
        "FactDomain",
        "FactObservation",
        "FactState",
        "LandingFact",
        "LandingRequest",
        "LandingState",
        "WorkflowFacts",
    ):
        assert getattr(compatibility, name) is getattr(model, name)


@pytest.mark.parametrize(
    "method,max_lines",
    (
        (Orchestrator._publish_work_decisions, 40),
        (Orchestrator.work_decision_projection, 15),
        (Orchestrator.work_decision_availability, 10),
        (Orchestrator.work_decision_snapshot, 10),
        (Orchestrator._post_event_on_loop, 8),
        (Orchestrator._post_event, 8),
        (Orchestrator._full_sync_loop, 12),
    ),
)
def test_orchestrator_composition_delegates_are_thin(
    method: object, max_lines: int
) -> None:
    lines, branches = _method_metrics(method)

    assert lines <= max_lines
    assert branches == 0


def test_projection_owner_has_bounded_publication_complexity() -> None:
    lines, branches = _method_metrics(WorkDecisionProjectionCoordinator.publish)

    assert lines <= 110
    assert branches <= 12
