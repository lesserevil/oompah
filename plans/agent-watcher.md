# Agent watcher (experimental)

> **Status: experimental — not committed.** This document records a proposed
> direction for an in-process watcher that observes completed agent runs and
> auto-files deferred tracker tasks for misbehavior patterns. It has not been
> implemented and may be rejected, replaced, or significantly reshaped before
> any work begins.

## Why

The /loop session today repeatedly pattern-matched over `make logs` and the
per-agent JSONL files at `~/.oompah/agent-logs/<id>__<utc-ts>.jsonl` for
things like:

- `Error: refusing to run` (cd-out-of-worktree guard tripped)
- `"<X>" is not a tool` (shell-command-as-tool-name)
- Agents past turn 40 still working, with no tracker close operation in sight
- Agents that committed and pushed but never moved the task to a terminal state
- Repeated identical tool errors below the stall watchdog's 3-error fatal threshold
- Context-budget prune events (signals oversized prompt / overlong run)
- Long stretches of `thinking` events with zero tool calls

These are second-order signals. They don't crash anything, but they're how
dispatch budget gets burned silently. Today the only auto-filed issue path is
`oompah.error_watcher.ErrorWatcher` for backend `logger.error(...)` calls
and frontend JS errors. Behavioral misbehaviors never get recorded.

## Decisions taken in conversation

| Q | Decision |
|---|---|
| **Initial status** (Q1) | `deferred` — operator review first, dispatcher does not auto-fix. Mirrors `ErrorWatcher`. |
| **Dedup grain** (Q2) | Per-fingerprint across all time. Each filed tracker task carries a note/comment listing the latest 5 occurrences (issue id, turn, ts). |
| **Live or post-mortem** (Q3) | Post-mortem only for v1. Live wires can be added later if post-mortem evidence shows a pattern that needs to be caught mid-flight. |
| **commit_without_close source** (Q4) | Both: tool stream check (did the agent call the tracker-specific close operation?) AND a tracker re-query at end of run (is it actually terminal, possibly by the operator via UI). Only file the report when both say no. |
| **Annotate original or new task** (Q5) | Both. Add a comment on the original issue so the next agent dispatched on it sees the prior misbehavior, AND file a new deferred tracker task for the operator-facing fix. |
| **Truncated runs** (Q6) | Scan partial logs anyway, tag the report with `partial_run: true` so operators don't over-read. |

## Architecture

Mirror the existing `ErrorWatcher` split.

### Layer 1 — `AgentWatcher` (post-mortem, default)

Tails completed agent JSONL log files. Runs detectors over the full event
stream, files one deferred task per *unique* fingerprint, with the existing
issue annotated.

Trigger: orchestrator calls `AgentWatcher.scan_log(log_path, issue_id,
project_id, exit_reason)` from `_on_worker_exit` (the post-completion
handler). Runs in `_tick_pool` so it doesn't block the main loop.

Reasons to stay post-mortem:
- No hot-path overhead.
- Sees the entire run in context (loops are easier to detect with full history).
- The stall watchdog and cd-guard already act live for fatal cases.

### Layer 2 — live signals (deferred)

Optional follow-up. Hook the live detection points (`stall_watchdog`,
`_validate_command_stays_in_workspace`, `_execute_tool` redirect) to also
emit "live misbehavior events" that AgentWatcher consumes. Don't build
this in v1.

## Detection categories (post-mortem)

Each detector consumes the JSONL event stream and emits zero or more
`MisbehaviorReport(category, issue_id, summary, evidence_excerpt,
turn_range, fingerprint, partial_run)`.

| Category | Detector | Default priority |
|---|---|---|
| `loop:identical_tool_calls` | ≥5 consecutive tool calls with byte-identical (name, args) | 2 |
| `loop:repeated_tool_error` | ≥5 tool errors with identical normalized message text | 2 |
| `loop:thrash_file` | Same file edited ≥10× across the run with no test progress between | 3 |
| `commit_without_close` | `git commit` + `git push` succeed but no tracker close operation before run end (only flag for `Worker completed normally`, AND tracker detail confirms not-terminal) | 1 |
| `cd_out_of_worktree` | `Error: refusing to run` appears in any tool result | 2 |
| `shell_as_tool_name` | `"<X>" is not a tool` redirect appears | 2 |
| `over_turn_budget` | Run hit `max_turns` without moving the task to a terminal state | 2 |
| `context_pruned_repeatedly` | ≥3 prune events in one run (oversized prompt) | 3 |
| `silent_thinking_burn` | ≥10 turns in a row of `thinking` with zero tool calls | 3 |
| `focus_complaint` | Agent's own messages match phrases like "wrong focus", "not the right specialist", "this isn't a frontend issue" | 4 |

Categories are independent. One run can emit multiple reports, deduped per
fingerprint.

## Filing protocol

Mirrors `ErrorWatcher`, using the configured tracker backend:

```
title:        "[agent-misbehavior:<category>] <issue_id>: <short_summary>"
type:         bug
description:  evidence excerpt (≤500 lines) + path to full log
priority:     per table above
initial_status: deferred
labels:       agent-misbehavior, <category>, project:<name>
notes (Q2):   updated each occurrence with last 5 (issue, turn, ts)
```

### Dedup fingerprint

`sha256(category + normalized_summary)` where `normalized_summary` strips
turn numbers, timestamps, and per-issue identifiers. Same
`_DEDUP_WINDOW_SECONDS` and `_MAX_FINGERPRINTS` policy as `ErrorWatcher`.

So the same loop pattern across 50 runs files 1 deferred task, not 50.
Each new occurrence within the window just appends to the filed task's
note/comment and refreshes `last_seen`. Outside the window, a new task is
filed.

### Annotation on original issue (Q5)

For each report, also call:

```
tracker.add_comment(
    issue.identifier,
    f"AgentWatcher: {category} detected at turn {turn_range}. "
    f"Evidence: {short_excerpt}. See task {filed_task.identifier}.",
    author="oompah",
)
```

So when the issue is re-dispatched, the next agent sees what went wrong last
time. (And so the operator clicking into the issue sees the misbehavior
inline rather than having to cross-reference.)

### `partial_run` flag (Q6)

Detectors run on truncated logs (orchestrator killed mid-flight, drain
timeout, hard restart). Reports tagged `partial_run: true` get appended to
the title — `"[agent-misbehavior:loop:identical_tool_calls] (partial)
<issue>: ..."` — and to the description so operators know the evidence may
be incomplete.

## Files to touch

- `oompah/agent_watcher.py` — new. `AgentWatcher` class + `MisbehaviorReport`
  dataclass + per-category detector functions + tracker-backed filing helper.
- `oompah/orchestrator.py` — call `AgentWatcher.scan_log(...)` from
  `_on_worker_exit`.
- `tests/test_agent_watcher.py` — fixture-based: feed synthetic JSONL
  streams (and replays of real ones from `~/.oompah/agent-logs/`), assert
  correct reports filed and correctly deduped.

## What does NOT change

- Per-agent JSONL logging (already there; just consumed).
- Stall watchdog. Stays as the live fast-path; its handling is unchanged.
- `ErrorWatcher`. Untouched.
- Dispatcher / focus / triage. None of this changes agent behavior; it only
  records.
- WORKFLOW.md. No agent-prompt changes needed for v1.

## Estimated scope

~1 day. Detectors are mostly small pattern matchers over event streams.
Most of the work is testing each detector with real-world JSONL samples —
this session alone produced 30+, including real positives for
`cd_out_of_worktree`, `over_turn_budget`, `commit_without_close`, and
`loop:repeated_tool_error` (aib's escalation to deep was driven by it).

## Reasons we might NOT want this

- Adds a new background scan to `_on_worker_exit` — small CPU but new
  code path that can fail. Has to be defensively wrapped (any detector
  exception → log warning, do not block worker exit).
- More tasks in the backlog (deferred, but still cluttering). Mitigated by
  dedup, but operators may need a UI surface to bulk-resolve.
- Detector accuracy may be poor at first — false positives risk teaching
  operators to ignore the watcher, like `make logs` warnings that get
  tuned out.

## Reasons we might

- Captures a class of failures that today only surfaces if an operator
  manually scrubs `make logs` and the per-agent JSONL files. The /loop
  babysit session today found at least three real patterns (cd-out-of-
  worktree, shell-as-tool-name, agents committing without closing the task)
  that without the watcher would have to be re-discovered each time.
- Pairs naturally with the agentic focus triage and the description gate:
  triage and gate prevent bad dispatches, the watcher records when a
  successful dispatch went wrong anyway.
- Each filed tracker task with evidence is a closed-loop signal for prompt /
  guardrail improvements (e.g. "we keep tripping cd_out_of_worktree —
  WORKFLOW.md should emphasize harder").

## Out of scope for v1

- Live mid-flight pausing of misbehaving agents. Stall watchdog already
  covers the worst case (3 identical tool errors in a row). Add later only
  if post-mortem evidence shows a pattern worth catching live.
- Cross-run analysis (e.g. "this agent always loops on file Y" across many
  issues). v1 is per-run only. Cross-run would need a query layer over the
  filed task history and is a separate concern.
- Operator UI for bulk-resolving misbehavior tasks. v1 is just the filing.
