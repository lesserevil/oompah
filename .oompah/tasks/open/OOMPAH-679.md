---
id: OOMPAH-679
type: bug
status: Open
priority: 1
title: Reset activity panel identity when a task starts a new agent run
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T12:05:24.382952Z'
updated_at: '2026-08-01T12:05:26.544129Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live UI regression observed for EXOCOMP-143 on 2026-08-01. A read-only Duplicate Investigator run completed normally at 11:58 with a no-duplicate verdict and zero mutating tool calls. Oompah immediately started a distinct implementation run for the same task with focus_name=chore and focus_role=Maintenance Engineer. The dashboard activity panel continued to show 'Agent: EXOCOMP-143 — Duplicate Investigator · default' while rendering the implementation run's activity, making it appear that the preflight agent violated its role. The client and activity route primarily key state by issue_identifier, which is reused across run boundaries. Implementation scope: expose a stable per-run identity/run id in running snapshots and activity responses; key/reset panel title, cached entries, provider metadata, and polling/WebSocket activity by that identity; update the title even during the brief empty-focus startup state; reject or ignore late activity from superseded runs. Relevant files: orchestrator RunningEntry serialization, /api/v1/state, /api/v1/agents/{identifier}/activity, dashboard activity state/rendering, and WebSocket lifecycle tests. Acceptance criteria: a duplicate-preflight-to-implementation transition on the same task never mixes labels or activity; the old run visibly ends before the new role appears; late old-run events cannot overwrite the new panel; regression coverage reproduces the rapid EXOCOMP-143 transition.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

