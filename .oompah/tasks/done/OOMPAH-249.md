---
id: OOMPAH-249
type: task
status: Done
priority: null
title: Wire Release Delivery PR fallback into server backlog service
parent: null
children: []
blocked_by:
- OOMPAH-248
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-19T19:14:04.819745Z'
updated_at: '2026-07-19T19:25:03.735672Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 483785da-a7c4-496a-9263-b689f09a5163
oompah.task_costs:
  total_input_tokens: 215012
  total_output_tokens: 3104
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 215012
      output_tokens: 3104
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 214942
    output_tokens: 1248
    cost_usd: 0.0
    recorded_at: '2026-07-19T19:15:32.513324+00:00'
  - profile: standard
    model: unknown
    input_tokens: 70
    output_tokens: 1856
    cost_usd: 0.0
    recorded_at: '2026-07-19T19:25:00.662310+00:00'
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
author: oompah
created: 2026-07-19 19:15
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 19:15
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-19 19:16
---
Understanding: I am the Test Engineer for this task. My goal is to write route-level tests that exercise the real server factory (_get_item_backlog_service in oompah/server.py) with the SCM and managed_repo arguments added by OOMPAH-248. I will: (1) explore the existing ItemBacklogService and server factory code; (2) identify existing test patterns for the release delivery route; (3) write API regression tests covering the deleted-branch PR fallback via the server factory; (4) verify make test passes.
---
author: oompah
created: 2026-07-19 19:18
---
Discovery: Found the key code. The _get_item_backlog_service factory (oompah/server.py:3763) creates ItemBacklogService without scm or managed_repo arguments. ItemBacklogService accepts both (OOMPAH-248), but the server factory doesn't pass them. I need to: (1) update the factory to call detect_provider and extract_repo_slug on project.repo_url and pass them; (2) update the cache key to (project_id, repo_url) so config changes invalidate the cache; (3) write route-level tests that exercise the real factory without mocking _get_item_backlog_service.
---
author: oompah
created: 2026-07-19 19:24
---
Implementation: Two changes made.\n\n1. oompah/server.py _get_item_backlog_service (lines 3758-3822): Updated factory to call detect_provider(repo_url) and extract_repo_slug(repo_url) from project.repo_url, then pass scm and managed_repo to ItemBacklogService. Cache key changed from project_id alone to (project_id, repo_url) so a config change (different host/slug) invalidates the stale entry and forces a fresh service with the correct SCM.\n\n2. tests/test_server_release_delivery_backlog_factory.py (new file, 12 tests): Route-level tests that exercise the real _get_item_backlog_service factory without mocking it. Tests cover: (a) factory_passes_scm_to_service, (b) factory_passes_managed_repo, (c) no_repo_url → graceful, (d) SCM detection failure → graceful, (e) cache keyed by repo_url, (f) same key returns same instance, (g) primary API regression (deleted branch + PR fallback → not_selected), (h) SCM receives correct owner/repo and review_number, (i) negative case (PR SHA not in main), (j) no review_number → excluded, (k) cache has scm/managed_repo after first request, (l) new repo_url evicts stale entry.
---
author: oompah
created: 2026-07-19 19:24
---
Verification: make test passes — 9207 passed, 36 skipped, 12 warnings, 0 failures (130s). All 12 new factory/route tests pass. Verified that the old factory (without scm/managed_repo wiring) would fail the key assertions: svc._scm is None and svc._managed_repo is None with the old code.
---
author: oompah
created: 2026-07-19 19:24
---
Completion: Delivered OOMPAH-249.\n\nFeature: Updated _get_item_backlog_service in oompah/server.py to pass scm (from detect_provider) and managed_repo (from extract_repo_slug) to ItemBacklogService. Cache key is now (project_id, repo_url) to handle config changes. SCM detection failure is caught gracefully.\n\nTests: New file tests/test_server_release_delivery_backlog_factory.py with 12 route-level tests — 6 factory unit tests and 6 API tests that exercise the real server factory without mocking _get_item_backlog_service. Covers the primary regression (deleted branch + review_number → not_selected item via SCM fallback), SCM args assertion, negative case (PR SHA not reachable from main), cache lifecycle, and initialization.\n\nmake test: 9207 passed, 0 failures.\n\nBranch pushed to origin/OOMPAH-249.
---
author: oompah
created: 2026-07-19 19:24
---
Wired SCM provider and managed_repo slug into _get_item_backlog_service server factory. Cache now keyed by (project_id, repo_url) to handle config changes. Added 12 route-level tests in test_server_release_delivery_backlog_factory.py covering the deleted-branch PR fallback through the real server factory. make test passes (9207 passed).
---
author: oompah
created: 2026-07-19 19:25
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 49
- Tokens: 70 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 9s
- Log: OOMPAH-249__20260719T191558Z.jsonl
---
<!-- COMMENTS:END -->
