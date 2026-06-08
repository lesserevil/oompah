---
id: TASK-465.2
title: Define serialized dispatch lane and maintenance lane contract
status: Done
assignee: []
created_date: 2026-06-08 18:47
updated_date: 2026-06-08 19:32
labels:
- task
- tick-latency
- dispatch-performance
dependencies:
- TASK-465.1
priority: 0
references:
- oompah/orchestrator.py
modified_files:
- oompah/orchestrator.py
- tests/test_orchestrator_handlers.py
parent_task_id: TASK-465
ordinal: 3
oompah.task_costs:
  total_input_tokens: 72
  total_output_tokens: 31025
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 72
      output_tokens: 31025
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 72
    output_tokens: 31025
    cost_usd: 0.0
    recorded_at: '2026-06-08T19:32:38.457326+00:00'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Design and implement the scheduling contract that keeps candidate claiming and agent startup serialized while allowing non-critical maintenance work to run on separate bounded lanes. Introduce explicit lane names, ownership rules for shared mutable state, and a single place where tick events are coalesced into dispatch work versus maintenance work.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Candidate selection, issue claiming, and _dispatch() remain single-owner and cannot run concurrently with another dispatch selection pass.
- [ ] #2 Maintenance jobs have explicit lane names and do not block the dispatch lane except where their outputs are required for correctness.
- [ ] #3 Repeated tick requests coalesce instead of piling up unbounded full-tick work.
<!-- AC:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-08 19:19

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-08 19:19

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-08 19:32

Agent completed successfully in 785s (31097 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-08 19:32

Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 119, Tool calls: 75
- Tokens: 72 in / 31.0K out [31.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 13m 5s
- Log: TASK-465.2__20260608T191958Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
