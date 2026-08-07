---
id: OOMPAH-889
type: task
status: Backlog
priority: null
title: Make Done-only maintenance repair survive native parent rollup
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T13:16:12.155503Z'
updated_at: '2026-08-07T13:16:12.155503Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live recurrence after merged OOMPAH-725, OOMPAH-825, and OOMPAH-829: OOMPAH-660 remains Merged while its lifecycle row is exhausted after five attempts with lifecycle_repair_not_applied. The classifier correctly says this auto-filed epic rebase helper's successful terminal target is Done. OOMPAH-829 recognizes the exact ab40139d2035↔62954f9b5fdc legacy fingerprint pair and checkpoints the repair, but the native tracker write does not remain applied; repeated authenticated owner Done overrides return HTTP 409 evidence_fingerprint_mismatch against the active historical Done record. Implementation scope: trace the native Markdown parent/child rollup and terminal-metadata transaction after the lifecycle repair; ensure a structurally Done-only maintenance child is excluded from generic parent-landed Merged promotion, or serialize the authoritative Done repair so the rollup cannot immediately overwrite it. Preserve ordinary child Merged convergence after parent landing, exact owner-override stale-evidence checks, and the bounded OOMPAH-829 legacy equivalence fence. Rearm an exhausted lifecycle row when the deployed repair version or authoritative rollup exclusion changes, then finalize and retire its incompatible Merged metadata atomically. Relevant code: native Markdown tracker child/epic rollup hooks, TerminalAuditEnforcement locked lifecycle repair and intent recovery, TerminalTransitionCoordinator override fingerprint matching, and OOMPAH-725/O825/O829 regressions. Required tests: exact production-shaped OOMPAH-660 metadata reaches and stays Done across repeated tracker refresh, parent rollup, restart, and concurrent reconciliation; an authenticated owner Done repair cannot be rejected solely because the current incompatible Merged projection differs from the matching authorized legacy Done evidence; OOMPAH-662 current-match control; ordinary landed children still reach Merged; tampered fingerprints and genuine stale evidence fail closed. Acceptance: without editing task files or service_state, deployed code converges OOMPAH-660 to Done, lifecycle exhausted=0/action_required=false, and repeated ticks cannot regress it to Merged; focused lifecycle/coordinator/native-tracker tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

