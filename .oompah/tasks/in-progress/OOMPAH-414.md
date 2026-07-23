---
id: OOMPAH-414
type: task
status: In Progress
priority: null
title: Prevent scheduler stalls from delaying task dispatch
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T19:20:53.199562Z'
updated_at: '2026-07-23T19:23:35.065344Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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
<!-- COMMENTS:END -->
