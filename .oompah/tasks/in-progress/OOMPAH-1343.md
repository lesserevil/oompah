---
id: OOMPAH-1343
type: task
status: In Progress
priority: 1
title: Stabilize production and clear current workflow blockers
parent: OOMPAH-1342
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-26T18:43:05.336022Z'
updated_at: '2026-08-26T19:00:22.212797Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: manual-service-recovery-20260826-stabilize
  request_fingerprint: dabe0aa14096afda9b212472b2eaaa2df9e97ca7dfa2885df9a800f491946d7e
oompah.lifecycle_revision: 2
---
## Summary

Execute workstream 1 of plans/service-throughput-recovery.md without delegating to the scheduler. Keep oompah and trickle paused, update the protected GitHub workflow evidence in .env to the reviewed current ci.yml blob and exact job set, land already-green recovery PRs in a safe serial order, deploy with make graceful, and disposition each current retry.exhausted/operator.action_required record through supported owner APIs. Verify no live work is interrupted, all changes are pushed, /healthz remains healthy, and make workflow-rollout-check passes before resuming projects. Record exact commands and evidence in task comments.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-26 18:56
---
Direct implementation ownership assigned to the current manual recovery session (owner claim: shedwards). The project is paused and the human-only fence is present; do not dispatch this task to an autonomous worker.
---
author: oompah
created: 2026-08-26 19:00
---
Progress: paused all managed projects; updated local protected-workflow policy to current ci.yml blob 269db57c687e533bfaa90d961cf4c53f4069a7a8 and required job test (3.12); set contributor evidence timeout to 60s; merged green recovery PRs #937, #943, and #946 serially; deployed main d258fc16b with make graceful; retained terminal provenance for stale Done tasks TRICKLE-128 and TRICKLE-129. Remaining operator actions are tracked in the recovery plan.
---
<!-- COMMENTS:END -->
