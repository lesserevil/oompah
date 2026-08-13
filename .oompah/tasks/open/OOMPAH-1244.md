---
id: OOMPAH-1244
type: bug
status: Open
priority: 2
title: '[backend:acp_agent] ACP backend ''claude'' crashed during run_turn: OSError:
  configured provider authentication artifact is unavailable'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T14:34:54.048407Z'
updated_at: '2026-08-13T15:55:03.269056Z'
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
Oompah detected a backend error from `backend:acp_agent`:

> ACP backend 'claude' crashed during run_turn: OSError: configured provider authentication artifact is unavailable

### Steps to Reproduce
1. Run oompah with `backend:acp_agent` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:acp_agent` and is recorded by oompah's `error_watcher`:

> ACP backend 'claude' crashed during run_turn: OSError: configured provider authentication artifact is unavailable

### Expected Behavior
The operation in `backend:acp_agent` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:acp_agent` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 1b3f11c8112aa2ab
- dedup_fingerprint: 1b3f11c8112aa2ab

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 15:55
---
Live root cause confirmed on TRICKLE-141: all dispatch profiles selected Claude subscription while the host lacks ~/.claude/.credentials.json, so isolated workers exited at zero turns with configured provider authentication artifact is unavailable. The generic provider probe still reported Claude healthy because it used ambient provider access rather than the isolated worker credential boundary. Operational workaround applied through the supported live profile API: quick, default, standard, and deep now select the authenticated Codex subscription provider. Permanent acceptance must make provider health/admission validate the same isolated-worker auth artifact before marking a provider dispatchable, with tests for probe-success/worker-auth-missing divergence and fallback to a genuinely launchable provider.
---
<!-- COMMENTS:END -->
