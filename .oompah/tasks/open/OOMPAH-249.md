---
id: OOMPAH-249
type: task
status: Open
priority: null
title: Wire Release Delivery PR fallback into server backlog service
parent: null
children: []
blocked_by:
- OOMPAH-248
labels:
- focus-complete:duplicate_detector
- needs:feature
assignee: null
created_at: '2026-07-19T19:14:04.819745Z'
updated_at: '2026-07-19T19:15:42.584749Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 0591c4c3-5581-4865-9466-20ae87fa608e
oompah.task_costs:
  total_input_tokens: 214942
  total_output_tokens: 1248
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 214942
      output_tokens: 1248
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 214942
    output_tokens: 1248
    cost_usd: 0.0
    recorded_at: '2026-07-19T19:15:32.513324+00:00'
---
## Summary

Problem

OOMPAH-248 added SCM-backed PR commit discovery for deleted task branches, but the live Trickle release delivery endpoint still returns items=0 and unassociated=7513 after PR #446 merged and the service restarted. The server factory at oompah/server.py around _get_item_backlog_service constructs ItemBacklogService without its new scm and managed_repo constructor arguments. Therefore the fallback condition cannot run in production.

Required implementation

- Update the server-side ItemBacklogService factory to pass the project SCM provider and the canonical owner/repository slug derived from the managed project configuration.
- Ensure cache lifecycle/refresh behavior does not retain an old service instance missing these dependencies after configuration changes or restart.
- Do not change candidate eligibility: tracker Merged evidence remains required and returned PR commits must still be reachable from the default branch.
- Add route-level tests that exercise the real server factory, not only a directly constructed ItemBacklogService.

Tests

- API regression with a Merged native task whose work branch is absent and whose review_number resolves through the mocked SCM provider: GET Release Delivery backlog returns a Not selected primary item.
- Assert the SCM provider receives the project owner/repo slug and review number.
- Negative API case: PR commits not reachable from default branch remain absent.
- Cache/initialization test proves the configured SCM and managed repo reach the service used by the route.

Acceptance criteria

- With the actual server route and a deleted task branch, the PR fallback added in OOMPAH-248 is invoked and produces a queueable Release Delivery item.
- The live Trickle release/0.11 backlog no longer reports zero primary items solely because original task branches were deleted.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 19:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 19:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 19:15
---
Understanding: Screening OOMPAH-249 for an existing equivalent before implementation. I will compare the server-factory wiring and route-level coverage requirements with the related Release Delivery tasks, especially OOMPAH-248.\n\nFocus handoff: duplicate_detector\n\n1. Outcome: No duplicate confirmed. OOMPAH-249 is a distinct follow-up to OOMPAH-248: #248 implemented the ItemBacklogService PR fallback itself; its post-merge validation (#20) identifies the missing server.py construction arguments as the remaining production defect.\n\n2. Evidence reviewed:  across .oompah/tasks/docs/plans and full  records for OOMPAH-248 and OOMPAH-249. OOMPAH-248 is Merged and its required/implemented scope is helper/service-level fallback plus unit regressions. OOMPAH-249 specifically requires wiring  and canonical managed repo through the real server factory, cache lifecycle behavior, and API-route regressions.\n\n3. Remaining work/risks: inspect  factory/cache and existing API tests; pass current project SCM and owner/repo slug to ItemBacklogService; prove deleted-branch fallback through the route while preserving Merged and default-branch reachability gates.\n\n4. Recommended next focus: feature (backend server integration and route-level tests).
---
author: oompah
created: 2026-07-19 19:15
---
Correction to prior handoff comment: shell quoting stripped literal file and command names; the duplicate-screening conclusion is unchanged. Relevant evidence: OOMPAH-248 is Merged and its post-merge validation comment #20 explicitly records the remaining missing server factory arguments. OOMPAH-249 is therefore a distinct follow-up for server.py factory/cache wiring and real API-route regressions, not a duplicate. Recommended next focus: feature.
---
author: oompah
created: 2026-07-19 19:15
---
Agent completed successfully in 50s (216190 tokens)
---
author: oompah
created: 2026-07-19 19:15
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 214.9K in / 1.2K out [216.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 50s
- Log: OOMPAH-249__20260719T191448Z.jsonl
---
author: oompah
created: 2026-07-19 19:15
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
<!-- COMMENTS:END -->
