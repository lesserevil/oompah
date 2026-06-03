---
id: TASK-426
title: Warn when PR checks wait on unavailable runner hardware
status: Done
assignee:
  - oompah
created_date: '2026-06-03 00:05'
updated_date: '2026-06-03 00:13'
labels: []
dependencies: []
priority: high
ordinal: 59000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Detect GitHub Actions jobs that are queued for self-hosted runner labels with no online matching runner, and surface a warning in oompah so operators can tell the difference between busy hardware and missing/offline hardware. Include tests for runner inventory matching and review serialization/UI-facing warning data.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added GitHub Actions self-hosted runner availability warnings. Queued jobs now inspect Actions job labels and repository runner inventory, attach unavailable-runner ci_warnings to review payloads, count them in reviews_summary, and surface them in the reviews page and dashboard badge. Verified live against trickle PRs #167/#168: both report the offline trickle-windows-runner.
<!-- SECTION:FINAL_SUMMARY:END -->
