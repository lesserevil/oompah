---
id: OOMPAH-888
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
created_at: '2026-08-07T13:06:34.028897Z'
updated_at: '2026-08-07T14:52:46.381372Z'
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
    override_id: override-21a07dbe624e
    project_id: proj-14849f1b
    task_id: OOMPAH-888
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4ebc7558acb7a78e1c2cabab5ffe96c8e7472294866c9b3d3d73eb93078198c9
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Superseded duplicate epic-rebase helper. Canonical OOMPAH-877 published
      exact full-gate-passing head e06bec549; this helper has no remaining independent
      work or authority.
    created_at: '2026-08-07T14:52:14.568874+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-888
    target_state: Archived
    evidence_fingerprint: 4ebc7558acb7a78e1c2cabab5ffe96c8e7472294866c9b3d3d73eb93078198c9
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-07T14:52:25.280269+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Retain superseded duplicate archival after canonical rebase e06bec549;
      do not reopen or redispatch this obsolete generation.
    marked_at: '2026-08-07T14:52:44.764532+00:00'
    updated_at: '2026-08-07T14:52:44.764532+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Retain superseded duplicate archival after canonical rebase e06bec549;
        do not reopen or redispatch this obsolete generation.
      recorded_at: '2026-08-07T14:52:44.764532+00:00'
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
created: 2026-08-07 13:17
---
Direct-owner containment applied before implementation. This is recurrence #8 of the duplicate epic-OOMPAH-763 rebase helper race while canonical OOMPAH-877 already owns and has repaired the same generation. Preserve this task/claim as fenced incident evidence; do not mutate or push the shared branch. OOMPAH-879 owns the systemic authority/idempotency fix.
---
author: oompah
created: 2026-08-07 14:52
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
