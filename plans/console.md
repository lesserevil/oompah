# Per-project ACP console

**Status:** shipped via oompah-zlz_2-ebwe.

**Why:** Operators kept a shell open next to the dashboard for planning,
asking the model for help, closing beads by hand. oompah already drives
ACP sessions via `acp_agent.py` for worker dispatch — the console gives
the operator the same SDK + tool catalog, no context-switching.

## Shape

```mermaid
flowchart LR
  subgraph browsers
    A[browser A]
    B[browser B]
  end
  subgraph server
    WS["/ws<br/>(WebSocket)"]
    REST["GET /api/v1/console/{pid}/transcript"]
    MGR[ConsoleManager]
    SESS[ConsoleSession<br/>per project_id]
  end
  subgraph disk
    JL[".oompah/console/{pid}.jsonl"]
  end
  subgraph sdk
    ACP[AcpAgentSession<br/>spawned per turn]
  end

  A <-->|console_input / console_event| WS
  B <-->|console_input / console_event| WS
  A -->|page transcript| REST
  WS --> MGR
  REST --> MGR
  MGR --> SESS
  SESS -->|append| JL
  SESS -->|spawn| ACP
  ACP -->|on_event| SESS
  SESS -->|broadcast| WS
```

One project, one session, many viewers. The JSONL on disk IS the
canonical state of the conversation; service restarts simply read it
back on the next operator message.

## Files

* `oompah/console.py` — `ConsoleStore`, `ConsoleSession`,
  `ConsoleManager`, `render_transcript_as_prompt`.
* `oompah/server.py` — `_console_manager` global, wired in
  `set_orchestrator()`. WS handler routes `console_input` messages and
  fans `console_event` outputs over the existing `_ws_clients` pool.
  `GET /api/v1/console/{project_id}/transcript` paginates over disk.
* `oompah/templates/dashboard.html` — `console-overlay` panel + JS
  glue (`openConsolePanel`, `sendConsoleMessage`, `handleConsoleEvent`).

## Lifecycle

1. **Open the Console panel.** UI calls
   `GET /api/v1/console/{pid}/transcript?limit=200`. Server reads from
   `ConsoleStore` directly (no session needed); UI renders existing
   chat history.
2. **Operator types a message and hits Send.** UI emits
   `{type:"console_input", project_id, text, attachments?}` over WS.
3. **Server enqueues.** `_handle_console_input` calls
   `ConsoleManager.get_or_create(project_id)`, then
   `session.ensure_runner(loop)`, then `session.submit(text, ...)`.
   The session's asyncio.Queue serializes concurrent operator inputs.
4. **Background runner pulls one item at a time.** For each turn:
   * Append `operator_input` event to JSONL + broadcast to WS.
   * Call `resolve_backend(project_id)` — looks up project's
     `default` role → provider → provider.backend (default
     `"claude"`). Returns `{backend_name, model, permission_mode,
     beads_dir}`.
   * Build tool catalog: `build_tool_catalog(workspace_path,
     beads_dir=...)` for Claude, `build_codex_tool_catalog(...)` for
     Codex. The catalogs share the same `_exec_*` helpers as the worker
     dispatch path, so `cd`-out-of-worktree guard, `BEADS_DIR` routing,
     and per-command timeouts apply.
   * Build the prompt via `render_transcript_as_prompt(transcript,
     new_input=...)`. Replays Operator:/Assistant:/tool-use lines so
     the SDK has full conversational context. Caps history at 200
     events to keep prompts bounded (UI still shows all history).
   * Spawn a fresh `AcpAgentSession`. Each `acp_*` event the SDK
     emits is forwarded through `_on_event` into both
     `ConsoleStore.append(...)` and the WS broadcast.
5. **Turn ends.** `console_status` / `acp_result` events flow to
   clients; the runner pulls the next item.

## Design decisions

* **Per-input serialization, no concurrency.** Two operators typing
  at once → the second message queues server-side until the first
  turn completes. v1 just queues; v2 could surface "X is typing".

* **Replay-on-every-turn rather than in-memory ClaudeSDKClient
  reuse.** The Claude Agent SDK / openai-agents SDKs are
  session-shaped, but oompah's `AcpAgentSession` is single-turn
  (prompt-in, response-out). Reusing the worker path's machinery is
  vastly simpler than holding a long-lived SDK session open per
  project. Slightly more tokens per turn; the transcript JSONL is
  canonical, in-memory is just a cache for fast renders.

* **Permission mode `acceptEdits`.** The operator is the human gate
  sitting at the browser. The console is interactive by design.

* **No worker-bead coupling.** The console session does NOT claim or
  close beads on the operator's behalf via the dispatch loop — it
  just gives the operator a chat interface with tool access. The
  operator can still ask "close oompah-zlz_2-foo with reason X" and
  the model will use `run_command("bd close oompah-zlz_2-foo ...")`,
  but that's an explicit tool call, not orchestrator dispatch.

* **Cost accounting.** Per-token billing meters against the
  project's chosen provider via the same `_estimate_cost` path
  workers use. ACP-subscription providers bypass the budget gate.
  The console does NOT roll its tokens into the global per-tick
  budget pool — it's a separate interactive surface, billing flows
  through the SDK's terminal `total_cost_usd` on each turn's
  `acp_result` event.

* **Storage.** `.oompah/console/<project_id>.jsonl` is gitignored
  (transitively via `.oompah/` and explicitly via `.oompah/console/`
  in the root `.gitignore`). Manual `cp` is the v1 export path.

## What's out of scope (deliberately deferred)

* Multi-project conversations from one input. (Operator switches
  projects via the dropdown.)
* Sharing transcripts across projects.
* Transcript search / export to git.
* Branching conversations (single linear thread per project).
* Real attachment upload from the console panel. v1 just stashes
  filenames in the input payload so the operator can see what's
  queued; the bead-detail dropzone is the canonical attachment path.
* Hot model swap mid-turn.

## Testing

* `tests/test_console.py` — 24 cases covering ConsoleStore (append,
  read, pagination, malformed-line resilience, oversize event
  truncation, project_id sanitization), `render_transcript_as_prompt`
  (history cap, role formatting, tool inlining), ConsoleSession
  (submit persistence, broadcast fan-out, concurrent serialization,
  restart replay), and ConsoleManager (lazy construction, unknown
  project handling).
* `tests/test_server_console.py` — 6 cases covering the
  `GET /api/v1/console/{pid}/transcript` endpoint (empty / persisted /
  unknown project / not-initialized / limit cap / pagination).
