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
updated_at: '2026-08-09T19:03:15.470726Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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
<!-- COMMENTS:END -->
