---
id: OOMPAH-942
type: bug
status: Ready to Integrate
priority: 1
title: Backfill trusted terminal-parent heads for pruned epic targets
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:26.152660Z'
updated_at: '2026-08-09T09:54:08.391730Z'
work_branch: OOMPAH-942
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-942
  base_branch: epic-OOMPAH-940
  base_sha: b7e7d9509a4e6025b48c54336098acef2dda4986
  head_sha: 1b50116ce5057a617b84d22dd542c621721fc20e
  submitted_at: '2026-08-09T09:32:14.484356+00:00'
  updated_at: '2026-08-09T09:32:14.484356+00:00'
oompah.work_branch: OOMPAH-942
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
author: oompah
created: 2026-08-09 09:32
---
Implemented/pushed 1b50116ce. Terminal-parent exact heads now backfill from existing immutable landing facts, integrated queue receipts, exact completed audit bindings, or route-matching merged-review heads; the selected proof is persisted before child use and ambiguity, wrong targets, malformed authority, or persistence failure remain fail-closed. Focused integration/runtime result: 153 passed; targeted undefined-name lint passed.
---
author: oompah
created: 2026-08-09 09:32
---
Backfilled and persisted exact terminal-parent heads with fail-closed legacy authority selection; 153 focused tests pass.
---
author: oompah
created: 2026-08-09 09:54
---
Independent review found and fixed a source-authority gap before integration: exact terminal-audit parent backfill now requires the persisted audit binding to match the parent source branch (or an equal immutable revision), and malformed or wrong-ref authority blocks lower-priority fallback. Added a wrong-source fail-closed regression. Verification: 154 integration/runtime tests passed; mutation and secret scans passed.
---
<!-- COMMENTS:END -->
