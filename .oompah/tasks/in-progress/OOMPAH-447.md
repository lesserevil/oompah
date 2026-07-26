---
id: OOMPAH-447
type: bug
status: In Progress
priority: 1
title: Do not reopen merged epic siblings for a later shared-branch PR
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-26T04:02:02.297716Z'
updated_at: '2026-07-26T04:04:11.158032Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a8c8219a-1068-46be-85c1-792605dc3425
---
## Summary

Triggered by: EXOCOMP-47

Problem
When a shared epic branch is reused for a later follow-up PR, _reconcile_terminal_open_reviews matches every Merged child and the parent epic only by work_branch. PR #17 from epic-EXOCOMP-6 was owned by EXOCOMP-47, but the reconciler demoted EXOCOMP-41, EXOCOMP-42, EXOCOMP-43, EXOCOMP-44, and EXOCOMP-6 to In Review. The merged-parent sweep then moved several siblings to Needs Human even though their recovery delivery was already verified on main.

Implementation
Add review ownership validation before demoting a terminal issue. A current review is owned when persisted review_number matches, the source branch is the standalone issue branch, or the review title identifies that exact issue. For shared epic branches, do not treat branch equality alone as ownership because multiple completed siblings share it. Preserve false-Merged repair for standalone task branches and for explicitly identified epic or child reviews. Log and skip ambiguous shared-branch reviews.

Tests
Add regression coverage with a Merged epic and multiple Merged children sharing epic-EPIC-1 while a later open PR titled for only one child is ahead of main. Only the identified owner may be repaired; unrelated siblings and the parent remain Merged. Retain existing standalone false-Merged, CI-failure, conflict, and stale-cache tests. Include exact-identifier matching so TASK-4 does not match TASK-41.

Acceptance Criteria
- A later follow-up PR on a reused shared epic branch never reopens unrelated Merged siblings or the parent.
- The task named by the review can still be repaired when its delivery is genuinely unmerged.
- Standalone false-Merged repair continues to work.
- make test passes and the live service no longer recreates these Needs Human states.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-26 04:02
---
Reproduced live with exocomp PR #17: shared branch epic-EXOCOMP-6 caused unrelated terminal siblings EXOCOMP-41/42/43/44 and parent EXOCOMP-6 to be demoted. Implementing exact review ownership checks in terminal/open-review reconciliation with focused regression tests.
---
author: oompah
created: 2026-07-26 04:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-26 04:04
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
