---
id: OOMPAH-641
type: task
status: Open
priority: null
title: Finish shared-epic pre-PR and reconciliation hardening from OOMPAH-428
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T05:59:48.550048Z'
updated_at: '2026-07-31T06:07:15.876125Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 185422e4b0e806f107adfa94370a37c1fab993031e705aca37b3ace64ccd6271
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 322b32eb-b03d-4e04-b91d-92b60633da0f
  claim_owner: d12922aa-baf6-4258-aa45-02da3deea710
  claimed_at: '2026-07-31T06:07:09.605001+00:00'
  claim_expires_at: '2026-07-31T06:37:09.605001+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 1aaa1857-82ca-4ddd-b588-deb35e2e9def
---
## Summary

Follow-up to incomplete OOMPAH-428 after parent epic OOMPAH-426 and PR #544 merged. Implement the remaining defense-in-depth for shared-epic children. Scope: ensure _ensure_review_exists blocks per-child PR creation even when work_branch is stale to the child identifier; fail closed when parent_id is absent in a partial issue but a parent epic is authoritatively resolvable; verify _create_workspace_for_issue always corrects the in-memory work/branch identity before routing even if metadata persistence fails; and ensure independently merged reconciliation detects a child whose own stale work_branch bypassed its epic. Relevant files: oompah/orchestrator.py, tests/test_epic_strategy.py, and independently-merged reconciliation tests. Required regressions: stale own work_branch with parent_id; missing parent_id but resolvable parent; persistence failure still corrects memory; EXOCOMP-57-style independently merged child detection. Acceptance: no child-to-main PR can be created through these pre-merge edge cases, the invalid merged-child path is actionable, focused epic strategy tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:07
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
