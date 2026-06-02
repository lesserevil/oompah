---
id: TASK-407.4
title: Add role candidate selector state and ordering algorithms
status: Done
assignee: []
created_date: '2026-06-01 21:44'
updated_date: '2026-06-02 15:24'
labels:
  - feature
dependencies:
  - TASK-407.1
modified_files:
  - oompah/roles.py
  - oompah/orchestrator.py
  - tests/test_role_store.py
parent_task_id: TASK-407
priority: high
ordinal: 34000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add the runtime state and ordering logic needed to choose role candidates for priority and round-robin strategies.

Current state to inspect first:
- RoleStore stores role config in .oompah/roles.json.
- The current orchestrator resolves one provider/model and has no candidate usage state.

Required behavior:
- Priority strategy returns candidates in the saved order.
- Round-robin strategy returns the least-recently-used candidate first, then the remaining candidates in deterministic fallback order.
- Runtime usage state should be separate from role config so normal dispatches do not constantly modify .oompah/roles.json.
- Usage state should be safe for concurrent dispatches inside the server process.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Priority strategy always returns candidates in configured order.
- [ ] #2 Round-robin strategy returns never-used candidates before recently used candidates.
- [ ] #3 Round-robin ties are resolved by configured order.
- [ ] #4 Recording usage updates only the selector-state file, not roles.json.
- [ ] #5 Removed candidates in stale usage state do not appear in ordered results.
- [ ] #6 Concurrent selector updates are protected by an in-process lock.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a small selector-state store, likely .oompah/role_usage.json, with a lock around load/update/save operations.
2. Key usage records by role name plus provider_id plus model so renamed or reordered candidates behave predictably.
3. Store last_used_at and optionally usage_count.
4. Add a helper that takes a Role and returns ordered candidates for dispatch according to the role strategy.
5. Add a method to record a candidate as used only after oompah has selected it for an actual agent start.
6. For round-robin ties, preserve configured candidate order so tests are deterministic.
7. Add unit tests for empty state, priority order, round-robin order, usage updates, ties, and removed candidates.
<!-- SECTION:PLAN:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Delivered CandidateSelector in oompah/roles.py with priority/round-robin ordering and thread-safe usage state in .oompah/role_usage.json. 56 tests in tests/test_candidate_selector.py cover all 6 acceptance criteria. No duplicate found for this task.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Selector state and ordering tests run without depending on the HTTP server.
- [ ] #2 The selector API is small enough for the orchestrator to use without duplicating ordering logic.
<!-- DOD:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 15:12

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-02 15:12

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-02 15:21

Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 82, Tool calls: 54
- Tokens: 45 in / 26.0K out [26.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 26s
- Log: TASK-407.4__20260602T151208Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-02 15:21

Agent completed successfully in 566s (26071 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-02 15:21

Agent completed without closing this issue (566s (26071 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-02 15:21

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
