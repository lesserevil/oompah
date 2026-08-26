---
id: OOMPAH-1344
type: task
status: Ready to Integrate
priority: 1
title: Bound workflow reconciliation and deduplicate forge observations
parent: OOMPAH-1342
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-26T18:43:10.725032Z'
updated_at: '2026-08-26T22:52:20.485408Z'
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
oompah.lifecycle_revision: 3
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
<!-- COMMENTS:END -->
