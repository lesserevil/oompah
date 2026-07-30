---
id: OOMPAH-625
type: bug
status: Open
priority: 1
title: Release terminal-auditor branch claims on forced termination
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:58:34.567478Z'
updated_at: '2026-07-30T21:59:44.436179Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-625
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d0577e40e55bd24cbfb63151e1b9d35254575d0f5079e9b7f9fdf505c2c5b251
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 63bf577e-3fa3-4046-8786-046af1cb2739
  claim_owner: c1f4a4cb-217d-4c2a-aad6-f768a3cdbb4b
  claimed_at: '2026-07-30T21:59:37.096681+00:00'
  claim_expires_at: '2026-07-30T22:29:37.096681+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: f71d790f-a7a4-40ef-be07-6ffa6a636594
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-625
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-625
  base_branch: epic-OOMPAH-585
  base_sha: ebb5b12d9bd9668458750ec38bee7d7216f186d7
  updated_at: '2026-07-30T21:59:41.934289+00:00'
---
## Summary

Implementation scope: update the orchestrator forced/manual worker termination path so terminating an auditor releases its  ownership exactly when that same runtime entry is removed. Preserve replacement-worker fencing and survivor-process safety; ordinary and duplicate-preflight termination semantics must remain unchanged. Add observability for the released claim if useful. Relevant context: OOMPAH-591's Claude auditor was terminated during a UI terminal-status transition at 20:20,  removed the RunningEntry and ordinary claim but retained  in , causing every later audit tick to skip the fresh pending audit forever. Tests: reproduce a forced auditor termination with a populated branch claim, assert running/claimed/claimed_issues/branch ownership are all released, cover a mismatched replacement claim so an older terminating worker cannot release a newer owner's fence, and run focused auditor/termination tests plus the Makefile gate. Acceptance criteria: forced auditor termination cannot deadlock future audit dispatch; a stale worker cannot clear a replacement auditor's branch claim; all focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:58
---
Confirmed reproducer: Orchestrator._terminate_running removes the RunningEntry and ordinary claimed/claimed_issues ownership but does not remove the matching entry.branch_key from Orchestrator._audit_branch_claims. The leaked key epic-OOMPAH-585--task-OOMPAH-591 has blocked its fresh audit since the forced UI-transition termination. Preserve a newer owner by releasing only when the recorded attempt ID matches the terminating entry.
---
author: oompah
created: 2026-07-30 21:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 21:59
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
