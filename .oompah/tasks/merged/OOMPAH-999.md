---
id: OOMPAH-999
type: bug
status: Merged
priority: 1
title: Do not revoke healthy quality gates on project-lock contention
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T16:13:42.956499Z'
updated_at: '2026-08-10T17:33:02.778261Z'
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
  creation_marker: oompah-997-gate-lock-contention-20260810
  request_fingerprint: 153fd005967abae58db03e565a0dda2ec93c87e3bf24c07ecaa9e6e381dbfee6
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-8b68e42682a2
    project_id: proj-14849f1b
    task_id: OOMPAH-999
    digest: 807aaf8e132e5bf7583701aa44b3db22f8edb5929a01df77d5bc97ec6a772bf5
  - version: 1
    audit_id: audit-31373eb67eb6
    project_id: proj-14849f1b
    task_id: OOMPAH-999
    digest: 807aaf8e132e5bf7583701aa44b3db22f8edb5929a01df77d5bc97ec6a772bf5
  oompah.terminal_override_records:
  - version: 1
    override_id: override-81f370fcabc2
    project_id: proj-14849f1b
    task_id: OOMPAH-999
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 807aaf8e132e5bf7583701aa44b3db22f8edb5929a01df77d5bc97ec6a772bf5
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner completion override after exact recovery head 6418a935de7b4aab93a24af4756a54b344463513
      passed the complete local make test gate (19,472 passed, 7 skipped, 2 xfailed),
      815 focused tests, terminal/secret/diff checks, and independent adversarial
      review; protected PR #799 passed Python 3.11, 3.12, and 3.13 CI and merged as
      0ce6c3131af200ab89090c13255c3606fc8d753b. The running terminal audit was repeating
      the same full gate because recovery-PR evidence was not imported into the branch-gate
      store.'
    created_at: '2026-08-10T17:32:58.280323+00:00'
    selected_ref: origin/OOMPAH-999
    selected_sha: 6418a935de7b4aab93a24af4756a54b344463513
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8b68e42682a2
    project_id: proj-14849f1b
    task_id: OOMPAH-999
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 807aaf8e132e5bf7583701aa44b3db22f8edb5929a01df77d5bc97ec6a772bf5
    attempts:
    - version: 1
      attempt_id: attempt-c918e21eb175
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 807aaf8e132e5bf7583701aa44b3db22f8edb5929a01df77d5bc97ec6a772bf5
      created_at: '2026-08-10T17:26:05.596980+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-10T17:26:05.596980+00:00'
      branch_key: OOMPAH-999
      selected_ref: origin/OOMPAH-999
      selected_sha: 6418a935de7b4aab93a24af4756a54b344463513
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-10T17:22:55.380838+00:00'
    selected_ref: origin/OOMPAH-999
    selected_sha: 6418a935de7b4aab93a24af4756a54b344463513
    updated_at: '2026-08-10T17:26:05.596980+00:00'
  - version: 1
    audit_id: audit-31373eb67eb6
    project_id: proj-14849f1b
    task_id: OOMPAH-999
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 807aaf8e132e5bf7583701aa44b3db22f8edb5929a01df77d5bc97ec6a772bf5
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-10T17:22:55.380838+00:00'
    selected_ref: origin/OOMPAH-999
    selected_sha: 6418a935de7b4aab93a24af4756a54b344463513
  attempt_history:
  - version: 1
    attempt_id: attempt-c918e21eb175
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 807aaf8e132e5bf7583701aa44b3db22f8edb5929a01df77d5bc97ec6a772bf5
    created_at: '2026-08-10T17:26:05.596980+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-10T17:26:05.596980+00:00'
    branch_key: OOMPAH-999
    selected_ref: origin/OOMPAH-999
    selected_sha: 6418a935de7b4aab93a24af4756a54b344463513
---
## Summary

Triggered by: OOMPAH-997

Regression of OOMPAH-953 observed during live OOMPAH-997 standalone delivery. BranchQualityGate hot cancellation polling calls the standalone local-authority predicate; that predicate attempts project_write_lock.acquire(blocking=False) and treats ordinary lock contention as false authority. Two exact OOMPAH-997 gates at unchanged head 94f1f5b84aa60bebf02cdd7d049de698df1e79ee were SIGTERM-cancelled after 14 seconds as owner_cancellation, consuming durable attempts without a test failure. Implementation scope: make transient project-lock contention distinguishable from actual local authority revocation in every long-running gate/validation cancellation callback. Use a stable local revocation token, tri-state/last-known-current result, or another bounded mechanism; never continue after a confirmed task/head/route/lease/workflow generation change. Keep expensive tracker/forge revalidation outside hot polling as required by OOMPAH-953, and retain exact pre-spawn and post-PASS barriers. Relevant code: oompah/integration_workflow.py standalone delivery authority checks, oompah/orchestrator.py local authorization and gate callbacks, oompah/quality_gate.py cancellation polling, and validation-resource admission. Required tests: deterministically hold the project write lock during a long gate and prove the gate is not interrupted and does not consume a retry; confirmed local lease/route/head/generation revocation still cancels promptly; contention followed by revocation cancels; pre-spawn and post-PASS full revalidation fail closed; unchanged exact-head retries remain idempotent; no tracker/forge I/O occurs in the hot loop. Acceptance: an OOMPAH-997-shaped gate survives routine project mutation contention, true authority loss remains bounded and fail-closed, no retry attempt is burned solely by lock contention, focused standalone/gate/lease tests and complete protected gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 16:54
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-999`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-10 16:54
---
Recovery head 6418a935de7b4aab93a24af4756a54b344463513 is pushed and protected PR #799 is open: https://github.com/lesserevil/oompah/pull/799. It preserves exact OOMPAH-997 94f1f5b84aa60bebf02cdd7d049de698df1e79ee, OOMPAH-998 9bf6011ac2481cbf3f73fe23085788814aa69434, and OOMPAH-999 76c86f0d760e4fa03361031d2055e02ade116b08 commits as ancestors. Exact-head verification: 815 combined focused tests passed; complete make test passed 19,472 tests with 7 skipped and 2 xfailed, zero failures, in 21m05s; terminal status-write scan, secret scan, diff check, and independent adversarial review passed. Project remains paused while protected Python 3.11/3.12/3.13 CI runs.
---
author: oompah
created: 2026-08-10 17:23
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-10 17:26
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-10 17:26
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
