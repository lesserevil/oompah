---
id: OOMPAH-864
type: bug
status: Open
priority: 1
title: Rearm abandoned duplicate-preflight work when an owner returns a task to Open
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T18:12:02.899266Z'
updated_at: '2026-08-06T18:13:55.867664Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1adcfa5d277fcb50a57de91e98d6e3b03c5c589b5269106064b265e244db4997
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 178e8855-2d33-446a-9c3b-9e26d663e1fa
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T18:13:43.126395+00:00'
  claim_expires_at: '2026-08-06T18:43:43.126395+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f04326f4-28e6-4257-80aa-02f798222dde
---
## Summary

Live reproduction on OOMPAH-863 (and latent on OOMPAH-855) after an inconclusive duplicate investigator moves an Open task to Needs Human. Duplicate preflight has already created the private worktree and persisted oompah.integration.state=working. The authenticated owner-resolution action records no_duplicate and sets the task to Open, but it neither retires nor rearms that abandoned duplicate-preflight run. Subsequent scheduler ticks report available agent capacity yet normal_dispatch=0 because the stale working record is treated as active; orphan recovery scans In Progress rather than this Open owner-resolved shape. Implementation scope: make successful no_duplicate owner resolution atomically reconcile the exact duplicate-preflight authority/run, work contributor, work branch/worktree, integration record, retry metadata, and tracker status into one dispatchable generation. Reuse a clean matching private worktree safely, preserve dirty/recovery checkpoints and branch identity, fence late output from the retired investigator, and never reset an unrelated implementation/integration owner. Apply the same restart reconciliation when the server stops between verdict persistence and rearm. duplicate_candidate resolutions must remain nondispatchable. Expose a truthful bounded reassessment reason rather than phantom working. Relevant code: _owner_resolve_duplicate_screening and its API transaction, duplicate-preflight completion/retirement, integration working metadata, candidate selection, orphan/liveness reconciliation, and owner-resolution tests. Required tests: exact Open→duplicate preflight→Needs Human→owner no_duplicate lifecycle dispatches implementation on the next bounded tick; crash/restart at each persistence boundary; late investigator completion cannot overwrite the owner verdict/new generation; clean versus dirty worktree; pre-existing unrelated worker authority; duplicate_candidate; repeated idempotent owner resolution; OOMPAH-855 hard-start remains blocked until its real prerequisite. Acceptance criteria: an owner-resolved no_duplicate task has exactly one durable dispatchable or explicitly blocked disposition, never an ownerless working record; OOMPAH-863-style tasks resume without waiting for watchdog age or manual metadata mutation; focused duplicate, ownership, workspace recovery, liveness, and restart tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 18:13
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
