---
id: OOMPAH-898
type: task
status: Archived
priority: 0
title: Rebase epic-OOMPAH-763 onto main
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-07T14:17:57.854034Z'
updated_at: '2026-08-07T14:57:09.576650Z'
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
    override_id: override-e41d228aeec0
    project_id: proj-14849f1b
    task_id: OOMPAH-898
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fff3cca55deed5cbf5ef48d60a26b3806b2dd3bf147b6ef191206671e4ae09b8
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Superseded duplicate epic-rebase helper. Canonical OOMPAH-877 published
      exact full-gate-passing head e06bec549; this helper has no remaining independent
      work or authority.
    created_at: '2026-08-07T14:56:35.851562+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-898
    target_state: Archived
    evidence_fingerprint: fff3cca55deed5cbf5ef48d60a26b3806b2dd3bf147b6ef191206671e4ae09b8
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-07T14:56:47.944443+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Retain superseded duplicate archival after canonical rebase e06bec549;
      do not reopen or redispatch this obsolete generation.
    marked_at: '2026-08-07T14:57:05.023118+00:00'
    updated_at: '2026-08-07T14:57:05.023118+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Retain superseded duplicate archival after canonical rebase e06bec549;
        do not reopen or redispatch this obsolete generation.
      recorded_at: '2026-08-07T14:57:05.023118+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
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
created: 2026-08-07 14:27
---
Fenced as recurrence 13 of the duplicate epic-rebase authority bug. The project is paused and a direct-owner claim prevents dispatch. Canonical recovery remains OOMPAH-877 against the protected local head; remote epic-OOMPAH-763 remains ca1c527. Do not launch or mutate the shared epic worktree. Permanent repair is tracked by OOMPAH-879 with OOMPAH-891 and OOMPAH-892.
---
author: oompah
created: 2026-08-07 14:56
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Superseded duplicate epic-rebase helper. Canonical OOMPAH-877 published exact full-gate-passing head e06bec549; this helper has no remaining independent work or authority.
---
author: oompah
created: 2026-08-07 14:57
---
Archived as a superseded duplicate of completed OOMPAH-877.
---
<!-- COMMENTS:END -->
