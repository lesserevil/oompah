---
id: TASK-407.5
title: Refactor orchestrator dispatch to try role candidates with failover
status: Done
assignee: []
created_date: '2026-06-01 21:44'
updated_date: '2026-06-03 03:01'
labels:
  - feature
dependencies:
  - TASK-407.3
  - TASK-407.4
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-407
priority: high
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Change the orchestrator so agent dispatch receives an ordered list of concrete provider/model targets for a role and can try the next target when the first one cannot start.

Current state to inspect first:
- oompah/orchestrator.py has _resolve_role, _resolve_provider, and _resolve_model paths that return one provider/model.
- _run_api_worker and _run_acp_worker may re-resolve provider/model inside worker execution.
- Existing retry and escalation logic is task/profile-level, not candidate-level.

Required behavior:
- Resolve role candidates once for the dispatch attempt and produce ordered DispatchTarget values.
- A DispatchTarget should include role name, provider, model, candidate key, and enough information for logging/status.
- API and ACP workers should receive the selected provider/model explicitly instead of resolving them again later.
- If candidate startup fails for provider availability reasons, try the next candidate before failing the worker.
- Existing task retry/escalation behavior must remain for non-provider task failures.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Priority roles try the first candidate, then the second when the first has a retryable provider startup failure.
- [ ] #2 Round-robin roles start with the least-recently-used candidate and fall back through the remaining candidates.
- [ ] #3 Provider/model is resolved once per candidate attempt and passed explicitly into API or ACP worker code.
- [ ] #4 A normal task failure after an agent has started does not silently switch provider unless it is classified as provider availability failure.
- [ ] #5 Running agent status shows the provider/model actually selected.
- [ ] #6 Existing focus/profile provider/model overrides continue to behave as before.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a small DispatchTarget dataclass or typed structure near the orchestrator resolution code.
2. Replace _resolve_role usage with a method that returns ordered targets from the role candidate selector.
3. Preserve focus/profile precedence: explicit focus provider/model still wins; focus/profile model_role uses the multi-candidate role config; legacy profile provider/model fallback continues until removed by a later cleanup.
4. Update _run_worker, _run_api_worker, and _run_acp_worker so the chosen target is passed in and not re-resolved mid-run.
5. Add a loop that tries targets in order when startup/preflight fails with a retryable provider reason.
6. Record selector usage only for the target that is actually selected for an agent start.
7. Ensure logs, running entries, dashboard status, and comments show the actual provider/model used.
8. Add tests that mock candidate failures and verify the next candidate starts.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
UNDERSTANDING [oompah 2026-06-02]: Investigating duplicates. Confirmed NOT a duplicate. TASK-407.5 is a distinct part of the TASK-407 epic. TASK-407.4 (Merged) provides CandidateSelector. This task adds DispatchTarget dataclass and candidate failover loop in orchestrator dispatch. Proceeding with implementation.

DISCOVERY [oompah 2026-06-02]: Key findings from codebase exploration: (1) CandidateSelector already implemented in oompah/roles.py (TASK-407.4, Merged). (2) orchestrator.py has _resolve_role/_resolve_provider/_resolve_model that need updating. (3) _run_api_worker raises ValueError before its try: block for startup validation — these need to become ProviderStartupError to propagate correctly to the failover loop. (4) _run_worker needs to resolve ordered DispatchTargets and loop with failover. (5) When target is explicit, focus overrides must use _resolve_focus_provider_override() to avoid re-resolving profile.model_role (which would always return first candidate). (6) All-candidates-fail case must explicitly call _on_worker_exit since inner workers won't have done so.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Merge conflict resolved: rebased TASK-407.5 onto main. The implementation commit was already present in main (PR #202 via cherry-pick detection). Rebased cleanly with no code conflicts. All 342 tests pass. Force-pushed.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Orchestrator tests cover priority fallback, round-robin fallback, explicit override precedence, and non-provider failure behavior.
- [ ] #2 No real providers are called in tests.
<!-- DOD:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 16:05

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-02 16:06

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-02 16:34

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-03 02:44

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-03 03:00

DISCOVERY: Confirmed NOT a duplicate. Searched for similar tasks across the TASK-407 epic and codebase. This is a unique implementation task: TASK-407.4 (Merged) provides CandidateSelector; TASK-407.5 adds DispatchTarget, _resolve_dispatch_targets(), and the failover loop in _run_worker. No other task covers the same ground.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-03 03:01

VERIFICATION: All 317 tests pass (pytest tests/test_orchestrator_handlers.py, test_candidate_selector.py, test_role_store.py, test_roles_api.py). Implementation in commit 46bf2ab covers: ProviderStartupError, DispatchTarget dataclass, _resolve_dispatch_targets(), _resolve_focus_provider_override(), and candidate failover loop in _run_worker with 26 targeted tests covering priority fallback, round-robin fallback, override precedence, and non-provider failure behavior.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-03 03:02

COMPLETION: Implementation was already committed by a prior agent session. Duplicate investigation confirmed this is not a duplicate. All acceptance criteria are met: (1) priority/round-robin failover works, (2) provider resolved once and passed explicitly to workers, (3) non-provider failures don't trigger candidate switch, (4) running status reflects actual provider/model selected, (5) focus/profile overrides preserved. Tests pass. Closing task.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-03 03:10

MERGE CONFLICT RESOLVED: Rebased TASK-407.5 onto origin/main. The implementation commit (46bf2ab) was already present in main as PR #202 — git cherry-pick detection skipped it cleanly. Only the Close task commit (backlog file update) remained. No code conflicts existed. Ran tests (130 orchestrator tests + 212 role/selector tests = 342 total pass). Force-pushed rebased branch. Task status confirmed Done.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
