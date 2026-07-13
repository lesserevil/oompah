---
id: OOMPAH-168
type: task
status: In Progress
priority: 1
title: Simplify orchestration to the shared epic workflow
parent: OOMPAH-166
children: []
blocked_by:
- OOMPAH-167
labels: []
assignee: null
created_at: '2026-07-13T02:23:07.456716Z'
updated_at: '2026-07-13T02:34:26.771376Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9221bf07-562a-4ced-b8ce-86463514a026
---
## Summary

Remove all flat and stacked branches from epic decomposition, task dispatch, branch/worktree selection, review/merge reconciliation, repair tasks, and roll-up status handling. Retain the shared workflow: one epic branch, child work commits to that branch, and the epic PR lands the work on the configured target/default branch. Delete obsolete fallback behavior and strategy-specific code paths rather than retaining dormant compatibility branches. Add regression tests covering decomposition, dispatch, child completion, repair/rebase, nested epics where supported, and epic landing.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 02:33
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 02:33
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 02:34
---
UNDERSTANDING: No duplicate found. OOMPAH-168 is a unique child of epic OOMPAH-166 covering the orchestration layer. Sibling OOMPAH-167 (config/domain layer) is Done and unblocks this task. Scope: remove flat/stacked strategy code paths from orchestrator.py epic decomposition, task dispatch, branch/worktree selection, review/merge reconciliation, repair tasks, and roll-up status handling. Retain only shared workflow logic. Add regression tests. Plan: (1) Read orchestrator.py and related files to find all epic_strategy conditionals, (2) Remove flat/stacked branches, (3) Simplify to shared-only paths, (4) Add/update tests, (5) Run make test.
---
<!-- COMMENTS:END -->
