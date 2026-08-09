---
id: OOMPAH-968
type: bug
status: Backlog
priority: 1
title: Fence absent-to-retained provenance changes during workflow publication
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T18:30:50.075307Z'
updated_at: '2026-08-09T18:30:50.075307Z'
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

