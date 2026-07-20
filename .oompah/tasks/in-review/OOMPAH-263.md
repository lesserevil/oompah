---
id: OOMPAH-263
type: task
status: In Review
priority: null
title: Widen the dashboard task detail pane
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-20T16:47:15.264773Z'
updated_at: '2026-07-20T16:49:26.856267Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Increase the dashboard right-side task detail pane width from its fixed 400px size to a responsive width of up to 800px, capped at 40 percent of the viewport. Preserve the existing open/close behavior and layout.

Tests

- Add a dashboard-template regression test that asserts the open pane uses the 800px and 40vw cap.
- Run make test.

Acceptance criteria

- The task detail pane is approximately twice as wide on large screens.
- It never exceeds 40 percent of window width.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 16:49
---
Implemented in PR #452: responsive dashboard detail-pane width of min(800px, 40vw), with a template regression test. make test passed.
---
<!-- COMMENTS:END -->
