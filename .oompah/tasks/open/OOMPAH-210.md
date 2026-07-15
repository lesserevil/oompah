---
id: OOMPAH-210
type: bug
status: Open
priority: 2
title: Detect and surface unavailable GitHub check-run access
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-15T20:39:59.115969Z'
updated_at: '2026-07-15T20:40:45.080689Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: TRICKLE-26

Oompah received HTTP 403 from GET /repos/NVIDIA-Omniverse/trickle/commits/<sha>/check-runs while reconciling PR #277. It consequently could not observe the failed CI lint check or automatically create/dispatch a CI-fix task. Make check-run access failures visible as a project capability/degraded-state error, document the exact required token permission and alternatives, and ensure CI repair dispatch has a reliable fallback when check-runs cannot be read. Add regression tests for 403 handling and failed-check detection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

