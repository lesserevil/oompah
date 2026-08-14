---
id: OOMPAH-1194
type: bug
status: In Validation
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=TRICKLE-134'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T23:56:09.835377Z'
updated_at: '2026-08-14T07:36:32.683552Z'
work_branch: OOMPAH-1194
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
    audit_id: audit-cad206e88330
    project_id: proj-14849f1b
    task_id: OOMPAH-1194
    digest: 7e7d8e7d0f17344513c3b12b35e933f54eafa6a2c6f652415ddf601bb1cfd7c0
  - version: 1
    audit_id: audit-a71c9fb75593
    project_id: proj-14849f1b
    task_id: OOMPAH-1194
    digest: 7e7d8e7d0f17344513c3b12b35e933f54eafa6a2c6f652415ddf601bb1cfd7c0
  - version: 1
    audit_id: audit-7fe08b784459
    project_id: proj-14849f1b
    task_id: OOMPAH-1194
    digest: cf4bb18a00cbb7a23542aa399caa0f1ebe21ff421c8e410cd9a783f0c045f951
  - version: 1
    audit_id: audit-598b35e5dd5a
    project_id: proj-14849f1b
    task_id: OOMPAH-1194
    digest: cf4bb18a00cbb7a23542aa399caa0f1ebe21ff421c8e410cd9a783f0c045f951
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-cad206e88330
    project_id: proj-14849f1b
    task_id: OOMPAH-1194
    target_state: Done
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7e7d8e7d0f17344513c3b12b35e933f54eafa6a2c6f652415ddf601bb1cfd7c0
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T00:29:04.516767+00:00'
    eligible_at: '2026-08-13T00:29:04.516767+00:00'
    selected_ref: origin/main
    selected_sha: 7140e70827fb1ead3135a559a5202089548a13f6
  - version: 1
    audit_id: audit-a71c9fb75593
    project_id: proj-14849f1b
    task_id: OOMPAH-1194
    target_state: Merged
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7e7d8e7d0f17344513c3b12b35e933f54eafa6a2c6f652415ddf601bb1cfd7c0
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T00:29:04.516767+00:00'
    prerequisite_audit_id: audit-cad206e88330
    selected_ref: origin/main
    selected_sha: 7140e70827fb1ead3135a559a5202089548a13f6
  - version: 1
    audit_id: audit-7fe08b784459
    project_id: proj-14849f1b
    task_id: OOMPAH-1194
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cf4bb18a00cbb7a23542aa399caa0f1ebe21ff421c8e410cd9a783f0c045f951
    attempts: []
    source_generation: 2
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: In Validation
    created_at: '2026-08-14T07:36:19.948209+00:00'
    eligible_at: '2026-08-14T07:36:19.948209+00:00'
    selected_ref: dc5b5998d013228a1409bd05a25b49f40787921a
    selected_sha: dc5b5998d013228a1409bd05a25b49f40787921a
  - version: 1
    audit_id: audit-598b35e5dd5a
    project_id: proj-14849f1b
    task_id: OOMPAH-1194
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cf4bb18a00cbb7a23542aa399caa0f1ebe21ff421c8e410cd9a783f0c045f951
    attempts: []
    source_generation: 2
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: In Validation
    created_at: '2026-08-14T07:36:19.948209+00:00'
    prerequisite_audit_id: audit-7fe08b784459
    selected_ref: dc5b5998d013228a1409bd05a25b49f40787921a
    selected_sha: dc5b5998d013228a1409bd05a25b49f40787921a
  attempt_history: []
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1194
  head_sha: dc5b5998d013228a1409bd05a25b49f40787921a
  submitted_at: '2026-08-13T00:31:33.176428+00:00'
  updated_at: '2026-08-13T00:31:33.176428+00:00'
oompah.work_branch: OOMPAH-1194
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=TRICKLE-134

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=TRICKLE-134

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
- fingerprint: 22e4547d85a51ca3
- dedup_fingerprint: 22e4547d85a51ca3
- source_issue: TRICKLE-134

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 00:02
---
Root cause confirmed during live Trickle dispatch: managed network Git operations pass the symbolic local remote name 'origin', so stale per-repository/worktree SSH configuration overrides the project's configured canonical HTTPS repo_url and its scoped credential environment. Scope: make ProjectStore managed network Git calls bind origin fetch/push to the project repo_url without mutating checkout config or exposing credentials; add a regression using a stale origin that proves the canonical remote is used; verify credential isolation/redaction remains intact. OOMPAH-1195 through OOMPAH-1198 are duplicate task-specific instances of this same systemic fault. Acceptance: workspace/epic refresh succeeds from canonical transport even when local origin is stale, and existing credential tests pass.
---
author: oompah
created: 2026-08-13 00:29
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-13 00:31
---
Fixed managed network Git transport authority: server-owned fetch/push/ls-remote now use the configured project repo URL, ignore stale local origins and ambient rewrites, preserve tracking and cleanup semantics, and cover the exact epic private-dispatch failure path. PR #842 merged; CI passed on Python 3.11, 3.12, and 3.13.
---
author: oompah
created: 2026-08-14 07:36
---
PR #842 merged as 7140e7082 with supported-Python CI passing; the landed tree is contained by origin/main and no implementation remains.
---
<!-- COMMENTS:END -->
