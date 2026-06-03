---
id: TASK-434
title: Handle diverged branches during auto-update
status: Done
assignee:
  - oompah
created_date: '2026-06-03 18:02'
updated_date: '2026-06-03 18:06'
labels:
  - bug
dependencies: []
priority: high
ordinal: 70000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The UI auto-update path can fail with git pull errors when the local branch and origin/main have diverged. Investigate the existing update/rebase handling and make the orchestrator auto-update use the built-in repair path instead of surfacing a raw diverged-branch git pull error.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Auto-update succeeds or gives a specific actionable error when local main has local commits and origin/main has new commits.
- [x] #2 The git update path preserves uncommitted user work and does not discard local commits.
- [x] #3 Tests cover the diverged branch scenario that currently reports 'can't be fast-forwarded'.
<!-- AC:END -->



## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented auto-update handling for diverged local main branches. Auto-update now detects local commits ahead of origin/main and uses git pull --rebase --autostash instead of ff-only pull, aborting a failed rebase before surfacing a UI alert. Added tests for behind-only fast-forward, diverged-branch rebase, and failed-rebase cleanup. Verified with make test: 4376 passed, 16 warnings.
<!-- SECTION:FINAL_SUMMARY:END -->
