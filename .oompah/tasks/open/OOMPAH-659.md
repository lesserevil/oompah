---
id: OOMPAH-659
type: task
status: Open
priority: null
title: Defer standalone full gates until finish dependencies are satisfied
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-657
labels: []
assignee: null
created_at: '2026-07-31T12:15:02.565914Z'
updated_at: '2026-07-31T13:01:44.171431Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 903f68bf1e5410244cf5b06395503984aed024890c87202e33be151b4e57ccf2
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: dd73564d-4b6b-49a1-8aa5-b1d0ed7ccb7d
  claim_owner: b69cac5c-f04f-4fcf-915d-a91676c7ce36
  claimed_at: '2026-07-31T13:01:37.058755+00:00'
  claim_expires_at: '2026-07-31T13:31:37.058755+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: e8f87de9-d36c-433e-ab24-b121b12442d3
---
## Summary

Triggered by: OOMPAH-658\n\nLive production reproduction on 2026-07-31: standalone task OOMPAH-658 has a normal finish-order dependency on OOMPAH-657, but each worker submission immediately starts the configured repository-wide quality gate. When the premature gate is operator-terminated, the task moves to Needs CI Fix, the stalled-task watchdog reopens it, another worker resubmits the unchanged head, and the loop repeats. Epic integration queues already wait for effective finish dependencies; standalone Ready-to-Integrate delivery does not.\n\nImplementation scope: before any standalone branch quality gate or review creation, compute the task's effective finish-order dependencies (including inherited parent constraints) using the same canonical dependency/status/audit-satisfaction semantics as ordered integration. If any dependency is unfinished, leave the exact submitted task/head durably in Ready to Integrate, do not run the gate, do not create a review, do not route to Needs CI Fix, and expose one idempotent non-actionable waiting reason that clears when dependencies become satisfied or the task/head changes. On dependency completion, restart, or explicit refresh, resume exactly once from the same submitted head through the normal immutable gate/review flow. Hard-start dependencies must continue to govern implementation dispatch separately.\n\nRelevant code: oompah/orchestrator.py standalone Ready-to-Integrate reconciliation and review-quality-gate entry points, dependency indexing/effective_dependencies helpers, delivery alerts/state surfaces, and tests/test_standalone_ready_to_integrate.py. Required deterministic tests: unfinished normal dependency causes zero gate/review calls across repeated ticks and restart; terminal-audit-satisfied dependency releases exactly one gate; inherited dependency behaves identically; dependency regression or head/status change cancels stale authority; project/task isolation; no Needs CI Fix/watchdog churn. Acceptance: standalone work may implement in parallel but can never consume its one full gate or create a review before every finish-order dependency is satisfied, and focused scheduler tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 12:15
---
Hard-start ordered after OOMPAH-657 because both tasks change standalone gate authority/cancellation code; implementation before that integration would create a conflict and test against obsolete lifecycle semantics.
---
author: oompah
created: 2026-07-31 13:01
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-31 13:01
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
