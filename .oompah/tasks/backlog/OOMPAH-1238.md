---
id: OOMPAH-1238
type: task
status: Backlog
priority: null
title: Return immutable helper identity after atomic epic-rebase creation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T12:43:56.637636Z'
updated_at: '2026-08-13T13:02:10.178732Z'
work_branch: OOMPAH-1238
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 4af593e6-a16d-4eff-aa71-fff5c999eafe
  request_fingerprint: a2594ec8b9a6ba7ba19351ae03d0c4fe3f2cfcb403f5e2b2cb9dc978d592a381
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1238
  head_sha: ab11ea173f0ca4a31345111b9f3ac854d3666fc2
  submitted_at: '2026-08-13T13:01:56.306150+00:00'
  updated_at: '2026-08-13T13:01:56.306150+00:00'
oompah.work_branch: OOMPAH-1238
---
## Summary

Live durable-effect bug: v3 epic-rebase job seq16530 successfully created TRICKLE-141 and persisted its exact authority metadata, but _file_rebase_task returned a normalized Issue without a stable identifier in the original effect path (subsequent retries reported 'rebase helper has no immutable identity'). The workflow exhausted even though the side effect succeeded. Implementation scope: after create_issue_once and authority persistence, re-read/normalize the created helper or otherwise return the exact immutable tracker identity proven by the create-once record; ensure crash/retry observes the existing helper and completes the durable receipt without duplicate creation. Relevant files: oompah/orchestrator.py, tracker adapter contract if required, oompah/epic_workflow_adapter.py, tests. Acceptance: one helper is created, apply returns its immutable ID on the first successful write and on replay, durable job completes, and duplicate/wrong-generation protections remain.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 12:51
---
Claimed directly from the live seq16530 failure. Implementing read-after-write/replay identity recovery so an exactly-once helper creation yields a durable receipt instead of exhausting after its side effect already succeeded.
---
author: oompah
created: 2026-08-13 13:01
---
Implemented immutable create-once receipt and exact-authority retry recovery. Also advanced the rebase event contract so live exhausted v3 jobs get a safe new durable identity after deployment. Focused tests: 171 passed; terminal mutation and secret scans passed. Commit ab11ea173 pushed.
---
author: oompah
created: 2026-08-13 13:02
---
Atomic epic-rebase creation now returns its immutable helper ID without depending on immediate child-index visibility; retries recover the exact active authority task, and v4 event identity re-arms exhausted pre-fix jobs. Tests and scans pass; ab11ea173 pushed.
---
<!-- COMMENTS:END -->
