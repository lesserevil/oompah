---
id: OOMPAH-1014
type: bug
status: Ready to Integrate
priority: 1
title: Retire orphaned terminal-audit authority before workflow publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T04:35:54.427125Z'
updated_at: '2026-08-11T06:24:01.592086Z'
work_branch: OOMPAH-1014
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/807
review_number: '807'
review_head: b7c5ab03f09d0bf994dfcbb04526f96f91d58979
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: o940-orphaned-audit-publication-deadlock-20260811
  request_fingerprint: a5344a93d25cc8ff40b2d235f76cc7c28c86a6f51b7c1633ee029b93841ffd28
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1014
  head_sha: b7c5ab03f09d0bf994dfcbb04526f96f91d58979
  submitted_at: '2026-08-11T06:20:01.281832+00:00'
  updated_at: '2026-08-11T06:20:01.281832+00:00'
oompah.work_branch: OOMPAH-1014
oompah.review_url: https://github.com/lesserevil/oompah/pull/807
oompah.review_number: '807'
oompah.target_branch: main
oompah.review_head: b7c5ab03f09d0bf994dfcbb04526f96f91d58979
---
## Summary

Triggered by: OOMPAH-1009

Live regression on deployed main 62c3cda3ea602b614a3a3dfc92c66468b5c34a4b after OOMPAH-1008 through OOMPAH-1013: OOMPAH-940 is canonically Needs CI Fix after leaving In Validation, but its terminal-audit document retains audit-ae12c1070eaf in_progress and sibling audit-a3c06f37679e pending. The terminal-audit candidate/health scanner correctly observes only In Validation tasks and reports zero active audits, while the workflow terminal_audit fact source still projects the orphaned record. Publication then includes a terminal snapshot proof whose liveness decision has no terminal-audit obligation; terminal_audit_lane_proof_source returns false, and every whole-world restart cut is superseded with 'terminal-audit disposition changed before publication'. Captured generations 2175, 2176, and 2177 failed at 04:28:54, 04:31:07, and 04:33:20 UTC while accepted/published remained 2123 and restart became overdue. Implement an exact, durable lifecycle rule for a task that leaves In Validation while a terminal audit is pending/running: retire/cancel the obsolete audit record and lane authority under the project fence, or project it as non-authoritative only after proving the current tracker status/evidence supersedes it. Ensure provider processes/worktrees/claims are safely retired and that a stale record cannot regain authority on restart. The workflow fact and publication proof paths must agree with audit candidate eligibility; do not weaken same-task fail-closed CAS for a genuinely current In Validation audit. Relevant code: oompah/orchestrator.py terminal_audit fact source and audit lane recovery, oompah/terminal_audit_enforcement.py recovery, oompah/terminal_transition_coordinator.py override/status lifecycle, oompah/workflow_runtime.py publication proofs, and focused tests. Required tests: Needs CI Fix/Open/Needs Human transition racing an in-progress audit; restart with the orphaned metadata and SQLite lane job; world publication converges within the restart deadline; old result/finalization cannot mutate the repair status; exact retry back to In Validation either reuses/rearms safely or creates a new generation; active current In Validation audit remains fail-closed; multi-project isolation; worktree/process cleanup; repeated ticks are idempotent. Acceptance: the OOMPAH-940 live shape publishes a complete current snapshot without direct SQLite/task-file edits, no stale auditor can relaunch or finalize, normal audit flow still works, focused workflow/runtime/audit suites and the complete Makefile gate pass, and make workflow-rollout-check is healthy after deployment.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 05:51
---
Implementation is active on branch OOMPAH-1014. The repair-status orphan authority, workflow publication proof, exact auditor runtime/job lease, ABA departure transaction, malformed-ledger fail-closed handling, maintenance writer bypass, and retryable detached-worktree cleanup are implemented with direct/integrated regressions. Latest stable relevant gate: 613 passed; terminal mutation scan 21/21 and secret scan passed. Independent race/correctness re-review is still in progress before the complete Makefile gate.
---
author: oompah
created: 2026-08-11 06:20
---
Fixed orphaned terminal-audit authority across status departures, restart publication, workflow/job identity, auditor runtime reconciliation, and retryable workspace cleanup. Added fail-closed ledger validation, durable fresh-generation rearm, operator documentation, and comprehensive race/restart regressions. Validation: make test (19,823 passed, 7 skipped, 2 xfailed); affected suite 614 passed; race soak 410 passed; workflow soak passed; terminal mutation scan 21/21; secret scan passed; three independent reviews clear. Exact pushed head b7c5ab03f09d0bf994dfcbb04526f96f91d58979.
---
<!-- COMMENTS:END -->
