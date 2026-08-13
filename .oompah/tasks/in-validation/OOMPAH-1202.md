---
id: OOMPAH-1202
type: bug
status: In Validation
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=TRICKLE-124 identifier=TRICKLE-124 run_id=5ec1b92404db430e9971b34803104ae8
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T00:37:46.158982Z'
updated_at: '2026-08-13T01:13:59.435396Z'
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
    audit_id: audit-a2f9379ecc6e
    project_id: proj-14849f1b
    task_id: OOMPAH-1202
    digest: 964a381cf343e46f2a0c06d6f0642fd123ae146b5f4afe538976b0424605ea6d
  - version: 1
    audit_id: audit-57d9f820651a
    project_id: proj-14849f1b
    task_id: OOMPAH-1202
    digest: 964a381cf343e46f2a0c06d6f0642fd123ae146b5f4afe538976b0424605ea6d
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a2f9379ecc6e
    project_id: proj-14849f1b
    task_id: OOMPAH-1202
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 964a381cf343e46f2a0c06d6f0642fd123ae146b5f4afe538976b0424605ea6d
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T01:13:53.346213+00:00'
    eligible_at: '2026-08-13T01:13:53.346213+00:00'
    selected_ref: origin/main
    selected_sha: 07d742c9cb37155beb22e8007937125f3ad053aa
  - version: 1
    audit_id: audit-57d9f820651a
    project_id: proj-14849f1b
    task_id: OOMPAH-1202
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 964a381cf343e46f2a0c06d6f0642fd123ae146b5f4afe538976b0424605ea6d
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T01:13:53.346213+00:00'
    prerequisite_audit_id: audit-a2f9379ecc6e
    selected_ref: origin/main
    selected_sha: 07d742c9cb37155beb22e8007937125f3ad053aa
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-124 identifier=TRICKLE-124 run_id=5ec1b92404db430e9971b34803104ae8 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=TRICKLE-124 identifier=TRICKLE-124 run_id=5ec1b92404db430e9971b34803104ae8 timeout_seconds=5.0

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
- fingerprint: e7961435ed8b5d8c
- dedup_fingerprint: e7961435ed8b5d8c

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 00:49
---
Operator reproduced this under live Trickle scheduling and took direct ownership. Root cause: a lock-order inversion. _persist_work_contributor() acquires AUDITOR_POLICY_AUTHORITY.mutation() before tracker publication later acquires the ProjectStore project lock, while ProjectStore.update() acquires that project lock before _update_unlocked() acquires AUDITOR_POLICY_AUTHORITY.mutation(). Concurrent contributor persistence and project state mutation deadlock permanently; the configured deadline only retires the runtime while its detached thread keeps both paths wedged. The HTTP control plane then blocks on provider admission/project state. Fixing lock ordering with regression coverage; the service has been emergency-restarted and globally paused with task worktrees preserved.
---
author: oompah
created: 2026-08-13 01:01
---
Fix implemented and pushed on branch OOMPAH-1202 (commit fdaa27b0c, PR #843). Contributor evidence now takes per-project authority before auditor-policy authority, matching ProjectStore.update and eliminating the deadlock cycle. Added a direct lock-order regression and a concurrent production-shape ProjectStore/ProvenanceGuardedTracker regression. Focused verification: 21 provider-retirement tests and 543 orchestrator/project tests pass; terminal mutation and secret scans pass. Full Python 3.11/3.12/3.13 CI is running.
---
author: oompah
created: 2026-08-13 01:13
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
