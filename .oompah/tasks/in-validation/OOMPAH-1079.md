---
id: OOMPAH-1079
type: bug
status: In Validation
priority: 2
title: '[backend:orchestrator] Lifecycle state publication failed'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T10:43:32.317191Z'
updated_at: '2026-08-11T11:24:03.318820Z'
work_branch: OOMPAH-1079
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1079
  head_sha: d54b92a0c5067aad11df0094d6f3cff5e1b28068
  submitted_at: '2026-08-11T11:12:30.936161+00:00'
  updated_at: '2026-08-11T11:12:30.936161+00:00'
oompah.work_branch: OOMPAH-1079
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-bb55a2f9eeb7
    project_id: proj-14849f1b
    task_id: OOMPAH-1079
    digest: 5402ae5f9530247b9bc7e3a4281e9c1b97fd16d5d9498afae5b2e1ad7a868bb2
  - version: 1
    audit_id: audit-9dc17c2a55b9
    project_id: proj-14849f1b
    task_id: OOMPAH-1079
    digest: 5402ae5f9530247b9bc7e3a4281e9c1b97fd16d5d9498afae5b2e1ad7a868bb2
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-bb55a2f9eeb7
    project_id: proj-14849f1b
    task_id: OOMPAH-1079
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5402ae5f9530247b9bc7e3a4281e9c1b97fd16d5d9498afae5b2e1ad7a868bb2
    attempts:
    - version: 1
      attempt_id: attempt-4029f01084b4
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5402ae5f9530247b9bc7e3a4281e9c1b97fd16d5d9498afae5b2e1ad7a868bb2
      created_at: '2026-08-11T11:23:49.397922+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T11:23:49.397922+00:00'
      branch_key: OOMPAH-1079
      selected_ref: d54b92a0c5067aad11df0094d6f3cff5e1b28068
      selected_sha: d54b92a0c5067aad11df0094d6f3cff5e1b28068
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-11T11:18:45.072100+00:00'
    selected_ref: d54b92a0c5067aad11df0094d6f3cff5e1b28068
    selected_sha: d54b92a0c5067aad11df0094d6f3cff5e1b28068
    updated_at: '2026-08-11T11:23:49.397922+00:00'
  - version: 1
    audit_id: audit-9dc17c2a55b9
    project_id: proj-14849f1b
    task_id: OOMPAH-1079
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5402ae5f9530247b9bc7e3a4281e9c1b97fd16d5d9498afae5b2e1ad7a868bb2
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-11T11:18:45.072100+00:00'
    selected_ref: d54b92a0c5067aad11df0094d6f3cff5e1b28068
    selected_sha: d54b92a0c5067aad11df0094d6f3cff5e1b28068
  attempt_history:
  - version: 1
    attempt_id: attempt-4029f01084b4
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5402ae5f9530247b9bc7e3a4281e9c1b97fd16d5d9498afae5b2e1ad7a868bb2
    created_at: '2026-08-11T11:23:49.397922+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T11:23:49.397922+00:00'
    branch_key: OOMPAH-1079
    selected_ref: d54b92a0c5067aad11df0094d6f3cff5e1b28068
    selected_sha: d54b92a0c5067aad11df0094d6f3cff5e1b28068
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Lifecycle state publication failed

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Lifecycle state publication failed

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 889532bf651003a0
- dedup_fingerprint: 889532bf651003a0

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 10:59
---
Root cause reproduced from the 2026-08-11 10:43 graceful restart: _run_lifecycle_publication called get_snapshot()->workflow_job_store.health_snapshot() after the workflow-jobs SQLite connection had closed, raising sqlite3.ProgrammingError. Direct-owner claim established; fix will make shutdown drain/close lifecycle publication authority before dependent stores and add a deterministic race regression.
---
author: oompah
created: 2026-08-11 11:10
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-1079`
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
created: 2026-08-11 11:12
---
Fix lifecycle publication teardown race; exact head d54b92a0c5067aad11df0094d6f3cff5e1b28068, 144 affected tests and terminal mutation scan passed.
---
author: oompah
created: 2026-08-11 11:18
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 11:21
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: Lifecycle state publication failed
---
author: oompah
created: 2026-08-11 11:23
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 11:24
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
