---
id: TASK-476
title: Split release-pick reconciliation from merged-label maintenance
status: Done
assignee:
  - oompah
created_date: '2026-06-09 17:37'
updated_date: '2026-06-09 17:53'
labels: []
dependencies: []
priority: high
ordinal: 204000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The merged_labels maintenance job currently also runs release-pick reconciliation, so status shows merged_labels running while the release-pick pass does full-corpus work. Split release-pick reconciliation into its own maintenance job with independent observability/throttling so the merged-label epic merge policy path cannot appear wedged by unrelated work.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Split release-pick reconciliation out of merged_labels into its own release_picks maintenance job with independent status/throttling, and updated tests so merged-label maintenance only owns merged issue/epic and stale In Review reconciliation.
<!-- SECTION:FINAL_SUMMARY:END -->
