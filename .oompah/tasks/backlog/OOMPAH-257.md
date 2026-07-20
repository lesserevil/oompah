---
id: OOMPAH-257
type: task
status: Backlog
priority: null
title: Coalesce native-tracker mutations into durable state-branch checkpoints
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-256
labels: []
assignee: null
created_at: '2026-07-20T16:29:39.587340Z'
updated_at: '2026-07-20T16:30:38.296532Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

