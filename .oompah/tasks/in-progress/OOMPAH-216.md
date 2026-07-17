---
id: OOMPAH-216
type: task
status: In Progress
priority: null
title: Make Release Delivery show reconciled branch status and actionable retries
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-17T00:40:53.660377Z'
updated_at: '2026-07-17T00:46:57.714645Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: cb7557e1-d85a-4a4f-8532-e76ca84b0964
---
## Summary

Fix the Release Delivery screen and supporting API so it accurately represents current release delivery state and remains correct after future merge/retry cycles.\n\nScope:\n- Reconcile ledger deliveries whose PR has merged: transition them from In Review to Merged and retain PR/result evidence.\n- Expose per-release-branch ahead/behind counts against main, plus last synchronization/merge evidence.\n- Treat tracker-only (.oompah-only) commits as a grouped UI row rather than individual pending rows; retain an expandable count/evidence view.\n- Surface each delivery's queued, in-progress, conflict-agent resolving, blocked, in-review/CI, merged, and archived state.\n- For blocked deliveries, show the actionable error and a Retry delivery control. Retrying after a successful history-preserving synchronization must refresh ancestry and avoid replaying already-delivered work.\n- Correct the current Trickle release/0.11 state: #279 and #280 merged, the history-repair result must be recognized, and the currently blocked 28c8a3d delivery must be retryable.\n\nTests:\n- API tests for merged PR reconciliation, ahead/behind values, tracker-only grouping, blocked retry, and post-retry delivery state.\n- Dashboard/UI tests for freshness summary, grouped tracker row, merged/blocked rendering, error/retry control, and no stale In Review state after PR merge.\n- Run make test.\n\nAcceptance criteria:\n- On Trickle release/0.11, the screen no longer reports #279 as In Review after its merge.\n- The screen reports real ahead/behind counts and identifies newer main commits.\n- .oompah-only commits are not shown as separate pending checkboxes.\n- A blocked delivery has a working retry path and meaningful error visibility.\n- Future release deliveries converge automatically after their PR merges.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-17 00:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-17 00:41
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-17 00:42
---
Understanding: Duplicate investigation complete for OOMPAH-216. I searched all existing tasks (OOMPAH-192 through OOMPAH-215) and confirmed this is NOT a duplicate. The closest related tasks are:\n- OOMPAH-209 (Merged): Grouped tracker-only commits in release delivery inventory — partially covers OOMPAH-216's tracker-only grouping requirement\n- OOMPAH-213 (Merged): Wired executor + sync with main — the Trickle delivery got blocked on a merge conflict\n- OOMPAH-214 (Merged): Resolved conflicts, created PR#279, delivery now in_review — but the UI requirement (clear status view, actionable retries) was noted but NOT implemented\n\nOOMPAH-216 is fresh incremental work surfaced after PR#279 (and #280) merged:\n1. PR reconciliation: deliveries still show In Review after PRs merged — the poller needs to be wired or executed\n2. Ahead/behind counts API: not exposed on the Release Delivery screen\n3. Blocked delivery retry path: 28c8a3d commit is blocked and needs a working retry control in the UI\n4. State surface: all delivery lifecycle states need to be visible on the Release Delivery screen\n\nPlan: (1) Investigate current state of release_delivery_poller.py and whether it's wired into the maintenance loop; (2) Check what the Release Delivery API returns for the Trickle project; (3) Add ahead/behind count support to the branch API; (4) Add retry endpoint for blocked ledger deliveries; (5) Update dashboard UI to show all states and retry control; (6) Run make test.
---
author: oompah
created: 2026-07-17 00:46
---
Discovery: Found all key gaps. OOMPAH-216 is NOT a duplicate.\n\nRoot causes:\n1. poll_delivery_pr() in release_delivery_poller.py is NEVER called from the orchestrator. PRs that merge don't automatically reconcile deliveries from in_review to merged (explains why #279 still shows In Review).\n2. ReleaseBranchInfo has no ahead/behind fields; the API never computes them.\n3. ReleaseStatusCell has no error or conflict_agent_resolving fields; the drawer can't show actionable error or retry UI.\n4. The retry endpoint (POST /issues/{id}/release-addendums/{aid}/retry) requires a source task identifier — but commit-inventory deliveries have no source task, so they can't be retried via this endpoint. Need a project-scoped retry endpoint.\n\nWhat OOMPAH-209 already did: tracker-only grouping via _rdiGroupTrackerRows is present in the UI.\n\nImplementation plan:\n1. orchestrator.py: Add _reconcile_delivery_pr_outcomes_sweep() and wire it into _reconcile_release_picks_pass()\n2. release_delivery_inventory.py: Add error+conflict_agent_resolving to ReleaseStatusCell; add ahead/behind to ReleaseBranchInfo\n3. server.py: Add POST /api/v1/projects/{id}/release-delivery/{delivery_id}/retry\n4. release_delivery_compat.py: Clear conflict_agent_task_id in retry_ledger_delivery()\n5. dashboard.html: Show ahead/behind in branch filter labels; add error+retry in drawer for blocked deliveries\n6. Tests for all above\n7. make test
---
<!-- COMMENTS:END -->
