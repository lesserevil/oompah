---
id: OOMPAH-1146
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] All dispatch candidates failed for issue TRICKLE-135:
  All 2 dispatch candidates unavailable: prov-651d553c/haiku: contributor_evidence_unavailable:
  Cannot durably record exac...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-12T15:20:40.043668Z'
updated_at: '2026-08-12T20:07:18.293254Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-792d261e1988
    project_id: proj-14849f1b
    task_id: OOMPAH-1146
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7199e66b20043cce51d15d82f669a495754ca4b4dd55c1222ef74850c6bd9138
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Historical auto-filed occurrence from the state-branch and dispatch-convergence
      incident, consolidated into completed roots OOMPAH-1127, OOMPAH-1128, and OOMPAH-1177.
      PRs #836 and #837 delivered the durable transport, stable incident identity,
      and fail-closed provider-admission repairs with full CI. This occurrence requires
      no independent implementation.'
    created_at: '2026-08-12T20:06:34.684453+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1146
    target_state: Archived
    evidence_fingerprint: 7199e66b20043cce51d15d82f669a495754ca4b4dd55c1222ef74850c6bd9138
    workflow_revision: null
    selected_ref: null
    selected_sha: null
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-12T20:06:44.627573+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> All dispatch candidates failed for issue TRICKLE-135: All 2 dispatch candidates unavailable: prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> All dispatch candidates failed for issue TRICKLE-135: All 2 dispatch candidates unavailable: prov-651d553c/haiku: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.; prov-52e94e83/gpt-5.6-luna: contributor_evidence_unavailable: Cannot durably record exact contributor provider/model evidence before launch (StateBranchFetchError). Restore tracker metadata writes and retry; no provider or workspace was started.

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
- fingerprint: 9108dea84bec5cb9
- dedup_fingerprint: 9108dea84bec5cb9

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 20:06
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Historical auto-filed occurrence from the state-branch and dispatch-convergence incident, consolidated into completed roots OOMPAH-1127, OOMPAH-1128, and OOMPAH-1177. PRs #836 and #837 delivered the durable transport, stable incident identity, and fail-closed provider-admission repairs with full CI. This occurrence requires no independent implementation.
---
author: oompah
created: 2026-08-12 20:07
---
Archived as a historical incident occurrence superseded by merged root fixes OOMPAH-1127, OOMPAH-1128, and OOMPAH-1177 (PRs #836/#837).
---
<!-- COMMENTS:END -->
