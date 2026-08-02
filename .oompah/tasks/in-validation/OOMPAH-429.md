---
id: OOMPAH-429
type: bug
status: In Validation
priority: 1
title: Clear scheduler completion state when an operator reopens a task
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T22:24:40.832138Z'
updated_at: '2026-08-02T01:40:07.008096Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-011a5e2126cf
    project_id: proj-14849f1b
    task_id: OOMPAH-429
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b0552c7d4dae66d3e50b047c54bfeebccf34c2876d35154c19bfaaadd6f93736
    attempts:
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
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:55.920904+00:00'
    updated_at: '2026-08-02T01:40:06.044545+00:00'
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
<!-- COMMENTS:END -->
