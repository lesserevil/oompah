---
id: OOMPAH-217
type: task
status: Open
priority: null
title: Handoff cleared duplicate investigations to normal-focus agents
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-17T03:17:53.831077Z'
updated_at: '2026-07-17T03:20:41.456561Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 48143362-3954-45d4-81e1-ce133c13e382
---
## Summary

Implement a two-stage agent workflow for tasks flagged by duplicate detection.

The initial Duplicate Investigator run must only determine whether the task duplicates a closed task. If it archives the task, no further work runs. If it completes normally while the task remains active, Oompah must record that screening cleared, prevent the same duplicate flag from being re-applied, return the task to Open, and promptly dispatch a fresh agent session with normal focus.

Update Duplicate Investigator instructions so it does not implement the task after clearing duplicate screening. Add focused tests for: terminal duplicate has no handoff; active cleared task is marked screened and reopened; later focus selection is not duplicate_detector; duplicate detection skips screened tasks. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-17 03:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-17 03:20
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
