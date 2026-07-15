---
id: OOMPAH-210
type: bug
status: In Progress
priority: 2
title: Detect and surface unavailable GitHub check-run access
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-15T20:39:59.115969Z'
updated_at: '2026-07-15T20:41:26.686888Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d1f951f3-d991-4b69-80bf-8b95c6d14746
---
## Summary

Triggered by: TRICKLE-26

Oompah received HTTP 403 from GET /repos/NVIDIA-Omniverse/trickle/commits/<sha>/check-runs while reconciling PR #277. It consequently could not observe the failed CI lint check or automatically create/dispatch a CI-fix task. Make check-run access failures visible as a project capability/degraded-state error, document the exact required token permission and alternatives, and ensure CI repair dispatch has a reliable fallback when check-runs cannot be read. Add regression tests for 403 handling and failed-check detection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-15 20:41
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-15 20:41
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-15 20:41
---
Understanding: This issue requires implementing 403 error handling for GitHub check-runs API. Plan: (1) Find where check-runs are fetched in oompah, (2) Add 403 detection + degraded-state surfacing, (3) Document required token permission, (4) Add fallback for CI repair dispatch when check-runs unavailable, (5) Write regression tests. Starting codebase exploration now.
---
<!-- COMMENTS:END -->
