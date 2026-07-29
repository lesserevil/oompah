---
id: OOMPAH-571
type: bug
status: Open
priority: 1
title: Keep active terminal auditors alive in In Validation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:57:40.926693Z'
updated_at: '2026-07-29T23:58:49.371254Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 67690d03e2c474f5851485e0d398ebc37696b6a30e2956c23d75e75144c8ab89
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: a3723b22-2a7a-4dd1-b8ee-a840709b4642
  claim_owner: 7e0ec335-e793-4bc9-8be7-8876913419b0
  claimed_at: '2026-07-29T23:58:45.868975+00:00'
  claim_expires_at: '2026-07-30T00:28:45.868975+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 5235a9b7-bff9-4a7c-aa62-99d633e92ad4
---
## Summary

Triggered by: OOMPAH-476

Implementation scope: fix running-agent reconciliation so an entry marked is_auditor remains active while its tracker task is In Validation. Continue terminating auditors if the task leaves In Validation or reaches a configured terminal state, and preserve existing behavior for ordinary implementation, duplicate-screening, and epic-repair workers. Relevant code: Orchestrator._reconcile in oompah/orchestrator.py. Tests: reproduce the live failure where the auditor is dispatched and the next reconciliation tick logs 'no longer in_progress' and terminates it; assert an In Validation auditor's snapshot is refreshed without termination, and assert an ordinary worker in In Validation still terminates. Acceptance criteria: completion auditors can reach submit_audit_result, OOMPAH-478/OOMPAH-482 leave In Validation after audit, focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 23:57
---
Taking this direct-main deadlock fix now while the integration queue continues its current gate.
---
author: oompah
created: 2026-07-29 23:58
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 23:58
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
