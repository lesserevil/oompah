---
id: TASK-472.8
title: Benchmark in representative environment and decide go/no-go for default
status: Backlog
assignee: []
created_date: '2026-06-09 04:19'
labels:
  - 'needs:backend'
dependencies: []
parent_task_id: TASK-472
priority: medium
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
