---
id: OOMPAH-1156
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=TRICKLE-118'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-12T15:36:08.719137Z'
updated_at: '2026-08-12T20:19:17.880460Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-975dc9d80203
    project_id: proj-14849f1b
    task_id: OOMPAH-1156
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: caf1264033965f3544aa7d7b6b0837dd563e30f0e5b5c9cadaf998395a295f03
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Historical auto-filed occurrence from the state-branch and dispatch-convergence
      incident, consolidated into completed roots OOMPAH-1127, OOMPAH-1128, and OOMPAH-1177.
      PRs #836 and #837 delivered durable transport fencing, stable incident identity,
      and fail-closed provider admission with passing full CI; this occurrence requires
      no independent implementation.'
    created_at: '2026-08-12T20:19:02.196550+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1156
    target_state: Archived
    evidence_fingerprint: caf1264033965f3544aa7d7b6b0837dd563e30f0e5b5c9cadaf998395a295f03
    workflow_revision: null
    selected_ref: null
    selected_sha: null
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-12T20:19:16.230091+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=TRICKLE-118

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=TRICKLE-118

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: dae6798cb24a91d0
- dedup_fingerprint: dae6798cb24a91d0
- source_issue: TRICKLE-118

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 20:19
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Historical auto-filed occurrence from the state-branch and dispatch-convergence incident, consolidated into completed roots OOMPAH-1127, OOMPAH-1128, and OOMPAH-1177. PRs #836 and #837 delivered durable transport fencing, stable incident identity, and fail-closed provider admission with passing full CI; this occurrence requires no independent implementation.
---
<!-- COMMENTS:END -->
