---
id: OOMPAH-1171
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-131:
  All 2 dispatch candidates unavailable: prov-651d553c/haiku: contributor_evidence_unavailable:
  Cannot durably record exac...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-12T15:48:09.597086Z'
updated_at: '2026-08-12T20:09:56.709614Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-8d637744795f
    project_id: proj-14849f1b
    task_id: OOMPAH-1171
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 78a25a06d723ce91e54722b26c5460741b3232323ec25f5f091e681cdee1bebe
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Historical auto-filed occurrence from the state-branch and dispatch-convergence
      incident, consolidated into completed roots OOMPAH-1127, OOMPAH-1128, and OOMPAH-1177.
      PRs #836 and #837 delivered the durable transport, stable incident identity,
      and fail-closed provider-admission repairs with full CI. This occurrence requires
      no independent implementation.'
    created_at: '2026-08-12T20:09:49.497046+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-131: All 2 dispatch candidates unavailable: prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-131: All 2 dispatch candidates unavailable: prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.

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
- fingerprint: c842ad671da83116
- dedup_fingerprint: c842ad671da83116

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

