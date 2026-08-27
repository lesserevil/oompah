---
id: OOMPAH-1341
type: bug
status: Open
priority: null
title: Run stalled-task watchdog in durable mode and reclaim obsolete review capacity
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-26T16:14:26.107948Z'
updated_at: '2026-08-27T16:25:42.592909Z'
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
  creation_marker: 53c97af1-a34d-48a0-bba1-6f39470e2c09
  request_fingerprint: 7c75150ecd7ebbe7b82e77a19511afdc4a2f600598f07a13249a897ff135bd5c
oompah.lifecycle_revision: 1
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7ef7b1fa56bec0f89af30e31d094f81565c59eb1844a6b48c19bf7b102854f65
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 384bd1036ee19b49930e7a259d2686cc73b337b8937b3c462daa97996ab215de:172607
  claim_owner: 86968e48-2056-49f5-aa87-3bb12ce6409f
  claimed_at: '2026-08-27T16:25:32.695325+00:00'
  claim_expires_at: '2026-08-27T16:55:32.695325+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 317814d1-69f0-413c-b091-6662292d7c4f
---
## Summary

### Problem
The configured stalled-task watchdog never runs in production when WorkflowRuntime is installed: `_tick()` returns through `_run_durable_workflow_tick`, whose `_run_non_lifecycle_housekeeping` intentionally omits `_maybe_run_stalled_task_watchdog`. Therefore the 10-minute setting is inert and no `stalled_task_watchdog` maintenance result/log exists. Separately, stale conflicting open reviews remain on the forge and consume all review capacity (8/8), even when their patch is already represented on main or the owning task/review generation is obsolete.

### Scope
1. Schedule the existing stalled-task watchdog from the durable workflow tick through a serialized maintenance lane that retains TaskTransitionService authority and does not race workflow publication. Preserve the single-writer lifecycle contract; do not silently reintroduce legacy lifecycle sweeps.
2. Add a separate non-task-lifecycle stale-review cleanup maintenance job at the same configurable interval. It must use a fresh authoritative open-review listing and exact review detail/head/target facts. Close a review only when safely proven obsolete: exact reviewed head already contained in target; or all review commits are patch-equivalent to target (`git cherry` has no `+` commits); or exact task/review generation is superseded by a newer current review. Never close on title similarity, branch advancement alone, provider errors, missing head/target, cross-repository source, active durable review work, or stranded unique commits.
3. After successful close, release only the exact review-capacity reservation and reconcile capacity from a fresh successful listing. Close failure must preserve capacity.
4. Expose watchdog and stale-review-cleanup run state/results in the public maintenance snapshot and log unexpected maintenance-future failures promptly.

### Tests
- Durable runtime tick schedules watchdog remediation at configured interval and records public maintenance telemetry.
- Watchdog remains coalesced/interval-gated and uses authoritative transition service.
- Fresh provider listing failure closes nothing.
- Exact target-contained and patch-equivalent conflicted reviews close and release exact capacity.
- Unique commits, wrong target, missing head, ambiguous task mapping, active review work, and close failure fail closed.
- Public maintenance snapshot exposes both jobs/results.

### Acceptance Criteria
- Production server records a completed stalled_task_watchdog run every configured 600 seconds.
- Stalled tasks with decisive machine evidence are repaired automatically.
- Obsolete open reviews no longer leak review capacity; live unique reviews remain untouched.
- Dashboard review capacity reflects forge truth after cleanup.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-26 16:16
---
Direct owner: I am implementing this watchdog/review-capacity fix now and will carry it through tests, PR merge, deployment, and live verification. No separate agent dispatch is required.
---
author: oompah
created: 2026-08-27 16:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-27 16:09
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 14s
---
<!-- COMMENTS:END -->
