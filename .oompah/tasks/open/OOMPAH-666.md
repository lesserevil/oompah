---
id: OOMPAH-666
type: bug
status: Open
priority: 1
title: Fix dashboard vertical scrolling when alerts precede the Kanban board
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T21:19:38.816688Z'
updated_at: '2026-07-31T22:55:44.368395Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c01898d7e202c2aa042354f310604e9ae494bf878078cb88c46a93a66f4bdac1
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 94023074-0e61-42c1-a6ac-624dbea445b7
  claim_owner: 83d630e6-ba64-48af-a521-3ffb6e2a4e3f
  claimed_at: '2026-07-31T22:55:36.185717+00:00'
  claim_expires_at: '2026-07-31T23:25:36.185717+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: d1ccdb04-081d-4609-b73d-d41e7cb79861
---
## Summary

Reproduce and fix the main dashboard layout bug where alert panels or other content above the Kanban board increase the page height but the vertical scroll container remains constrained, preventing the operator from scrolling through the board to its bottom. Inspect the height and overflow rules in oompah/templates/dashboard.html and related dashboard CSS/JavaScript; identify the actual document or application scroll owner and remove conflicting fixed-height, min-height, or overflow clipping without breaking horizontal board scrolling, per-column scrolling, sticky controls, drag and drop, or responsive layouts. Add regression coverage following the existing dashboard test patterns in tests/ that exercises the page with no alerts and with one or multiple alert panels, verifies that content above the board remains visible, and verifies that the viewport or designated vertical container can reach the bottom edge of a board taller than the viewport. Acceptance criteria: on common desktop viewport heights, an operator can scroll continuously from the dashboard header and alerts to the final Kanban row or card; the bottom is not clipped; behavior remains correct when alerts appear or clear dynamically; existing board horizontal and column scrolling behavior is preserved; focused dashboard tests and the configured project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 22:55
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-07-31 22:55
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
