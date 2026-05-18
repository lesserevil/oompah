"""SDK-shape regression smoke test for the codex console translator.

If ``openai-agents`` is installed in the test environment, validate
that the shapes emitted by
:func:`oompah.console_translators.codex.normalized_to_sdk_history`
pass the SDK's :class:`agents.items.TResponseInputItem` Pydantic
union. This is the canary for a future SDK release breaking the
input-item shape contract documented in ``plans/codex-sdk-pin.md``.

When ``openai-agents`` is not installed (the default for a base
oompah install — the SDK is an optional ``codex`` extra), the test is
skipped via :func:`pytest.importorskip` so the suite stays green on
ACP-free installs.

This is **not** a replacement for the broader
:mod:`tests.test_console_translator_codex` per-kind mapping coverage
— that suite already pins the dict shape with hand-built dict
comparisons. This file adds one targeted assertion: that the dicts
those hand-built tests assert on are *also* what the live SDK
accepts. Without this gate, a silent SDK shape drift could leave the
hand-built tests green while the production code path breaks.

Issue: ``oompah-zlz_2-jrkz.1``.
"""

from __future__ import annotations

import json

import pytest

from oompah.console_format import ConsoleEvent, make_operator_input
from oompah.console_translators.codex import normalized_to_sdk_history


# Skip the entire module if openai-agents (or pydantic) isn't installed.
# importorskip evaluates at collection time, so the test file is a no-op
# in environments that don't have the codex extra.
agents = pytest.importorskip(
    "agents",
    reason="openai-agents SDK not installed — install with `pip install "
    "'oompah[codex]'` to run codex SDK-shape regression tests.",
)
agents_items = pytest.importorskip(
    "agents.items",
    reason="openai-agents SDK present but agents.items missing "
    "TResponseInputItem — SDK version may be too old (need >=0.0.10).",
)
pydantic = pytest.importorskip(
    "pydantic",
    reason="pydantic is a transitive dependency of openai-agents; if "
    "missing the codex extras install is broken.",
)


def _build_full_history() -> list[dict]:
    """Build a normalized event stream that exercises every translator
    branch that produces an SDK input item, then run it through
    :func:`normalized_to_sdk_history`.

    The intent is to surface every concrete dict shape the production
    code path can emit, not to exercise the translator's mapping logic
    (which is :mod:`tests.test_console_translator_codex`'s job).
    """
    events = [
        make_operator_input("t0", "please read the README"),
        ConsoleEvent(
            ts="t1", kind="agent_text", backend="codex",
            text="Sure — fetching it now.",
        ),
        ConsoleEvent(
            ts="t2", kind="tool_call", backend="codex",
            tool="read_file",
            args={"path": "README.md", "_tool_use_id": "tu_42"},
        ),
        ConsoleEvent(
            ts="t3", kind="tool_result", backend="codex",
            result={"tool_use_id": "tu_42", "content": "file body"},
        ),
        ConsoleEvent(
            ts="t4", kind="tool_call", backend="codex",
            tool="run_command",
            # _raw_input is the truncated-repr fallback the backend
            # emits when tool input isn't a dict.
            args={"_raw_input": "<truncated repr>", "_tool_use_id": "tu_43"},
        ),
        ConsoleEvent(
            ts="t5", kind="tool_result", backend="codex",
            result={"tool_use_id": "tu_43", "content": "ENOENT"},
            is_error=True,
        ),
        ConsoleEvent(
            ts="t6", kind="agent_text", backend="codex",
            text="Done — file contents above.",
        ),
        # operator_input with attachments — inlines the paths into the
        # user message.
        make_operator_input(
            "t7", "and look at these",
            attachments=["/tmp/a.png", "/tmp/b.txt"],
        ),
        # Tool result with dict content — JSON-encoded by the translator
        # so output stays a string.
        ConsoleEvent(
            ts="t8", kind="tool_result", backend="codex",
            result={"tool_use_id": "tu_44", "content": {"key": "value"}},
        ),
    ]
    history = normalized_to_sdk_history(events)
    assert history, "translator produced empty history"
    return history


def test_translator_output_validates_against_sdk_response_input_item():
    """The exact dicts the translator emits must validate against the
    SDK's TResponseInputItem union.

    A regression in this assertion means the openai-agents SDK
    shape contract changed and we need to bump the pin in
    pyproject.toml ``[project.optional-dependencies] codex`` after
    updating the translator.
    """
    from pydantic import TypeAdapter
    from agents.items import TResponseInputItem

    history = _build_full_history()
    ta = TypeAdapter(list[TResponseInputItem])
    # Should not raise. ValidationError would mean the SDK changed
    # the shape under one of: EasyInputMessage / FunctionCallParam /
    # FunctionCallOutputParam.
    ta.validate_python(history)


def test_function_call_arguments_must_be_json_string():
    """The OpenAI Responses spec requires ``arguments`` to be a string.

    Regression guard: if the translator ever starts emitting
    ``arguments`` as a dict (the natural Anthropic shape), the SDK
    will reject it. This test exercises the contract on a tool_call
    event with a real dict input.
    """
    from pydantic import TypeAdapter
    from agents.items import TResponseInputItem

    events = [
        ConsoleEvent(
            ts="t", kind="tool_call", backend="codex",
            tool="read_file",
            args={"path": "x.txt", "mode": "rb", "_tool_use_id": "tu_1"},
        ),
    ]
    history = normalized_to_sdk_history(events)
    assert len(history) == 1
    call = history[0]
    # Sanity-check our own translator output before passing to SDK.
    assert call["type"] == "function_call"
    assert isinstance(call["arguments"], str), (
        f"translator emitted non-string arguments: {type(call['arguments'])}"
    )
    # Must be valid JSON.
    payload = json.loads(call["arguments"])
    assert payload == {"path": "x.txt", "mode": "rb"}

    # And must pass SDK validation.
    ta = TypeAdapter(list[TResponseInputItem])
    ta.validate_python(history)


def test_function_call_output_required_fields():
    """`function_call_output` items must have call_id + output (strings)."""
    from pydantic import TypeAdapter
    from agents.items import TResponseInputItem

    events = [
        ConsoleEvent(
            ts="t", kind="tool_result", backend="codex",
            result={"tool_use_id": "tu_X", "content": "the output"},
        ),
    ]
    history = normalized_to_sdk_history(events)
    assert len(history) == 1
    out = history[0]
    assert out == {
        "type": "function_call_output",
        "call_id": "tu_X",
        "output": "the output",
    }
    ta = TypeAdapter(list[TResponseInputItem])
    ta.validate_python(history)


def test_runner_run_streamed_accepts_input_list_annotation():
    """Runner.run_streamed must annotate ``input`` to include
    ``list[TResponseInputItem]``. The codex backend code uses this
    parameter to hand a pre-built history back to the SDK.

    This is a structural assertion (we check the annotation string,
    not call the live SDK against a real model — that requires an
    API key).
    """
    import inspect

    runner = getattr(agents, "Runner", None)
    assert runner is not None, "openai-agents missing Runner export"
    run_streamed = getattr(runner, "run_streamed", None)
    assert run_streamed is not None, "Runner missing run_streamed"
    sig = inspect.signature(run_streamed)
    assert "input" in sig.parameters
    annotation = str(sig.parameters["input"].annotation)
    assert "TResponseInputItem" in annotation, (
        f"Runner.run_streamed input annotation drifted: {annotation}"
    )
