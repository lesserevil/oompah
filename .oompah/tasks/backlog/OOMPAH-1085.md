---
id: OOMPAH-1085
type: task
status: Backlog
priority: null
title: Dispatch exact terminal-audit successors through a dedicated bounded continuation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T12:49:48.293345Z'
updated_at: '2026-08-11T12:49:48.293345Z'
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
  creation_marker: 878c6a42-3053-4e28-9139-8645e8b04dc0
  request_fingerprint: 8824c8446f415f1a94222b85e22a48381259f92dbe2560f42f2a306bb103013a
---
## Summary

Live OOMPAH-1082 acceptance failed on 2026-08-11: the Merged terminal-audit successor became durably eligible at 12:37:31.504 UTC and the Done workflow job completed at 12:37:40.499, but the successor was not claimed until 12:39:36.908 (116.409 seconds after completion). The current wake bridge stores the exact hint and posts generic REFRESH_REQUESTED, which is serialized behind a long full-world scheduler tick; _refresh_requested has no effective consumer. Implement a dedicated, coalesced, single-flight terminal-audit continuation lane that can run the audit phase independently of an in-flight full reconciliation. Preserve exact prerequisite and workflow-job CAS authority, same-branch fencing, pause/capacity/fairness behavior, restart durability, and no-concurrent-sibling guarantees. Re-arm the lane when a worker retires or capacity is released and eligible exact wakes remain, and on unpause/restart. Add observability for eligible, wake registered, lane scheduled/started/deferred, claim/dispatch, and latency. Tests must barrier-block a production durable reconciliation after its audit phase, complete Done PASS, retire the current worker/branch fence, and prove the exact Merged successor is claimed before the full reconciliation is released; also cover a wake arriving while the lane is active with one-owner/one-recheck handoff, capacity held until worker exit, coalesced multiple wakes, pause/unpause, restart, stale hint retirement, no duplicate launch, and deferred/failure paths. Run focused and adjacent terminal-audit/orchestrator tests plus the project gate. Acceptance: successor dispatch latency is bounded by the dedicated continuation and does not depend on completion of an unrelated full-world tick.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

