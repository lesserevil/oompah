---
id: TASK-467.2
title: Bound and parallelize project-scoped refresh work
status: In Progress
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-08 20:18'
labels:
  - task
  - tick-latency
  - dispatch-performance
  - 'needs:backend'
  - 'needs:test'
dependencies:
  - TASK-467.1
  - TASK-465.1
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-467
ordinal: 12
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Refactor candidate fetch, running-state refresh, review fetch, merged-branch fetch, and maintenance project scans to use bounded per-project concurrency with timeouts and stale-cache fallback. The dispatch lane should use the freshest complete data available while avoiding one slow project blocking all other projects.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A slow or wedged project refresh does not block dispatch for unrelated projects after its timeout.
- [ ] #2 Review/open-PR gating remains conservative when refresh data is stale or unavailable.
- [ ] #3 Per-project refresh timings and timeout counts are visible in diagnostics.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 20:12
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 20:17
---
UNDERSTANDING: As Test Engineer, I need to write tests for the bounded per-project parallel refresh behavior in oompah/orchestrator.py. The key behaviors to test are:

1. _fetch_all_candidates: parallel fetch across projects, TrackerTimeoutError per project doesn't block others, returns [] for failed projects, logs WARNING for timeouts
2. _fetch_in_progress_issues: same pattern
3. _fetch_all_reviews: stale-cache fallback - failed fetches return previous cache (not []), conservative behavior
4. _fetch_all_merged_branches: failed projects return empty set, others succeed
5. Dispatch isolation: one slow project (TrackerTimeoutError) doesn't prevent candidates from other projects

Acceptance criteria drive the test design:
- AC#1: Slow/wedged project doesn't block others → test multi-project fetch where one times out
- AC#2: Conservative review gating with stale/unavailable data → test _fetch_all_reviews stale-cache fallback
- AC#3: Diagnostics visibility → test slow-tick warning includes timing info

Target file: tests/test_orchestrator_handlers.py - adding new test classes for multi-project parallel refresh.
---

author: oompah
created: 2026-06-08 20:18
---
DISCOVERY: The key functions for bounded parallel refresh are in oompah/orchestrator.py:
- _fetch_all_candidates (L1811): uses ThreadPoolExecutor(max_workers=min(len(projects),4)), handles TrackerTimeoutError with WARNING log, returns [] for failed projects
- _fetch_in_progress_issues (L1868): same pattern
- _fetch_all_reviews (L4015): has stale-cache fallback - captures previous_cache at start, returns _cached_reviews() on webhook-healthy, provider-absent, or exception cases (conservative)  
- _fetch_all_merged_branches (L4070): returns empty set for failed projects, no stale cache

Existing coverage: TestFetchAllCandidatesTimeout covers single-project timeout logging. Missing: multi-project isolation tests, stale-cache fallback verification, slow-tick timing diagnostics, conservative review gating with stale data.

Will add new test classes in test_orchestrator_handlers.py covering AC#1 (isolation), AC#2 (conservative caching), and AC#3 (diagnostics).
---
<!-- COMMENTS:END -->
