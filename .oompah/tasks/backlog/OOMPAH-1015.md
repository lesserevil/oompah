---
id: OOMPAH-1015
type: bug
status: Backlog
priority: 2
title: '[backend:terminal_audit_enforcement] terminal-audit enforcement: pre_recovery_finalization_metadata_malformed:proj-14849f1b:OOMPAH-415'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T06:31:39.314795Z'
updated_at: '2026-08-11T07:45:20.448526Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:terminal_audit_enforcement`:

> terminal-audit enforcement: pre_recovery_finalization_metadata_malformed:proj-14849f1b:OOMPAH-415

### Steps to Reproduce
1. Run oompah with `backend:terminal_audit_enforcement` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:terminal_audit_enforcement` and is recorded by oompah's `error_watcher`:

> terminal-audit enforcement: pre_recovery_finalization_metadata_malformed:proj-14849f1b:OOMPAH-415

### Expected Behavior
The operation in `backend:terminal_audit_enforcement` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:terminal_audit_enforcement` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 5bb394d82599b866
- dedup_fingerprint: 5bb394d82599b866

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 07:45
---
Canonical incident for the 2026-08-11 startup flood OOMPAH-1015..1070. Build 05ed11f22 rejected valid legacy terminal-override ledger rows whose historical schema omitted the later applied field, then task-specific error fingerprints auto-filed one task per affected source. OOMPAH-1016..1070 are duplicate symptoms and are being archived. Compatibility, fail-closed ledger validation, retired-authority filtering, and explicit-false transaction ordering are deployed at 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17; paused postdeploy recovery completed with zero malformed-ledger errors, zero quarantines, and no task above OOMPAH-1070. A separate systemic task will bound terminal-enforcement error fan-out by diagnostic class.
---
<!-- COMMENTS:END -->
