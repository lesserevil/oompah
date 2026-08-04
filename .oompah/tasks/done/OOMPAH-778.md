---
id: OOMPAH-778
type: task
status: Done
priority: 1
title: Route orchestrator lifecycle writes through TaskTransitionService
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-776
labels: []
assignee: null
created_at: '2026-08-04T13:58:53.917290Z'
updated_at: '2026-08-04T17:44:26.640671Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  task_branch: OOMPAH-778
  base_branch: epic-OOMPAH-769
  head_sha: 6561d52e5a879375ea3587582f335419ed49310e
  submitted_at: '2026-08-04T17:41:55.468626+00:00'
  updated_at: '2026-08-04T17:42:23.215924+00:00'
  last_error: task worktree head db015701875b7976bfdaa7993b4043f2a21f2817 differs
    from the published task head 6561d52e5a879375ea3587582f335419ed49310e; refusing
    to reset a preserved recovery snapshot
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-f3ad3220be48
    project_id: proj-14849f1b
    task_id: OOMPAH-778
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e626484b0a37592c3e672ebc405760f10e3c1f9a3def9c8942e03319f229ee3f
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct-owner implementation was fully tested and landed at exact pushed
      head 6561d52e5 on epic-OOMPAH-769 after the integration worker incorrectly compared
      against stale parent-worktree head db0157018.
    created_at: '2026-08-04T17:44:18.062346+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-778
    target_state: Done
    evidence_fingerprint: e626484b0a37592c3e672ebc405760f10e3c1f9a3def9c8942e03319f229ee3f
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-04T17:44:25.352453+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Inventory and migrate every orchestrator.py status mutation to TaskTransitionService, preserving each call site reason, authority, exact-head/generation fence, and recovery behavior. Cover dispatch, worker exit, retry, integration, review, epic rollup, duplicate screening, watchdog, CI/rebase repair, and direct maintenance. Refactor callers to consume TransitionOutcome rather than assuming tracker writes succeed. Required focused tests for each migrated family plus race/restart tests; no terminal safety bypass. Acceptance: orchestrator.py contains no direct task-status update_issue call, stale/rejected transitions cannot mutate newer work, and existing lifecycle tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 17:41
---
Implemented the complete orchestrator lifecycle-write migration through TaskTransitionService. All status mutations now carry stable reason/authority context and use durable journal ownership, fresh version/status fencing, exact-head/generation checks where required, and terminal audit staging. Added AST guards against direct status writes, recovery/race coverage, terminal-stage routing, false-terminal repair edges, and exact-head reconstruction for stale-review requeue. Validation: 958 lifecycle tests passed; 69 focused transition/workflow/submission tests passed; terminal-audit scan, secret scan, py_compile, diff check, and F821/F822/F823 checks passed.
---
author: oompah
created: 2026-08-04 17:42
---
Centralized every orchestrator lifecycle status mutation in TaskTransitionService with durable journaling, fresh CAS fencing, terminal audit staging, exact-head/generation authority checks, recovery-edge contract coverage, and race/restart regression tests. Pushed exact reviewed head 6561d52e5; 958 lifecycle tests and 69 focused transition/workflow/submission tests pass.
---
author: oompah
created: 2026-08-04 17:42
---
Integration could not verify `OOMPAH-778`: task worktree head db015701875b7976bfdaa7993b4043f2a21f2817 differs from the published task head 6561d52e5a879375ea3587582f335419ed49310e; refusing to reset a preserved recovery snapshot

Fetch the private branch, preserve its commits, push a clean current head, and submit it again.
---
author: oompah
created: 2026-08-04 17:44
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct-owner implementation was fully tested and landed at exact pushed head 6561d52e5 on epic-OOMPAH-769 after the integration worker incorrectly compared against stale parent-worktree head db0157018.
---
<!-- COMMENTS:END -->
