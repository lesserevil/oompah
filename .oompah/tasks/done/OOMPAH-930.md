---
id: OOMPAH-930
type: task
status: Done
priority: null
title: Isolate event-loop and close-race tests from live project reconciliation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T03:11:25.306117Z'
updated_at: '2026-08-09T05:16:38.737425Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-e5493a4590f1
    project_id: proj-14849f1b
    task_id: OOMPAH-930
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 84a259db785128f8e24e1ac7359a7cc4476be3206ffcedc601d6360710a4a74e
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:16:28.098471+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-930
    target_state: Done
    evidence_fingerprint: 84a259db785128f8e24e1ac7359a7cc4476be3206ffcedc601d6360710a4a74e
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:16:37.098567+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

The exact OOMPAH-929 gate reproducibly times out in tests/test_event_driven_loop.py and tests/test_dispatch_close_race.py because directly constructed Orchestrator fixtures retain unmocked startup/state-publication reconcilers that traverse the operator's live WORKFLOW.md projects and native task corpus. A serial reproduction shows TestRunEventDrivenLoop::test_run_calls_tick_on_startup blocked in _reconcile_owner_duplicate_resolution_boundaries reading real Exocomp/Oompah task Markdown until pytest's five-second timeout; close-race TestClient fixtures similarly expose live snapshot work through module-global server state. Implementation scope: make these unit fixtures explicitly isolate every unrelated startup reconciler, project binding, state publisher, and observer path while preserving the behavior each test claims to exercise; do not weaken production startup, lifecycle, transition, or cleanup behavior and do not merely extend timeouts. Relevant files: tests/test_event_driven_loop.py, tests/test_dispatch_close_race.py, shared test factories/fixtures if appropriate, and production only if an actual boundary defect is demonstrated. Required tests: both complete modules pass serially and in parallel with a large live task corpus present; focused failing cases repeat at least 20 times; fixture teardown leaves no event-loop tasks, threads, timers, or module-global orchestrator leakage; exact make test passes. Acceptance: these unit tests never read configured live project trackers or invoke unrelated Git/forge work, remain deterministic under parallel load, and retain assertions for shutdown/event coalescing and retry cancellation races.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 05:16
---
Completed by direct project owner. Live-project fixture isolation commits 765c187e6 and d8610fbdc are included in rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e. Repeated focused runs and the exact full gate passed with the production server stopped; the same exact build is live in enforce.
---
author: oompah
created: 2026-08-09 05:16
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct project-owner completion after exact-head full-gate and live enforce verification.
---
<!-- COMMENTS:END -->
