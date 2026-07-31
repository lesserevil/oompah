---
id: OOMPAH-666
type: bug
status: Backlog
priority: 1
title: Fix dashboard vertical scrolling when alerts precede the Kanban board
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- needs:frontend
assignee: null
created_at: '2026-07-31T21:19:38.816688Z'
updated_at: '2026-07-31T21:19:38.816688Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Reproduce and fix the main dashboard layout bug where alert panels or other content above the Kanban board increase the page height but the vertical scroll container remains constrained, preventing the operator from scrolling through the board to its bottom. Inspect the height and overflow rules in oompah/templates/dashboard.html and related dashboard CSS/JavaScript; identify the actual document or application scroll owner and remove conflicting fixed-height, min-height, or overflow clipping without breaking horizontal board scrolling, per-column scrolling, sticky controls, drag and drop, or responsive layouts. Add regression coverage following the existing dashboard test patterns in tests/ that exercises the page with no alerts and with one or multiple alert panels, verifies that content above the board remains visible, and verifies that the viewport or designated vertical container can reach the bottom edge of a board taller than the viewport. Acceptance criteria: on common desktop viewport heights, an operator can scroll continuously from the dashboard header and alerts to the final Kanban row or card; the bottom is not clipped; behavior remains correct when alerts appear or clear dynamically; existing board horizontal and column scrolling behavior is preserved; focused dashboard tests and the configured project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

