---
id: TASK-407.5
title: Refactor orchestrator dispatch to try role candidates with failover
status: Done
assignee: []
created_date: '2026-06-01 21:44'
updated_date: '2026-06-03 03:10'
labels:
  - feature
dependencies:
  - TASK-407.3
  - TASK-407.4
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-407
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
Implementation already merged to main as PR #202 (commit 83c3579). DispatchTarget dataclass, ProviderStartupError, _resolve_dispatch_targets(), _resolve_focus_provider_override(), and candidate failover loop in _run_worker are all present in main. PR #214 merged the backlog task closure. Task re-dispatched due to orchestrator resetting status; closing as Done after confirming implementation is complete and correct.
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
created: 2026-06-03 02:44

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-03 02:49

Agent completed successfully in 315s (5650 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-03 02:49

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 53, Tool calls: 32
- Tokens: 35 in / 5.6K out [5.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 15s
- Log: TASK-407.5__20260603T024440Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-03 02:51

YOLO: Merge conflict detected on MR #214. Rebase onto main and resolve conflicts.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-03 02:53

YOLO: Merge conflict detected on MR #214. Rebase onto main and resolve conflicts.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 10
author: oompah
created: 2026-06-03 02:55

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 11
author: oompah
created: 2026-06-03 02:55

Focus: Merge Conflict Resolver
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 12
author: oompah
created: 2026-06-03 02:55

Agent failed: OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 13
author: oompah
created: 2026-06-03 02:55

Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Codex/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 6s
- Log: TASK-407.5__20260603T025545Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 14
author: oompah
created: 2026-06-03 02:56

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 15
author: oompah
created: 2026-06-03 02:56

Focus: Merge Conflict Resolver
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 16
author: oompah
created: 2026-06-03 03:01

Agent completed successfully in 324s (8802 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 17
author: oompah
created: 2026-06-03 03:01

Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Claude/default]
- Turns: 77, Tool calls: 51
- Tokens: 46 in / 8.8K out [8.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 24s
- Log: TASK-407.5__20260603T025607Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 18
author: oompah
created: 2026-06-03 03:01

Review handoff failed: the task branch has unmerged work but no review artifact was created.

Branch: `TASK-407.5`
Target branch: `main`
Unmerged commits: 3 commits
  796c93e TASK-407.5: Update final summary after merge conflict resolution
  921ff00 TASK-407.5: Resolve merge conflict - rebase onto main, implementation already merged
  8c17e28 TASK-407.5: Close task - mark Done with investigation comments and final summary

Reason: forge provider returned no review

Required: create or restore the PR/MR for this branch, then move the task to In Review only after the review exists.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 19
author: oompah
created: 2026-06-03 03:07

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 20
author: oompah
created: 2026-06-03 03:10

UNDERSTANDING (Duplicate Investigator): Task is NOT a duplicate — confirmed by prior agents and code inspection. The implementation of DispatchTarget, ProviderStartupError, _resolve_dispatch_targets(), _resolve_focus_provider_override(), and candidate failover loop in _run_worker is already merged to main as PR #202 (commit 83c3579). PR #214 (commit 24230f6) then merged the backlog task closure commits. The task was re-dispatched because the orchestrator reset status to In Progress in the working tree. Closing as Done — no new implementation needed.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
