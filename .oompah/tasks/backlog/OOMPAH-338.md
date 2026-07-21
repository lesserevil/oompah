---
id: OOMPAH-338
type: task
status: Backlog
priority: null
title: Add GitLab tracker lifecycle relationships and metadata persistence
parent: OOMPAH-323
children: []
blocked_by:
- OOMPAH-337
labels: []
assignee: null
created_at: '2026-07-21T23:24:39.407769Z'
updated_at: '2026-07-21T23:24:52.989337Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Extend GitLabIssueTracker on top of the core adapter to preserve Oompah task/epic semantics: priority/type labels, parent-child and blocked-by dependency issue links, fetch_children, attachments metadata round trips, generic metadata fields, and enriched issue detail. Define and test the GitLab link direction/type mapping so parent and dependency retrieval remains correct across globally unambiguous nested-namespace identifiers. Add mocked API tests for link creation/listing, comments and attachment/metadata round trips, label preservation, and archive/reopen behavior. Keep native external intake out of scope. Acceptance: all non-governance relationship and metadata TrackerProtocol operations have GitLab implementations and tested round-trip behavior.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

