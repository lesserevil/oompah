---
id: TASK-473.1
title: Profile request latency under load to confirm the true bottleneck
status: Open
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 16:06'
labels:
  - performance
dependencies: []
parent_task_id: TASK-473
priority: high
ordinal: 199000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Before optimizing, profile end-to-end request/WebSocket latency under realistic load to confirm where time actually goes (HTTP layer vs orchestrator vs subprocess/LLM). Use scripts/bench_server.py plus a mixed real-workload scenario. Output guides the rest of this epic.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Documented latency breakdown under load (HTTP vs orchestrator vs blocking calls)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 14:32
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 14:32
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 15:45
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 15:48
---
Understanding: No duplicate confirmed. TASK-472.8 is the closest match (also uses bench_server.py + mixed workload) but its goal is benchmarking Granian vs. default for a go/no-go adoption decision — not a latency breakdown by layer. TASK-473.1 is distinct: profile WHERE time goes (HTTP vs orchestrator vs subprocess/LLM) under load to guide the TASK-473 optimization epic. Proceeding with profiling work: explore scripts/bench_server.py, run a mixed-workload scenario, and produce a documented latency breakdown.
---

author: oompah
created: 2026-06-09 15:54
---
Discovery: scripts/bench_server.py was referenced in the Granian migration doc (doc-1) but intentionally not committed (plan-only commit df80546). It must be created fresh. Key findings from code analysis: (1) Server already has latency instrumentation via _record_api_latency() for /api/v1/state and /api/v1/issues, and orchestrator_metrics in the state snapshot (added by TASK-469.1). (2) Hot blocking sites in server.py: ~4 sync open() calls in foci/attachment routes (lines 4793, 4826, 4889, 5645), urllib.request.urlopen (lines 4141, 4178, 4308), one run_in_executor (line 660). (3) The orchestrator tick and dispatch metrics are already captured in get_snapshot(). Plan: create scripts/bench_server.py (mixed workload benchmarker), document latency breakdown in plans/, add unit tests for the helper functions.
---

author: oompah
created: 2026-06-09 16:05
---
Implementation: Created three deliverables for TASK-473.1: (1) scripts/bench_server.py — a mixed-workload benchmarking script using asyncio + httpx that measures p50/p90/p95/p99 latency for favicon (HTTP-only baseline), /api/v1/state, /api/v1/issues, and the dashboard HTML route; cross-validates with server-side api_metrics and orchestrator_metrics; prints layer breakdown and bottleneck summary; supports --json output for machine-readable results and CI/CD comparison. (2) plans/request-latency-profiling.md — documents the architecture, static analysis of ~10 blocking sites (3 urllib.urlopen on event loop, 4 sync open() calls, 2 run_in_executor), expected latency table by layer, how to interpret green/yellow/red output, and relationship to TASK-472.8 / TASK-473.2/.3/.4. (3) tests/test_bench_server.py — 26 unit tests covering percentile(), RouteResult stats, to_dict(), arg parser, and ROUTES constant.
---
<!-- COMMENTS:END -->
