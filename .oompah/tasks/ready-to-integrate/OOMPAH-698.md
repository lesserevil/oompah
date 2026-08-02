---
id: OOMPAH-698
type: bug
status: Ready to Integrate
priority: 1
title: Recover legacy stale reviews without persisted review-head metadata
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
- ci-fix
assignee: null
created_at: '2026-08-02T18:20:27.192609Z'
updated_at: '2026-08-02T19:42:25.781270Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-698
  head_sha: 6de721ae2f44a8ce0d3c21fcf660cc332a996e1b
  submitted_at: '2026-08-02T19:37:11.543655+00:00'
  updated_at: '2026-08-02T19:37:11.543655+00:00'
---
## Summary

Triggered by: OOMPAH-697

Triggered by: OOMPAH-697\n\nProduction regression: OOMPAH-680 and OOMPAH-682 remain In Review with no open forge review after their branches advanced beyond already-merged PRs. OOMPAH-697 added exact-head review binding, but legacy task records have review_url/review_number and no oompah.review_head. _is_review_stale returns false when that field is missing, then the merged review for the reused branch name is treated as current.\n\nImplementation scope:\n- In stale In Review reconciliation, recover the reviewed head from authoritative forge review evidence when persisted review_head is absent.\n- Alternatively compare the current branch tip with the target branch for merged historical reviews before requesting Merged; an ahead current tip must be requeued to Ready to Integrate, never treated as covered by the old review.\n- Persist recovered/superseding exact-head metadata and preserve review history.\n- Make legacy migration, restart, webhook lag, and concurrent reconciliation idempotent.\n- Do not reopen work already contained in the target and do not duplicate a current-head open review.\n\nRelevant code: oompah/orchestrator.py _reconcile_stale_in_review_tasks, _is_review_stale, _clear_stale_review_and_requeue; oompah/scm.py review head evidence; tests/test_orchestrator_merged.py.\n\nRequired tests:\n- Reproduce the exact OOMPAH-680/OOMPAH-682 legacy record with no review_head, a merged old PR, a current branch ahead of main, and zero open reviews; it returns to Ready to Integrate.\n- A legacy record whose current head is contained in main requests Merged.\n- Missing/unavailable forge or Git evidence fails closed without false terminalization.\n- Repeated passes create at most one fresh review for the current head.\n\nAcceptance criteria:\n- Legacy tasks cannot remain In Review solely because exact-head metadata was introduced after their review.\n- The live OOMPAH-680 and OOMPAH-682 records progress through an exact-head gate and fresh review.\n- Focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 18:42
---
Promoted by the project owner: the bug report is actionable and ready for implementation.
---
author: oompah
created: 2026-08-02 19:06
---
Production mitigation completed on 2026-08-02: legacy stale reviews OOMPAH-680 and OOMPAH-682 were requeued against their exact current heads, passed fresh CI/audit paths, and merged via PR #657 (merge 126422448bb23f19561533eebbdfc0a4aa4f9178) and PR #658 (merge 24b27b8fc30a4ee16db7f736577e96758ceba4d1). This task remains Open for the automated legacy-metadata recovery so the manual intervention is not needed again.
---
author: oompah
created: 2026-08-02 19:23
---
Claimed for direct owner implementation; reproducing the legacy missing-review-head reconciliation path.
---
author: oompah
created: 2026-08-02 19:37
---
Direct implementation complete at 6de721ae2f44a8ce0d3c21fcf660cc332a996e1b. Added forge-reported historical review-head recovery for GitHub/GitLab, Git-containment fallback when legacy payloads lack a head, fail-closed evidence errors, durable superseded-review comments, and repeated-pass idempotence. Focused: 455 passed. Full make test: 14,990 passed, 7 skipped, 1 xfailed in 382.36s. make check-secrets passed.
---
author: oompah
created: 2026-08-02 19:37
---
Recovered legacy review heads and safely requeued advanced branches; full gate and secret scan passed.
---
author: oompah
created: 2026-08-02 19:37
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-698`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `error`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
No existing worktree matched the review branch tip. Recreate the task worktree before retrying.
```
---
author: oompah
created: 2026-08-02 19:42
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #8)

**State audited:** `Needs CI Fix`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Recent comment indicates CI is now passing or PR has been merged; safe to reopen for dispatch.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-08-02 19:42
---
Restored the submitted exact head in the managed task worktree after the gate could not discover the temporary checkout; resubmitting the unchanged, fully tested head.
---
<!-- COMMENTS:END -->
