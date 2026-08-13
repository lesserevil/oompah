---
id: OOMPAH-1241
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=TRICKLE-141'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T13:47:10.437674Z'
updated_at: '2026-08-13T16:07:42.976214Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=TRICKLE-141

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=TRICKLE-141

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
- fingerprint: 78f5767e541d43e7
- dedup_fingerprint: 78f5767e541d43e7
- source_issue: TRICKLE-141

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 13:53
---
Root cause confirmed from the live traceback: workspace allocation re-derives TRICKLE-130's source with the default epic-* naming convention, ignoring its authoritative persisted work_branch=TRICKLE-130. The exact helper is therefore rejected as generation-stale and, if admitted, would allocate the wrong shared branch. I am fixing this together with the adjacent rebase receipt bug on branch OOMPAH-1240; tests will cover persisted non-convention branches and ensure ordinary helpers remain fail-closed.
---
author: oompah
created: 2026-08-13 13:59
---
Implemented regression coverage and repair: helper admission and direct maintenance workspace allocation now preserve the parent epic's persisted work_branch instead of synthesizing a current-convention branch. This covers the live TRICKLE-130/TRICKLE-141 pre-convention source mismatch.
---
author: oompah
created: 2026-08-13 14:52
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: ACP worker failed issue_id=TRICKLE-141

Source issue: `TRICKLE-141`
---
author: oompah
created: 2026-08-13 15:53
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: ACP worker failed issue_id=TRICKLE-141

Source issue: `TRICKLE-141`
---
author: oompah
created: 2026-08-13 16:00
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: ACP worker failed issue_id=TRICKLE-141

Source issue: `TRICKLE-141`
---
author: oompah
created: 2026-08-13 16:07
---
Root cause refined live after provider-auth recovery: TRICKLE-141 reaches implementation dispatch, but direct epic-maintenance allocation refuses Oompah's managed Trickle clone because its common .git/config retains an HTTP userinfo remote and local credential helpers from pre-migration/adoption state. The dedicated sandbox would strip these and disable network, but the earlier security preflight correctly refuses to launch. Permanent managed-clone sanitation is tracked as OOMPAH-1249; immediate scoped workaround will normalize only Oompah's managed clone to the canonical credential-free project URL and remove its local helpers, preserving server-owned token transport.
---
<!-- COMMENTS:END -->
