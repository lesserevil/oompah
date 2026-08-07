---
id: OOMPAH-903
type: bug
status: Done
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=OOMPAH-648'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T18:58:05.057419Z'
updated_at: '2026-08-07T20:34:15.558422Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c37690678527
    project_id: proj-14849f1b
    task_id: OOMPAH-903
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c7e6b945872f4b4d87bcb66e80199d721f56d88cfc423912b364d90173ae43f3
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Incident root cause was stale watchdog reopening of already-merged OOMPAH-648,
      followed by correct accepted-head mismatch fencing. OOMPAH-871 PR #741 merged
      exact head 158a2d03f0651b955666ba31c25b3fb412973ccd as 41b1477682c6460a1bb55356ac44c799c9fa783a
      with all three CI jobs green; OOMPAH-648 is restored to Merged and retained
      as terminal provenance, preventing recurrence.'
    created_at: '2026-08-07T20:34:11.811878+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=OOMPAH-648

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=OOMPAH-648

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
- fingerprint: 6eb4555dc5faaadc
- dedup_fingerprint: 6eb4555dc5faaadc
- source_issue: OOMPAH-648

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 19:10
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: ACP worker failed issue_id=OOMPAH-648

Source issue: `OOMPAH-648`
---
author: oompah
created: 2026-08-07 19:54
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: ACP worker failed issue_id=OOMPAH-648

Source issue: `OOMPAH-648`
---
author: oompah
created: 2026-08-07 20:09
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: ACP worker failed issue_id=OOMPAH-648

Source issue: `OOMPAH-648`
---
<!-- COMMENTS:END -->
