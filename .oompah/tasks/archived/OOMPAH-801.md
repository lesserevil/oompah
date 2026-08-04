---
id: OOMPAH-801
type: feature
status: Archived
priority: 1
title: Implement TransitionIntent, transition journal, and TaskTransitionService
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T14:00:53.127556Z'
updated_at: '2026-08-04T14:02:38.357063Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-ffd3e3130c18
    project_id: proj-14849f1b
    task_id: OOMPAH-801
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a290ea9eb5f0db2c4717a9538c995039326e68ea5fc96e247fc26ca662bee4ce
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Accidental duplicate created while verifying concurrently submitted task-creation
      requests; canonical task is OOMPAH-776.
    created_at: '2026-08-04T14:02:33.986411+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Create project-scoped TransitionIntent/Outcome, append-only journal, compare-and-swap preconditions, idempotency, apply/verify, and terminal coordinator adaptation. Include expected status/version/head, actor, reason, and originating job. Test concurrent conflicts, replay, stale generation, project/actor isolation, tracker failure before/after effects, terminal staging, and restart. Acceptance: service safely supports every transition class before call-site migration.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

