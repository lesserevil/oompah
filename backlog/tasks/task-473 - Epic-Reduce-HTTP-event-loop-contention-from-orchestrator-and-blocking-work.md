---
id: TASK-473
title: 'Epic: Reduce HTTP event-loop contention from orchestrator and blocking work'
status: Done
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 22:10'
labels:
  - feature
  - epic
  - 'needs:backend'
  - performance
dependencies: []
documentation:
  - backlog/docs/doc-1 - Granian-HTTP-server-migration-plan.md
priority: medium
ordinal: 198000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Complementary to the Granian adoption (Epic TASK-472) and the bigger performance lever: oompah's real load is LLM/subprocess/orchestrator-bound, and the web layer shares one event loop with the orchestrator. Route handlers contain ~11 subprocess/run_in_executor/sync-I/O sites; some hot paths do synchronous file reads in async handlers. This epic moves blocking work off the request loop, confirms the true bottleneck via profiling, and evaluates splitting the orchestrator into its own process (which would also unlock Granian multi-worker). See doc-1.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Hot request paths no longer block the event loop on sync I/O
- [ ] #2 Profiling identifies the true latency bottleneck under load
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Epic PR #255 merged into main with all four child tasks complete.
<!-- SECTION:FINAL_SUMMARY:END -->
