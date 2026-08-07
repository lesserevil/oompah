---
id: OOMPAH-904
type: bug
status: In Progress
priority: 2
title: '[backend:server] Post-commit worker cleanup failed for OOMPAH-647'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T19:33:51.824852Z'
updated_at: '2026-08-07T21:12:17.099634Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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
<!-- COMMENTS:END -->
