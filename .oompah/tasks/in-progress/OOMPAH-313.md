---
id: OOMPAH-313
type: task
status: In Progress
priority: null
title: 'Regression tests: OOMPAH-285/286 routing fixture and native shared-epic child
  lifecycle'
parent: OOMPAH-307
children: []
blocked_by:
- OOMPAH-308
- OOMPAH-309
labels: []
assignee: null
created_at: '2026-07-21T16:54:41.720887Z'
updated_at: '2026-07-22T21:36:00.448100Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 267c8adc-8d38-45ee-b289-a25820f5efd6
oompah.task_costs:
  total_input_tokens: 316218
  total_output_tokens: 2343
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 316218
      output_tokens: 2343
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 316218
    output_tokens: 2343
    cost_usd: 0.0
    recorded_at: '2026-07-22T21:35:57.638528+00:00'
---
## Summary

Add regression coverage for the OOMPAH-285/286 shared-epic child routing lifecycle.
## Context

No regression tests currently exist for the specific OOMPAH-285/286 routing failure. All existing tests in test_epic_strategy.py mock the tracker with MagicMock. We need regression fixtures that:
1. Prove the OOMPAH-285/OOMPAH-286 scenario cannot recur
2. Cover the full dispatch-to-status-promotion lifecycle for native (oompah_md) shared-epic children
3. Pass via 'make test' (see Makefile)

## Implementation scope

1. Add a new test file tests/test_shared_epic_child_routing.py with:

   a) Regression fixture for OOMPAH-285/286 pattern:
      - Native oompah_md child OOMPAH-286 with parent_id=OOMPAH-285
      - Child has stale work_branch='OOMPAH-286' and target_branch='main' in metadata
      - Verify _create_workspace_for_issue routes to the OOMPAH-285 epic worktree (not per-task)
      - Verify _ensure_review_exists does NOT create a per-child PR to main
      - Verify Done→Merged promotion does NOT mark OOMPAH-286 as Merged when 'OOMPAH-286' appears in merged_branches

   b) Status lifecycle test:
      - Child routes to epic worktree → work completes → child status is Done
      - While epic PR is not merged: child remains Done (is_terminal → true but Merged is not set)
      - After epic PR confirmed merged: child is promoted to Merged
      - Verify this sequence produces no intermediate Merged state on the child

   c) PR-prevention test for native tasks:
      - Native child with parent_id set → dispatch → _ensure_review_exists called
      - Verify no PR is opened with source=child_branch and target=default_branch
      - Only the epic→main PR exists for the shared group

   d) Tracker-error resilience test:
      - _resolve_parent_epic fails with tracker exception for a child with parent_id
      - Verify per-task worktree is NOT created
      - Verify Merged status is NOT set

2. Ensure all new tests run under 'make test' (pytest) without requiring live git repos (use MagicMock / tmp_path fixtures following existing patterns in test_epic_strategy.py).

## Relevant files
- tests/test_epic_strategy.py: reference for fixture patterns (_make_orch, _make_issue, _make_project_record)
- tests/conftest.py: shared test fixtures
- oompah/orchestrator.py: the code under test
- Makefile: 'make test' target

## Tests required
All four test groups described above.

## Acceptance criteria
- All tests pass via 'make test'
- The OOMPAH-285/286 routing scenario is permanently covered by a failing-before-fix / passing-after-fix regression test
- The lifecycle tests prove Done-then-Merged (not Merged-before-epic) for shared children

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 21:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 21:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 21:35
---
Agent completed successfully in 59s (318561 tokens)
---
author: oompah
created: 2026-07-22 21:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 6
- Tokens: 316.2K in / 2.3K out [318.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 59s
- Log: OOMPAH-313__20260722T213500Z.jsonl
---
author: oompah
created: 2026-07-22 21:36
---
Agent completed without closing this issue (59s (318561 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
