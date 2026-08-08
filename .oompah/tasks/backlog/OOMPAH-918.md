---
id: OOMPAH-918
type: bug
status: Backlog
priority: 1
title: Make management-tracker alert diagnostics path-length independent
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T15:12:47.858971Z'
updated_at: '2026-08-08T15:12:47.858971Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

The management_tracker_resolution alert currently stores a raw repository/path exception in detail and relies on the generic alert sanitizer length threshold to move it into diagnostic. Its regression test passes or fails solely according to the generated temporary path length, and short paths can leak local filesystem diagnostics into the compact dashboard. Update oompah/server.py to emit an explicit bounded operator-facing detail plus the raw failure under diagnostic, update tests/test_management_tracker_resolution.py to assert the structured producer and snapshot contracts, and run focused tests plus the exact full make test gate. Acceptance: compact detail never exposes the raw repository path, diagnostic_available is true with the actionable exact diagnostic, behavior is independent of temp-root length, and the full gate is green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

