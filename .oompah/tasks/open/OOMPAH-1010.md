---
id: OOMPAH-1010
type: bug
status: Open
priority: 1
title: Do not stage shared-epic children for invalid Merged audits
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T01:48:19.145541Z'
updated_at: '2026-08-11T02:15:45.413779Z'
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
  creation_marker: oompah-1007-shared-child-merged-staging
  request_fingerprint: 52ea41240b5c2fed7d8b1b7fbf99afb2a6a75ad0b9449b1e9acc47eaa65775ee
---
## Summary

Triggered by: OOMPAH-1007

Live reproduction after PR #805 merged OOMPAH-1007 directly to main: the forge webhook commented 'Queued for terminal transition to Merged' and moved the shared-epic child into In Validation. Its first exact audit correctly passed the topology-valid Done stage, then a second Merged-stage auditor was launched; the callback was fenced stale, and an owner Merged override was rejected because parent epic OOMPAH-940 has not landed. This creates unnecessary auditor work and contributed tracker churn to OOMPAH-1009. Scope: when protected delivery lands a shared-epic child while its parent epic remains nonterminal, resolve and stage the topology-valid child terminal target (Done) instead of blindly staging Merged from the PR target. Preserve true standalone/root task Merged handling, nested epic topology, direct-main delivery evidence, webhook idempotency, Done-to-Merged ordering when the parent later lands, and exact terminal audit authority. Relevant code: merged pull-request webhook staging, review/workflow terminal target resolution, TaskTransitionService topology guard, and terminal coordinator chain construction. Required tests: merged PR for a shared child with nonterminal parent stages one Done audit and no Merged audit; parent landing later permits normal rollup; root/standalone tasks still stage Merged; nested parent ambiguity fails closed; duplicate webhook delivery is idempotent. Acceptance: OOMPAH-1007-like delivery reaches Done after one audit with no invalid Merged callback or owner workaround, while OOMPAH-940 remains the sole parent responsible for final Merged topology.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

