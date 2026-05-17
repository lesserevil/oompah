# OpenCode ACP Backend

## Context

The multi-backend ACP epic (root bead) established a pluggable backend layer for ACP-mode agent sessions. Child A (`oompah-zlz_2-0hzh`) introduced the abstract `AcpBackend` / `AcpBackendSession` / `BackendEvent` surface. Child B (`oompah-zlz_2-yiuy`) implemented `CodexAcpBackend` against the OpenAI Agents Python SDK as a concrete proof of the abstraction. This issue adds a **third backend** against the OpenCode Python SDK.

Adding a third backend diversifies the agent runner options, which is valuable for:

- Reducing vendor dependency (Claude closed-source SDK vs. open-source alternatives)
- Supporting different model families via a single frontend interface
- Establishing the common machinery for any future backends

## Decision: OpenCode SDK

**OpenCode** is chosen because it provides:

1. A session-shaped async streaming API via `opencode.Chat` with `chat.stream(prompt)` returning an async generator of `(event, data)` tuples
2. A `@tool` decorator for tool injection — same surface as Claude (unlike Codex's `@function_tool`)
3. An open-source Python SDK installable via `pip install opencode`
4. API-key-based auth compatible with OpenAI-compatible endpoints
5. Streaming token-usage events (`("usage", dict)`) mid-flight

### Alternative considered: direct HTTP via `openai` client

Skipped because it would require re-implementing the session runner and event buffering that OpenCode's SDK provides. The `openai` client is the right choice for the API-mode agent; the ACP backends are specifically for managed-session paths.

## Architecture

Follows the established pattern from the Claude and Codex backends:

```
oompah/acp_backends/
    opencode.py        ← OpenCodeAcpBackend + OpenCodeAcpBackendSession
```

`OpenCodeAcpBackend` subclasses `AcpBackend` and registers itself as `"opencode"` at import time. `OpenCodeAcpBackendSession` implements `AcpBackendSession` with an async `run_turn()` that drives `opencode.Chat.stream()`.

Tool catalog is built via `build_opencode_tool_catalog()` in `oompah/acp_tools.py` — parallels `build_tool_catalog` (Claude) and `build_codex_tool_catalog` (Codex).

## OpenCode SDK Stream Event Types

OpenCode's `Chat.stream()` yields `(event, data)` tuples:

| event | data | maps to |
|-------|------|---------|
| `"text"` | `str` | `acp_text` |
| `"text_done"` | `str` | `acp_text` |
| `"tool_call"` | `dict{name, arguments, id}` | `acp_tool_use` |
| `"tool_result"` | `dict{tool_call_id, content, is_error}` | `acp_tool_result` |
| `"thinking"` / `"reasoning"` / `"thought"` | `str` | `acp_thinking` |
| `"usage"` | `dict{input_tokens, output_tokens}` | counter update |
| `"session_id"` | `str` | `session_id` |
| `"error"` | `str` | `acp_assistant_error` |

## Provider Validation

Mirrors the Codex backend's rules:

- **Per-token billing** (default): requires `api_key` on the provider record.
- **Subscription billing**: `api_key` optional (OpenCode CLI OAuth flow handles auth).
- **base_url**: must be `http://` or `https://` if overridden from the default endpoint.

The `billing_model` field (`"per_token"` or `"subscription"`) gates the api_key requirement.

## Cost Reporting

Same pattern as the Codex backend: `OOMPAH_OPENCODE_BILLING` env var (default `"per_token"`) controls cost reporting. Terminal event's `usage` dict includes `cost_usd` (None for subscription tier, populated for per-token when the SDK reports it).

## Implementation Checklist

- [x] `OpenCodeAcpBackend` + `OpenCodeAcpBackendSession` in `oompah/acp_backends/opencode.py`
- [x] `build_opencode_tool_catalog` in `oompah/acp_tools.py`
- [x] Register import in `oompah/acp_backends/__init__.py`
- [x] Tests in `tests/test_acp_opencode_backend.py`
- [x] Provider validation tests
- [x] Session lifecycle smoke tests (mock SDK)
- [x] Tool bridging round-trip tests
- [x] Cross-backend regression tests (claude + codex still work)

## Status

Complete — committed as `oompah-zlz_2-p1ti`.