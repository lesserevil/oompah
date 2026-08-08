---
id: OOMPAH-904
type: bug
status: Done
priority: 2
title: '[backend:server] Post-commit worker cleanup failed for OOMPAH-647'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T19:33:51.824852Z'
updated_at: '2026-08-08T03:57:57.188125Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-33099a05fe73
    project_id: proj-14849f1b
    task_id: OOMPAH-904
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6426a4776f9a7d7ea5e22f758094c6a0305b8c234d3adadb93f93b247217cf06
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner reconciliation for OOMPAH-904: its accepted implementation
      is patch-contained in published epic-OOMPAH-763 at e74449e4f9303f35c2cc2c1c5fc78ee979f4d268.
      Independent composition review completed, affected tests passed 392/392, and
      the exact full make test passed 17,860 with zero failures.'
    created_at: '2026-08-08T03:57:39.820467+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-904
    target_state: Done
    evidence_fingerprint: 6426a4776f9a7d7ea5e22f758094c6a0305b8c234d3adadb93f93b247217cf06
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T03:57:49.499801+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Post-commit worker cleanup failed for OOMPAH-647

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Post-commit worker cleanup failed for OOMPAH-647

### Expected Behavior
The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 1800c05d942836b4
- dedup_fingerprint: 1800c05d942836b4

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 21:02
---
Direct repair in progress on isolated branch compose-OOMPAH-763--O904 based on epic OOMPAH-763 lineage. Root cause confirmed: the one-second owner-loop publication acknowledgement timeout raises a generic RuntimeError after the status commit, so server logger.exception creates a false backend task and no exact-runtime retry is requested. Patch now uses a distinct retryable timeout type, warning-level classification, generation-fenced scheduled retirement retry, and API/coordinator regressions. Focused tests are queued behind the shared broker; no live checkout changes.
---
author: oompah
created: 2026-08-07 21:12
---
Repair complete and pushed on origin/compose-OOMPAH-763--O904 at exact head 7574bd004d8fba1ce43122d036f68d2ec3fe4d6d, based on epic OOMPAH-763 lineage. The distinct owner-loop publication timeout now requests an exact-generation retirement retry; admitted retries are warning-only, while no-admission/scheduling failures and generic cleanup exceptions remain error-visible with truthful API diagnostics. Validation: 8 focused API/coordinator regressions passed, py_compile/diff check green, make check-secrets passed, independent revised-head review ACCEPT. Holding for cherry-pick into final OOMPAH-763 composition.
---
author: oompah
created: 2026-08-08 03:57
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project-owner reconciliation for OOMPAH-904: its accepted implementation is patch-contained in published epic-OOMPAH-763 at e74449e4f9303f35c2cc2c1c5fc78ee979f4d268. Independent composition review completed, affected tests passed 392/392, and the exact full make test passed 17,860 with zero failures.
---
author: oompah
created: 2026-08-08 03:57
---
Integrated and validated on epic-OOMPAH-763 at e74449e4f9303f35c2cc2c1c5fc78ee979f4d268.
---
<!-- COMMENTS:END -->
