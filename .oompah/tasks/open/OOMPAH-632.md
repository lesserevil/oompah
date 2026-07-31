---
id: OOMPAH-632
type: bug
status: Open
priority: 1
title: Refresh candidate refs before child landing reconciliation
parent: OOMPAH-584
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T00:46:34.785511Z'
updated_at: '2026-07-31T00:47:14.326699Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: make Done-child landing reconciliation fetch authoritative remote refs for both the rollup container branch and every recorded/canonical candidate task branch before comparing patches. A force-pushed rebase must not be judged from a stale refs/heads task branch when refs/remotes/origin contains the rewritten commit. Preserve fail-closed behavior when either required fetch cannot be proven and do not mutate genuine unlanded children. Relevant code: oompah/orchestrator.py landing-evidence refresh and merged-epic child reconciliation. Tests: reproduce a local task branch at the pre-rebase SHA with origin/task at a rewritten SHA already contained in the landed target; prove reconciliation accepts it, while fetch failures defer mutation and genuinely unlanded rewritten heads still escalate. Acceptance criteria: an auditor PASS cannot be overwritten by stale local source evidence; focused epic-strategy tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 00:46
---
Claimed directly by the operator Codex session because stale candidate-ref reconciliation is currently re-escalating OOMPAH-595 after a valid auditor PASS and blocks the green recovery epic. Implementing the regression fix against the latest OOMPAH-584 head now.
---
<!-- COMMENTS:END -->
