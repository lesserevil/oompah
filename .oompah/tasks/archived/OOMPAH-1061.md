---
id: OOMPAH-1061
type: bug
status: Archived
priority: 2
title: '[backend:terminal_audit_enforcement] terminal-audit enforcement: inactive_status_override_records_malformed:proj-14849f1b:OOMPAH-575'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T06:34:48.727280Z'
updated_at: '2026-08-11T08:03:25.748895Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-8663e856fc23
    project_id: proj-14849f1b
    task_id: OOMPAH-1061
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4cbb4ea59cc6486e6ee42c9b7330445b9dd65720d39d4ad33d7e99a8cc1be818
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Erroneous auto-file duplicate from the 2026-08-11 05ed11f22 malformed-ledger
      startup flood; OOMPAH-1015 is the canonical incident. The compatibility repair
      is deployed at 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 and paused recovery
      is healthy; this task owns no distinct implementation work.
    created_at: '2026-08-11T08:03:03.731285+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1061
    target_state: Archived
    evidence_fingerprint: 4cbb4ea59cc6486e6ee42c9b7330445b9dd65720d39d4ad33d7e99a8cc1be818
    workflow_revision: null
    selected_ref: null
    selected_sha: null
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-11T08:03:17.642430+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:terminal_audit_enforcement`:

> terminal-audit enforcement: inactive_status_override_records_malformed:proj-14849f1b:OOMPAH-575

### Steps to Reproduce
1. Run oompah with `backend:terminal_audit_enforcement` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:terminal_audit_enforcement` and is recorded by oompah's `error_watcher`:

> terminal-audit enforcement: inactive_status_override_records_malformed:proj-14849f1b:OOMPAH-575

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
- fingerprint: a83baeb553226db7
- dedup_fingerprint: a83baeb553226db7

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 08:03
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Erroneous auto-file duplicate from the 2026-08-11 05ed11f22 malformed-ledger startup flood; OOMPAH-1015 is the canonical incident. The compatibility repair is deployed at 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 and paused recovery is healthy; this task owns no distinct implementation work.
---
author: oompah
created: 2026-08-11 08:03
---
Archived duplicate startup-flood symptom; canonical incident is OOMPAH-1015.
---
<!-- COMMENTS:END -->
