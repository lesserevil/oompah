---
id: OOMPAH-742
type: feature
status: Open
priority: 1
title: Replace stacked dashboard banners with a compact alert center
parent: OOMPAH-740
children: []
blocked_by:
- OOMPAH-741
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T22:56:17.550824Z'
updated_at: '2026-08-03T23:01:21.312676Z'
work_branch: epic-OOMPAH-740--task-OOMPAH-742
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6380acf6cb02a369f8a5d0ac580523b98cd20810c4347ded4c5d30e0e753180c
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 24557270-31dc-4c8f-b4fe-8325f59fd049
  claim_owner: a032ecbf-d61c-48ca-9cba-cbf452c15431
  claimed_at: '2026-08-03T23:00:13.916343+00:00'
  claim_expires_at: '2026-08-03T23:30:13.916343+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: fc13532a-2a41-462a-ad0b-5c0f46db1c81
oompah.work_branch: epic-OOMPAH-740--task-OOMPAH-742
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-740--task-OOMPAH-742
  base_branch: epic-OOMPAH-740
  base_sha: 583fb236963493a820f36eabdd29789fa5497e6b
  updated_at: '2026-08-03T23:01:17.028172+00:00'
---
## Summary

Replace the current collection of always-visible warning and health banners with one compact operator alert center while preserving access to all relevant information.

Scope:
- Remove the duplicate generic rendering in the agent bar and Oompah alerts banner.
- Render a single collapsed summary showing the actionable count and highest severity, with a clear control to expand details.
- Enforce a strict viewport-relative maximum height and internal scrolling for expanded details so the Kanban board retains meaningful visible space.
- Move healthy repository inventory, running quality gates, normal audit throughput, authentication status, and other non-actionable facts into a compact status or diagnostics view that does not displace the board.
- Render each stable alert identity once even if multiple legacy fields contain it during migration.
- Preserve responsive layout, existing board scroll owners, drag and drop, dynamic appearance and clearing, keyboard navigation, focus management, and aria-live behavior without repeatedly announcing full transcripts.

Relevant files: oompah/templates/dashboard.html and dashboard UI tests under tests/.

Required tests:
- No alerts, one alert, many alerts, mixed severity, and expanded or collapsed states.
- Duplicate generic and dedicated health facts render once.
- The board remains visible and scrollable at common desktop viewport heights.
- Dynamic alert addition and removal does not corrupt layout or focus.
- Keyboard and accessible-name assertions cover the disclosure control and alert list.

Acceptance criteria:
- The default dashboard view is board-first, not alert-first.
- Alerts consume at most the compact summary height until an operator explicitly expands them.
- Expanded details are bounded and independently scrollable.
- No condition is repeated in both the agent bar and a banner.
- Focused dashboard tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 23:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 23:01
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
