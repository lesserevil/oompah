---
id: TASK-389
title: >-
  Budget window: align rolls to calendar boundaries (top of hour, midnight,
  Sunday 00:00)
status: In Progress
assignee: []
created_date: '2026-05-05 20:18'
updated_date: '2026-06-01 16:03'
labels:
  - feature
  - beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: feature
beads:
  id: oompah-zlz_2-54k
  state: open
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-54k
  target_branch: null
  url: null
  created_at: '2026-05-05T20:18:01Z'
  updated_at: '2026-05-05T20:18:01Z'
  closed_at: null
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The rolling budget window from commit 331a895 starts whenever the first budget check fires (typically the moment the orchestrator boots) and rolls every N seconds from there. So an "hour" window started at 14:17:23 resets at 15:17:23 the following hour, not at 15:00.

Operators think in calendar boundaries — "$50 this hour" means top-of-hour to top-of-hour, not "$50 in any 60-minute span starting whenever the process happened to boot". Same for day (midnight to midnight) and week (Saturday-midnight to Saturday-midnight, i.e. window resets at Sunday 00:00).

Update the budget windowing to align to natural calendar boundaries:
- hour: window resets at :00:00 of each hour (e.g. 14:00, 15:00, 16:00).
- day: window resets at 00:00:00 of each calendar day (local midnight).
- week: window resets at 00:00:00 Sunday (the transition between Saturday-night and Sunday-morning).

Implementation sketch:
- Replace _budget_window_seconds() arithmetic and _roll_budget_window_if_due()'s `now - start >= window_seconds` check with a calendar-aware "is now past the next boundary" check using datetime.
- On cold start, snap budget_window_start to the *previous* boundary (so spend already accumulated in the current period is correctly attributed).
- Persist budget_window_start as the Unix timestamp of the snapped boundary, not the moment of first-check.
- Timezone: default to the host's local timezone (most operators think in local time); offer OOMPAH_BUDGET_TIMEZONE env var for explicit IANA names (e.g. "America/Los_Angeles", "UTC").
- DST-safe: use zoneinfo (Python 3.9+) so day/week boundaries handle the spring-forward / fall-back correctly. The "next midnight" is whatever the timezone says it is, not naive-UTC arithmetic.

Plan: pairs with the existing windowed-budget work (commit 331a895). This is a refinement, not a rewrite — the persistence shape doesn't change, only the boundary computation.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
