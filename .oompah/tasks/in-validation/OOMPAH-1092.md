---
id: OOMPAH-1092
type: bug
status: In Validation
priority: 1
title: Do not let suspended terminal audits starve active dispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T16:02:12.775197Z'
updated_at: '2026-08-11T17:28:11.496565Z'
work_branch: OOMPAH-1092
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/828
review_number: '828'
review_head: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: terminal-audit-suspended-candidate-starvation-20260811
  request_fingerprint: 68772903779a44f84bd9b470b5fc1ed7cbe623f05a4cd03711601f9ccf5375f4
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1092
  base_branch: main
  base_sha: 3264da6780e35b10f759de8aade7b3509977bbb9
  head_sha: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
  submitted_at: '2026-08-11T16:42:26.075292+00:00'
  updated_at: '2026-08-11T16:51:00.742316+00:00'
oompah.work_branch: OOMPAH-1092
oompah.review_url: https://github.com/lesserevil/oompah/pull/828
oompah.review_number: '828'
oompah.target_branch: main
oompah.review_head: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-e2e2f80707ad
    project_id: proj-14849f1b
    task_id: OOMPAH-1092
    digest: 17602685e9446493caf47e87af8fdc62bd483b6d13205ae49dc654ca5e88d59a
  - version: 1
    audit_id: audit-592cc86088a4
    project_id: proj-14849f1b
    task_id: OOMPAH-1092
    digest: 17602685e9446493caf47e87af8fdc62bd483b6d13205ae49dc654ca5e88d59a
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e2e2f80707ad
    project_id: proj-14849f1b
    task_id: OOMPAH-1092
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 17602685e9446493caf47e87af8fdc62bd483b6d13205ae49dc654ca5e88d59a
    attempts:
    - version: 1
      attempt_id: attempt-c657832cd0a5
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 17602685e9446493caf47e87af8fdc62bd483b6d13205ae49dc654ca5e88d59a
      created_at: '2026-08-11T17:28:09.416497+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T17:28:09.416497+00:00'
      branch_key: OOMPAH-1092
      selected_ref: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
      selected_sha: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T17:09:25.284230+00:00'
    eligible_at: '2026-08-11T17:09:25.284230+00:00'
    selected_ref: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
    selected_sha: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
    updated_at: '2026-08-11T17:28:09.416497+00:00'
  - version: 1
    audit_id: audit-592cc86088a4
    project_id: proj-14849f1b
    task_id: OOMPAH-1092
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 17602685e9446493caf47e87af8fdc62bd483b6d13205ae49dc654ca5e88d59a
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T17:09:25.284230+00:00'
    prerequisite_audit_id: audit-e2e2f80707ad
    selected_ref: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
    selected_sha: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
  attempt_history:
  - version: 1
    attempt_id: attempt-c657832cd0a5
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 17602685e9446493caf47e87af8fdc62bd483b6d13205ae49dc654ca5e88d59a
    created_at: '2026-08-11T17:28:09.416497+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T17:28:09.416497+00:00'
    branch_key: OOMPAH-1092
    selected_ref: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
    selected_sha: a355a5ddd3dd006f1bdd2187cfe83b9333b9468a
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 16:35
---
Implementation review-ready and pushed at exact head a355a5ddd3dd006f1bdd2187cfe83b9333b9468a on branch OOMPAH-1092. Scheduler now separates the scan-bounded observation corpus from the active operation budget, snapshots pause authority once per project-list read, excludes suspended work from active priority blockers, preserves the durable cursor/health cycle, and exposes active_operation_count plus observation_limit. Deterministic regression reproduces the live 9 higher-priority suspended + 1 lower-priority active shape under operation_limit=8: the active audit launches once in one lane cut, all 9 suspended audits remain visible, active operations=1, candidate_scan_complete=true, no continuation/spin, and no runtime overrun. Evidence in branch-local .venv: 945 focused/surrounding scheduler-health-restart tests passed in 23.85s; final direct scheduler/health rerun 137 passed in 3.51s; make terminal-audit-scan passed 21/21; git diff --check and commit secret hooks passed. An attempted complete gate was deliberately cancelled at 46% after detecting that its initial invocation had been pointed at the shared operator venv; it had no failures before cancellation and is not claimed as evidence. Work is pushed but intentionally not submitted pending independent exact-head review.
---
author: oompah
created: 2026-08-11 16:40
---
Fresh independent review ACCEPTED exact head a355a5ddd3dd006f1bdd2187cfe83b9333b9468a. Reviewer independently reproduced one-cut dispatch for the live 9-suspended plus 1-active shape (1 dispatch, 1/8 active operations, 10 scanned, 9 suspended) and zero duplicate dispatch on the next cut; verified once-per-project suspension snapshots, fail-closed read errors, strict active priority/cursor/continuation semantics, and truthful bounded health metrics. Independent evidence: 545 terminal-audit tests, 252 observability/config tests, 172 scheduler/health tests, terminal mutation scan 21/21, clean diff. Holding submission only while OOMPAH-1085 owns the sole canonical validation slot; not merged.
---
author: oompah
created: 2026-08-11 16:42
---
Keep suspended terminal-audit observations from consuming active operation capacity; snapshot pause authority once per project and dispatch active work within one bounded lane cut.
---
author: oompah
created: 2026-08-11 16:48
---
Branch quality gate passed for `a355a5ddd3dd006f1bdd2187cfe83b9333b9468a` using `make test` in 189.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 17:02
---
Branch quality gate passed for `a355a5ddd3dd006f1bdd2187cfe83b9333b9468a` using `make test` in 181.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 17:09
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
