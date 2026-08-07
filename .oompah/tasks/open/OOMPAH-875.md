---
id: OOMPAH-875
type: task
status: Open
priority: null
title: Prevent slow scheduler lanes from starving Ready integration claims
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T08:44:33.807355Z'
updated_at: '2026-08-07T08:48:06.838605Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-875
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e89e104efd8da99c68e706e9e416c2db51b30f62fd17f04c8dab8f82c683df24
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 786cfd67-0dd4-4928-8297-274f1cfe197f
  claim_owner: 0c3fdd32-3af4-41c2-89eb-bba40d25c9aa
  claimed_at: '2026-08-07T08:47:28.493002+00:00'
  claim_expires_at: '2026-08-07T09:17:28.493002+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: eb3c671b-557d-472d-b96f-f9101577659e
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-875
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-875
  base_branch: epic-OOMPAH-768
  base_sha: 6a84d9bcc2ca1e3e825883d298793e04bd9c43a8
  updated_at: '2026-08-07T08:48:00.632247+00:00'
---
## Summary

Live cutover regression on 2026-08-07: OOMPAH-865 was durably Ready at 08:33:01 with an idle validation broker, but no integration claim began until 08:41:29. The first post-cutover scheduler tick took 366 seconds, including 320 seconds in dispatch and 175 seconds in terminal-audit scanning/launch. _process_integration_queues is only scheduled after reconcile, review, dispatch, YOLO, and watchdog, so eligible exact-head delivery is starved behind unrelated slow lanes despite available validation capacity.

Implementation scope:
- Give durable shared-epic integration reconciliation its own promptly woken lane or schedule it before unrelated unbounded dispatch/audit work.
- Preserve one active integration pass, exact-head CAS authority, dependency ordering, project isolation, and the single validation-resource lease.
- Make submit/refresh/cutover events wake the integration lane without duplicate claims.
- Publish bounded latency/progress telemetry and an actionable alert only when an eligible row exceeds the configured claim bound.
- Keep terminal-audit, normal dispatch, and maintenance work from monopolizing integration progress.

Relevant code: oompah/orchestrator.py _tick and _process_integration_queues, event/refresh coalescing, integration_queue.py claiming, and state telemetry.

Required tests:
- A synthetic multi-minute dispatch/audit lane cannot delay an eligible Ready integration claim beyond the configured bound.
- Restart/cutover with a pre-existing Ready row starts exactly one integration pass.
- Concurrent submit/refresh events coalesce and never double-claim.
- Dependency-blocked rows remain blocked while an independent eligible row claims.
- Validation broker capacity and exact authority generation remain unchanged.

Acceptance criteria: a Ready integration row with satisfied dependencies and available validation capacity is claimed within a bounded interval independent of dispatch/audit duration; state exposes the last integration run/claim latency; no duplicate gate or lost wakeup occurs; focused scheduler/integration/event-loop tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 08:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 08:48
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
