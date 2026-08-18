---
id: OOMPAH-1203
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-131:
  All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable:
  Cannot durably reco...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T01:19:28.760792Z'
updated_at: '2026-08-18T16:18:18.970327Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-41327bd44d2248989351b0a98c84746f
  actor: shedwards
  committed_at: '2026-08-18T16:18:18.970327Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-131: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-131: All 2 dispatch candidates unavailable: prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.; prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.

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
- fingerprint: 7177dadeaf0eac51
- dedup_fingerprint: 7177dadeaf0eac51

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

