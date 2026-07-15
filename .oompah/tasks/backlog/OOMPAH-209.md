---
id: OOMPAH-209
type: feature
status: Backlog
priority: 2
title: Group tracker-only commits in release delivery inventory
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-15T16:20:43.833803Z'
updated_at: '2026-07-15T16:20:43.833803Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-197

In the Release delivery popup, represent commits whose changes are limited to .oompah/ as one checkbox rather than individual rows. Selecting the group must expand to every underlying source commit when queueing, preserve source order, show accurate per-release status, and remain compatible with server-side delivered/active filtering. Keep non-.oompah commits individually selectable. Add inventory, UI, and queue payload regression tests.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

