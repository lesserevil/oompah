---
id: OOMPAH-1345
type: task
status: Done
priority: 1
title: Serve reviews API from a bounded generation-aware snapshot
parent: OOMPAH-1342
children: []
blocked_by:
- OOMPAH-1344
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-26T18:43:16.245447Z'
updated_at: '2026-08-26T22:53:45.464795Z'
work_branch: OOMPAH-1345
target_branch: main
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: manual-service-recovery-20260826-reviews-api
  request_fingerprint: 5a3db0f23c9f70bbbab1f418eae47d0ecb3157c46df451e04969ebec76c5df55
oompah.lifecycle_revision: 4
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  post_landed_parent_id: OOMPAH-1342
  task_branch: OOMPAH-1345
  base_branch: main
  base_sha: d258fc16b1478ff902139c66cdb3e51fa96d209c
  head_sha: f13ca97b66bea10214dadec8464737557a4a04e8
  submitted_at: '2026-08-26T20:30:13.595059+00:00'
  updated_at: '2026-08-26T20:30:13.595059+00:00'
oompah.work_branch: OOMPAH-1345
oompah.target_branch: main
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-d7cbada03f12
    project_id: proj-14849f1b
    task_id: OOMPAH-1345
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6459838e31d8def8b65f223e1d10fb86fdbc2f0a6fce6b134d7268edc4d1deaa
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct owner completed implementation; exact commits are on the published
      epic branch and make test passed with 20,449 tests.
    created_at: '2026-08-26T22:53:34.544899+00:00'
    selected_ref: f13ca97b66bea10214dadec8464737557a4a04e8
    selected_sha: f13ca97b66bea10214dadec8464737557a4a04e8
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1345
    target_state: Done
    evidence_fingerprint: 6459838e31d8def8b65f223e1d10fb86fdbc2f0a6fce6b134d7268edc4d1deaa
    workflow_revision: null
    selected_ref: f13ca97b66bea10214dadec8464737557a4a04e8
    selected_sha: f13ca97b66bea10214dadec8464737557a4a04e8
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-26T22:53:43.992668+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Implement workstream 3 of plans/service-throughput-recovery.md. Refactor GET /api/v1/reviews so a cache miss does not synchronously fetch all forge reviews. Maintain a bounded generation-aware snapshot using existing background/event-driven refresh paths; expose stale and per-project unavailable metadata while retaining successful sibling data. Add route, cache invalidation, webhook refresh, timeout, and partial-provider-failure tests in tests/. Acceptance: cold API requests perform no forge network calls and return promptly, while background refreshes advance exact project generations without stale resurrection.

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
created: 2026-08-26 19:22
---
Changed reviews API to serve the scheduler review snapshot without synchronous forge fanout, with generation metadata and regression coverage. Focused API tests pass (58).
---
author: oompah
created: 2026-08-26 19:28
---
Reviews API now returns the scheduler-maintained generation-aware snapshot without request-path forge I/O; focused reviews tests pass.
---
author: oompah
created: 2026-08-26 19:30
---
Implementation complete under direct owner claim; focused tests pass.
---
author: oompah
created: 2026-08-26 19:32
---
Direct implementation is committed and pushed. Keep this task reserved for the current manual recovery session; do not dispatch it to the oompah worker.
---
author: oompah
created: 2026-08-26 20:26
---
Validation update: combined focused suites pass (756 tests). Full make test reached 20,447 passed with only tests/test_restart_api.py::test_repeated_replacement_timeout_detection_under_load timing out under parallel load; rerunning that test alone passes. No product failure observed.
---
author: oompah
created: 2026-08-26 20:30
---
Reviews API now returns the scheduler-maintained generation-aware snapshot without request-path forge I/O; focused reviews tests pass.
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
<!-- COMMENTS:END -->
