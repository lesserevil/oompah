---
id: OOMPAH-240
type: task
status: In Progress
priority: null
title: 'Dashboard test: newly merged task with no release history is visible and queueable'
parent: OOMPAH-237
children: []
blocked_by:
- OOMPAH-238
labels: []
assignee: null
created_at: '2026-07-19T02:30:36.850057Z'
updated_at: '2026-07-19T03:39:15.573914Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Add dashboard-level regression coverage for the corrected item-centric Release Delivery workflow.

This task depends on OOMPAH-238. Update the existing Release Delivery dashboard tests to model a selected release branch containing a newly merged task with no release-delivery ledger history.

Verify the UI renders that task as a primary queueable row with its identifier, title, source commit count, and Not selected state; selection sends all associated source commits to the existing queue endpoint for the selected branch. Verify delivered, active, and archived items cannot be queued again.

Do not change production UI behavior beyond adjustments required to make the testable interface match the corrected backend contract.

Acceptance criteria: the dashboard test suite fails against the ledger-only candidate bug and passes with the tracker-sourced backlog implementation.
## Context

After OOMPAH-238 fixes the candidate discovery algorithm, the dashboard should show tasks in 'Merged' tracker state that have never been queued for release delivery. This task adds the dashboard-level test that verifies this end-to-end behaviour.

## Required test

In tests/test_dashboard_release_delivery_ui.py, add a test that:
1. Sets up a mock backlog result where an item (e.g., 'TASK-NEW') has delivery_status.state = 'not_selected' and no delivery_id (simulating a task merged to main but never queued for release delivery).
2. Loads the dashboard and selects a release branch.
3. Verifies that the item appears in the backlog table (not filtered out by default needs_delivery filter — 'not_selected' is not delivered/archived so it should appear).
4. Verifies that the item's checkbox is enabled (not disabled — delivered/archived items have disabled checkboxes).
5. Verifies that clicking 'Queue selected items' with this item checked sends the correct POST /release-delivery/commits request body (source_commits, target_branches).
6. Verifies that the item row shows 'Not selected' in the status column.

## Acceptance criteria (for this task)
- Dashboard test for newly-merged-task-no-history scenario passes
- Test follows existing patterns in tests/test_dashboard_release_delivery_ui.py
- make test passes

## Files to change
- tests/test_dashboard_release_delivery_ui.py — add test class or test methods

## Key references
- tests/test_dashboard_release_delivery_ui.py — existing dashboard test patterns
- oompah/templates/dashboard.html — _rdiRenderItemRow(), _rdiQueueSelected(), ReleaseStatusCell rendering
- oompah/release_delivery_backlog.py — BacklogResult, ItemRow, ReleaseStatusCell

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes
