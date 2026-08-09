---
id: OOMPAH-968
type: bug
status: In Progress
priority: 1
title: Fence absent-to-retained provenance changes during workflow publication
parent: OOMPAH-940
children: []
blocked_by:
- OOMPAH-967
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T18:30:50.075307Z'
updated_at: '2026-08-09T19:09:23.589823Z'
work_branch: OOMPAH-968
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-968
  base_branch: epic-OOMPAH-940
  base_sha: 2dd74be288b81265ea4a242d7467ecc1ed9f1435
  head_sha: 277a99a1c53d6ce61ec92f88cc85413132ca6a86
  submitted_at: '2026-08-09T19:09:13.751837+00:00'
  updated_at: '2026-08-09T19:09:13.751837+00:00'
oompah.work_branch: OOMPAH-968
---
## Summary

A workflow snapshot collected while a task has no terminal-provenance marker currently does not request the terminal-audit snapshot proof, so an authenticated owner can add a retained marker after collection but before publication and the stale delivery decision may still publish. Scope: make marker absence part of the exact terminal-provenance authority observed and revalidated for terminal Done-task publication, without turning ordinary absent metadata into an operator warning or changing healthy delivery behavior. Preserve the project write lock and workflow job-store publication fence; supersede and roll back any snapshot when provenance changes absent→retained before publication. Relevant code: oompah/orchestrator.py terminal-audit fact source, oompah/work_decision.py if representation changes, oompah/workflow_runtime.py proof selection/publication, and focused tests. Required regression: collect a normal Done-task landing-refresh decision with no marker, add an owner-retained marker immediately before publication, prove publication_authority_changed, no stale delivery authority is published, and no current job is incorrectly retired; retry must observe retained provenance and publish the zero-job terminal decision. Acceptance: absent, retained, and new-revision marker states are all exact publication authority; no malformed payload bypass exists; focused workflow/provenance tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 18:53
---
Implementation is pushed at 92ebd94c2 on OOMPAH-968, based on final OOMPAH-967 head 5adb50e55. Markerless Done tasks now project stable explicit absence authority; healthy absence preserves the normal landing decision, invalid/ambiguous absence fails closed, and the existing locked in-transaction proof detects absent-to-retained mutation. The production regression proves first publication supersedes and rolls back without retiring the exhausted row, then the retained retry publishes zero-job authority and retires it. Verification: 547 focused tests pass; critical Ruff/diff checks pass; three independent reviews are running.
---
author: oompah
created: 2026-08-09 19:03
---
Corrective exact head 514bc9e30 is pushed. A later audit-envelope read failure now preserves scoped malformed zero-job authority; impossible present/non-retained generation-zero markers fail closed in persistence and decision layers; and the runtime matrix proves clean absence publication, clean stale effect supersession/nonclaimability, retained retry, exhausted-row rollback/retirement, retained-to-revision supersession, and unchanged generation-1 publication. Verification: 553 focused tests pass; two independent final reviews report no blockers (189 selected tests plus acceptance review); critical Ruff/diff checks pass.
---
author: oompah
created: 2026-08-09 19:03
---
Exact head 514bc9e30 fences absent-to-retained provenance publication races, fails closed on audit-read and generation-zero edge cases, and proves clean/stale/exhausted convergence. 553 focused tests and two independent reviews are green.
---
author: oompah
created: 2026-08-09 19:06
---
Prior submission is superseded by pushed corrective head 285fc11fe. The supported absent-to-authorize-new-revision path now records the revising owner, reason, and timestamps on its generation-one marker, so the writer, adapter, decision, and publication proof agree. Added direct persistence, production adapter, and truly absent-to-authorize runtime coverage. Verification: 555 focused tests pass; critical Ruff/diff checks pass. Final independent re-reviews are in progress; do not integrate 514bc9e30.
---
author: oompah
created: 2026-08-09 19:09
---
Final exact head 277a99a1c is pushed. Revision and retention timestamps are now distinct: absent-to-authorize records owner/reason/updated_at with generation 1 and leaves marked_at empty until the first actual retain; retained facts still require a real mark timestamp. Verification: 557 focused tests pass; two independent final reviews report no blockers (one reran 193 relevant tests); critical Ruff/diff checks pass. This supersedes every prior submitted head and is the integration candidate.
---
author: oompah
created: 2026-08-09 19:09
---
Final exact head 277a99a1c closes absent-to-retained and absent-to-revision publication races with consistent owner/generation/timestamp authority. 557 focused tests and two independent final reviews are green.
---
<!-- COMMENTS:END -->
