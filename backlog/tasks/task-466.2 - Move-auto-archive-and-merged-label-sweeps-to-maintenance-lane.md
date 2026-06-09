---
id: TASK-466.2
title: Move auto-archive and merged-label sweeps to maintenance lane
status: Done
assignee: []
created_date: 2026-06-08 18:48
updated_date: 2026-06-09 00:39
labels:
- task
- tick-latency
- maintenance
dependencies:
- TASK-466.1
references:
- oompah/orchestrator.py
modified_files:
- oompah/orchestrator.py
- tests/test_orchestrator_merged.py
parent_task_id: TASK-466
ordinal: 7
oompah.task_costs:
  total_input_tokens: 211
  total_output_tokens: 23344
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 211
      output_tokens: 23344
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 140
    output_tokens: 4833
    cost_usd: 0.0
    recorded_at: '2026-06-08T20:08:45.515621+00:00'
  - profile: default
    model: unknown
    input_tokens: 71
    output_tokens: 18511
    cost_usd: 0.0
    recorded_at: '2026-06-09T00:34:56.798049+00:00'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move auto-archive, merged issue labeling, merged epic labeling, and stale In Review reconciliation out of the dispatch-critical tick path. Keep forge-state reuse where helpful, but allow the sweeps to run on their own cadence with bounded runtime and idempotent retries.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Archive and merged-label sweeps run on a maintenance cadence and do not block candidate dispatch.
- [ ] #2 Closed merged tasks still transition to Merged/Archived correctly after the maintenance job runs.
- [ ] #3 Failures are logged once per fingerprint or surfaced in diagnostics without spamming every tick.
<!-- AC:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-08 19:50

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-08 19:50

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-08 20:08

Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 95
- Tokens: 140 in / 4.8K out [5.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 18m 21s
- Log: TASK-466.2__20260608T195117Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-08 23:05

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-08 23:05

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-09 00:05

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-09 00:05

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-09 00:35

Agent completed successfully in 1758s (18582 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-09 00:35

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 119, Tool calls: 81
- Tokens: 71 in / 18.5K out [18.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 29m 18s
- Log: TASK-466.2__20260609T000658Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 10
author: oompah
created: 2026-06-09 00:35

Agent completed without closing this issue (1758s (18582 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 11
author: oompah
created: 2026-06-09 00:39

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
