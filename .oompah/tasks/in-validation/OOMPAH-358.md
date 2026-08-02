---
id: OOMPAH-358
type: task
status: In Validation
priority: 1
title: Gate epic rebase scheduling on actionable conditions
parent: OOMPAH-356
children: []
blocked_by:
- OOMPAH-357
labels: []
assignee: null
created_at: '2026-07-22T01:23:51.390755Z'
updated_at: '2026-08-02T01:12:59.446655Z'
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
    audit_id: audit-09c5d6e686c7
    project_id: proj-14849f1b
    task_id: OOMPAH-358
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a95209a2e5e84d25e663b6c89792d61d9093b88b02f7b73fe663bca15169800e
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:55.913861+00:00'
  attempt_history: []
---
## Summary

Update the epic maintenance and rebase-dispatch flow to consume the synchronization policy. Preserve staleness detection, but make it observational by default. Do not create an agent task, worktree operation, merge, or rebase unless the policy returns an allowed actionable reason.\n\nImplementation scope:\n- Remove automatic rebase scheduling triggered only by commit-count/file-overlap staleness.\n- Retain configured threshold detection as an alert/signal.\n- Carry the actionable reason into logs, task comments, and rebase state.\n- Ensure PR-preparation and explicit operator paths can request an allowed synchronization.\n\nTests:\n- Integration-style tests proving stale incomplete epics cause no branch mutation or agent dispatch.\n- Tests proving PR preparation, explicit requests, and merge-blocking conflicts still schedule exactly one rebase.\n- Verify repeated ticks coalesce rather than repeatedly scheduling the same permitted rebase.\n\nAcceptance criteria:\n- Main advancing alone cannot generate a rebase agent for an unfinished epic.\n- Existing permitted rebase workflows remain functional and auditable.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:30
---
Removed periodic proactive rebase scheduling; staleness detection no longer creates branch-mutating work.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: removal of periodic proactive rebase scheduling is present on origin/main in commit 2ba37886b. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:27
---
Verified delivered on origin/main in 2ba37886b and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:12
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
