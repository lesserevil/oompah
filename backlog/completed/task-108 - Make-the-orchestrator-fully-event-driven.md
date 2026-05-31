---
id: TASK-108
title: Make the orchestrator fully event-driven
status: Done
assignee: []
created_date: 2026-03-08 21:18
updated_date: 2026-03-08 22:37
labels:
- archive:yes
- epic
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: epic
beads:
  id: oompah-k3d
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-k3d
  target_branch: null
  url: null
  created_at: '2026-03-08T21:18:24Z'
  updated_at: '2026-03-08T22:37:41Z'
  closed_at: '2026-03-08T22:37:41Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem

The orchestrator's main loop (`orchestrator.py:run()`) is fundamentally poll-based. Every 30 seconds (configurable via `poll_interval_ms`), it runs a full `_tick()` cycle that:

1. **Reconciles** all running agents against the tracker (fetches states for every running issue)
2. **Fetches ALL candidate issues** from every configured project via `bd list --status=<state> --json` (one subprocess per state per project)
3. **Fetches ALL open reviews/PRs** from every project's forge (GitHub/GitLab API calls)
4. **Fetches ALL merged branches** from every project
5. **Pre-resolves blocker states** for candidates (more tracker calls)
6. **Sorts and dispatches** agents for eligible issues
7. **Runs YOLO review actions**, auto-archive, and merged-label passes
8. **Checks for git auto-update** when idle

This is ~10-20 subprocess/HTTP calls per tick, even when nothing has changed. With multiple projects, it scales linearly worse.

The `_refresh_requested` asyncio.Event provides a mechanism to trigger immediate ticks, but the tick itself always does a full world-scan regardless of what triggered it. There's no concept of "what changed" — every tick re-fetches everything.

## Goal

Replace the poll-based tick loop with an event-driven architecture where the orchestrator only acts in response to specific state changes. The existing `EventBus` (oompah/events.py) and `_refresh_requested` Event are the foundation.

## Current Architecture

```
run() loop:
  while not stopping:
    _tick()                          # full world scan every time
    wait(refresh_event, timeout=30s) # poll interval fallback
```

### What triggers work today:
- **New/changed issues in tracker** → discovered by polling `bd list`
- **Agent completes/fails** → already event-driven via `_on_worker_exit()`
- **PR state changes** → discovered by polling forge APIs
- **User actions** (pause/resume, manual dispatch, UI issue moves) → already event-driven via API endpoints that call `_refresh_requested.set()`
- **Retry timers firing** → already event-driven via `call_later()`

## Target Architecture

```
run() loop:
  while not stopping:
    event = await event_queue.get()    # block until something happens
    handle(event)                      # targeted action based on event type

    # Periodic full-sync as safety net (5-10 min, not 30s)
    if time_since_last_full_sync > full_sync_interval:
      _full_tick()
```

### Change-detection sources needed:

1. **Tracker changes (bd/Dolt)**: The tracker is backed by Dolt SQL server. Dolt supports `CALL dolt_log()` and diff queries. Add a lightweight change-detection query that checks if the working set has changed since the last poll (e.g., compare `@@<dbname>_working` hash or use `CALL dolt_status()`). If unchanged, skip the full candidate fetch. This replaces the expensive `bd list` calls with a single SQL query.

2. **Forge webhooks or polling optimization**: PR/review state changes currently require polling GitHub/GitLab APIs. Options:
   - **Webhook receiver**: Add an endpoint that GitHub/GitLab can POST to on PR events. This eliminates forge polling entirely.
   - **Conditional requests**: Use ETags/If-Modified-Since on forge API calls to avoid re-fetching unchanged data.
   - **Reduced frequency**: Move forge polling to a separate slower cadence (e.g., every 2-5 minutes) independent of the main dispatch loop.

3. **Internal events (already working)**: Agent lifecycle events, user actions, retry timers — these already use `_refresh_requested` or direct method calls.

## Key Design Decisions

### Split the monolithic _tick()

The current `_tick()` does 8 different things. Split it into targeted handlers:

- `_handle_dispatch_needed()` — only runs when tracker state changes or an agent exits
- `_handle_review_check()` — only runs when forge state might have changed
- `_handle_reconcile()` — only runs periodically or when an agent reports activity
- `_handle_yolo_review()` — only runs when reviews are fetched and have actionable items
- `_handle_auto_update()` — only runs when idle (no agents, no retries)

### Tracker change detection

The beads tracker uses Dolt SQL server. Instead of running `bd list` every 30s, we can:

1. Query `SELECT * FROM dolt_status` or compare the working set hash
2. If no changes, skip the full candidate fetch
3. If changes detected, fetch only changed issues (Dolt supports `dolt_diff()` queries)

This requires either:
- A new method on `BeadsTracker` that talks directly to the Dolt SQL server (port 3307/3308) instead of shelling out to `bd`
- Or a `bd` subcommand that returns a change hash/fingerprint cheaply

### Keep a safety-net full sync

Don't remove polling entirely. Keep a full sync at a much longer interval (5-10 minutes) as a consistency safety net. This catches edge cases like:
- External changes to the tracker database
- Missed webhook deliveries
- State drift from bugs

## What NOT to change

- **Agent lifecycle**: Already event-driven via callbacks. Don't touch.
- **WebSocket push**: Already event-driven via observers. Don't touch.
- **Retry timers**: Already use `call_later()`. Don't touch.
- **User API actions**: Already trigger `_refresh_requested`. Don't touch.

## Implementation order

1. Add tracker change-detection (cheap hash/diff query)
2. Split `_tick()` into targeted handlers
3. Replace the poll loop with an event-driven dispatch loop
4. Add forge webhook receiver (or conditional request optimization)
5. Add the safety-net full sync at longer interval
6. Remove or extend `poll_interval_ms` to safety-net-only role
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: e1c584bb-a647-4498-a53b-7d34a8435595
author: oompah
created: 2026-03-08T21:18:31Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ded2ff58-c614-4cec-bc99-fadd8f226ca9
author: oompah
created: 2026-03-08T21:18:32Z

Focus: Epic Planner
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 36f56650-cd05-4b94-b44e-dd07dca98a7c
author: oompah
created: 2026-03-08T21:18:37Z

I understand the issue: Make the orchestrator fully event-driven. My plan is to first explore the codebase and find the relevant code for the orchestrator's main loop, then identify the key components that need to be changed to achieve an event-driven architecture. After that, I will implement the changes, write tests, and finally commit and push my changes.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ac284198-c819-423d-b703-98fed8b9ef8c
author: oompah
created: 2026-03-08T21:18:56Z

Agent completed successfully in 24s (76268 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
