---
id: OOMPAH-429
type: bug
status: Archived
priority: 1
title: Clear scheduler completion state when an operator reopens a task
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T22:24:40.832138Z'
updated_at: '2026-08-02T01:48:02.604819Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-9cad6472a0e2: '2026-08-02T01:47:58.442070+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-429
    target_state: Archived
    evidence_fingerprint: b0552c7d4dae66d3e50b047c54bfeebccf34c2876d35154c19bfaaadd6f93736
    audit_ids:
    - audit-011a5e2126cf
    kind: result
    applied: true
    retired_at: '2026-08-02T01:47:58.442077+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-429
    audit_id: audit-011a5e2126cf
    attempt_id: attempt-9cad6472a0e2
    target_state: Archived
    evidence_fingerprint: b0552c7d4dae66d3e50b047c54bfeebccf34c2876d35154c19bfaaadd6f93736
    status: Archived
    audit_ids:
    - audit-011a5e2126cf
    applied: false
    created_at: '2026-08-02T01:47:58.442085+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-011a5e2126cf
    project_id: proj-14849f1b
    task_id: OOMPAH-429
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b0552c7d4dae66d3e50b047c54bfeebccf34c2876d35154c19bfaaadd6f93736
    attempts:
    - version: 1
      attempt_id: attempt-9cad6472a0e2
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b0552c7d4dae66d3e50b047c54bfeebccf34c2876d35154c19bfaaadd6f93736
      created_at: '2026-08-02T01:40:06.044545+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:40:06.044545+00:00'
      branch_key: OOMPAH-429
      verdict: pass
      completed_at: '2026-08-02T01:47:58.441974+00:00'
      ended_at: '2026-08-02T01:47:58.441974+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:55.920904+00:00'
    updated_at: '2026-08-02T01:47:58.441974+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9cad6472a0e2
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b0552c7d4dae66d3e50b047c54bfeebccf34c2876d35154c19bfaaadd6f93736
    created_at: '2026-08-02T01:40:06.044545+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:40:06.044545+00:00'
    branch_key: OOMPAH-429
---
## Summary

When a task moved to Needs Human/Done is manually or watchdog reopened to an active status, remove its identifier from the orchestrator in-memory completed set immediately. EXOCOMP-55 reproduced the bug: it was returned to Open with a valid feature handoff but remained rejected as completed until the periodic watchdog sweep. Update the issue-status API transition path, preserve terminal-state behavior, add regression coverage for reopening a completed task, and verify the reopened task can dispatch on the next scheduler pass. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 22:26
---
Implemented and verified the immediate-reopen fix: reopening a dispatchable task now clears the scheduler's stale completed/claimed entries, so it can be selected on the next tick rather than waiting for the watchdog. Full test suite passed; committing and deploying next.
---
author: oompah
created: 2026-07-23 22:27
---
Fixed and deployed in 3e921ab76. Reopening a dispatchable task now removes stale scheduler completed/claimed entries immediately; full test suite passed. Verified EXOCOMP-55 was requeued and is now In Progress.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: scheduler completion-state clearing on reopen is present on origin/main in commit 3e921ab76. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:29
---
Verified delivered on origin/main in 3e921ab76 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:13
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:40
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:40
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:48
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- fix_commit: 3e921ab766b4d7c098769ca6d5ef3b0474d18635
- fix_commit_title: Clear scheduler completion state on reopen
- fix_file: oompah/server.py
- fix_location: api_update_issue, ~line 10331
- regression_test_file: tests/test_server_epic_state.py
- regression_test_class: TestReopenClearsSchedulerCompletionState
- regression_test_method: test_reopen_removes_completed_and_claimed_entries
- focused_pytest_result: 3 passed in 0.95s (TestReopenClearsSchedulerCompletionState)
- commit_present_on_main: true (git log main -- oompah/server.py includes 3e921ab76)
- current_head: 6252b5434f392b74de9703a9fc8dca1951dfeaca
- previous_state: Merged
- auto_archive_trigger: Aged Merged auto-archive (closed 7 days ago)
---
<!-- COMMENTS:END -->
