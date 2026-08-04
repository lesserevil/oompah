---
id: OOMPAH-749
type: bug
status: Open
priority: 1
title: Bound historical audit replay so Ready integration claims cannot starve
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:41:30.892995Z'
updated_at: '2026-08-04T00:43:01.987226Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4698d2271ba63ef638c73fc19cc3cefef395888bec37a945df02b8759054e000
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4b9ef48b-ae3a-4abf-9c0a-30fff07fb2b8
  claim_owner: b6e50576-eec3-4dce-bc89-fe685f70768e
  claimed_at: '2026-08-04T00:42:49.067423+00:00'
  claim_expires_at: '2026-08-04T01:12:49.067423+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5de4717e-9dce-4cd0-8855-b1f21288ac60
---
## Summary

Live reproduction on 2026-08-04: the integration ledger contains 37 Ready submissions across Oompah, Exocomp, and Nodevirt, with the oldest submitted 2026-08-01. Every row still has attempts=0, no lease owner, and no last error after repeated healthy ticks and a service restart. The integration driver scans and stages audits for the entire historical integrated set before it groups and claims live Ready rows, so growing history can indefinitely postpone forward work while the main orchestrator remains healthy. Implementation scope: make historical integrated-audit recovery incremental and bounded by a durable cursor or batch budget; claim or fairly interleave live Ready work before replaying unbounded history; preserve idempotent audit staging, lease recovery, per-epic serialization, dependencies, and cross-project fairness; expose progress and a degraded signal when Ready rows receive no claim within the expected interval. Relevant code includes _process_integration_queues, integrated terminal-audit staging, IntegrationQueue ledger scans, scheduling futures, and state metrics. Required tests: hundreds of historical integrated rows plus a live Ready row claimed within one driver interval; bounded replay across restarts; fair progress across projects and epic groups; dependency-blocked rows skipped without blocking eligible groups; no duplicate audits or lost lease recovery. Acceptance criteria: queue latency is bounded independently of historical ledger size, existing 37 Ready rows begin receiving leases naturally, and stalled claim progress becomes observable rather than silently healthy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 00:43
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 00:43
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
