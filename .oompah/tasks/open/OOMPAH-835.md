---
id: OOMPAH-835
type: task
status: Open
priority: 1
title: Bind review and CI actions to fresh project-scoped workflow handlers
parent: OOMPAH-804
children: []
blocked_by:
- OOMPAH-781
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:33.085889Z'
updated_at: '2026-08-06T00:02:23.428339Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 22cf4c368761061373a8189b48d42124efc777fc8f7db0248c5530fde45b0728
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 7545c45a-0134-47cd-a6f0-040da3de013b
  claim_owner: f7278be4-f84b-419e-8352-94d46afbf29e
  claimed_at: '2026-08-06T00:02:20.626630+00:00'
  claim_expires_at: '2026-08-06T00:32:20.626630+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Implement production ReviewWorkflow backends for all ten actions: monitor, refresh, landing refresh, CI repair, conflict repair, terminal stage, closed repair, head reconciliation, merge, and capacity recheck. Provide a fresh provider-backed review fact source before enforce reconciliation (the current _reviews_cache is stale because runtime runs before legacy review refresh), extract exact task/review bodies from legacy project sweeps, and emit TaskTransitionService intents instead of direct tracker status writes. Keep forge mutations, review metadata, landing evidence, and capacity receipts fenced to exact project/task/review/head generations. Relevant files: oompah/review_workflow.py, oompah/workflow_runtime.py or a typed adapter module, orchestrator review refresh/reconciliation and forge helpers. Required tests: provider unavailable vs empty results, webhook/event ordering, CI/conflict/closed/head changes, merge idempotency, capacity release, restart after effect before verify, multi-project routing, and shadow zero-write/enforce single-writer behavior. Acceptance: every review action has truthful fresh evidence and a real handler; no task job invokes a whole-project sweep; UI reasons and executor decisions share the same durable receipt/transition.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 00:01
---
All prerequisite domain adapters are now available in prepared branches and the project has resumed. Promoting the review and CI production adapter so the oompah server can implement it in parallel while OOMPAH-791 and OOMPAH-796 advance through their parent rebases.
---
<!-- COMMENTS:END -->
