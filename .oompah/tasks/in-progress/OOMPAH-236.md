---
id: OOMPAH-236
type: task
status: In Progress
priority: null
title: Replace Release Delivery commit pagination with an item-centric release backlog
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-19T00:33:24.455215Z'
updated_at: '2026-07-19T00:35:42.302167Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 7877f413-a3a6-4eb6-8f46-1a347f1abf10
---
## Summary

Problem
The Release Delivery overlay currently pages through individual main-branch commits. Its “Load next page” action is commit-history pagination, which does not match the operator workflow: choosing which completed tasks and epics should be delivered to one release branch.

Required behavior
- Require the operator to select one configured supported release branch before loading the backlog.
- Display one row per task or epic that has individually merged to the project default branch and is not already delivered to the selected release branch.
- A row represents the source task/epic, not each constituent commit. Show the identifier, title, source-main merge evidence, and current release-delivery state.
- Selecting one or more rows queues delivery of every associated source commit to the selected release branch through the existing release-delivery ledger and executor. Do not create child merge tasks.
- If an item is already queued, in progress, in review, blocked, or delivered to the selected branch, render that state on the row and prevent duplicate queueing.
- Remove the commit-history “Load next page” control from this primary workflow. The ordinary release backlog must load as a complete bounded list. If an implementation limit is necessary, use explicit search/filtering with an explanatory count, not cursor-based history pages.
- Preserve the ability to inspect item-level commit evidence in a details drawer; commits are subordinate detail, not top-level rows.
- Do not present unassociated direct-to-main commits as normal candidates in this item-centric view. If retained for diagnostics, show them in a clearly separate, non-primary section.

Implementation notes
Replace or adapt the current commit-inventory API and dashboard overlay. Reuse the project release-delivery ledger, ancestry checks, and delivery executor; do not rewrite delivery execution. Update plans/release-delivery-commit-inventory.md and docs/release-addendums.md to describe the item-centric backlog and remove commit-page terminology.

Tests
- Unit-test candidate derivation for merged tasks, merged epics, already-delivered items, active deliveries, and items with multiple associated commits.
- API tests verify a selected branch returns complete item rows with the required status/evidence and does not return a next cursor.
- Dashboard tests verify branch-first selection, no “Load next page” control, item-row rendering, duplicate-queue prevention, and queue request construction from associated commits.
- Regression-test that an item already present on the target by ancestry is not queueable.

Acceptance criteria
- An operator selecting release/0.11 sees a single understandable backlog of merged tasks and epics still absent from release/0.11.
- Each row can be queued once and creates the correct existing ledger delivery records for its associated commits.
- No commit-history pagination is visible in the primary Release Delivery workflow.
- Existing delivery states and historical evidence remain inspectable.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 00:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 00:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 00:35
---
Understanding: I am the Duplicate Investigator for OOMPAH-236. This issue requests replacing the Release Delivery commit-pagination model with an item-centric backlog (one row per task/epic, not per commit). I will now search for existing tasks that cover the same ground before any implementation begins.
---
<!-- COMMENTS:END -->
