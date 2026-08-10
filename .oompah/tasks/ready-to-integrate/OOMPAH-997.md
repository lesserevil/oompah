---
id: OOMPAH-997
type: bug
status: Ready to Integrate
priority: 2
title: '[backend:workflow_runtime] Durable workflow source evaluation failed for proj-14849f1b'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T15:04:29.205558Z'
updated_at: '2026-08-10T15:34:30.268325Z'
work_branch: OOMPAH-997
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-997
  head_sha: 94f1f5b84aa60bebf02cdd7d049de698df1e79ee
  submitted_at: '2026-08-10T15:34:15.105659+00:00'
  updated_at: '2026-08-10T15:34:15.105659+00:00'
oompah.work_branch: OOMPAH-997
---
## Summary

### Problem
Oompah detected a backend error from `backend:workflow_runtime`:

> Durable workflow source evaluation failed for proj-14849f1b

### Steps to Reproduce
1. Run oompah with `backend:workflow_runtime` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:workflow_runtime` and is recorded by oompah's `error_watcher`:

> Durable workflow source evaluation failed for proj-14849f1b

### Expected Behavior
The operation in `backend:workflow_runtime` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:workflow_runtime` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: be60e35246101e15
- dedup_fingerprint: be60e35246101e15

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 15:29
---
Direct-owner hotfix is committed locally at exact head 94f1f5b84aa60bebf02cdd7d049de698df1e79ee on branch OOMPAH-997. Transient None publication revisions now cleanly supersede source/preflight/finalization snapshots; superseded async reconciles clear admission and cannot claim prior shared work; active projects and controller caches are preserved for stable retry. Regressions cover five None windows, integer revision change, production composition, multi-project reporting, and real prior-generation job fencing with zero attempts/effects until a newer cut republishes. Full workflow-runtime suite: 130 passed; Python 3.11 focused new regressions: 10 passed; independent adversarial review approved; terminal mutation scan and secret checks passed. Exact complete Makefile gate is now running before push/submission.
---
author: oompah
created: 2026-08-10 15:34
---
Fixed tracker publication-revision races so transient mutation authority cleanly supersedes and retries, while prior shared jobs remain fenced until a stable world snapshot republishes. Added source/preflight/finalization, async admission, retry, composition, and multi-project regressions; 130 workflow-runtime tests and focused Python 3.11 checks pass; independent review approved.
---
<!-- COMMENTS:END -->
