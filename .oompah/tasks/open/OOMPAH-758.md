---
id: OOMPAH-758
type: bug
status: Open
priority: 1
title: Atomically fence direct epic maintenance from ordinary integration enqueue
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:13:06.220562Z'
updated_at: '2026-08-04T11:14:54.768602Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3a5cf97524206a21bd89f17e45fdeef379b3dbd1ac80288a363273f3e8bf57a8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 6c2832ec-e2f3-4e7f-8bb1-fbba0fb4c400
  claim_owner: bb82706b-fb95-42cd-a68d-43d670f815c6
  claimed_at: '2026-08-04T11:14:42.384037+00:00'
  claim_expires_at: '2026-08-04T11:44:42.384037+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 54420ec4-e738-4970-9a71-cce91a679e87
---
## Summary

Triggered by: OOMPAH-755

Live regression of merged OOMPAH-731 on revision 5368e236. OOMPAH-755 is a direct maintenance helper identified by title 'Rebase epic-OOMPAH-740 onto main' plus parent OOMPAH-740. Its resolver correctly used the canonical shared epic worktree, advanced origin/epic-OOMPAH-740 from 583fb236 to proven head 5368e236, verified current-main/OOMPAH-735 ancestry, and submitted through the direct Done-only path; the task reached In Validation at 11:10 UTC. Nevertheless, a durable ordinary integration row was also created at 11:08:47 with task_branch=epic-OOMPAH-740, base_sha=583fb236, head_sha=5368e236. A later queue pass leased that stale row and failed integration preparation because git worktree add tried to check out epic-OOMPAH-740 while its authoritative registered worktree already owned the branch. The row became blocked, the task was reopened, and an actionable integration_retry alert appeared. This violates OOMPAH-731's no-enqueue/Done-only atomicity. Implementation scope: serialize task-handoff submission, worker-exit fallback, same-head/restart recovery, and direct-maintenance completion under one authority generation; once is_direct_epic_maintenance_issue is true, make ordinary queue enqueue impossible at every producer and atomically cancel any stale concurrent row before staging Done; fence late worker-exit and duplicate-screening paths after terminal ownership; reconcile already-published exact heads idempotently; clear integration retry/delivery alerts and cancel obsolete queue rows without touching the authoritative epic worktree. Relevant code: api_submit_issue/task-handoff submit, worker exit reconciliation, complete_direct_epic_maintenance_submission, integration_queue enqueue/claim, direct helper classification, terminal coordinator handoff, and restart recovery. Required tests: exact OOMPAH-755 race with direct submission and worker exit/concurrent tick; preexisting stale Ready/integrating/blocked row; restart between publish, queue write, and Done staging; duplicate submit; authoritative worktree already owns branch; lease loss; terminal override; ordinary child control. Acceptance criteria: a proven direct epic helper has exactly one Done-only lifecycle and zero ordinary integration rows; no queue executor attempts to create/reset its epic worktree; late/stale rows are cancelled before mutation and alerts clear; OOMPAH-755 converges without duplicate implementation; focused worker submission, integration queue/executor, maintenance, terminal lifecycle, alert, race, and restart tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 11:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 11:14
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
