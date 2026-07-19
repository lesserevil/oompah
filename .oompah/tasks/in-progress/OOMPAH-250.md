---
id: OOMPAH-250
type: task
status: In Progress
priority: null
title: Use the selected project's tracker for Release Delivery backlog discovery
parent: null
children: []
blocked_by:
- OOMPAH-249
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-19T21:11:24.255407Z'
updated_at: '2026-07-19T21:14:02.629513Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3fec8cb8-2e6d-4ac3-aebb-5b4ce3b06605
oompah.task_costs:
  total_input_tokens: 12
  total_output_tokens: 2847
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 12
      output_tokens: 2847
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 12
    output_tokens: 2847
    cost_usd: 0.0
    recorded_at: '2026-07-19T21:13:39.412928+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 21:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 21:12
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 21:13
---
Focus handoff: duplicate_detector

1. Outcome: OOMPAH-250 is NOT a duplicate. Duplicate screening complete.

Candidates reviewed:
- OOMPAH-248 (Merged, PR #446): Added _find_pr_commits_in_main() and PR fallback in ItemBacklogService for deleted-branch discovery. Post-merge validation found factory not passing scm/managed_repo — filed OOMPAH-249.
- OOMPAH-249 (Merged, PR #447): Wired SCM + managed_repo into _get_item_backlog_service server factory. Post-merge validation found final gap: api_release_delivery_backlog still passes orch.tracker (legacy/global) to get_backlog(), so Trickle Merged tasks are never fetched — filed OOMPAH-250.

OOMPAH-250 is the distinct third step in the fix chain. Neither OOMPAH-248 nor OOMPAH-249 addresses the tracker-resolution logic inside api_release_delivery_backlog itself.

2. Relevant files and evidence:
- oompah/server.py — api_release_delivery_backlog route; currently passes getattr(orch, 'tracker', None) to ItemBacklogService.get_backlog(); needs to use _get_tracker(orch, project_id) or equivalent project-scoped helper instead
- oompah/server.py — _get_tracker helper (if it exists) or orch._tracker_for_project(project.id) is the project-scoped tracker API to use
- oompah/release_delivery_backlog.py — ItemBacklogService.get_backlog(tracker=...) receives whatever tracker the route passes
- tests/test_server_release_delivery_backlog_factory.py — existing route-level test patterns from OOMPAH-249

3. Remaining work:
- In api_release_delivery_backlog, replace getattr(orch, 'tracker', None) with project-scoped tracker resolution
- Handle tracker resolution failures (not silently substitute another tracker)
- Keep SCM/repo wiring from OOMPAH-249 unchanged
- Add multi-project regression tests: legacy + Trickle tracker, Merged Trickle task with deleted branch and review_number appears only for the Trickle project request
- Assert legacy tracker is not queried for a managed-project backlog request
- Test unavailable project tracker yields documented error, not candidates from another project
- Retain single-project/legacy-mode compatibility test
- make test passes

4. Recommended next focus: feature (backend fix to api_release_delivery_backlog in server.py + multi-project route regression tests)
---
author: oompah
created: 2026-07-19 21:13
---
Agent completed successfully in 74s (2859 tokens)
---
author: oompah
created: 2026-07-19 21:13
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 20, Tool calls: 15
- Tokens: 12 in / 2.8K out [2.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 14s
- Log: OOMPAH-250__20260719T211230Z.jsonl
---
author: oompah
created: 2026-07-19 21:13
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-19 21:13
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 21:14
---
Focus: Test Engineer
---
<!-- COMMENTS:END -->
