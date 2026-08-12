---
id: OOMPAH-1149
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-121:
  All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable:
  Cannot durably record exa...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-12T15:23:31.745991Z'
updated_at: '2026-08-12T20:17:26.970715Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-82f5802e992a
    project_id: proj-14849f1b
    task_id: OOMPAH-1149
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a47d7a186ab9526f8c0d61025cb1b6c8198e3814f37ed0ca87f27dc230b8059a
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Historical auto-filed occurrence from the state-branch and dispatch-convergence
      incident, consolidated into completed roots OOMPAH-1127, OOMPAH-1128, and OOMPAH-1177.
      PRs #836 and #837 delivered durable transport fencing, stable incident identity,
      and fail-closed provider admission with passing full CI; this occurrence requires
      no independent implementation.'
    created_at: '2026-08-12T20:17:20.884020+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-121: All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-terra: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-121: All 2 dispatch candidates unavailable: prov-651d553c/sonnet: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before the bounded task-authority deadline. The pre-provider runtime was retired for retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-terra: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.

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
- fingerprint: 52bc5c65776b99bc
- dedup_fingerprint: 52bc5c65776b99bc

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

