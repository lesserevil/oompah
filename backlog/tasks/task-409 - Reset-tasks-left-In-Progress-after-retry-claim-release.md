---
id: TASK-409
title: Reset tasks left In Progress after retry claim release
status: Done
assignee:
  - oompah
created_date: '2026-06-01 23:57'
updated_date: '2026-06-02 02:29'
labels:
  - bug
dependencies: []
priority: high
ordinal: 41000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Observed after reopening TASK-389 on 2026-06-01. The task moved to Open successfully and dispatched. The worker completed normally without closing the task, oompah logged `Escalating TASK-389 from default to standard after completing without closing (1/3)`, then logged `Retry released claim issue_id=TASK-389 (no longer candidate)`. After that, `/api/v1/state` showed no running or retrying entry for TASK-389, but `backlog task view TASK-389` still showed `Status: In Progress`.

Expected behavior: if oompah releases or cancels the retry claim for a task that is still `In Progress` and has no running agent, it must move that task back to `Open` (or another explicit waiting/deferred status) so the dashboard never shows an in-progress task with no owner.

Implementation guidance:
- Trace the retry-release path that logs `no longer candidate`.
- Add a regression test where a worker completes without closing, escalation/retry is cancelled or released, and the tracker still has `In Progress`.
- Ensure the orphan reset/reconcile path covers this case even when the task is no longer a dispatch candidate.
- Verify the dashboard state and backlog task status agree after the reset.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 When a retry claim is released for a task still marked In Progress with no running agent, oompah moves the task to Open or another explicit non-running status.
- [ ] #2 The dashboard no longer shows an In Progress task without a matching running or retrying owner after this path.
- [ ] #3 Regression tests cover the retry-release/no-longer-candidate path.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed orphaned In Progress cleanup so stale completed markers no longer prevent resetting tasks back to Open, and the stale marker is discarded after reset. Verified with uv run pytest tests/test_orchestrator_merged.py tests/test_dashboard_conditional_columns.py -q and make test (3685 passed, 18 warnings).
<!-- SECTION:FINAL_SUMMARY:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Understanding [2026-06-02]: Not a duplicate of TASK-402.11. Root cause found in _on_retry_timer: when an In Progress task fires its retry, it is NOT in candidates (candidates are Open tasks only), so the retry is released with 'no longer candidate' but the task remains In Progress. _reset_orphaned_in_progress also only iterates candidates so it never sees this orphaned In Progress task. Fix plan: (1) in _on_retry_timer no-longer-candidate path, fetch issue state and reset to Open if still In Progress. (2) supplement _reset_orphaned_in_progress to also sweep over running entry ids whose issue state is In Progress but have no active agent. Add regression tests.

Discovery [2026-06-02]: Root cause confirmed. (1) _reset_orphaned_in_progress(candidates) only iterates Open/Needs CI Fix/Needs Rebase tasks — never In Progress. (2) _on_retry_timer drops the retry entry and releases the claim when the issue is 'no longer candidate' (because In Progress tasks are NOT candidates), but does not reset the tracker status. Fix: (A) Primary — in _on_retry_timer no-longer-candidate path, fetch the issue state and reset to Open if In Progress. (B) Defense-in-depth — add fetch_in_progress_issues() to tracker, add _fetch_all_in_progress_issues() to orchestrator, and extend _reset_orphaned_in_progress to also sweep In Progress tasks not in the candidates list.
<!-- SECTION:NOTES:END -->
