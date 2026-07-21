---
id: OOMPAH-292
type: task
status: Open
priority: null
title: Show mergeable-item summaries and full task details in Release Delivery
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T15:01:48.947973Z'
updated_at: '2026-07-21T15:02:07.715014Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem

Release Delivery rows show only identifier/title/commit metadata, so users must leave the page to understand a mergeable task or epic. Clicking an identifier opens a narrow 420px evidence drawer that shows only release evidence, not the full task detail available on the dashboard.

Implement

- Extend the Release Delivery backlog payload with a concise, safely derived task or epic summary for every associated mergeable item. Use the task description/summary, normalize whitespace, and truncate to a documented bounded length; preserve a clear fallback when no description exists.
- Render that summary directly beneath or alongside the title in each Release Delivery item row. It must be readable without opening the detail drawer and must not expose raw HTML.
- Change the Release Delivery drawer width to match the dashboard detail panel: width min(800px, 40vw), retaining an appropriate narrow-viewport fallback.
- On opening an associated task/epic drawer, request GET /api/v1/issues/{identifier}/detail with the selected project ID and render the same core information as the dashboard: title, state, priority, labels, type, parent, description, children where applicable, comments, source/repository links, and task metadata. Keep delivery status and source-commit evidence as an additional Release Delivery section.
- Show an in-drawer loading/error state without losing already rendered delivery evidence. Do not fetch task details for unassociated commits.

Tests

- Backlog service/API tests for summary extraction, normalization, truncation, missing-description fallback, and HTML-safe transport.
- Template tests asserting the summary is rendered for every item row.
- Drawer tests asserting the full-detail endpoint is called with project_id, all core dashboard fields are rendered, delivery evidence remains visible, and errors are displayed safely.
- CSS test asserting the drawer uses min(800px, 40vw).

Acceptance criteria

A user can understand the purpose of every mergeable task/epic from the Release Delivery list, and clicking it shows substantially the same task information as the dashboard without leaving the page. The drawer is no wider than 40% of the viewport and no narrower than the dashboard detail-panel behavior at normal desktop widths.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

