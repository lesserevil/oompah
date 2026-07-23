---
id: OOMPAH-430
type: task
status: In Progress
priority: null
title: Provide focus agents a supported tracker-handoff mutation path
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-23T22:26:45.549947Z'
updated_at: '2026-07-23T22:58:25.657444Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e67e071a-652d-4121-b279-d7a20d7bbed5
oompah.task_costs:
  total_input_tokens: 2342643
  total_output_tokens: 27538
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 2342643
      output_tokens: 27538
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 77
    output_tokens: 18389
    cost_usd: 0.0
    recorded_at: '2026-07-23T22:43:43.956769+00:00'
  - profile: standard
    model: unknown
    input_tokens: 1451155
    output_tokens: 5090
    cost_usd: 0.0
    recorded_at: '2026-07-23T22:46:45.727409+00:00'
  - profile: deep
    model: unknown
    input_tokens: 891411
    output_tokens: 4059
    cost_usd: 0.0
    recorded_at: '2026-07-23T22:49:18.683927+00:00'
---
## Summary

Focus handlers must record completion labels and a handoff comment before the scheduler chooses the next focus. EXOCOMP-55 showed that the agent environment lacked task-mutation MCP tools while project instructions prohibited loopback CLI use; duplicate screening therefore completed but could not persist its handoff and was retried repeatedly. Provide an approved mutation interface or change the focus protocol so agents can reliably add completion labels and comments. Add regression coverage for a no-commit focus completion advancing to the requested implementation focus. Acceptance: duplicate detection that finds no duplicate records its completion and handoff exactly once, and the next run begins feature work rather than another duplicate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 22:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 22:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 22:35
---
Understanding: Investigating OOMPAH-430 as Duplicate Investigator. The issue requests a supported mutation path for focus agents to record completion labels and handoff comments. EXOCOMP-55 is cited as the motivating incident where duplicate screening completed but couldn't persist its handoff (no MCP mutation tools in agent environment, loopback CLI prohibited). Will search for any prior tasks covering this same problem before handoff to implementation focus.
---
author: oompah
created: 2026-07-23 22:43
---
Discovery: No duplicate found. Searched all .oompah/tasks/ states (archived, done, merged, open, backlog), plans/, and docs/ for: focus handoff, mutation path, loopback CLI, EXOCOMP, MCP mutation, tracker handoff, agent mutation, focus complete, duplicate_detector handoff.

Closest candidates reviewed and ruled out:

1. OOMPAH-217 (Merged): 'Handoff cleared duplicate investigations to normal-focus agents' — implements _handoff_completed_focus and the two-stage duplicate investigation protocol. Does NOT provide an approved mutation interface for agents; it only adds server-side detection of completed focus. Scope is distinct.

2. OOMPAH-219 (Merged): Fixed bugs in _handoff_completed_focus (entry.id → entry.identifier) and added TestFocusHandoff tests. Does NOT add a no-commit focus completion regression test that covers the full pipeline through _on_worker_exit.

3. OOMPAH-419 (Merged): Defined the OpenAPI-to-MCP exposure policy (mcp_exposure_policy.py), exposing TASK_MUTATION routes. Scope is the policy definition only. The gateway implementation (OOMPAH-420) and integration tests (OOMPAH-421) are NOT yet committed (git log shows no commits for those identifiers).

Key gaps that OOMPAH-430 addresses (not covered by any prior task):
a) No test in test_acp_project_tools.py for add-label through _exec_oompah_task_command — the approved no-HTTP mutation path for focus agents adding focus-complete labels
b) No end-to-end regression test: duplicate_detector runs (no commits), posts handoff comment + adds label, _on_worker_exit is called, select_focus picks a feature focus (not duplicate_detector again)

Evidence: test_orchestrator_duplicate_detection.py::TestFocusHandoff tests _handoff_completed_focus in isolation but does not cover the full _on_worker_exit → _handoff_completed_focus → select_focus pipeline for a no-commit focus completion. test_acp_project_tools.py::TestExecOompahTaskCommand covers comment and set-status but not add-label.
---
author: oompah
created: 2026-07-23 22:43
---
Focus handoff: duplicate_detector

1. **Outcome**: No duplicate found. OOMPAH-430 is a unique task.

2. **Evidence reviewed**:
   - All .oompah/tasks/ states (200+ tasks scanned)
   - Key candidates: OOMPAH-217 (focus handoff protocol), OOMPAH-219 (handoff bug fixes + tests), OOMPAH-419 (MCP exposure policy)
   - None covers the specific requirements: (a) approved mutation interface tests for add-label via _exec_oompah_task_command, (b) end-to-end no-commit focus completion regression test
   - plans/mcp-openapi-exposure-policy.md references OOMPAH-420 (gateway) and OOMPAH-421 (tests) as not yet committed

3. **Remaining work**:
   - Add test for add-label (focus-complete label addition) through _exec_oompah_task_command in tests/test_acp_project_tools.py
   - Add end-to-end regression test in tests/test_orchestrator_duplicate_detection.py: no-commit duplicate_detector completes → _on_worker_exit → select_focus picks feature (not duplicate_detector again)
   - Risk: the _exec_oompah_task_command already handles add-label correctly per the code; tests are purely coverage gaps. No structural change needed for the approved mutation interface since the ACP tool interceptor already provides it.
   - Risk: the scenario where an agent environment has NO ACP interceptor (EXOCOMP-55 case with a different agent harness) may need OOMPAH-420 gateway implementation — but that is a separate, larger task already tracked.

4. **Recommended next focus**: feature (add the two missing regression tests; verify the existing code path already works for add-label; no new implementation required for the mutation interface itself)
---
author: oompah
created: 2026-07-23 22:43
---
Agent completed successfully in 501s (18466 tokens)
---
author: oompah
created: 2026-07-23 22:43
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 102, Tool calls: 74
- Tokens: 77 in / 18.4K out [18.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 21s
- Log: OOMPAH-430__20260723T223525Z.jsonl
---
author: oompah
created: 2026-07-23 22:43
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-23 22:44
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 22:44
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-23 22:46
---
Agent completed successfully in 162s (1456245 tokens)
---
author: oompah
created: 2026-07-23 22:46
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 18
- Tokens: 1.5M in / 5.1K out [1.5M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 42s
- Log: OOMPAH-430__20260723T224412Z.jsonl
---
author: oompah
created: 2026-07-23 22:46
---
Agent completed without closing this issue (162s (1456245 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-23 22:47
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-23 22:47
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-23 22:49
---
Agent completed successfully in 133s (895470 tokens)
---
author: oompah
created: 2026-07-23 22:49
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 13
- Tokens: 891.4K in / 4.1K out [895.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 13s
- Log: OOMPAH-430__20260723T224707Z.jsonl
---
author: oompah
created: 2026-07-23 22:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 22:49
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-23 22:50
---
Understanding: I am the third Technical Writer agent dispatched for this task. Prior Technical Writer agents (standard and deep Codex profiles) completed without closing the issue. The duplicate_detector focus already ran and found no duplicates, recommending a 'feature' focus for the implementation work. 

As Technical Writer, I will: (1) explore the existing code and test files to understand what mutation path documentation is needed, (2) determine if any plans/ or docs/ documentation is missing or incomplete regarding the focus-agent handoff protocol and mutation interface, (3) either write that documentation or, if the remaining work is purely test implementation, perform a proper focus handoff to 'feature'.

The prior agents appear to have read files but not produced any documentation or handoff comment. I will determine the correct path and complete this phase.
---
author: oompah
created: 2026-07-23 22:52
---
Discovery: Assessed the current state after reading all relevant code and docs.

Key findings:
1. The approved mutation interface (ACP run_command interceptor via _exec_oompah_task_command) already exists and handles: view, comment, set-status, add-label, remove-label, set-dependency, create, child-create. The add-label path is implemented at acp_tools.py:437-445.

2. WORKFLOW.md already documents the interception: 'The task commands in oompah Task Reference are safe when passed directly to ACP's run_command: ACP intercepts them before shell execution and mutates the tracker in-process.'

3. Missing documentation: There is no plans/ doc that explains (a) the internal mechanism of _exec_oompah_task_command, (b) the _handoff_completed_focus recovery behavior (comment-as-durable-evidence, label backfill), or (c) the regression gap from EXOCOMP-55. This design doc is what focus agents and future contributors need.

4. Missing tests (not my job as Technical Writer, will hand off):
   - tests/test_acp_project_tools.py: no test for add-label via _exec_oompah_task_command
   - tests/test_orchestrator_duplicate_detection.py: no end-to-end test of no-commit duplicate_detector completion → _on_worker_exit → _handoff_completed_focus → select_focus picks feature (not duplicate_detector again)

Plan: Write plans/focus-handoff-mutation-protocol.md explaining the architecture, then hand off to feature for the tests.
---
author: oompah
created: 2026-07-23 22:58
---
Implementation: Wrote plans/focus-handoff-mutation-protocol.md documenting:

1. The approved mutation interface for focus agents (ACP run_command interceptor via _exec_oompah_task_command in oompah/acp_tools.py)
2. All intercepted subcommands: comment, set-status, add-label, remove-label, view, set-dependency, create, child-create
3. The required handoff sequence (comment first, then add-label)
4. The _handoff_completed_focus recovery behavior: comment is the durable evidence; label-without-comment triggers re-dispatch; comment-without-label triggers label backfill
5. How select_focus excludes completed focuses via _completed_focus_names()
6. The two regression gaps that need test coverage

All 12064 tests pass. Changes pushed to OOMPAH-430 branch.
---
<!-- COMMENTS:END -->
