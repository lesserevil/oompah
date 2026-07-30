---
id: OOMPAH-625
type: bug
status: Backlog
priority: 1
title: Release terminal-auditor branch claims on forced termination
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:58:34.567478Z'
updated_at: '2026-07-30T21:58:34.567478Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: update the orchestrator forced/manual worker termination path so terminating an auditor releases its  ownership exactly when that same runtime entry is removed. Preserve replacement-worker fencing and survivor-process safety; ordinary and duplicate-preflight termination semantics must remain unchanged. Add observability for the released claim if useful. Relevant context: OOMPAH-591's Claude auditor was terminated during a UI terminal-status transition at 20:20,  removed the RunningEntry and ordinary claim but retained  in , causing every later audit tick to skip the fresh pending audit forever. Tests: reproduce a forced auditor termination with a populated branch claim, assert running/claimed/claimed_issues/branch ownership are all released, cover a mismatched replacement claim so an older terminating worker cannot release a newer owner's fence, and run focused auditor/termination tests plus the Makefile gate. Acceptance criteria: forced auditor termination cannot deadlock future audit dispatch; a stale worker cannot clear a replacement auditor's branch claim; all focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

