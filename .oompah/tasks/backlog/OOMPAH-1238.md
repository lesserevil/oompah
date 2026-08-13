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
updated_at: '2026-08-13T12:51:20.033996Z'
work_branch: null
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
<!-- COMMENTS:END -->
