---
id: OOMPAH-1013
type: task
status: Backlog
priority: null
title: Prevent cross-priority starvation in bounded terminal-audit health scans
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T03:11:11.351608Z'
updated_at: '2026-08-11T03:11:11.351608Z'
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
  creation_marker: 1811b247-76cb-42e8-a581-6332fedb32d7
  request_fingerprint: a83e0074173ca57ca5cdc39b2a729c1c44644e24bed7a062c8e971c58bde77a3
---
## Summary

Triggered by: live OOMPAH-940 rollout diagnostics and the planned ~100-task dispatch load. Problem: Orchestrator._audit_candidate_window globally orders terminal-audit health candidates by priority, but cursor rotation is confined to the cursor priority group before the operation limit is applied. When higher-priority candidates fill the entire operation budget, lower-priority candidates can remain permanently outside every bounded slice, so candidate_scan_complete never becomes true and rollout health can remain degraded indefinitely despite continuation ticks. A read-only reproduction with eight priority-1 candidates, one priority-0 candidate, and operation limit 8 scanned HIGH-0..HIGH-7 for four consecutive cycles and never selected LOW-0. Scope: make bounded terminal-audit health traversal fair across priority groups while preserving priority ordering for actual auditor dispatch, deterministic cursor/restart behavior, candidate-key-set resets, continuation coalescing, and the operation/time budgets. Relevant code: Orchestrator._audit_candidate_window and bounded health scan accounting in oompah/orchestrator.py; observability regressions in tests/test_terminal_audit_observability.py. Required tests: mixed-priority corpus where the high-priority group fills the cap still selects every lower-priority candidate within a bounded number of slices; cursor persistence/restart continues rather than resets; candidate additions/removals reset safely; actual auditor dispatch priority is unchanged; no scan-error/action-required alert is emitted for ordinary continuation. Acceptance: a stable mixed-priority corpus completes a health cycle under an operation limit smaller than the high-priority group, with exact bounded work per slice and no lower-priority starvation; focused tests, the final combined Makefile gate, and live rollout canary pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

