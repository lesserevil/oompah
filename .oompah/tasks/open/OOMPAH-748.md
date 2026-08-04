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
updated_at: '2026-08-04T00:42:50.151660Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c9fbcc861c522c73c72cc1ac5637b98b071961b57276069044961a27cbe66c16
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: c6f318f9-40ae-4edd-862b-2c5bda4714f0
  claim_owner: b6e50576-eec3-4dce-bc89-fe685f70768e
  claimed_at: '2026-08-04T00:42:28.225032+00:00'
  claim_expires_at: '2026-08-04T01:12:28.225032+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 82407244-35fe-46b1-8da2-e804f3a98724
---
## Summary

Triggered by: EXOCOMP-128

Live reproduction: EXOCOMP-128 passed a Merged audit after PR 21 landed its nested epic branch into epic-EXOCOMP-127, but lifecycle validation rejects Merged until EXOCOMP-127 lands on main. At the same time, EXOCOMP-127 auto-close refuses to proceed until nested child EXOCOMP-128 is Merged. This creates a closed lifecycle cycle even though the child branch is landed on its immediate parent target. Implementation scope: define target-relative terminal semantics for nested shared epics so the parent rollup can accept an independently audited child that is landed on the immediate parent branch, without marking the root epic landed on main prematurely. Reconcile epic auto-close, terminal validation, rollup status, and audit evidence around one rule; preserve the safety constraints from OOMPAH-725. Relevant code includes nested-epic target resolution, lifecycle transition validation, _label_merged_epics, epic rollup, and epic auto-close in oompah/orchestrator.py and transition gates. Required tests: nested epic landed on parent but parent not main; root parent then opens and lands; genuinely unlanded nested child; wrong target; deleted or rebased refs with trusted evidence; override and restart reconciliation. Acceptance criteria: no state cycle exists between a nested child and its parent; proven immediate-target landing naturally unblocks the parent; premature root-level Merged remains impossible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 00:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 00:42
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
