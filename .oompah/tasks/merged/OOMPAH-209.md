---
id: OOMPAH-209
type: feature
status: Merged
priority: 2
title: Group tracker-only commits in release delivery inventory
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-15T16:20:43.833803Z'
updated_at: '2026-07-15T16:22:28.198363Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f1e98f02-767b-4d62-aa16-ca79956d42ef
---
## Summary

Triggered by: OOMPAH-197

In the Release delivery popup, represent commits whose changes are limited to .oompah/ as one checkbox rather than individual rows. Selecting the group must expand to every underlying source commit when queueing, preserve source order, show accurate per-release status, and remain compatible with server-side delivered/active filtering. Keep non-.oompah commits individually selectable. Add inventory, UI, and queue payload regression tests.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-15 16:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-15 16:21
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-15 16:21
---
Understanding: Investigating OOMPAH-209 as a Duplicate Investigator. The issue asks to group tracker-only commits (limited to .oompah/) in the Release delivery popup as a single checkbox rather than individual rows. It was triggered by OOMPAH-197. My plan: (1) read OOMPAH-197 to understand the relationship, (2) search for similar tasks about release delivery, commit grouping, or tracker-only commits, (3) determine if this is a duplicate or new work.
---
author: oompah
created: 2026-07-15 16:22
---
Implemented in 59ad8d05: the inventory identifies .oompah-only commits by changed paths and the popup renders them as one checkbox that expands to the underlying SHAs when queued. make test passed.
---
<!-- COMMENTS:END -->
