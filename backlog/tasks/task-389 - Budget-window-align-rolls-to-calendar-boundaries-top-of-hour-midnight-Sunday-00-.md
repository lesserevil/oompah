---
id: TASK-389
title: 'Budget window: align rolls to calendar boundaries (top of hour, midnight,
  Sunday 00:00)'
status: Merged
assignee: []
created_date: 2026-05-05 20:18
updated_date: 2026-06-03 04:47
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
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-03 01:05

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-03 01:05

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-03 01:05

Agent failed: OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-03 01:05

Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 7s
- Log: TASK-389__20260603T010551Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-03 01:06

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-03 01:06

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-03 01:06

Agent failed: OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-03 01:06

Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 10s
- Log: TASK-389__20260603T010629Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-03 01:07

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Attempt #7: Implementation verified complete. 3825 tests pass. No duplicate. Calendar-aligned budget windows fully implemented. Closing as Done.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Feature fully implemented in commit a971be9. Calendar-aligned budget windows (top-of-hour, midnight, Sunday 00:00) using zoneinfo, OOMPAH_BUDGET_TIMEZONE env var for explicit IANA timezone, cold-start snapping to previous boundary. DST-safe via Python 3.9+ zoneinfo. 3825 tests pass. No duplicate found.
<!-- SECTION:FINAL_SUMMARY:END -->
