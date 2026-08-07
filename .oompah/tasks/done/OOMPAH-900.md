---
id: OOMPAH-900
type: bug
status: Done
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=OOMPAH-658'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T17:46:19.331376Z'
updated_at: '2026-08-07T20:33:02.002299Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-2c259886cac8
    project_id: proj-14849f1b
    task_id: OOMPAH-900
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9bc21329da9577cdb1f0e953bf725bf9e15a19d1798586fd9675e5e7d44cbdfd
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Incident root cause was stale watchdog reopening of already-merged OOMPAH-658,
      followed by correct accepted-head mismatch fencing. OOMPAH-871 PR #741 merged
      exact head 158a2d03f0651b955666ba31c25b3fb412973ccd as 41b1477682c6460a1bb55356ac44c799c9fa783a
      with all three CI jobs green; OOMPAH-658 is restored to Merged and retained
      as terminal provenance, preventing recurrence.'
    created_at: '2026-08-07T20:32:55.886148+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=OOMPAH-658

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=OOMPAH-658

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
- fingerprint: dc13793d1a58970f
- dedup_fingerprint: dc13793d1a58970f
- source_issue: OOMPAH-658

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

