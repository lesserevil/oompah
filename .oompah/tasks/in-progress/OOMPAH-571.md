---
id: OOMPAH-571
type: bug
status: In Progress
priority: 1
title: Keep active terminal auditors alive in In Validation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:57:40.926693Z'
updated_at: '2026-07-29T23:57:48.843633Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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
<!-- COMMENTS:END -->
