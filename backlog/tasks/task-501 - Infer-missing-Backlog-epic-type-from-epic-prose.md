---
id: TASK-501
title: Infer missing Backlog epic type from epic prose
status: Done
assignee: []
created_date: '2026-06-10 02:35'
updated_date: '2026-06-10 02:36'
labels:
  - bug
dependencies: []
priority: high
ordinal: 219000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Backlog tasks that are written as epics but miss the explicit type/label can be normalized as feature/task, causing shared-epic projects to open per-child PRs. Add a narrow normalization fallback for clear epic prose so shared epic PR gating still applies.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 02:36
---
Implementing parser fallback and focused regression tests now.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
BacklogMdTracker now treats clear epic prose as issue_type=epic when no explicit type is set, while preserving explicit type precedence. Added focused parser tests and ran Backlog tracker plus shared epic-strategy subsets.
<!-- SECTION:FINAL_SUMMARY:END -->
