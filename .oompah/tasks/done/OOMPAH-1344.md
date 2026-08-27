---
id: OOMPAH-1344
type: task
status: Done
priority: 1
title: Bound workflow reconciliation and deduplicate forge observations
parent: OOMPAH-1342
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-26T18:43:10.725032Z'
updated_at: '2026-08-27T01:56:33.041962Z'
work_branch: OOMPAH-1344
target_branch: main
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: manual-service-recovery-20260826-reconcile
  request_fingerprint: e6c78ba0978cc6d0161af8a4dfd78cefb2d4c74f979a7ef712c76116bc784ea9
oompah.lifecycle_revision: 4
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  post_landed_parent_id: OOMPAH-1342
  task_branch: OOMPAH-1344
  base_branch: main
  base_sha: d258fc16b1478ff902139c66cdb3e51fa96d209c
  head_sha: f74fdd4cf5d6370c502dfdf317f511645a75d54d
  submitted_at: '2026-08-26T20:29:33.494624+00:00'
  updated_at: '2026-08-26T20:29:33.494624+00:00'
oompah.work_branch: OOMPAH-1344
oompah.target_branch: main
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-8e8a06d21a0c
    project_id: proj-14849f1b
    task_id: OOMPAH-1344
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a524eb9e788ead25a6014b0488e93928be2667f23f3a4cdba2b0a18d3585fe12
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct owner completed implementation; exact commits are on the published
      epic branch and make test passed with 20,449 tests.
    created_at: '2026-08-26T22:53:14.353836+00:00'
    selected_ref: f74fdd4cf5d6370c502dfdf317f511645a75d54d
    selected_sha: f74fdd4cf5d6370c502dfdf317f511645a75d54d
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1344
    target_state: Done
    evidence_fingerprint: a524eb9e788ead25a6014b0488e93928be2667f23f3a4cdba2b0a18d3585fe12
    workflow_revision: null
    selected_ref: f74fdd4cf5d6370c502dfdf317f511645a75d54d
    selected_sha: f74fdd4cf5d6370c502dfdf317f511645a75d54d
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-26T22:53:23.375823+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: 'Implementation is merged to main in PR #951 at 13718ac1c; retain the
      completed child as terminal provenance.'
    marked_at: '2026-08-26T23:12:45.865758+00:00'
    updated_at: '2026-08-26T23:12:45.865758+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: 'Implementation is merged to main in PR #951 at 13718ac1c; retain the
        completed child as terminal provenance.'
      recorded_at: '2026-08-26T23:12:45.865758+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Implement workstream 2 of plans/service-throughput-recovery.md. Profile the durable integration/review fact paths and cache project-scoped review, CI, branch-head, parent, and landing observations for one generation-bound world scan. Skip expensive terminal-task work only when complete durable landing/provenance evidence proves it safe. Preserve stale-authority rejection and all exact-head/project fences. Add production-shaped tests under tests/ that use hundreds of Done/Ready tasks and assert SCM calls are bounded by distinct evidence keys; include mutation/supersede regressions and a deterministic runtime-budget test. Acceptance: the Trickle-sized fixture completes within the configured restart-convergence budget with no unexplained liveness divergence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-26 18:56
---
Direct implementation ownership assigned to the current manual recovery session (owner claim: shedwards). The project is paused and the human-only fence is present; do not dispatch this task to an autonomous worker.
---
author: oompah
created: 2026-08-26 19:20
---
Added generation-scoped integration resolver and review-provider caches. Focused workflow tests pass (366).
---
author: oompah
created: 2026-08-26 19:28
---
Generation-scoped caches deduplicate review listings and parent landing resolution while preserving exact authority boundaries; focused workflow tests pass.
---
author: oompah
created: 2026-08-26 19:30
---
Implementation complete under direct owner claim; focused tests pass.
---
author: oompah
created: 2026-08-26 19:31
---
Direct implementation is committed and pushed. Keep this task reserved for the current manual recovery session; do not dispatch it to the oompah worker.
---
author: oompah
created: 2026-08-26 20:26
---
Validation update: combined focused suites pass (756 tests). Full make test reached 20,447 passed with only tests/test_restart_api.py::test_repeated_replacement_timeout_detection_under_load timing out under parallel load; rerunning that test alone passes. No product failure observed.
---
author: oompah
created: 2026-08-26 20:29
---
Generation-scoped caches deduplicate review listings and parent landing resolution while preserving exact authority boundaries; focused workflow tests pass.
---
author: oompah
created: 2026-08-26 21:36
---
Implementation is committed, pushed, and present on the published epic branch. The complete make test gate passes functionally except for the known parallel-only 5-second restart stress timeout; that exact test passes in isolation. Awaiting integration while the project remains paused.
---
author: oompah
created: 2026-08-26 22:50
---
Full repository test gate completed successfully: 20,449 passed, 7 skipped, 2 xfailed. Changes are pushed and included in epic PR #951.
---
author: oompah
created: 2026-08-26 22:53
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct owner completed implementation; exact commits are on the published epic branch and make test passed with 20,449 tests.
---
author: oompah
created: 2026-08-27 01:56
---
Additional network-I/O fix is in PR #957: authoritative target refs are now observed with one stable multi-ref ls-remote/fetch per project reconciliation rather than once per task. Focused project/runtime tests: 435 passed. Production measurement before this follow-up remained 155.7-200.9s, dominated by Oompah integration (112.8-180.5s); project was re-paused after measurement.
---
<!-- COMMENTS:END -->
