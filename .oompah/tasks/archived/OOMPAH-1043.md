---
id: OOMPAH-1043
type: bug
status: Archived
priority: 2
title: '[backend:terminal_audit_enforcement] terminal-audit enforcement: pre_recovery_finalization_metadata_malformed:proj-14849f1b:OOMPAH-640'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T06:32:30.689762Z'
updated_at: '2026-08-11T07:56:12.174360Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-022585f3f862
    project_id: proj-14849f1b
    task_id: OOMPAH-1043
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b50fe6b93e938ad38e364fc6cb8f185547f105f8db411f75c0b96190f54f78fa
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Erroneous auto-file duplicate from the 2026-08-11 05ed11f22 malformed-ledger
      startup flood; OOMPAH-1015 is the canonical incident. The compatibility repair
      is deployed at 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 and paused recovery
      is healthy; this task owns no distinct implementation work.
    created_at: '2026-08-11T07:55:50.501698+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1043
    target_state: Archived
    evidence_fingerprint: b50fe6b93e938ad38e364fc6cb8f185547f105f8db411f75c0b96190f54f78fa
    workflow_revision: null
    selected_ref: null
    selected_sha: null
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-11T07:56:01.070280+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:terminal_audit_enforcement`:

> terminal-audit enforcement: pre_recovery_finalization_metadata_malformed:proj-14849f1b:OOMPAH-640

### Steps to Reproduce
1. Run oompah with `backend:terminal_audit_enforcement` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:terminal_audit_enforcement` and is recorded by oompah's `error_watcher`:

> terminal-audit enforcement: pre_recovery_finalization_metadata_malformed:proj-14849f1b:OOMPAH-640

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
- fingerprint: 25f641e76fdfe027
- dedup_fingerprint: 25f641e76fdfe027

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 07:56
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Erroneous auto-file duplicate from the 2026-08-11 05ed11f22 malformed-ledger startup flood; OOMPAH-1015 is the canonical incident. The compatibility repair is deployed at 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 and paused recovery is healthy; this task owns no distinct implementation work.
---
author: oompah
created: 2026-08-11 07:56
---
Archived duplicate startup-flood symptom; canonical incident is OOMPAH-1015.
---
<!-- COMMENTS:END -->
