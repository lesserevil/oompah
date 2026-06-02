---
id: TASK-407.4
title: Add role candidate selector state and ordering algorithms
status: In Progress
assignee: []
created_date: 2026-06-01 21:44
updated_date: 2026-06-02 15:12
labels:
- feature
- needs:backend
- needs:test
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
created: 2026-06-02 15:20

UNDERSTANDING: Task requires adding CandidateSelector - a runtime state tracker and ordering algorithm for role candidates. The data model (Candidate, Role with multi-candidates, strategy) is already implemented in oompah/roles.py. What is missing: CandidateSelector class with ordered_candidates(role) and record_used() methods, separate role_usage.json storage, thread safety. Plan: implement CandidateSelector in oompah/roles.py and write comprehensive tests.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-02 15:25

DISCOVERY: Confirmed no CandidateSelector exists in any file. The roles.py has the Role/Candidate data model and RoleStore but no runtime selection state. The implementation plan calls for .oompah/role_usage.json with nested {role_name: {provider_id: {model: last_used_at_iso}}} structure, a threading.Lock for concurrency, and two public methods: ordered_candidates(role) and record_used(role_name, candidate).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-02 15:35

IMPLEMENTATION: Added CandidateSelector class to oompah/roles.py with DEFAULT_USAGE_PATH constant. Implemented: (1) ordered_candidates(role) - returns priority order for priority strategy, LRU order for round_robin with never-used-first and configured-index tiebreaking; (2) record_used(role_name, candidate) - persists ISO timestamp to role_usage.json under lock; (3) thread-safe lock around all state mutations. Usage state uses nested dict {role: {provider_id: {model: ts}}}. Stale entries silently ignored.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
