---
id: OOMPAH-962
type: bug
status: Open
priority: 1
title: Recover quarantined control effects without task deadlock
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T14:35:21.482578Z'
updated_at: '2026-08-09T15:35:45.306387Z'
work_branch: OOMPAH-962
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-962
  base_branch: epic-OOMPAH-940
  base_sha: 2dd74be288b81265ea4a242d7467ecc1ed9f1435
  head_sha: d46e474e1a49a65b714c3304fc0fb6ccc35aea3d
  submitted_at: '2026-08-09T15:17:04.691942+00:00'
  updated_at: '2026-08-09T15:17:04.691942+00:00'
oompah.work_branch: OOMPAH-962
---
## Summary

Fix durable workflow recovery when a synchronous control-effect adapter exceeds its operation timeout and the invocation cannot be terminated. Live reproduction on OOMPAH-959: authority_revocation exceeded 60 seconds, WorkflowJobStore.quarantine_owned left the job running with phase=quarantined and lease_expires_at=NULL, and the per-task serialization predicate then blocked a newer direct_owner_claim indefinitely while the service process remained alive. Preserve the core safety invariant that a possibly running external mutation must never overlap a replacement. Add an observable bounded recovery path: detect when the detached call actually returns and safely finalize/recover its exact fenced job, or request/coalesce a graceful service recycle when it cannot be proven complete; surface operator health until recovery and do not require manual SQLite edits. Relevant code: workflow_worker quarantine/detached-call lifecycle, workflow job recovery and per-task serialization, orchestrator restart/health signaling. Tests: late successful and failed return, permanently blocked call, concurrent replacement, shutdown/restart, PID-generation fencing, no duplicate external mutation, no busy loop, and exact control/data lane behavior. Acceptance: a quarantined control effect either reaches a safe terminal/retry state after its call returns or triggers bounded safe recovery, subsequent same-task work flows automatically, and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 14:42
---
Direct-owner implementation started in isolated worktree /home/shedwards/src/oompah-962 on branch OOMPAH-962. I am reproducing the authority_revocation timeout/quarantined NULL-lease deadlock and implementing fenced late-completion recovery while preserving never-overlap safety; no service mutation or deployment.
---
author: oompah
created: 2026-08-09 15:14
---
Implemented the quarantine settlement/recycle design on branch OOMPAH-962: exact late-result CAS settlement, durable bounded recycle marker, production mutation drain transfer, process/PID generation fencing, and no-overlap guards across control/data lanes and replacement paths. Focused config/job/worker/adapter/runtime suite is green (385 tests plus targeted replacement coverage). Rebasing onto current origin/main and performing final checks now.
---
author: oompah
created: 2026-08-09 15:17
---
Completed and pushed commit d46e474e1a49a65b714c3304fc0fb6ccc35aea3d on origin/OOMPAH-962, rebased on current origin/main. Verification: 386 focused tests passed across config, workflow ledger, worker, production implementation adapter, and runtime; terminal-audit scan passed; secret scan exited clean. The branch preserves quarantine until exact late settlement/process recovery, checkpoints late apply receipts without duplicate mutation, terminalizes late failures, requests one durable bounded graceful recycle for permanent blocks, and fences same-PID exec/PID reuse.
---
author: oompah
created: 2026-08-09 15:17
---
Implemented exact late quarantine settlement and bounded restart-safe recovery for timed-out workflow effects; pushed d46e474e1.
---
author: oompah
created: 2026-08-09 15:35
---
Independent-review corrections are complete and pushed at exact head 8bea28656286d06fd254e8d6a39592ade981939f. Marker/worker UUID mismatch no longer proves abandonment; only dead PID/start/process-generation or explicit operator authority recovers. Late settlement clears markers, stale markers are atomically replaced across lease ABA, failed settlement writes cross the bounded recycle path, and live quarantine count/age now degrade top-level health, emit an actionable alert, and fail the rollout canary. Verification: 468 affected tests passed, including the hosted workflow_scheduler health expectation; terminal-audit and secret scans passed.
---
<!-- COMMENTS:END -->
