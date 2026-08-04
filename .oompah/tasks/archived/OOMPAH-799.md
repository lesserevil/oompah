---
id: OOMPAH-799
type: task
status: Archived
priority: 1
title: Build replayable fixtures for historical stuck-task incidents
parent: OOMPAH-764
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T14:00:44.163423Z'
updated_at: '2026-08-04T14:02:08.962834Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-1f5c385e811b
    project_id: proj-14849f1b
    task_id: OOMPAH-799
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 155afbcb9595ba1b4e62a56cafd2780690df8df929a461e60f11e98ae60a3fff
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Accidental duplicate created while verifying concurrently submitted task-creation
      requests; canonical task is OOMPAH-774.
    created_at: '2026-08-04T14:01:55.416964+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-799
    target_state: Archived
    evidence_fingerprint: 155afbcb9595ba1b4e62a56cafd2780690df8df929a461e60f11e98ae60a3fff
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-04T14:02:03.168142+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Convert OOMPAH-562/731/732/739/748/749/751 into deterministic scenario fixtures covering mixed queue rows, self-invalidating epic maintenance, benign metadata authority churn, deleted branches, nested target cycles, audit-history starvation, and peer-denial poisoning. Use native Markdown tracker and temporary Git where feasible. Tests must assert historical failure conditions and reusable expected facts/decisions. Acceptance: every incident replays deterministically and is reusable by evaluator, job, liveness, and full-stack suites.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 14:02
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Accidental duplicate created while verifying concurrently submitted task-creation requests; canonical task is OOMPAH-774.
---
author: oompah
created: 2026-08-04 14:02
---
Archived accidental duplicate; use OOMPAH-774.
---
<!-- COMMENTS:END -->
