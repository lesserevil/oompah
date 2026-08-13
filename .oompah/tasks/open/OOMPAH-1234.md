---
id: OOMPAH-1234
type: task
status: Open
priority: null
title: Wake queued nested topology repairs independently of implementation retry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T11:02:41.641589Z'
updated_at: '2026-08-13T11:15:50.179479Z'
work_branch: OOMPAH-1234
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: cd7a3378-bd51-43b7-a1c4-f5b7ee908979
  request_fingerprint: 77a790dd37017add0acfd675dc561e5750a30bcfb90c6a44ed4551f6572ecedb
oompah.lifecycle_revision: 1
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1234
  head_sha: c3a50bc6c4df16d3c52aaf1110e50a2e502521e8
  submitted_at: '2026-08-13T11:15:42.599789+00:00'
  updated_at: '2026-08-13T11:15:42.599789+00:00'
oompah.work_branch: OOMPAH-1234
---
## Summary

Live follow-up to OOMPAH-1232 on TRICKLE-138/139. OOMPAH-1232 breaks the in-call implementation-versus-repair exclusion deadlock for new admissions, but repair jobs already queued before deployment have no independent consumer and remain dormant until their associated implementation_start retry_at, which may be hours away after repeated administrative deferrals. Implementation scope: add a bounded, project-pause-aware recovery sweep for active nested_dispatch_topology_repair jobs; reload the exact task and current topology evidence, use the existing generation-fenced schedule/drive path, persist cleared wait evidence after a successful repair, and request ordinary reconciliation so the obsolete implementation retry is superseded by the new task evidence. Do not bypass task/project pause, do not claim unrelated actions, do not overlap an unapproved running action, and preserve repair retry backoff/errors. Required tests: queued repair is driven without a due implementation job; successful repair clears wait evidence and triggers reconciliation/new authority; paused project is untouched; stale generation is superseded safely; bounded batch/restart replay is idempotent; unrelated workflow rows unchanged. Acceptance: a pre-deployment TRICKLE-138/139-shaped queued repair progresses promptly after startup without waiting for the inherited implementation retry deadline, and focused topology/workflow/runtime plus complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 11:02
---
Claimed directly after live verification of OOMPAH-1232. The deployed overlap fix handles new admissions, but pre-existing queued repairs need a bounded independent startup/maintenance wake. Implementing that recovery path now while Oompah remains paused and only Trickle is resumed.
---
author: oompah
created: 2026-08-13 11:15
---
Implementation complete on OOMPAH-1234 at c3a50bc6c. Added bounded startup replay for queued nested topology repairs, pause/backoff/generation fencing, and stabilized initial wait authority before enqueue. Focused topology/job/runtime/architecture suite: 335 passed. Terminal mutation and secret scans passed. Submitting for validation.
---
author: oompah
created: 2026-08-13 11:15
---
Recover queued nested topology repairs independently at startup with pause/backoff/generation fencing; stabilize wait authority before enqueue. 335 focused tests and repository scans pass.
---
<!-- COMMENTS:END -->
