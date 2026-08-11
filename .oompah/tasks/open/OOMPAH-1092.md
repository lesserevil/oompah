---
id: OOMPAH-1092
type: bug
status: Open
priority: 1
title: Do not let suspended terminal audits starve active dispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T16:02:12.775197Z'
updated_at: '2026-08-11T16:02:54.486476Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: terminal-audit-suspended-candidate-starvation-20260811
  request_fingerprint: 68772903779a44f84bd9b470b5fc1ed7cbe623f05a4cd03711601f9ccf5375f4
---
## Summary

Live regression on deployed main 41de8026c53d3d280d5673349792d637444a0815 after OOMPAH-947 and OOMPAH-1013: terminal-audit telemetry repeatedly reported 10 discovered candidates and an 8-operation bounded scan. Nine candidates belonged to intentionally paused Trickle projects and were correctly non-dispatchable/suspended, while active eligible OOMPAH-1089 had pending Merged audit work and free auditor capacity. The suspended candidates nevertheless consumed the default operation/priority window, so each tick exhausted the 8-operation budget before reaching OOMPAH-1089; the eligible audit was starved for more than seven minutes with zero active auditors and nine free auditor slots. Raising OOMPAH_AUDIT_LANE_SCAN_LIMIT and OOMPAH_AUDIT_LANE_OPERATION_LIMIT to 32 made the same 10-candidate scan complete and immediately launched OOMPAH-1089's audit, confirming bounded-window accounting as the cause rather than transport or capacity.

Implementation scope: make paused, suspended, or otherwise dispatch-ineligible terminal-audit candidates cheap observational entries that do not consume the operation/priority capacity reserved for active dispatch-eligible work. Preserve bounded total work and truthful health projection for suspended obligations. Define and enforce a bounded cursor/window rule that guarantees every active eligible candidate is considered within an explicit scheduler SLO even when more than operation_limit higher-priority suspended candidates precede it. Keep project fairness, strict priority among active launchable audits, durable cursor/restart behavior, exact audit ownership, launch/finalization fencing, pause/resume semantics, and coalesced continuations. candidate_scan_complete must remain false while the observation corpus is incomplete, become true only after a complete fair cycle, and continuation scheduling must make forward progress without a tight loop or duplicate launch.

Relevant code/context: Orchestrator._dispatch_audit_lane, _audit_candidate_window, operation/runtime budget accounting, paused-project suspension projection, terminal-audit cursor persistence, candidate_scan_complete health state, and scheduler continuation requests in oompah/orchestrator.py plus terminal audit observability/config tests.

Required tests: create more than operation_limit high-priority candidates in paused/suspended projects followed by an active eligible candidate with idle auditor capacity; prove the active candidate is launched within the stated bounded number of lane continuations without increasing the configured operation limit. Cover cursor rotation and restart persistence, pause-to-resume eligibility, candidate additions/removals, strict priority among simultaneously active eligible candidates, candidate_scan_complete truth across partial slices, continuation coalescing/no spin, exactly-once launch, and deterministic operation/runtime bounds. Include a control showing suspended obligations remain visible in suspended health metrics but cannot starve active dispatch.

Acceptance criteria: with the live 9-suspended-plus-1-active shape and the default 8-operation limit, the active audit launches within the documented SLO while the lane stays within configured operation/runtime bounds; repeated ticks visit the full corpus fairly; no duplicate launch, lost suspended obligation, stale healthy claim, action-required alert, or manual limit increase is required; focused terminal-audit scheduler/observability/restart tests and the project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

