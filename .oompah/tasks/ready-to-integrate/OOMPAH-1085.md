---
id: OOMPAH-1085
type: task
status: Ready to Integrate
priority: null
title: Dispatch exact terminal-audit successors through a dedicated bounded continuation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T12:49:48.293345Z'
updated_at: '2026-08-11T13:35:37.410321Z'
work_branch: OOMPAH-1085
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
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1085
  head_sha: 7bd90702b13bfa876f49e5b4e5e27483997945b6
  submitted_at: '2026-08-11T13:35:21.687037+00:00'
  updated_at: '2026-08-11T13:35:21.687037+00:00'
oompah.work_branch: OOMPAH-1085
---
## Summary

Live OOMPAH-1082 acceptance failed on 2026-08-11: the Merged terminal-audit successor became durably eligible at 12:37:31.504 UTC and the Done workflow job completed at 12:37:40.499, but the successor was not claimed until 12:39:36.908 (116.409 seconds after completion). The current wake bridge stores the exact hint and posts generic REFRESH_REQUESTED, which is serialized behind a long full-world scheduler tick; _refresh_requested has no effective consumer. Implement a dedicated, coalesced, single-flight terminal-audit continuation lane that can run the audit phase independently of an in-flight full reconciliation. Preserve exact prerequisite and workflow-job CAS authority, same-branch fencing, pause/capacity/fairness behavior, restart durability, and no-concurrent-sibling guarantees. Re-arm the lane when a worker retires or capacity is released and eligible exact wakes remain, and on unpause/restart. Add observability for eligible, wake registered, lane scheduled/started/deferred, claim/dispatch, and latency. Tests must barrier-block a production durable reconciliation after its audit phase, complete Done PASS, retire the current worker/branch fence, and prove the exact Merged successor is claimed before the full reconciliation is released; also cover a wake arriving while the lane is active with one-owner/one-recheck handoff, capacity held until worker exit, coalesced multiple wakes, pause/unpause, restart, stale hint retirement, no duplicate launch, and deferred/failure paths. Run focused and adjacent terminal-audit/orchestrator tests plus the project gate. Acceptance: successor dispatch latency is bounded by the dedicated continuation and does not depend on completion of an unrelated full-world tick.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 13:09
---
Implemented the dedicated single-flight terminal-audit continuation lane on branch OOMPAH-1085. Exact wakes now bypass serialized full-world reconciliation, share one audit scan lock with ordinary ticks, retain pause/restart authority, and re-arm on WORKER_EXIT capacity release. Added blocked-durable-reconcile, active-wake coalescing, capacity handoff, pause/unpause, restart reconstruction, stale-hint, one-owner, failure-observability, and latency coverage. Focused terminal-audit suites pass (141); broader adjacent audit/event/quiesce suites pass (708 and 238); terminal mutation scan passes 21/21. The full project gate is running. After it completes I will compose current origin/main (OOMPAH-1083), rerun combined focused checks and the final gate, then push and submit.
---
author: oompah
created: 2026-08-11 13:18
---
Additional production evidence on the pre-fix path: the OOMPAH-1083 Done audit PASS was accepted at 13:12:30 UTC, its worker/worktree and branch fence retired by 13:12:42, but the exact Merged successor did not begin dispatch until 13:13:43. The roughly 61-second post-retirement gap confirms the remaining delay was the generic full-tick wake path, not provider capacity or same-branch authority.
---
author: oompah
created: 2026-08-11 13:35
---
Review-ready head 7bd90702b13bfa876f49e5b4e5e27483997945b6 is pushed on OOMPAH-1085, based exactly on origin/main fe06a0ff1. Post-rebase verification: 238 focused orchestrator/audit/event/pause tests passed; 1,102 adjacent terminal-audit/quiesce/quality-gate/server tests passed; focused terminal suite 141 passed; terminal mutation scan 21/21; paranoid secret scan passed. A duplicate manual full gate was stopped at 9,467 passed, 7 skipped, 2 xfailed, zero failures so the server can own the single canonical exact-head branch gate. Production acceptance context includes both the 116.409-second OOMPAH-1082 delay and the later roughly 61-second OOMPAH-1083 post-retirement delay on the pre-fix generic path.
---
author: oompah
created: 2026-08-11 13:35
---
Implemented and pushed a dedicated coalesced single-flight terminal-audit continuation lane at 7bd90702b. Exact successor wakes now bypass unrelated full-world reconciliation while preserving shared audit ownership, workflow CAS authority, branch/capacity/pause/restart fences, and emitting claim/dispatch latency telemetry. Added production blocked-reconcile and race/lifecycle regression coverage; focused and adjacent verification is green. Ready for the server-owned exact-head branch gate and independent terminal audits.
---
<!-- COMMENTS:END -->
