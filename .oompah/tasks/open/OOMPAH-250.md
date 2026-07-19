---
id: OOMPAH-250
type: task
status: Open
priority: null
title: Use the selected project's tracker for Release Delivery backlog discovery
parent: null
children: []
blocked_by:
- OOMPAH-249
labels: []
assignee: null
created_at: '2026-07-19T21:11:24.255407Z'
updated_at: '2026-07-19T21:12:16.075311Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem

Despite OOMPAH-248 and OOMPAH-249 being merged and deployed, the live Trickle release/0.11 backlog still returns items=0 and unassociated=7513. The route api_release_delivery_backlog in oompah/server.py passes getattr(orch, "tracker", None) to ItemBacklogService.get_backlog(). In managed-project mode that is the legacy/global tracker, not Trickle’s native tracker. ItemBacklogService therefore fetches no Trickle Merged tasks or epics, so neither work-branch nor PR fallback discovery can run.

Required implementation

- In api_release_delivery_backlog, resolve the tracker using the existing project-scoped server helper (_get_tracker(orch, project_id)) or the equivalent orch._tracker_for_project(project.id). Do not use the legacy orch.tracker for a managed project.
- Preserve best-effort title enrichment behavior, but candidate discovery must receive the tracker belonging to the selected project.
- Handle tracker resolution failures as the route already handles tracker/inventory errors; do not silently substitute another project tracker.
- Keep the SCM/repository wiring from OOMPAH-249 unchanged.

Tests

- Multi-project API regression: configure a legacy/default tracker plus a distinct Trickle native tracker. A Merged Trickle task with a deleted work branch and review_number must appear as a Not selected candidate only when the request names the Trickle project.
- Assert the legacy tracker is not queried for a managed-project backlog request.
- Verify an unavailable project tracker yields the documented error/cached behavior, not candidates from a different project.
- Retain a single-project/legacy-mode compatibility test.

Acceptance criteria

- The Trickle release/0.11 endpoint uses Trickle task metadata and returns eligible Merged tasks/epics as release candidates.
- Candidate rows are never sourced from another project tracker.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

