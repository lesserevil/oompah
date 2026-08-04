---
id: OOMPAH-756
type: bug
status: Backlog
priority: 1
title: Reconcile already-landed nested epics from In Review
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:07:47.294756Z'
updated_at: '2026-08-04T11:07:47.294756Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: EXOCOMP-128

Regression/incomplete implementation of OOMPAH-748 on live revision 5368e236. EXOCOMP-128 remains In Review with no open review even though GitHub PR 21 merged epic-EXOCOMP-128 into its authoritative immediate target epic-EXOCOMP-127 at merge commit 2476a39252e92b4690337d7fe706d1b28781bd60, that merge commit is reachable from origin/epic-EXOCOMP-127, and multiple independent terminal auditors previously returned PASS for Merged. OOMPAH-748 head d4282363 is live, but it changed only _epic_auto_close_check. Existing nested epics already routed to In Review by the old lifecycle cycle do not naturally re-enter that auto-close path. The live scheduler instead repeatedly runs epic review readiness, reports historical child task branches as unverifiable, and defers EXOCOMP-128 as if a new review were needed, despite the authoritative merged review already existing. This continues to block parent EXOCOMP-127. Implementation scope: make merged-review and stale-In-Review reconciliation target-relative for nested epics; recognize an authoritative provider review whose source is the nested epic branch, target is the immediate parent branch, and merge commit is reachable from that parent; route terminal state through the coordinator using existing Done/Merged audit evidence or a fresh bounded audit; do not reopen a review or require deleted/private child branch refs after the epic review has landed; make restart reconciliation idempotent and preserve wrong-target, missing-merge, source-advanced, and premature-root protections. Relevant code: _epic_auto_close_check, _label_merged_epics, stale/deferred In Review reconciliation, _open_epic_main_prs readiness ordering, nested target resolution, terminal lifecycle coordinator, and provider review evidence. Required tests: exact EXOCOMP-128 restart state (In Review, merged PR to parent, merge reachable, prior passing audits); source branch present and deleted; historical child private refs absent; wrong target; merge not reachable; parent not yet on main; later parent landing; duplicate ticks/restarts. Acceptance criteria: a nested epic already landed on its immediate parent cannot remain In Review waiting for a new review or root-main landing; it reaches the target-relative audited terminal state and unblocks its parent, while root epics still cannot become Merged before main landing; focused epic, review reconciliation, audit lifecycle, and restart tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

