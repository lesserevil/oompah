# Codex backend / openai-agents SDK pin

**Status:** Recommendation finalized. Pin to be wired into
`pyproject.toml` `[project.optional-dependencies] codex` by
`oompah-zlz_2-jrkz.2` (the broader pyproject extras refactor).

**Issue:** [oompah-zlz_2-jrkz.1](https://oompah/issues/oompah-zlz_2-jrkz.1)

## TL;DR

```toml
[project.optional-dependencies]
codex = [
    "openai-agents>=0.17.2,<0.18",
]
```

Install with (from a cloned oompah repo — oompah is not on PyPI):

```bash
uv pip install -e '.[codex]'
# or, editable install with pip
pip install -e '.[codex]'
```

## Why this pin

The `oompah/console_translators/codex.py` translator emits an
`Runner.run_streamed(input=...)`-compatible list of "input items"
that the OpenAI Agents SDK validates via the
`agents.items.TResponseInputItem` Pydantic union. The three shapes
the translator produces are:

```python
# Messages (operator_input, agent_text):
{"role": "user", "content": "..."}
{"role": "assistant", "content": "..."}

# Tool call (tool_call):
{
    "type": "function_call",
    "name": "read_file",
    "arguments": "{\"path\":\"README.md\"}",   # JSON string, NOT a dict
    "call_id": "tu_42",
}

# Tool result (tool_result):
{
    "type": "function_call_output",
    "call_id": "tu_42",
    "output": "file body…",
}
```

These shapes line up with the OpenAI Responses API "input items" spec
and have been stable in `openai-agents` since `0.0.10` (Apr 2025). The
SDK does add new fields over time (e.g. `RunState` was added to the
`input` union at `0.10.0`), but those additions never broke the three
shapes above — they're strict supersets.

We pin to `>=0.17.2,<0.18` because:

1. **`0.17.2`** is the verified known-good version at the time the
   codex backend + translator shipped (2026-05-12). All four smoke
   tests pass: SDK exports, `Runner.run_streamed` signature,
   `TResponseInputItem` validation, and `Agent` construction with a
   bridged `function_tool` catalog.

2. **`<0.18`** caps the next minor. The SDK is still 0.x: minors
   ship roughly weekly and the changelog has had real breaking
   changes (e.g. `0.16.0` changed `max_turns: int` → `int | None`,
   `0.10.0` added `RunState` to the input union). The translator
   shape itself has been resilient, but the *runtime* surface the
   backend depends on (`stream_events`, `run_item_stream_event` item
   types, `RunResult.context_wrapper.usage`) is not formally
   versioned. Better to require an explicit re-verification when
   the next minor lands.

## Verification

A reusable smoke test lives at `scripts/smoke_codex_sdk.py`. Run it
in an environment that has `openai-agents` installed:

```bash
python scripts/smoke_codex_sdk.py
```

It exits 0 on success, non-zero on the first mismatch with a clear
error explaining what the SDK rejected. The script is intentionally
dependency-light (only imports `agents` and `pydantic`) so it can be
run in a minimal environment that just has the SDK.

A gated pytest regression at `tests/test_codex_sdk_shape_smoke.py`
re-runs the input-item validation against whatever SDK version is
installed (skipped via `pytest.importorskip("agents")` when the
optional dep is absent), so the test suite catches a future SDK
release that breaks the shape contract.

### Verification matrix at time of writing

Manually validated `normalized_to_sdk_history` output against the
following SDK versions on Python 3.11:

| Version | Released   | TResponseInputItem | Runner.run_streamed input | Agent ctor |
|---------|------------|--------------------|---------------------------|------------|
| 0.10.5  | 2026-03-05 | ✓                  | ✓                         | ✓          |
| 0.13.6  | 2026-04-09 | ✓                  | ✓                         | ✓          |
| 0.15.3  | 2026-05-06 | ✓                  | ✓                         | ✓          |
| 0.17.0  | 2026-05-08 | ✓                  | ✓                         | ✓          |
| 0.17.2  | 2026-05-12 | ✓                  | ✓                         | ✓          |

Earlier versions (0.0.10 through 0.10.0) also validate the input-item
shape but have small `Runner.run_streamed` signature differences (no
`RunState` in the input union, narrower `max_turns` annotation). The
pin floor of `0.17.2` is conservative on purpose — keeping us on
the version we actually tested end-to-end.

## Bumping the pin

When `openai-agents` releases `0.18.x`, the operator (or a follow-up
task in the next epic) should:

1. Run `scripts/smoke_codex_sdk.py` against `0.18.x`.
2. If it passes, also run `pytest tests/test_codex_sdk_shape_smoke.py`
   and the broader `tests/test_acp_codex_backend.py` suite with the
   new SDK installed.
3. If both pass, widen the pin to `>=0.17.2,<0.19`.
4. If either fails, update the translator or backend to match the
   new SDK shape **before** bumping the pin.

The shape-validation smoke test in particular is the canary for
breakage: a single `TResponseInputItem` rejection means the SDK
changed one of the three input-item shapes and the translator (and
likely the backend) needs an update.

## Related

* `oompah/console_translators/codex.py` — the translator emitting
  the input-item shape.
* `oompah/acp_backends/codex.py` — the runtime backend driving
  `Runner.run_streamed`.
* `oompah-zlz_2-jrkz.2` — the broader pyproject refactor that
  actually wires this pin into `[project.optional-dependencies]`
  and lazy-guards the remaining ACP SDK imports so the base
  install works without ACP backends.
