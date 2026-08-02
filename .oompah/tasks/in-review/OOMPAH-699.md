---
id: OOMPAH-699
type: bug
status: In Review
priority: 0
title: Converge historical Done records after parent terminalization
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-02T18:20:28.879414Z'
updated_at: '2026-08-02T20:36:15.374049Z'
work_branch: OOMPAH-699
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/660
review_number: '660'
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-699
  head_sha: 46b708cb1d830f613f52ba3ef53610dda4ace32e
  submitted_at: '2026-08-02T20:12:04.109767+00:00'
  updated_at: '2026-08-02T20:12:04.109767+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/660
oompah.review_number: '660'
oompah.work_branch: OOMPAH-699
oompah.target_branch: main
---
## Summary

Triggered by: OOMPAH-550

Triggered by: OOMPAH-550\n\nProduction lifecycle backlog: 69 historical Oompah tasks remained in Done after their implementation containers or parent epics had already reached Merged/Archived. Many retain durable integrated rows in the integration queue while their task integration metadata was reset to working or lost during cleanup; human-owned legacy work has merge/audit evidence but no work_branch. The normal reconciler therefore never converges these records to a terminal state.\n\nImplementation scope:\n- Add an idempotent maintenance/backfill path for Done tasks after a parent/container reaches Merged or Archived.\n- Use authoritative parent terminal state, terminal-audit evidence, integration-queue integrated_sha/head_sha, recovery/rollup records, and Git ancestry. Do not depend on a pruned live child branch.\n- Promote delivered children to Merged through the terminal transition coordinator.\n- Archive superseded/abandoned helper work when its parent was Archived and no delivered-work evidence exists.\n- Handle legacy human-owned standalone Done tasks with explicit merged/deployment evidence without inventing Git proof.\n- Preserve fail-closed behavior for ambiguous or unreachable evidence and emit one actionable alert/comment rather than silently guessing.\n- Ensure parent/child ordering and repeated maintenance/restart passes are idempotent.\n\nRelevant code: oompah/orchestrator.py merged-epic/child reconciliation, integration queue persistence, terminal transition coordinator, startup/maintenance sweeps, and tests/test_epic_strategy.py plus terminal lifecycle tests.\n\nRequired tests:\n- Done child + Merged parent + historical integrated queue row + pruned branch converges to Merged.\n- Done child + Archived parent + proven recovery landing converges to Merged.\n- Superseded rebase/helper task under Archived parent converges to Archived.\n- Legacy human-only Done epic/child with recorded merged PR evidence is handled safely.\n- Ambiguous Done records remain non-terminal with actionable evidence.\n- Repeat startup/maintenance passes do not churn or duplicate audits.\n\nAcceptance criteria:\n- No proven-delivered task remains indefinitely in Done after its container is terminal.\n- Cleanup or metadata reset cannot erase durable completion evidence.\n- The current historical Done backlog is safely converged and does not recur.\n- Focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 18:43
---
Promoted by the project owner: the bug report is actionable and ready for implementation.
---
author: oompah
created: 2026-08-02 19:06
---
Production mitigation completed on 2026-08-02: all 69 historical Done records were reconciled through canonical owner-audit transitions using parent terminal state, retained integration/recovery evidence, and explicit archival evidence for obsolete helpers. The current Done backlog is empty. This task remains Open for the idempotent maintenance/backfill implementation so the backlog cannot recur.
---
author: oompah
created: 2026-08-02 19:23
---
Claimed for direct owner implementation after OOMPAH-698; adding durable historical Done convergence.
---
author: oompah
created: 2026-08-02 19:44
---
Claimed for direct owner implementation. Building an idempotent historical Done reconciliation sweep around durable queue, parent-terminal, forge, Git, and terminal-audit evidence.
---
author: oompah
created: 2026-08-02 20:10
---
Direct owner implementation is complete and fully validated; preparing the exact tested head for submission.
---
author: oompah
created: 2026-08-02 20:12
---
Implemented and pushed exact head 46b708cb10d28e4457fcb4c2e9ef7974a3a03b5c. Added durable historical Done reconciliation using parent terminal state, queue/Git landing evidence, current audit fingerprints, and exact merged forge reviews; ambiguous records fail closed with deduplicated alerts. Focused suites: 857 passed. Full make test rerun: 14,999 passed, 7 skipped, 1 xfailed in 447.50s. make check-secrets and git diff --check passed.
---
author: oompah
created: 2026-08-02 20:12
---
Historical Done reconciliation is implemented and fully validated.
---
author: oompah
created: 2026-08-02 20:19
---
Branch quality gate passed for `46b708cb1d830f613f52ba3ef53610dda4ace32e` using `make test` in 417.6s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 20:28
---
YOLO: CI tests failed on MR #660. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-08-02 20:31
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #2)

**State audited:** `Needs CI Fix`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Recent comment indicates CI is now passing or PR has been merged; safe to reopen for dispatch.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-08-02 20:35
---
PR #660 CI failed only on the background-thread race in test_pr_merged_stages_task_merged under Python 3.11; Python 3.13 passed, Python 3.12 was canceled by fail-fast, and the exact failing test passed on immediate local rerun. Filed OOMPAH-702 for deterministic webhook-test synchronization and reran the failed matrix jobs. No OOMPAH-699 implementation failure was found.
---
<!-- COMMENTS:END -->
