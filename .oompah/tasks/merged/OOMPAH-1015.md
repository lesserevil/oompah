---
id: OOMPAH-1015
type: bug
status: Merged
priority: 2
title: '[backend:terminal_audit_enforcement] terminal-audit enforcement: pre_recovery_finalization_metadata_malformed:proj-14849f1b:OOMPAH-415'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T06:31:39.314795Z'
updated_at: '2026-08-11T08:10:01.118347Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-2b4aec74cbdd
    project_id: proj-14849f1b
    task_id: OOMPAH-1015
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e9e054d2c6c10dc88e29b3fea5a77095557a6a3dfcde76b2158c2726cfcbe1cd
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Protected PR #808 merged and hosted Python 3.11/3.12/3.13 gates passed;
      deployed build 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 is healthy while paused,
      accepted all legacy override ledger rows, completed terminal-audit recovery
      with no malformed rows or quarantine, and passed the paused rollout canary.'
    created_at: '2026-08-11T08:09:56.603183+00:00'
    selected_ref: origin/OOMPAH-1015
    selected_sha: 0226b16bcab880a62122e893d8aab799f3393133
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
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
