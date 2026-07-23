---
id: OOMPAH-414
type: task
status: In Progress
priority: null
title: Prevent scheduler stalls from delaying task dispatch
parent: null
children:
- OOMPAH-415
- OOMPAH-416
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-23T19:20:53.199562Z'
updated_at: '2026-07-23T19:34:31.056925Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 28e0109e-70af-4e36-a8db-f4dbcd7ab473
oompah.task_costs:
  total_input_tokens: 1908857
  total_output_tokens: 9597
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1908857
      output_tokens: 9597
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 1908857
    output_tokens: 9597
    cost_usd: 0.0
    recorded_at: '2026-07-23T19:30:17.272684+00:00'
---
## Summary

Investigate and fix the event-driven scheduler stall observed on 2026-07-23: after the Exocomp task push, the last completed tick and state snapshot remained at 19:15 UTC with no running agents and no new dispatch. The current stale-loop recovery threshold is full_sync_interval × factor (15 minutes), delaying recovery. Identify the blocking tick phase from diagnostics, ensure maintenance work cannot starve the dispatch loop, and make stale-dispatch recovery prompt and observable. Add regression coverage for the observed stall/recovery path and run make test. Acceptance: a stalled scheduler recovers before newly opened work is delayed for the current 15-minute threshold; clean eligible Exocomp tasks dispatch after recovery.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 19:23
---
Operational recovery completed: restarted the stale scheduler at 19:21 UTC. Its first fresh tick found 43 Exocomp candidates but no ready work because EXOCOMP-7 and EXOCOMP-41 were still orphaned In Progress during selection. Maintenance reset both to Open after selection; I posted /api/v1/refresh, and the scheduler dispatched both at 19:22:57–19:22:59 UTC. Permanent investigation remains: heartbeat recovery waits 15 minutes (300s full-sync × factor 3), and orphan resets should request a prompt dispatch refresh.
---
author: oompah
created: 2026-07-23 19:23
---
Scheduler recovered and Exocomp roots dispatched; permanent stale-loop recovery improvement remains in progress.
---
author: oompah
created: 2026-07-23 19:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 19:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 19:30
---
Understanding: Duplicate screening for the 2026-07-23 scheduler stall. I will compare the full canonical records of earlier stale-loop, scheduler-wedge, diagnostics, and maintenance tasks against this incident. This focus will not implement code; it will either archive a confirmed duplicate or hand the unique gap to a backend implementation focus.
---
author: oompah
created: 2026-07-23 19:30
---
Discovery: No duplicate confirmed. OOMPAH-348/349/350/352 delivered bounded tracker refreshes, scheduler/API loop isolation, and first-stall diagnostics, but did not shorten the full_sync_interval × factor stale-recovery window or wake dispatch after maintenance reopens orphaned work. OOMPAH-406/407 only changed stale diagnostic/alert logging from ERROR to WARNING to prevent error-watcher noise; they did not address dispatch latency or maintenance starvation. The July 23 recurrence after those changes is a distinct reliability gap.
---
author: oompah
created: 2026-07-23 19:30
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate found; OOMPAH-414 is a distinct post-hardening scheduler reliability gap.
2. Evidence: Full canonical records reviewed for OOMPAH-348, OOMPAH-349, OOMPAH-350, OOMPAH-352, OOMPAH-406, and OOMPAH-407, plus the earlier dispatch-heartbeat implementation commit. The OOMPAH-348 family bounds tracker reads, isolates the scheduler from HTTP, and captures stall diagnostics. OOMPAH-406/407 suppress error-watcher auto-filing. None makes stale recovery prompt, keeps maintenance from starving dispatch, or requests a new dispatch pass after orphan resets.
3. Relevant context: oompah/orchestrator.py contains stale-loop supervision, tick phase/maintenance ordering, and orphan reset behavior; tests/test_dispatch_loop_heartbeat.py contains existing stale recovery coverage; docs/tick-latency-diagnostics.md describes long-tick observability. No source changes were made in this focus.
4. Remaining work/risks: inspect the July 23 diagnostic artifact to identify the blocking phase; bound or decouple maintenance from dispatch; wake dispatch when orphan maintenance makes tasks eligible; choose an independently prompt and observable stale threshold; add regression coverage for the observed stall/recovery and clean Exocomp dispatch; run make test. Recommended next focus: feature (backend scheduler implementation).
---
author: oompah
created: 2026-07-23 19:30
---
Agent completed successfully in 268s (1918454 tokens)
---
author: oompah
created: 2026-07-23 19:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 24
- Tokens: 1.9M in / 9.6K out [1.9M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 28s
- Log: OOMPAH-414__20260723T192550Z.jsonl
---
author: oompah
created: 2026-07-23 19:30
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-23 19:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 19:30
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-23 19:33
---
Understanding: Epic planner focus for OOMPAH-414. The July 23 stall exposed two gaps in the scheduler:

1. Stale-dispatch recovery is coupled to full_sync_interval × dispatch_loop_stale_factor (300s × 3 = 15 min detection, then +300s grace = up to 20 min before restart). The fix is to add a dedicated OOMPAH_DISPATCH_STALE_THRESHOLD_MS (default ~120s) independent of full_sync_interval.

2. _reset_orphaned_in_progress() (step 5c, fire-and-forget) resets orphaned tasks to Open but never posts REFRESH_REQUESTED—operators had to call /api/v1/refresh manually. The fix: after resetting ≥1 orphan, call self._post_event(REFRESH_REQUESTED). _post_event is already thread-safe.

Key files: oompah/orchestrator.py (stale detection, check_and_recover_dispatch_loop, _reset_orphaned_in_progress), oompah/config.py (dispatch_loop_stale_factor, full_sync_interval_ms), tests/test_dispatch_loop_heartbeat.py, docs/tick-latency-diagnostics.md.

Plan: decompose into 3 child tasks—(1) lower stale threshold independently, (2) wake dispatch after orphan resets, (3) regression tests + make test verification.
---
<!-- COMMENTS:END -->
