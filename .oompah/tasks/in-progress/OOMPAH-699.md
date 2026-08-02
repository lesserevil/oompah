---
id: OOMPAH-699
type: bug
status: In Progress
priority: 1
title: Converge historical Done records after parent terminalization
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-02T18:20:28.879414Z'
updated_at: '2026-08-02T19:23:40.488641Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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
<!-- COMMENTS:END -->
