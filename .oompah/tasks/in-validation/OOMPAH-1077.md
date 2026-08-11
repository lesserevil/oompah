---
id: OOMPAH-1077
type: task
status: In Validation
priority: null
title: Make workflow-worker heartbeat lease proof deterministic under loaded CI
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T09:45:59.661224Z'
updated_at: '2026-08-11T10:14:01.253275Z'
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
  creation_marker: ba8cb63b-b18c-47c9-a649-ff62bff38df3
  request_fingerprint: 8717186aaf2588a4b6febd726286b9fd9ad8279083d60b757222210d206c14a4
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-70d3e2b7ecda
    project_id: proj-14849f1b
    task_id: OOMPAH-1077
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 47978ac9237e1409a73867143159e56cc1b715abbeec7b11394e17ab357ee60d
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: '[REDACTED]'
    created_at: '2026-08-11T10:13:59.682515+00:00'
    selected_ref: origin/main
    selected_sha: 4be80277a97a06a0de2165406f3c87e351b85780
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Protected PR #812 Python 3.11 failed after 19,876 passing tests in tests/test_workflow_worker.py::test_heartbeat_renews_lease_during_long_effect: a real-clock 80ms lease plus 20ms heartbeat and a 150ms asyncio sleep returned LEASE_LOST under hosted load. OOMPAH-970 fixed the analogous detached WorkflowRuntime test but did not cover this lower-level worker test. A sleep-and-hope lease proof is a race-dependent test bug and cannot be handled by blind reruns. Implementation scope: replace the wall-clock timing gamble with deterministic synchronization or an injectable clock/renewal observation proving DurableWorkflowWorker renews the exact live lease while apply is blocked; preserve production lease-expiry semantics and do not merely widen delays. Relevant files: tests/test_workflow_worker.py and only the narrow oompah/workflow_worker.py seam if necessary. Required tests: repeated focused execution remains stable under scheduler delay; proof fails if renewal is absent; exact lease token, at least two renewals, single apply, and final completion remain asserted. Acceptance: focused repeated runs and the workflow-worker suite pass, the change is independently reviewed, and protected Python 3.11/3.12/3.13 CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 09:53
---
Implemented deterministic workflow-worker lease proof on bundled PR #812 branch OOMPAH-1075 at exact head 9158bb02df2505b232fbbe49d40eacc72ca23183. The test now holds apply behind an explicit barrier, waits for two observed heartbeat renewals of the exact lease token, advances the injected store clock past the original lease expiry to prove renewal kept authority live, verifies the external effect is still unapplied before release, and then asserts one apply plus completion. No production semantics or timers were changed. Validation: focused test passed 50/50 consecutive runs; tests/test_workflow_worker.py passed 50/50; git diff --check passed. Commit pushed; branch intentionally not rebased so the coordinator can rebase it once onto newly deployed main.
---
author: oompah
created: 2026-08-11 09:54
---
The deterministic heartbeat-test fix was rebased with OOMPAH-1075 onto deployed main and is now published at exact combined head d912a999d13d4fc739f4c14580b1facd94056382 in PR #812. The focused heartbeat test passed 50 consecutive runs before rebase; after rebase the combined affected suite passed 481 tests. Independent exact-head review and protected matrix are running.
---
author: oompah
created: 2026-08-11 10:05
---
Merged as commit d912a999d within protected PR #812 / merge 4be80277a; exact-head independent review and Python 3.11/3.12/3.13 gates passed.
---
<!-- COMMENTS:END -->
