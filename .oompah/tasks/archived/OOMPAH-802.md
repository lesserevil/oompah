---
id: OOMPAH-802
type: task
status: Archived
priority: 1
title: Route orchestrator lifecycle writes through TaskTransitionService
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T14:00:59.248935Z'
updated_at: '2026-08-04T14:02:53.037545Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-49fc3c991aed
    project_id: proj-14849f1b
    task_id: OOMPAH-802
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7129bb2225a2fbc5a02e199e3b656e4564ce2a21a6c19494f8c18bc30cae9b08
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Accidental duplicate created while verifying concurrently submitted task-creation
      requests; canonical task is OOMPAH-778.
    created_at: '2026-08-04T14:02:50.724270+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Migrate all orchestrator.py status writes across dispatch, worker exit, retry, integration, review, epic rollup, duplicate screening, watchdog, CI/rebase, and maintenance. Preserve reason, authority, exact-head generation, and recovery semantics. Add family-focused race/restart tests. Acceptance: orchestrator has no direct task-status update_issue calls and stale outcomes cannot mutate newer work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

