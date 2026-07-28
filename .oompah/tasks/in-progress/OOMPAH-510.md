---
id: OOMPAH-510
type: task
status: In Progress
priority: 1
title: Measure throughput improvements and validate the clean epic branch
parent: OOMPAH-502
children: []
blocked_by:
- OOMPAH-503
- OOMPAH-504
- OOMPAH-505
- OOMPAH-506
- OOMPAH-507
- OOMPAH-508
- OOMPAH-509
labels: []
assignee: null
created_at: '2026-07-28T15:06:11.106221Z'
updated_at: '2026-07-28T17:37:15.269998Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 275e3fd3-0a4c-42e6-aaf0-d396468b9491
oompah.work_branch: epic-OOMPAH-502
---
## Summary

Final validation after every implementation child is Done. From a clean checkout of the exact epic head, measure duplicate-screen decisions, rendered prompt comment/byte counts, provider/model resolution for all six role candidates, storage-cleanup dry fixtures, restart drain behavior, and serial/parallel pytest wall time. Run the focused suites, make test, make check-secrets, git diff --check, and verify no test-owned subprocesses or network Git operations remain. Confirm the branch-head quality evidence matches HEAD and that no PR/MR existed before this task and all siblings were complete.

Post a before/after report against the July 28 observations: duplicate screens of 2.5-4 minutes and 400k-750k input tokens, repeated roughly four-minute full suites, only default provider models, interrupted restart recovery, root/tmp pressure, and serial test runtime. Do not weaken tests or thresholds to claim improvement.

Acceptance criteria: all gates pass from a clean branch; measurements and remaining tradeoffs are recorded; git status is clean/up-to-date; every sibling is Done with landing evidence; this task is the final dependency before the single epic-owned review is created.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 17:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 17:37
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
