---
id: OOMPAH-1067
type: bug
status: Backlog
priority: 2
title: '[backend:terminal_audit_enforcement] terminal-audit enforcement: inactive_status_override_records_malformed:proj-14849f1b:OOMPAH-602'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T06:34:59.329288Z'
updated_at: '2026-08-11T08:05:45.235664Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7887017d6536
    project_id: proj-14849f1b
    task_id: OOMPAH-1067
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3adb3ce3475e0fbb033fdec78ff4ab7a072ce020821e34feefe1b5bb6af960a6
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Erroneous auto-file duplicate from the 2026-08-11 05ed11f22 malformed-ledger
      startup flood; OOMPAH-1015 is the canonical incident. The compatibility repair
      is deployed at 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 and paused recovery
      is healthy; this task owns no distinct implementation work.
    created_at: '2026-08-11T08:05:43.389274+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:terminal_audit_enforcement`:

> terminal-audit enforcement: inactive_status_override_records_malformed:proj-14849f1b:OOMPAH-602

### Steps to Reproduce
1. Run oompah with `backend:terminal_audit_enforcement` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:terminal_audit_enforcement` and is recorded by oompah's `error_watcher`:

> terminal-audit enforcement: inactive_status_override_records_malformed:proj-14849f1b:OOMPAH-602

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
- fingerprint: ad9e99ed8fc96b57
- dedup_fingerprint: ad9e99ed8fc96b57

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

