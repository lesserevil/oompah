---
id: TASK-403
title: Filter running agent chips by selected project
status: Done
assignee:
  - oompah
created_date: '2026-06-01 20:12'
updated_date: '2026-06-01 20:15'
labels: []
dependencies: []
priority: medium
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The dashboard can show global running-agent chips while the board is filtered to a single project, which makes it look like agents are running without matching In Progress cards. Update the UI so visible running-agent chips use the same selected project filter as the board, while keeping the underlying state/global counts available for dispatch logic. Add regression tests that a selected project filter causes only matching project agents to be rendered.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Filtered visible running-agent chips through the same selected project filter used by the board, updated the chip count to reflect visible agents, and re-rendered chips immediately when the project filter changes. Added dashboard regression tests for the project-filtered chip behavior.
<!-- SECTION:FINAL_SUMMARY:END -->
