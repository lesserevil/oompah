---
id: OOMPAH-257
type: task
status: In Progress
priority: null
title: Coalesce native-tracker mutations into durable state-branch checkpoints
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-256
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-20T16:29:39.587340Z'
updated_at: '2026-07-20T18:44:48.209870Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d4b1383a-e327-4807-b55a-951cdde1ba4d
oompah.task_costs:
  total_input_tokens: 23
  total_output_tokens: 5956
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 23
      output_tokens: 5956
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 23
    output_tokens: 5956
    cost_usd: 0.0
    recorded_at: '2026-07-20T18:43:55.884036+00:00'
---
## Summary

Scope

Reduce Git commit volume after state-branch support exists. Introduce a per-project single-writer checkpoint queue that immediately updates in-process/UI state but combines compatible native-tracker file mutations into one state-branch commit.

Implementation requirements

- Coalesce multiple pending mutations per project into one atomic checkpoint commit. Use configuration values from .env for debounce delay, maximum delay, and any queue bounds.
- Flush immediately for explicit human mutations, terminal task states, service shutdown, and any operation that requires durable state before continuing.
- Store durable task data: descriptions, state, dependencies, labels, human comments, and one concise handoff/result per completed focus. Do not emit a separate Git commit for heartbeats, polling, token/cost counters, retry counters, cache state, or intermediate agent chatter.
- Preserve task ordering and atomicity under concurrent API, webhook, and agent updates. On push races, safely rebase/retry the checkpoint without dropping updates.
- Expose checkpoint health and pending mutation count in the existing service status/observability surface.

Tests

- Deterministic clock test proves many mutations within the debounce window produce one commit containing all changed tasks.
- Maximum-delay and mandatory-flush tests cover terminal status, explicit human edit, and shutdown.
- Concurrent-writer and rebase-race tests prove no task mutation is lost or reordered.
- Regression test proves ephemeral agent updates do not create commits while a focus handoff does.
- Integration test confirms all resulting commits target the configured state branch only.

Acceptance criteria

- Routine agent activity produces substantially fewer Git commits without losing durable task state.
- Required immediate transitions are durable before their caller receives success.
- Operators can observe pending/failed checkpoint work.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 18:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 18:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 18:40
---
Understanding: I am the Duplicate Investigator for OOMPAH-257. This task proposes a checkpoint queue system that coalesces native-tracker file mutations into single atomic state-branch commits, reducing Git commit volume. Key concepts: debounce/coalesce logic, durable state-branch commits, mandatory flush for terminal states/human edits/shutdown, ephemeral-vs-durable distinction, rebase-race safety. I will now search for existing tasks covering the same ground before any implementation begins.
---
author: oompah
created: 2026-07-20 18:43
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-257 is NOT a duplicate of any existing task.

**Evidence reviewed:**
- Searched all .oompah/tasks/ directories for: coalesce, checkpoint, debounce, commit volume, mutation, batch commit, durable, state-branch
- Read plans/state-branch-design.md (§5 Checkpoint coalescing policy) — the authoritative design spec for this task's implementation scope
- Reviewed all sibling tasks in the OOMPAH-253 epic:
  - OOMPAH-254 (Done): design document creation — distinct, covers design not implementation
  - OOMPAH-255 (Done): project model fields (state_branch_enabled, checkpoint_debounce_ms, checkpoint_max_delay_ms) — distinct, config model only, no coalescing logic
  - OOMPAH-256 (Done): state-branch-aware tracker reads/writes via git worktree — distinct, write routing not coalescing; OOMPAH-256's duplicate investigator explicitly noted OOMPAH-257 is 'write coalescing, not read/write routing'
  - OOMPAH-258 (Open): bootstrap and docs — distinct scope
  - OOMPAH-259 (Open): migration of existing projects — distinct scope
  - OOMPAH-260 (Open): E2E validation — distinct scope
  - OOMPAH-265, OOMPAH-267, OOMPAH-268, OOMPAH-270: git lock/push-race bug fixes — different scope, no coalescing logic
- Also reviewed archived tasks OOMPAH-264, OOMPAH-266 — about suppressing rebase task auto-filing, not coalescing

**Closest reviewed tasks (all confirmed distinct):**
- OOMPAH-256 (Done): Implements git worktree write routing, not the debounce/coalesce/flush-on-terminal-state behavior
- OOMPAH-255 (Done): Added the per-project config fields that OOMPAH-257 will consume, but no runtime coalescing logic

**Key implementation scope for the next agent (from plans/state-branch-design.md §5 and §7.3):**
- _schedule_checkpoint(): start/reset debounce timer (OOMPAH_STATE_BRANCH_CHECKPOINT_DEBOUNCE_MS, default 5s)
- _flush_checkpoint(reason): commit all pending in-memory mutations atomically and push to origin
- Maximum delay timer (OOMPAH_STATE_BRANCH_CHECKPOINT_MAX_DELAY_MS, default 30s) forcing flush regardless of ongoing activity
- Mandatory immediate flush: terminal task states (Done/Merged/Archived), In Review, agent session exit, SIGTERM, human API mutations, release_addendum transitions
- Durable vs ephemeral classification (§4): only commit task status/title/description/labels/deps/human-comments/handoffs; never commit heartbeats/token-counters/retry-counts/cache state
- Concurrent-writer safety: _write_lock RLock covers entire in-memory mutation + checkpoint flush
- Push-race recovery: fetch → rebase --autostash → retry (OOMPAH_STATE_BRANCH_PUSH_RETRY_COUNT, default 3)
- Observability: GET /api/v1/state → state_branch block with pending_mutations, last_push_at, push_failures, alert
- Tests per task description: deterministic clock test (debounce coalescing), max-delay test, mandatory-flush test, concurrent-writer/rebase-race test, ephemeral-vs-durable regression test, integration test (commits target state branch only)

**Blocker status:** OOMPAH-256 is Done — OOMPAH-257 is now unblocked.

**Recommended next focus:** feature (backend implementation of checkpoint coalescing queue)
---
author: oompah
created: 2026-07-20 18:43
---
Agent completed successfully in 212s (5979 tokens)
---
author: oompah
created: 2026-07-20 18:44
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 43, Tool calls: 30
- Tokens: 23 in / 6.0K out [6.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 32s
- Log: OOMPAH-257__20260720T184035Z.jsonl
---
author: oompah
created: 2026-07-20 18:44
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-20 18:44
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-20 18:44
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-20 18:44
---
Understanding: I am the Test Engineer for OOMPAH-257. My role is to write comprehensive tests for the checkpoint coalescing queue system. From the prior agent's handoff, the key behaviors to test are: (1) debounce coalescing — many mutations within the window produce one commit, (2) max-delay flush — timer forces commit regardless of activity, (3) mandatory immediate flush — terminal states (Done/Merged/Archived), human edits, shutdown, (4) concurrent-writer safety — no mutations lost under concurrent access, (5) rebase-race recovery — push races handled without data loss, (6) ephemeral-vs-durable classification — heartbeats/token counters don't create commits, (7) integration — all commits target state branch only. I will now explore the codebase to find the implementation to test.
---
<!-- COMMENTS:END -->
