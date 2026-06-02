---
id: TASK-421
title: Keep dashboard review cache aligned with live open PRs
status: Done
assignee:
  - oompah
created_date: '2026-06-02 19:30'
updated_date: '2026-06-02 19:33'
labels: []
dependencies: []
priority: high
ordinal: 54000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: the dashboard can show zero open reviews or has_open_review=false for a project while the forge still has open PRs. Reproduce by having the orchestrator review cache contain an open PR, marking the project webhook-healthy, and running a review check; the current code replaces skipped healthy-project review data with an empty list, so /api/v1/state and /api/v1/issues can diverge from /api/v1/reviews and GitHub reality. Fix requirements: skipped webhook-healthy projects must preserve existing review cache data instead of clearing it; provider fetch failures must also avoid clearing known review data; successful fetches with an empty list must still clear the cache because the forge confirmed there are no open reviews. Add tests covering preserve-on-skip, preserve-on-provider-error, and clear-on-success-empty.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed dashboard review cache reconciliation so skipped webhook-healthy projects and provider fetch failures preserve known open PRs instead of clearing them. Added regression tests for preserve-on-skip, preserve-on-provider-error, and successful empty fetch clearing the cache. Verified with focused pytest and full make test: 4098 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
