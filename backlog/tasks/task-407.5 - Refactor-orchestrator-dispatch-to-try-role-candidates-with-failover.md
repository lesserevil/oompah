---
id: TASK-407.5
title: Refactor orchestrator dispatch to try role candidates with failover
status: To Do
assignee: []
created_date: '2026-06-01 21:44'
labels:
  - feature
  - 'needs:backend'
  - 'needs:test'
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Orchestrator tests cover priority fallback, round-robin fallback, explicit override precedence, and non-provider failure behavior.
- [ ] #2 No real providers are called in tests.
<!-- DOD:END -->
