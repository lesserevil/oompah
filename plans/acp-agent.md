# ACP agent execution path (experimental)

> **Status: experimental — not committed.** This document records a proposed
> direction for adding a third agent execution mode to oompah, alongside the
> existing CLI-subprocess and OpenAI-compatible-chat-completions paths. It
> has not been implemented and may be rejected, replaced, or significantly
> reshaped before any work begins.

## Why

Today oompah has two ways to run an agent against an issue:

1. **CLI mode** — `oompah/agent.py:AgentSession` spawns whatever
   `profile.command` says (currently `claude --dangerously-skip-permissions`)
   and reads its native streaming-JSON output line-by-line. Selected by
   `_run_cli_worker` when no provider resolves.
2. **API mode** — `oompah/api_agent.py:ApiAgentSession` speaks
   OpenAI-compatible chat completions directly to a configured provider
   (InferenceAPI, Godspeed) and runs the agent loop in-process. Selected by
   `_run_api_worker` when a provider resolves. This is the path we've been
   using all session.

API mode owns the budget tracking, focus triage hookup, per-agent JSONL
logging, context-budget pruning, transient-error retry, and the cd /
shell-tool-name guards. CLI mode is the original implementation; it
predates much of that infrastructure.

ACP (Agent Client Protocol) is a third option. It's a JSON-RPC over stdio
contract that several agents implement (`claude --acp`, `gemini --acp`,
some Cursor builds, future ACP-speaking agents). Adding an ACP mode
gives oompah:

- **Protocol portability** — swap in any ACP server without changing the
  orchestrator or rewriting an agent loop. Today, supporting a new agent
  means writing a new client (api_agent has 1500+ lines).
- **Native agent loop** — multi-step tool use, permission requests,
  file-edit operations, planning all run inside the agent rather than
  being re-derived via chat completions. Less risk of subtle drift between
  what api_agent does and what the agent actually wants to do.
- **Stable contract** — ACP messages have explicit shapes
  (`session.new`, `prompt.send`, `permission.request`, `tool.execute`)
  that don't churn with each provider's chat-completions field
  additions.

What it does NOT give us:

- New Claude capabilities. `claude --dangerously-skip-permissions` (CLI
  mode) already runs the same Claude binary; ACP is a different transport
  for the same engine.
- Free tooling. The budget tracking, focus triage, and JSONL logging that
  api_agent has would need to be plumbed through the new mode separately.
- A drop-in replacement. The execution model differs — ACP servers
  manage their own working directory and tool-call lifetimes; oompah
  has to map its issue/worktree/tool surface onto that contract.

## Architecture

A new `oompah/acp_agent.py` modeled on `api_agent.py`'s shape:

### Selection

`_run_worker` becomes a 3-way decision keyed off a new profile field
`mode: api | acp | cli`. Default behavior unchanged: profiles that don't
set `mode` follow the existing api-if-provider-else-cli logic. Profiles
that opt in via `mode: acp` get routed to the new path.

### Session lifecycle

1. **Spawn**. `asyncio.create_subprocess_exec(profile.command, ...)`
   with stdin/stdout pipes. `profile.command` for an ACP profile is
   something like `claude --acp` or `gemini --acp`.
2. **Initialize**. Send `initialize` request with our protocol version
   and capabilities (tool surface). Read the agent's `initialize`
   response.
3. **Open session**. Send `session.new` with the worktree path as the
   working directory, the rendered WORKFLOW.md prompt as the system
   message, and the agent profile's model preference (passed through if
   the agent supports model selection).
4. **Loop on stream**. Read JSON-RPC messages from stdout in a tight
   asyncio reader. For each:
   - `prompt.streaming_chunk` → forward to per-agent JSONL log
     (existing logging.py shape) and update token counters.
   - `tool.execute` → bridge to oompah's tool catalog
     (`workspace_tools.execute(...)` etc.); send back `tool.result`.
   - `permission.request` → auto-accept under YOLO (mirrors
     `--dangerously-skip-permissions`) and respond with `permission.allow`.
   - `session.update` (status changes) → translate to `AgentEvent` for
     the orchestrator's state.
5. **Termination**. On agent's `session.end` or our own stall/turn-limit
   trigger, send `session.end` ourselves and `terminate()` the
   subprocess. Capture exit code, flush logs.

### Tool surface bridging

ACP agents typically come with their own built-in tools (file ops, shell,
search). Two approaches:

- **A. Native tools** — let the agent use its own. oompah just brokers
  permissions and watches for misbehavior. Simplest, least leverage.
- **B. Bridged tools** — declare oompah's existing tool catalog
  (read_file / edit_file / run_command / search_files / list_files /
  the tracker-routing helpers) in `initialize.capabilities.tools`. The agent
  picks ours over its built-ins. This keeps the cd-guard and
  shell-as-tool-name redirects functional, and routes tracker commands
  through the backend-specific environment (`BEADS_DIR` for beads,
  Backlog.md path/root hints for Backlog.md).

Recommendation: **B**, even though it's more work, because losing the
guards is unacceptable.

### Logging + cost tracking

ACP messages don't carry token usage in the standard schema (this differs
from chat completions where `usage` is on the response). Two options:

- Capture token data from the agent's stderr or sidecar log (varies by
  agent, brittle).
- Run ACP profiles without budget enforcement and emit a one-time
  warning. Operator opts in knowing cost is unaccounted.

Recommendation: **acceptable degradation for v1** — disable budget
checks for ACP profiles and emit `Budget tracking disabled for ACP
profiles in this build` once at startup. Cost tracking can be a follow-up
once we know which agents expose usage and how.

For per-agent JSONL logging: keep the existing
`~/.oompah/agent-logs/<id>__<ts>.jsonl` shape. Map ACP message types to
the existing `kind: request|response|activity` taxonomy where possible;
emit unknown types as `kind: acp_raw` with the message body. The
agent_watcher detectors (planned in `plans/agent-watcher.md`) keep working
because they pattern-match on `event_kind: tool_call/tool_result` which
we'd populate from ACP `tool.execute`/`tool.result`.

### Files

- `oompah/acp_agent.py` — new. `AcpAgentSession` class mirroring
  `ApiAgentSession`'s public shape (`run_task`, `input_tokens`,
  `output_tokens`, `total_tokens`, `terminate`).
- `oompah/orchestrator.py` — extend `_run_worker` to dispatch on
  `profile.mode`, add `_run_acp_worker` symmetric to `_run_api_worker`.
- `oompah/models.py` — add `mode: str = "auto"` to `AgentProfile` and
  thread it through `from_yaml`.
- `tests/test_acp_agent.py` — fake ACP server fixture (a Python
  subprocess that echoes scripted JSON-RPC), assertions on session
  init, tool bridging, permission auto-accept, stall behavior.

### What does NOT change

- `oompah/api_agent.py` — untouched. API mode stays the default for
  Claude/MiniMax/etc. via inference-api.
- `oompah/agent.py` (CLI mode) — untouched. Still available as the
  fallback when no provider resolves and a profile prefers `mode: cli`.
- WORKFLOW.md profile shape — only an additive `mode` field.
- Focus triage, description gate, webhook handlers — none of these
  touch the agent runtime.

## Estimated scope

~2 days. ACP itself is a small protocol but the wiring touches the
worker dispatch, profile config, tool bridging, logging, and tests.
Hardest part is the tool-bridging: getting `tool.execute` payloads
into our existing tool functions without losing the cd-guard / shell-as-
tool-name redirect / context-budget pruning. Smallest part is the
JSON-RPC client itself (~150 lines).

## Reasons we might NOT want this

- Three execution paths is one more thing to break and one more matrix
  to test against. CLI + API + ACP × all guard rails × all retry paths
  × all per-state behaviors.
- We already have `claude` running via CLI mode. ACP doesn't unlock new
  Claude capabilities — it's a different wire format for the same
  agent.
- ACP servers vary in which extensions they implement
  (`fs.read`, `terminal.execute`, `mcp.list_tools`). We'd need to
  detect capability and degrade — more conditional code.
- Token-accounting gap means budget caps don't apply to ACP profiles
  in v1. That's a real downgrade if you've gone to the trouble of
  configuring `$50/hour`.

## Reasons we might

- Future-proofing: the next ACP-native agent (and there will be more)
  becomes a one-line config change rather than a 1500-line client port.
- Native loop for complex multi-step work. The agent's planner runs
  in-process; we don't have to re-derive multi-tool sequences via the
  chat completions API's request/response pattern.
- Aligns with where the broader ecosystem is moving. Zed + Claude Code +
  Cursor all converging on ACP as the local-agent contract.

## Out of scope for v1

- MCP integration. ACP servers can themselves connect to MCP servers, but
  oompah orchestrating MCP servers on behalf of ACP agents is a separate
  concern.
- Per-ACP-server capability negotiation. v1 supports a fixed expected
  capability set (initialize → session.new → prompt → tool/permission →
  session.end). If an agent doesn't support that, we error out rather
  than degrade.
- Cross-agent comparison runs. Some operators will want "run this issue
  on Claude-ACP and Gemini-ACP, compare diffs, pick the better one".
  Out of scope; could be layered on top later.

## Open design questions

**Q1 — Profile mode field default**
Add `mode: auto` (existing behavior: api if provider resolves, else cli)
or `mode: api` (no auto)? Auto preserves zero-config behavior; explicit
`api` is more predictable. **Recommend: `auto`**, with the existing
api/cli decision logic. Operators opt into ACP per profile.

**Q2 — Tool surface bridging (A or B)**
A: let the ACP agent use its native tools (simpler, loses oompah's
guards). B: declare oompah's tool catalog in `initialize.capabilities`
and intercept `tool.execute` (more work, preserves guards).
**Recommend: B**. The guards are too valuable to lose.

**Q3 — Budget tracking**
ACP doesn't standardize token-usage reporting. Disable budget checks for
ACP profiles in v1 with a one-time warning, or block-list them entirely
until we have a token-counting story?
**Recommend: disable with warning**. Block-list is too restrictive for
an experimental feature.

**Q4 — Permission model**
Auto-accept all `permission.request` (mirroring
`--dangerously-skip-permissions`) or have oompah middleware check
something? Today's CLI mode already runs claude with
`--dangerously-skip-permissions`, so symmetry says auto-accept. But ACP
lets us audit — should we log what was auto-accepted?
**Recommend: auto-accept + log to per-agent JSONL** as `kind: acp_permission_grant`
events so the agent_watcher can flag overly-broad grants later.

**Q5 — Initial agent target**
Just `claude --acp` for v1, or build it against a fake reference server
and let operators wire any ACP-speaking agent? Building against the fake
server is more rigorous; starting with claude is faster to demo.
**Recommend: fake server in tests, claude in real config**. The same
code paths are exercised by both, so we don't pay extra for the
flexibility.

**Q6 — Profile resolution interaction**
When `mode: acp` and `provider_id` is also set on the profile (because
the ACP agent honors `--model` flags backed by a specific provider's API
key), do we still resolve the provider as today? It would help with
metering / auth but creates an ambiguity (does the provider's
`default_model` override the ACP server's choice?).
**Recommend: provider_id is informational for ACP profiles** — passed
to the ACP agent's `--model` flag if the agent supports it, but oompah
doesn't second-guess the agent's actual model selection.

---

Once Q1-Q6 are answered, the next step is converting this to tracker
work items with the current project tracker (beads today, Backlog.md
after `plans/tracker-backends.md` lands):
- Parent epic for the ACP feature.
- One task per Files-to-touch entry (acp_agent.py, orchestrator.py
  dispatch routing, models.py field, tests).
- Dependency edges from the orchestrator wiring onto the
  acp_agent.py implementation onto the test scaffolding.

Do not create a beans tracker work item or plan a beans adapter for this
feature.
