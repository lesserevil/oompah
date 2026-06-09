---
id: TASK-472.8
title: Benchmark in representative environment and decide go/no-go for default
status: Done
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 21:02'
labels:
  - 'needs:backend'
dependencies: []
parent_task_id: TASK-472
priority: high
ordinal: 197000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Run scripts/bench_server.py (and a realistic mixed workload) in a representative deployment environment. Record numbers and decide whether to make granian the default server. Until then it stays opt-in behind --server granian.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Benchmark numbers recorded in the plan doc
- [ ] #2 Documented go/no-go decision on making granian default
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 15:44
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 15:46
---
Understanding: As Duplicate Investigator, I searched for similar tasks. TASK-473.1 overlaps in tool use (bench_server.py + mixed workload) but serves a different purpose (latency bottleneck profiling for the event-loop epic, not a go/no-go decision for granian-as-default). No true duplicate found. TASK-472.8 is unique. Proceeding with the work: run scripts/bench_server.py, record numbers, decide go/no-go, update doc-1.
---
<!-- COMMENTS:END -->
