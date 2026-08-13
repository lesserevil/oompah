---
id: OOMPAH-1244
type: bug
status: In Validation
priority: 2
title: '[backend:acp_agent] ACP backend ''claude'' crashed during run_turn: OSError:
  configured provider authentication artifact is unavailable'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T14:34:54.048407Z'
updated_at: '2026-08-13T16:35:49.231080Z'
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
    audit_id: audit-57a82a4889eb
    project_id: proj-14849f1b
    task_id: OOMPAH-1244
    digest: 43620d7f3d9ed22fbf1cb4fb05cde1146f1843414d129e2bb60df599f718fb45
  - version: 1
    audit_id: audit-27d3a4d92676
    project_id: proj-14849f1b
    task_id: OOMPAH-1244
    digest: 43620d7f3d9ed22fbf1cb4fb05cde1146f1843414d129e2bb60df599f718fb45
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-57a82a4889eb
    project_id: proj-14849f1b
    task_id: OOMPAH-1244
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 43620d7f3d9ed22fbf1cb4fb05cde1146f1843414d129e2bb60df599f718fb45
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T16:35:43.939700+00:00'
    eligible_at: '2026-08-13T16:35:43.939700+00:00'
    selected_ref: origin/OOMPAH-1244
    selected_sha: 84d03e811aaabe1a0cfa7bd851261f4c49bac765
  - version: 1
    audit_id: audit-27d3a4d92676
    project_id: proj-14849f1b
    task_id: OOMPAH-1244
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 43620d7f3d9ed22fbf1cb4fb05cde1146f1843414d129e2bb60df599f718fb45
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T16:35:43.939700+00:00'
    prerequisite_audit_id: audit-57a82a4889eb
    selected_ref: origin/OOMPAH-1244
    selected_sha: 84d03e811aaabe1a0cfa7bd851261f4c49bac765
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:acp_agent`:

> ACP backend 'claude' crashed during run_turn: OSError: configured provider authentication artifact is unavailable

### Steps to Reproduce
1. Run oompah with `backend:acp_agent` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:acp_agent` and is recorded by oompah's `error_watcher`:

> ACP backend 'claude' crashed during run_turn: OSError: configured provider authentication artifact is unavailable

### Expected Behavior
The operation in `backend:acp_agent` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:acp_agent` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 1b3f11c8112aa2ab
- dedup_fingerprint: 1b3f11c8112aa2ab

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 15:55
---
Live root cause confirmed on TRICKLE-141: all dispatch profiles selected Claude subscription while the host lacks ~/.claude/.credentials.json, so isolated workers exited at zero turns with configured provider authentication artifact is unavailable. The generic provider probe still reported Claude healthy because it used ambient provider access rather than the isolated worker credential boundary. Operational workaround applied through the supported live profile API: quick, default, standard, and deep now select the authenticated Codex subscription provider. Permanent acceptance must make provider health/admission validate the same isolated-worker auth artifact before marking a provider dispatchable, with tests for probe-success/worker-auth-missing divergence and fallback to a genuinely launchable provider.
---
author: oompah
created: 2026-08-13 16:08
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:acp_agent`

Message: ACP backend 'claude' crashed during run_turn: OSError: configured provider authentication artifact is unavailable
---
author: oompah
created: 2026-08-13 16:13
---
Direct implementation claimed after reproducing the exact current-layout mismatch: claude auth status is healthy from the operator environment, but the installed Claude release reads a primaryApiKey from ~/.claude.json while isolated rebase bootstrap only accepts ~/.claude/.credentials.json. A minimal isolated home containing only the primaryApiKey authenticates successfully. Fix will support both explicit layouts without copying unrelated operator configuration, add regression coverage, and keep missing/unsafe artifacts fail-closed.
---
author: oompah
created: 2026-08-13 16:35
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
