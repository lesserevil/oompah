---
id: OOMPAH-1343
type: task
status: Backlog
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
updated_at: '2026-08-26T18:46:04.405903Z'
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
---
## Summary

Execute workstream 1 of plans/service-throughput-recovery.md without delegating to the scheduler. Keep oompah and trickle paused, update the protected GitHub workflow evidence in .env to the reviewed current ci.yml blob and exact job set, land already-green recovery PRs in a safe serial order, deploy with make graceful, and disposition each current retry.exhausted/operator.action_required record through supported owner APIs. Verify no live work is interrupted, all changes are pushed, /healthz remains healthy, and make workflow-rollout-check passes before resuming projects. Record exact commands and evidence in task comments.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

