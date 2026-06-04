---
id: TASK-436
title: Make landing gate shared-epic aware
status: Done
assignee: []
created_date: '2026-06-03 19:35'
updated_date: '2026-06-04 16:41'
labels:
  - bug
  - ci-fix
dependencies: []
ordinal: 72000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The completed-without-landing gate checks child issue branches such as TASK-706.1 even when the project uses epic_strategy=shared and child work lands on the shared epic branch such as epic-TASK-706. This caused trickle TASK-706.1 and TASK-706.2 to be marked Needs Human even though the epic branch contains commits and the task files are Done on origin/epic-TASK-706. Update landing detection and its diagnostic comment/telemetry to resolve the effective landing branch for shared-epic children.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 For shared-epic child tasks, landing detection checks the shared epic branch instead of the child identifier branch.
- [ ] #2 A child task with commits on origin/epic-<parent> is not marked Needs Human solely because origin/<child> does not exist.
- [ ] #3 Tests cover the TASK-706.1-style false positive and preserve existing flat/per-task landing-gate behavior.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
CI fix: added landing_result.effective_branch = '' to mock in test_completed_without_landing_schedules_escalated_retry. The new build_telemetry_event() accesses result.effective_branch; without setting it, MagicMock returns a truthy Mock object causing json.dumps() to throw TypeError, silently caught by bare except Exception, adding issue to completed instead of scheduling retry.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed CI test failure on MR #224. The new build_telemetry_event() in landing_gate.py accesses result.effective_branch, but the existing test test_completed_without_landing_schedules_escalated_retry used a bare MagicMock() without setting this attribute. MagicMock returns a truthy Mock for unset attributes, causing json.dumps() to throw TypeError (not JSON serializable), silently caught by the outer bare except Exception block — which then added the issue to state.completed instead of scheduling the escalated retry. Fix: added landing_result.effective_branch = '' to the mock in the test (1-line change). All 146 tests in test_landing_gate.py + test_orchestrator_handlers.py pass.
<!-- SECTION:FINAL_SUMMARY:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-04 15:55

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-04 15:55

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-04 16:01

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 84, Tool calls: 62
- Tokens: 54 in / 13.4K out [13.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 17s
- Log: TASK-436__20260604T155541Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-04 16:01

Agent completed successfully in 377s (13412 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-04 16:07

YOLO: CI tests failed on MR #224. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-04 16:07

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-04 16:07

Focus: CI Failure Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-04 16:20

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-04 16:20

Focus: CI Failure Fixer
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
