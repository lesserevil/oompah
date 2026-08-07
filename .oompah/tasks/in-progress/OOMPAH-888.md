---
id: OOMPAH-888
type: task
status: In Progress
priority: 0
title: Rebase epic-OOMPAH-763 onto main
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T13:06:34.028897Z'
updated_at: '2026-08-07T13:17:43.150450Z'
work_branch: null
target_branch: main
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.target_branch: main
oompah.epic_rebase_target:
  version: 1
  epic_identifier: OOMPAH-763
  epic_branch: epic-OOMPAH-763
  target_branch: main
  parent_id: null
  resolution: confirmed_top_level
---
## Summary

The epic branch `epic-OOMPAH-763` is stale: it has fallen behind `main`. Rebase the branch onto `origin/main`, resolve any conflicts, and force-push with `git push --force-with-lease`.

This task was auto-filed because epic OOMPAH-763 was detected as stale. Do NOT create a new branch or PR — work directly on `epic-OOMPAH-763`.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 13:17
---
Direct-owner containment applied before implementation. This is recurrence #8 of the duplicate epic-OOMPAH-763 rebase helper race while canonical OOMPAH-877 already owns and has repaired the same generation. Preserve this task/claim as fenced incident evidence; do not mutate or push the shared branch. OOMPAH-879 owns the systemic authority/idempotency fix.
---
<!-- COMMENTS:END -->
