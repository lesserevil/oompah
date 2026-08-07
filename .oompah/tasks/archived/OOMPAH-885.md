---
id: OOMPAH-885
type: task
status: Archived
priority: 0
title: Rebase epic-OOMPAH-763 onto main
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T12:41:29.315884Z'
updated_at: '2026-08-07T14:52:03.281833Z'
work_branch: null
target_branch: main
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.target_branch: main
oompah.epic_rebase_target:
  version: 1
  epic_identifier: OOMPAH-763
  epic_branch: epic-OOMPAH-763
  target_branch: main
  parent_id: null
  resolution: confirmed_top_level
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-71e71916367c
    project_id: proj-14849f1b
    task_id: OOMPAH-885
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: be7b8c4ece24ad981ade3661410cb6159cac75b837a5864ec4b8bf7f42d94505
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Superseded duplicate epic-rebase helper. Canonical OOMPAH-877 published
      exact full-gate-passing head e06bec549; this helper has no remaining independent
      work or authority.
    created_at: '2026-08-07T14:51:42.902921+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-885
    target_state: Archived
    evidence_fingerprint: be7b8c4ece24ad981ade3661410cb6159cac75b837a5864ec4b8bf7f42d94505
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-07T14:51:54.259396+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

The epic branch `epic-OOMPAH-763` is stale: it has fallen behind `main`. Rebase the branch onto `origin/main`, resolve any conflicts, and force-push with `git push --force-with-lease`.

This task was auto-filed because epic OOMPAH-763 was detected as stale. Do NOT create a new branch or PR — work directly on `epic-OOMPAH-763`.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 12:43
---
Operator containment: direct-owner fenced immediately on discovery; no provider work or shared-worktree mutation is authorized. This is recurrence #7 of OOMPAH-879 and must remain fenced until that fix is deployed.
---
author: oompah
created: 2026-08-07 14:51
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded duplicate epic-rebase helper. Canonical OOMPAH-877 published exact full-gate-passing head e06bec549; this helper has no remaining independent work or authority.
---
author: oompah
created: 2026-08-07 14:52
---
Archived as a superseded duplicate of completed OOMPAH-877.
---
<!-- COMMENTS:END -->
