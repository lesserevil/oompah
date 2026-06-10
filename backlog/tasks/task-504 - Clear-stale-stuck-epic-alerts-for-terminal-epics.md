---
id: TASK-504
title: Clear stale stuck-epic alerts for terminal epics
status: Done
assignee:
  - oompah
created_date: '2026-06-10 06:18'
updated_date: '2026-06-10 06:19'
labels: []
dependencies: []
priority: high
ordinal: 224000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: a stuck_epic dashboard alert can remain after the epic is already Merged/Archived because _auto_close_completed_epics skips terminal epics before _epic_auto_close_check gets a chance to clear the alert. Clear stale stuck_epic alerts when terminal epics are encountered and when an epic is marked Merged.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Cleared stale stuck_epic alerts when the auto-close sweep encounters an already-terminal epic and when the epic landing path marks an epic Merged. Added regression tests for both stale-alert paths.
<!-- SECTION:FINAL_SUMMARY:END -->
