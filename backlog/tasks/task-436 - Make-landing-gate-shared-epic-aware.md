---
id: TASK-436
title: Make landing gate shared-epic aware
status: Backlog
assignee: []
created_date: '2026-06-03 19:35'
labels:
  - bug
dependencies: []
priority: high
ordinal: 72000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The completed-without-landing gate checks child issue branches such as TASK-706.1 even when the project uses epic_strategy=shared and child work lands on the shared epic branch such as epic-TASK-706. This caused trickle TASK-706.1 and TASK-706.2 to be marked Needs Human even though the epic branch contains commits and the task files are Done on origin/epic-TASK-706. Update landing detection and its diagnostic comment/telemetry to resolve the effective landing branch for shared-epic children.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 For shared-epic child tasks, landing detection checks the shared epic branch instead of the child identifier branch.
- [ ] #2 A child task with commits on origin/epic-<parent> is not marked Needs Human solely because origin/<child> does not exist.
- [ ] #3 Tests cover the TASK-706.1-style false positive and preserve existing flat/per-task landing-gate behavior.
<!-- AC:END -->
