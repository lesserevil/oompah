---
id: OOMPAH-1257
type: task
status: Backlog
priority: null
title: Recognize noncanonical epic rebase helpers after terminal audit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T18:57:41.903878Z'
updated_at: '2026-08-13T18:57:41.903878Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: d2d82af2-71ba-4073-8f80-0b564b096e86
  request_fingerprint: c1f4d6c1fe9df59e7d2246ebc306b734d3afe6f68b28501495e6d3f247715124
---
## Summary

Bug exposed live after OOMPAH-1255 allowed TRICKLE-141 to publish the persisted noncanonical TRICKLE-130 epic branch. The helper published candidate b4add27840872ec39ea08bcb4c68895a4ff978db and passed independent audit to Done, but integration.py:is_direct_epic_maintenance_issue still classifies only titles containing the convention-derived epic-<parent> name. Because TRICKLE-141 is titled "Rebase TRICKLE-130 onto epic-TRICKLE-127", downstream integration/rollup no longer recognizes it as direct epic maintenance, emits evidence.landing_missing, exhausts refresh retries, and leaves the parent rebase state/epic:rebasing label uncleared even though guarded publication is proven. Scope: replace convention-only downstream classification with explicit, project-scoped authoritative helper evidence (including persisted noncanonical epic branch) while retaining fail-closed rejection for ordinary title-shaped tasks and conflicting scope; ensure a successfully published/audited helper reaches the maintenance completion path instead of generic source-to-target landing. Relevant files: oompah/integration.py, integration/work-decision fact projection and epic rebase reconciliation paths. Tests must reproduce a noncanonical helper through publish -> audit Done -> parent rebase-state convergence, retain canonical helper compatibility, and reject spoofed/conflicting metadata. Acceptance: TRICKLE-141-like helpers do not emit evidence.landing_missing/retry.exhausted after audit; the parent exits rebasing based on exact guarded publication evidence; no direct Git push or manual task-ledger edit is required.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

