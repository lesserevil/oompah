---
id: OOMPAH-942
type: bug
status: Open
priority: 1
title: Backfill trusted terminal-parent heads for pruned epic targets
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:26.152660Z'
updated_at: '2026-08-09T09:10:28.571678Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Fourteen resolver-shaped legacy child rows have exact source authority but target pruned epic refs; terminal parents such as OOMPAH-460/585/586/587/588/619 have no accepted exact head, so exact landing evidence remains unavailable. Scope: define and persist a one-time/restart-safe backfill from authoritative parent integration receipts, accepted terminal audit provenance, or exact forge landing evidence; never infer from branch names or current main. Feed the resulting immutable accepted parent head into IntegrationLandingRequestResolver/GitLandingCollector. Tests: each authoritative source, missing/ambiguous/conflicting evidence, pruned branch, restart idempotence, and no mutation of historical jobs. Acceptance: qualifying children prove ancestry/complete patch equivalence against the accepted parent head; unknown parents remain actionable and fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 09:10
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
<!-- COMMENTS:END -->
