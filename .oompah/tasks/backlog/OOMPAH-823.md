---
id: OOMPAH-823
type: task
status: Backlog
priority: null
title: Bootstrap lifecycle reconciliation retry backoff onto main
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T06:45:32.566233Z'
updated_at: '2026-08-05T06:45:32.566233Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Urgent standalone deployment bootstrap for systemic child OOMPAH-822. The currently deployed main server retry-spins failed terminal lifecycle reconciliation rows OOMPAH-452/453/455/456 above 30,000 attempts, rewriting+fsyncing ~835 KiB service state 10-13 times/sec and starving the only OOMPAH-814 exact gate. Implement on current main the bounded scheduler/ledger fix specified by OOMPAH-822: pending-first fair cursor, durable failed-row next-at exponential backoff and bounded exhaustion/action-required state, one coalesced persistence checkpoint per batch (except pre-external-effect intent where required), scheduler delay from earliest due retry with a nonzero floor, restart/transient recovery, and observability without a hot loop. Required tests: four permanent failed rows plus later pending rows; retry not due/due across restart; no starvation; bounded persist and reschedule counts; transient recovery; schedule coalescing; state endpoint responsiveness. Acceptance: deploying this standalone patch stops continuous lifecycle fsync immediately, drains pending rows fairly, preserves fail-closed reconciliation, and lets exact validation gates run. OOMPAH-822 will record the reviewed logical patch on epic-OOMPAH-763 after this main bootstrap merges.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

