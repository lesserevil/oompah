---
id: OOMPAH-748
type: bug
status: Open
priority: 1
title: Break nested-epic rollup cycle between Done child epics and parent landing
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:41:04.498057Z'
updated_at: '2026-08-04T00:41:14.615074Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: EXOCOMP-128

Live reproduction: EXOCOMP-128 passed a Merged audit after PR 21 landed its nested epic branch into epic-EXOCOMP-127, but lifecycle validation rejects Merged until EXOCOMP-127 lands on main. At the same time, EXOCOMP-127 auto-close refuses to proceed until nested child EXOCOMP-128 is Merged. This creates a closed lifecycle cycle even though the child branch is landed on its immediate parent target. Implementation scope: define target-relative terminal semantics for nested shared epics so the parent rollup can accept an independently audited child that is landed on the immediate parent branch, without marking the root epic landed on main prematurely. Reconcile epic auto-close, terminal validation, rollup status, and audit evidence around one rule; preserve the safety constraints from OOMPAH-725. Relevant code includes nested-epic target resolution, lifecycle transition validation, _label_merged_epics, epic rollup, and epic auto-close in oompah/orchestrator.py and transition gates. Required tests: nested epic landed on parent but parent not main; root parent then opens and lands; genuinely unlanded nested child; wrong target; deleted or rebased refs with trusted evidence; override and restart reconciliation. Acceptance criteria: no state cycle exists between a nested child and its parent; proven immediate-target landing naturally unblocks the parent; premature root-level Merged remains impossible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

