#!/usr/bin/env python3
"""Smoke test for the openai-agents SDK pin (oompah-zlz_2-jrkz.1).

Run this script against any installed ``openai-agents`` version to
verify the Codex ACP backend + console translator contracts hold:

* The SDK exports ``Agent``, ``Runner``, and ``function_tool``.
* ``Runner.run_streamed`` accepts ``input: list[TResponseInputItem]``
  (the shape the translator emits for SDK history hand-off).
* ``TResponseInputItem`` validates all three shape variants
  produced by :func:`oompah.console_translators.codex.normalized_to_sdk_history`:

  * ``{"role": "user" | "assistant", "content": str}``
  * ``{"type": "function_call", "name": str,
        "arguments": str (JSON), "call_id": str}``
  * ``{"type": "function_call_output",
        "call_id": str, "output": str}``

* An ``Agent`` instance can be constructed with a bridged
  ``function_tool`` catalog (smoke test of the
  :mod:`oompah.acp_tools.build_codex_tool_catalog` path).

Usage::

    # In a venv that has openai-agents installed:
    python scripts/smoke_codex_sdk.py

Exits 0 on success, non-zero on the first mismatch with a clear
error explaining what the SDK rejected. Suitable for CI gating the
``codex`` extras pin in ``pyproject.toml``.

This script is intentionally dependency-light: it only imports
``agents`` and ``pydantic`` (a transitive dependency of agents).
It does NOT import the oompah codebase so it can be executed in a
minimal environment that just has the SDK installed.
"""
from __future__ import annotations

import inspect
import json
import sys
from typing import Any


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _check_exports(agents_mod: Any, version: str) -> None:
    """Verify the SDK exports the symbols the backend imports."""
    required = ("Agent", "Runner", "function_tool")
    missing = [name for name in required if not hasattr(agents_mod, name)]
    if missing:
        _fail(f"openai-agents=={version} missing required exports: {missing}")
    print(f"OK: openai-agents=={version} exports {list(required)}")


def _check_runner_signature(agents_mod: Any, version: str) -> None:
    """Verify Runner.run_streamed accepts a list of TResponseInputItem."""
    runner_cls = getattr(agents_mod, "Runner")
    run_streamed = getattr(runner_cls, "run_streamed", None)
    if run_streamed is None:
        _fail(
            f"openai-agents=={version} Runner has no run_streamed; the "
            f"codex backend depends on a streaming Runner."
        )
    sig = inspect.signature(run_streamed)
    if "input" not in sig.parameters:
        _fail(
            f"openai-agents=={version} Runner.run_streamed has no 'input' "
            f"parameter (signature: {sig})"
        )
    input_anno = str(sig.parameters["input"].annotation)
    if "TResponseInputItem" not in input_anno:
        _fail(
            f"openai-agents=={version} Runner.run_streamed 'input' "
            f"annotation does not reference TResponseInputItem: {input_anno}"
        )
    print(
        f"OK: Runner.run_streamed input annotation accepts "
        f"list[TResponseInputItem] ({input_anno!r})"
    )


def _check_input_item_shape(version: str) -> None:
    """Validate the exact shapes the codex translator emits."""
    from pydantic import TypeAdapter
    from agents.items import TResponseInputItem

    history = [
        # operator_input → user message
        {"role": "user", "content": "please read README"},
        # agent_text → assistant message
        {"role": "assistant", "content": "Reading..."},
        # tool_call → function_call (arguments is JSON-encoded string!)
        {
            "type": "function_call",
            "name": "read_file",
            "arguments": json.dumps({"path": "README.md"}),
            "call_id": "tu_42",
        },
        # tool_result → function_call_output
        {
            "type": "function_call_output",
            "call_id": "tu_42",
            "output": "file body",
        },
        # adjacent same-role messages (translator allows; SDK accepts)
        {"role": "assistant", "content": "Done."},
        # tool_result with is_error → output prefixed with [ERROR]
        {
            "type": "function_call_output",
            "call_id": "tu_43",
            "output": "[ERROR] ENOENT",
        },
    ]
    ta = TypeAdapter(list[TResponseInputItem])
    ta.validate_python(history)
    print(
        f"OK: openai-agents=={version} TResponseInputItem validates "
        f"all {len(history)} translator-emitted shapes"
    )


def _check_agent_construction(agents_mod: Any, version: str) -> None:
    """Smoke test: construct an Agent with a bridged function_tool."""
    function_tool = getattr(agents_mod, "function_tool")
    Agent = getattr(agents_mod, "Agent")

    @function_tool
    def echo(value: str) -> str:
        """Return the input unchanged. Smoke test only."""
        return value

    agent = Agent(
        name="oompah-codex-smoke",
        instructions="You are a test agent.",
        tools=[echo],
        model="gpt-4o-mini",
    )
    if agent is None:
        _fail(f"Agent construction returned None on openai-agents=={version}")
    print(
        f"OK: Agent construction with bridged function_tool catalog OK "
        f"on openai-agents=={version}"
    )


def main() -> int:
    try:
        import agents
    except ImportError as exc:
        _fail(
            f"openai-agents SDK not installed. Codex ACP backend requires "
            f"the OpenAI Agents Python SDK. Install with: "
            f"uv pip install 'oompah[codex]'"
        )
    version = getattr(agents, "__version__", "?")
    _check_exports(agents, version)
    _check_runner_signature(agents, version)
    _check_input_item_shape(version)
    _check_agent_construction(agents, version)
    print(
        f"\nDONE: openai-agents=={version} is compatible with the "
        f"oompah codex backend + translator."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
