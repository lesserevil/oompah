---
id: TASK-420
title: Keep review badge in sync with review board
status: Done
assignee:
  - oompah
created_date: '2026-06-02 16:08'
updated_date: '2026-06-02 16:13'
labels: []
dependencies: []
priority: high
ordinal: 53000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The dashboard can show a reviews badge such as '1 awaiting enqueue' while the Reviews page shows no open reviews. Diagnose and fix the mismatch between the dashboard reviews_summary source and the /api/v1/reviews board source. Add a regression test that proves an authoritative empty reviews payload clears the orchestrator review summary/cache so the badge and board agree.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 16:08

Claiming this bug. Repro path: dashboard badge uses reviews_summary from orchestrator cache while the Reviews board fetches /api/v1/reviews directly; if those sources diverge, the badge can show an awaiting-enqueue count with an empty board.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed the review badge/review board mismatch by making /api/v1/reviews fetch typed ReviewRequest data, update the orchestrator review cache for successfully fetched projects, and emit a state update when the review summary changes. Added regression tests for clearing stale review-summary cache when the authoritative Reviews payload is empty, rebuilding cache entries as ReviewRequest objects, and preserving existing cache when a project fetch fails.
<!-- SECTION:FINAL_SUMMARY:END -->
