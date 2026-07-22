---
id: OOMPAH-358
type: task
status: Done
priority: 1
title: Gate epic rebase scheduling on actionable conditions
parent: OOMPAH-356
children: []
blocked_by:
- OOMPAH-357
labels: []
assignee: null
created_at: '2026-07-22T01:23:51.390755Z'
updated_at: '2026-07-22T01:30:12.460844Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Update the epic maintenance and rebase-dispatch flow to consume the synchronization policy. Preserve staleness detection, but make it observational by default. Do not create an agent task, worktree operation, merge, or rebase unless the policy returns an allowed actionable reason.\n\nImplementation scope:\n- Remove automatic rebase scheduling triggered only by commit-count/file-overlap staleness.\n- Retain configured threshold detection as an alert/signal.\n- Carry the actionable reason into logs, task comments, and rebase state.\n- Ensure PR-preparation and explicit operator paths can request an allowed synchronization.\n\nTests:\n- Integration-style tests proving stale incomplete epics cause no branch mutation or agent dispatch.\n- Tests proving PR preparation, explicit requests, and merge-blocking conflicts still schedule exactly one rebase.\n- Verify repeated ticks coalesce rather than repeatedly scheduling the same permitted rebase.\n\nAcceptance criteria:\n- Main advancing alone cannot generate a rebase agent for an unfinished epic.\n- Existing permitted rebase workflows remain functional and auditable.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:30
---
Removed periodic proactive rebase scheduling; staleness detection no longer creates branch-mutating work.
---
<!-- COMMENTS:END -->
