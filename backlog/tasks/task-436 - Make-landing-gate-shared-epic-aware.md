---
id: TASK-436
title: Make landing gate shared-epic aware
status: Done
assignee: []
created_date: '2026-06-03 19:35'
updated_date: '2026-06-09 22:18'
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

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 22:18
---
Understanding: Re-dispatched as Duplicate Investigator. Searching for any prior task that covers the same ground (shared-epic landing gate awareness). Candidate: TASK-437 (retry non-landing runs). Will confirm whether overlap is superficial or substantive.
---

author: oompah
created: 2026-06-09 22:18
---
Discovery: No duplicate exists. TASK-437 addresses retry behavior (non-landing runs → escalate instead of Needs Human), while TASK-436 addresses wrong-branch detection for shared-epic children (TASK-706.1 should check epic-TASK-706, not TASK-706.1 branch). Distinct problems with distinct root causes. The implementation of TASK-436 is already committed on this branch (commits 086ad16 and bee3082) and the task was already marked Done on 2026-06-04.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Duplicate investigation complete: TASK-436 is not a duplicate. TASK-437 (retry non-landing runs) covers a different problem. TASK-436's implementation (shared-epic branch resolution in landing gate) was already completed and committed on 2026-06-04. Task remains Done.
<!-- SECTION:FINAL_SUMMARY:END -->
