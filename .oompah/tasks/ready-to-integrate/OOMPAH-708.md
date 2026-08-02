---
id: OOMPAH-708
type: task
status: Ready to Integrate
priority: null
title: Repair duplicate-screening owner-resolution project lookup
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-02T22:20:11.202634Z'
updated_at: '2026-08-02T22:22:52.623007Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-708
  head_sha: b965154dbf216ffb3587f59c2eb30aa681c73796
  submitted_at: '2026-08-02T22:22:47.553512+00:00'
  updated_at: '2026-08-02T22:22:47.553512+00:00'
---
## Summary

Triggered by: OOMPAH-706\n\nProduction reproduction on 2026-08-02: authenticated POST /api/v1/issues/OOMPAH-706/duplicate-screening/owner-resolution returned HTTP 503 with `Orchestrator object has no attribute _get_project_by_id`. The route calls orch._get_project_by_id(project_id), but Orchestrator exposes project_store.get instead. This makes the documented recovery action for exhausted duplicate screening unusable and strands tasks in Needs Human.\n\nImplementation scope:\n- Resolve the managed project through the supported ProjectStore API in the owner-resolution route.\n- Preserve authenticated-principal/actor-conflict checks and fail closed when the project is absent.\n- Ensure owner authorization receives the actual managed Project object.\n\nRelevant code: oompah/server.py api_owner_resolve_duplicate_screening; tests/test_server_duplicate_screening_owner.py.\n\nRequired tests:\n- Reproduce the route against an Orchestrator-shaped object without _get_project_by_id and prove a valid owner request succeeds.\n- Prove missing projects and non-owner principals remain denied without mutating duplicate metadata.\n\nAcceptance criteria:\n- The live owner-resolution endpoint no longer returns 503 for a valid managed project.\n- OOMPAH-706 can be authoritatively returned from Needs Human to Open.\n- Focused tests and make test/check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 22:20
---
Claimed directly to unblock the currently stranded OOMPAH-706 owner-resolution flow. OOMPAH-707 separately tracks the watchdog resetting direct owner work without a scheduler runtime.
---
author: oompah
created: 2026-08-02 22:22
---
Replaced the nonexistent orchestrator project lookup with ProjectStore.get, added fail-closed missing-project handling, and added endpoint regressions. Focused tests: 5 passed. Secret scan passed.
---
<!-- COMMENTS:END -->
