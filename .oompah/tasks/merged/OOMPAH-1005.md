---
id: OOMPAH-1005
type: task
status: Merged
priority: null
title: Wake durable workflow admission after asynchronous supersession
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T21:14:15.251946Z'
updated_at: '2026-08-10T22:57:39.740967Z'
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
  creation_marker: 366e40d8-e159-470e-acc7-edf805f13e50
  request_fingerprint: 7229ac1d63d12bb628dc737c92f1580a61dbfeed38f4aa2568f969080eb115c5
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-de07ca92991b
    project_id: proj-14849f1b
    task_id: OOMPAH-1005
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 741fc72be49dab4de6957d18f2137cabb0c715e23464d61799ed2a4ba52424a4
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Protected PR #804 merged exact reviewed and fully gated implementation
      into main at 74e68a020357615c81cf7c7b5cff808763dc34d3; direct owner is terminalizing
      the claimed repair after hosted Python 3.11/3.12/3.13 success.'
    created_at: '2026-08-10T22:57:22.700432+00:00'
    selected_ref: origin/OOMPAH-1005
    selected_sha: 2f0eb05f4798107e07876469386b9060a0cb9ba9
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1005
    target_state: Merged
    evidence_fingerprint: 741fc72be49dab4de6957d18f2137cabb0c715e23464d61799ed2a4ba52424a4
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-10T22:57:32.077050+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-940

Problem: after generation 1720 published a current OOMPAH-940 epic_auto_close job, the retained background invocation for obsolete OOMPAH-1003 parent_rollup_review finished as SUPERSEDED and released its durable lease, but no new orchestrator/admission wake was requested. The current OOMPAH-940 job remained queued with zero attempts and no lease until another external event or the five-minute full-sync safety net. This violates event-driven progress and makes the cached UI worker snapshot look retained after durable ownership is gone.

Scope: make every retained durable workflow invocation completion path (including SUPERSEDED, LEASE_LOST, RETRY_SCHEDULED, ACTION_REQUIRED, and exception/cancellation cleanup) publish one coalesced scheduler/admission wake when claimable current work may remain; preserve bounded lanes, pause/quiesce fences, exact snapshot-generation admission, and avoid busy loops when no job is claimable. Refresh the cached state projection when the retained task exits so worker/lease counts cannot remain stale until an unrelated tick. Relevant code: oompah/workflow_runtime.py retained invocation scheduling/completion callbacks, oompah/workflow_worker.py result paths, and orchestrator refresh/event intake.

Required tests: reproduce a background job that is superseded after admission while a second current job is queued; prove the second job is claimed without waiting for full sync; cover non-success result paths, completion-vs-pause/quiesce races, wake coalescing, no-claimable-work behavior, and state snapshot worker/lease convergence.

Acceptance: queued current durable work always receives an event-driven follow-up admission after any retained invocation exits, no spin loop is introduced, and focused plus complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 21:29
---
Accepted for direct-owner repair after live OOMPAH-940 canary reproduced the missing asynchronous completion wake.
---
author: oompah
created: 2026-08-10 21:40
---
Implementation in progress on branch OOMPAH-1005. The lost-wake boundary is the admission owner's exit handoff: completion can arrive after its last recheck but before its Future is observably done. The fix records durable coalesced wake intent, transfers it to exactly one successor, keeps pause/quiesce/drain admission fenced, and publishes retained-worker state after every exit. Focused race, non-success, exception/cancellation, fencing, and state-convergence regressions are being added; independent review is active.
---
author: oompah
created: 2026-08-10 21:47
---
Implementation is committed and pushed at exact head 2f0eb05f4798107e07876469386b9060a0cb9ba9. It preserves coalesced admission intent across owner exit, consumes stale failed-owner results before identity fencing, refreshes state after every retained invocation exit, and isolates state publication failures from the flow-critical admission wake. The affected-file suite passed 185 tests; secrets, hooks, attribution, and worktree sync are green. Independent final exact-head review is in progress before combined protected delivery.
---
author: oompah
created: 2026-08-10 22:11
---
Exact combined recovery head 1e9032b4bdd870acf6822962fb45dcc8c5e73d3a passed focused validation (457 passed, 2 expected xfails), terminal mutation scan 20/20, secret/diff checks, and the complete make test gate: 19,679 passed, 7 skipped, 2 expected xfails in 21m06s. Protected delivery PR #804 is open and running hosted Python 3.11/3.12/3.13 checks.
---
author: oompah
created: 2026-08-10 22:46
---
Hosted PR #804 exposed one test-only xdist incompatibility: production emitted and captured the expected stale-owner failure on Python 3.11/3.12/3.13, but the new test inspected caplog records after asyncio.run. The assertion now directly observes the logger call and preserves the production invariants. It passed repeated xdist runs and isolated Python 3.11/3.12/3.13 checks. Updated exact head 5fc2432263ad3593ef891dc716b43332083ed455 passed the full make test gate: 19,679 passed, 7 skipped, 2 expected xfails in 21m09s, and is pushed to rerun hosted CI.
---
author: oompah
created: 2026-08-10 22:57
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Protected PR #804 merged exact reviewed and fully gated implementation into main at 74e68a020357615c81cf7c7b5cff808763dc34d3; direct owner is terminalizing the claimed repair after hosted Python 3.11/3.12/3.13 success.
---
author: oompah
created: 2026-08-10 22:57
---
Preserve durable workflow admission wakes across retained-effect completion and owner-exit races.
---
<!-- COMMENTS:END -->
