---
id: OOMPAH-661
type: task
status: Backlog
priority: null
title: Cancel stale implementation retries when task authority changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T13:12:19.387161Z'
updated_at: '2026-07-31T13:12:19.387161Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live reproduction on 2026-07-31: OOMPAH-660 failed implementation dispatch because its clean shared epic worktree had not yet followed a force-pushed rebase. The scheduler accumulated retry attempt #6 with the old divergence error. After the operator proved patch equivalence, reconciled the worktree, and successfully resubmitted OOMPAH-660 to Ready to Integrate, /api/v1/state still reported the stale implementation retry and counted the task as retrying while its exact head was already queued for integration. This is stale generation authority and can produce a redundant worker dispatch or misleading UI health.\n\nImplementation scope: bind every delayed implementation retry to the exact project/task/status/attempt/assignment/work-branch/head generation that failed; synchronously cancel and remove it when submission, status change, new assignment, head replacement, terminal transition, or operator reconciliation withdraws that generation; revalidate fresh tracker state and ownership immediately before any due retry dispatch; make cancellation idempotent across restart and ensure state/counts/alerts expose only actionable retries. Preserve historical run/error comments without treating them as live retry authority. Relevant code includes orchestrator retry scheduling/dispatch, task submission and status reconciliation, restart persistence, state serialization, and retry/watchdog tests.\n\nRequired deterministic tests: failed In Progress generation then submit same head to Ready clears retry immediately; Backlog/Open/Needs Human/terminal changes clear it; replacement head or attempt cannot inherit it; due-time race with submit allows only one authority winner; restart with stale persisted retry discards it; unrelated tasks/projects remain isolated; retrying UI count and error clear without deleting history. Acceptance: a retry can launch only while its exact failed implementation generation is still current, and OOMPAH-660-style reconciliation cannot leave a stale retry or spawn another worker after Ready to Integrate.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

