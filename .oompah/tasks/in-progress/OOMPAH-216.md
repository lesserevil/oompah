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
updated_at: '2026-07-17T00:41:07.764376Z'
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
<!-- COMMENTS:END -->
