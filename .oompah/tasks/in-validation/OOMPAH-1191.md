---
id: OOMPAH-1191
type: bug
status: In Validation
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=TRICKLE-140'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T22:41:57.033700Z'
updated_at: '2026-08-13T04:44:50.277720Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 2
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-279f36055070
    project_id: proj-14849f1b
    task_id: OOMPAH-1191
    digest: fc049f390ddcd11b482b9f697e28cfcec3a38657d07caf7b8d6b590d36ec8c94
  - version: 1
    audit_id: audit-7709dfbfe186
    project_id: proj-14849f1b
    task_id: OOMPAH-1191
    digest: fc049f390ddcd11b482b9f697e28cfcec3a38657d07caf7b8d6b590d36ec8c94
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-279f36055070
    project_id: proj-14849f1b
    task_id: OOMPAH-1191
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fc049f390ddcd11b482b9f697e28cfcec3a38657d07caf7b8d6b590d36ec8c94
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T01:55:31.525192+00:00'
    eligible_at: '2026-08-13T01:55:31.525192+00:00'
    selected_ref: origin/main
    selected_sha: 5f88d74b9668dbf611767fdbd0cd1ef9d1750587
  - version: 1
    audit_id: audit-7709dfbfe186
    project_id: proj-14849f1b
    task_id: OOMPAH-1191
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fc049f390ddcd11b482b9f697e28cfcec3a38657d07caf7b8d6b590d36ec8c94
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T01:55:31.525192+00:00'
    prerequisite_audit_id: audit-279f36055070
    selected_ref: origin/main
    selected_sha: 5f88d74b9668dbf611767fdbd0cd1ef9d1750587
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=TRICKLE-140

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=TRICKLE-140

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
- fingerprint: 15f7150750a148eb
- dedup_fingerprint: 15f7150750a148eb
- source_issue: TRICKLE-140

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 22:57
---
Live root cause confirmed during the paused Trickle verification window. TRICKLE-140 retains accepted integration head 6d089ed6 and work_branch TRICKLE-140, but GitLab MR !4 merged that exact head into main and deleted origin/TRICKLE-140; follow-up MR !5 also merged. Duplicate preflight is read-only, yet _create_workspace_for_issue routes it through accepted_submission_branch/create_worktree, which requires the mutable remote branch to still exist and equal the accepted head. The accepted commit is present and is an ancestor of origin/main, so branch deletion after merge is normal, not an infrastructure failure. Repair should bind read-only duplicate screening to the immutable accepted commit (or a freshly proven containing target) without requiring the deleted source ref, retain exact authority fencing, and add a merged+deleted-source-branch regression. Trickle is paused; TRICKLE-140 was restored to Open but duplicate screening exhausted to owner action after this third inconclusive attempt.
---
author: oompah
created: 2026-08-13 01:16
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: ACP worker failed issue_id=TRICKLE-140

Source issue: `TRICKLE-140`
---
author: oompah
created: 2026-08-13 01:43
---
Root cause confirmed live on TRICKLE-140: duplicate screening reused mutable implementation workspace recovery after an accepted branch had been merged/deleted. Implemented attempt-scoped detached read-only screening at the immutable accepted SHA (or an atomic target-branch snapshot for fresh tasks), plus exact cleanup. Focused tests cover merged/deleted source branches and cleanup scoping.
---
author: oompah
created: 2026-08-13 01:55
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-13 03:41
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: ACP worker failed issue_id=TRICKLE-140

Source issue: `TRICKLE-140`
---
author: oompah
created: 2026-08-13 03:59
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: ACP worker failed issue_id=TRICKLE-140

Source issue: `TRICKLE-140`
---
author: oompah
created: 2026-08-13 04:44
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: ACP worker failed issue_id=TRICKLE-140

Source issue: `TRICKLE-140`
---
<!-- COMMENTS:END -->
