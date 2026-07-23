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
- needs:feature
assignee: null
created_at: '2026-07-23T22:26:45.549947Z'
updated_at: '2026-07-23T22:43:29.125452Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 07e1562f-a79b-4a1f-b5fd-6c5bbec9d3ee
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
<!-- COMMENTS:END -->
