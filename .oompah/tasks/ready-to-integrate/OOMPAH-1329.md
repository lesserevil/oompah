---
id: OOMPAH-1329
type: task
status: Ready to Integrate
priority: null
title: Stop over-budget workflow reconciliation from hot-looping worker admission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T01:36:28.768799Z'
updated_at: '2026-08-24T01:50:39.706040Z'
work_branch: OOMPAH-1329
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 371719b5-9bbc-4ef2-9eb3-463362b66297
  request_fingerprint: 42c3c0fde84cd2ad321f76f112089c3ffe9d915f0fc8cafd65d70f412596c940
oompah.lifecycle_revision: 2
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1329
  base_branch: main
  base_sha: 1d2953c14bc925aaef79a40cd33fd3ea280ff6a4
  head_sha: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
  submitted_at: '2026-08-24T01:50:18.216653+00:00'
  updated_at: '2026-08-24T01:50:18.216653+00:00'
oompah.work_branch: OOMPAH-1329
---
## Summary

The durable workflow runtime can spend longer than the restart correction budget, lose tracker authority at the final publication barrier, return requires_reconcile=true, and immediately enqueue another full reconciliation. Each continuation receives a fresh budget, restart reconstruction remains pending, and normal workflow worker admission stays closed indefinitely. Observed live with 54 Ready to Integrate tasks and zero ordinary workers; reconciliation took ~199s (integration ~144s) against a 120s budget and returned publication_authority_changed. Implement a fail-closed retry disposition: consistently mark generic and scoped publication supersession that completes after the deadline as restart_deadline_exceeded, and do not immediately self-enqueue another reconciliation for that exhausted result. A later periodic or authority-change wake may retry. Add runtime and orchestrator regression tests proving the worker remains closed but no hot continuation loop is generated. Acceptance: no stale jobs are admitted; over-budget supersession is observable; immediate retries stop; a later stable reconciliation can publish and reopen admission.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 01:50
---
Live diagnosis confirmed repeated over-budget publication supersession hot-loops full reconciliation while worker admission remains closed. Implementing explicit exhaustion signaling and suppressing immediate self-requeue.
---
author: oompah
created: 2026-08-24 01:50
---
Over-budget superseded reconciliations now expose restart_deadline_exceeded and do not immediately enqueue another full scan. Focused runtime/orchestrator regression tests pass.
---
<!-- COMMENTS:END -->
