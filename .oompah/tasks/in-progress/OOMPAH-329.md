---
id: OOMPAH-329
type: task
status: In Progress
priority: 1
title: Add cross-forge GitLab acceptance and migration test suite
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-321
- OOMPAH-322
- OOMPAH-323
- OOMPAH-324
- OOMPAH-325
- OOMPAH-326
- OOMPAH-327
- OOMPAH-328
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T20:34:42.931068Z'
updated_at: '2026-07-22T07:55:30.412685Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b1ce6826-3ed7-43ae-acf3-c3d6c4bd75f7
oompah.task_costs:
  total_input_tokens: 210602
  total_output_tokens: 5629
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 210602
      output_tokens: 5629
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 210579
    output_tokens: 1434
    cost_usd: 0.0
    recorded_at: '2026-07-22T07:53:02.080936+00:00'
  - profile: standard
    model: unknown
    input_tokens: 23
    output_tokens: 4195
    cost_usd: 0.0
    recorded_at: '2026-07-22T07:55:00.906174+00:00'
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Migration, testing, and acceptance.

Add the final cross-forge acceptance layer after all GitLab feature tasks land. Build network-free GitLab HTTP fixtures and a provider contract suite shared with GitHub. Add gated integration configuration for GitLab.com and a GitLab 17.x self-managed fixture; standard tests must not require credentials or network. Verify existing GitHub projects load unchanged and GitLab projects cover setup, task lifecycle, native intake, MR/pipeline lifecycle, webhook/polling fallback, selected release delivery, and CI remediation.

Tests:
- Execute the shared provider and tracker contracts for both forges.
- Migration fixture for persisted pre-forge GitHub project records.
- Gated live GitLab.com and self-managed smoke tests, skipped with explicit reason when credentials are absent.

Acceptance criteria:
- The full plan acceptance criteria are demonstrably covered by automated tests.
- No standard test needs a GitLab token, public endpoint, or live GitLab service.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 07:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 07:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 07:53
---
Agent completed successfully in 58s (212013 tokens)
---
author: oompah
created: 2026-07-22 07:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 210.6K in / 1.4K out [212.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 58s
- Log: OOMPAH-329__20260722T075206Z.jsonl
---
author: oompah
created: 2026-07-22 07:53
---
Agent completed without closing this issue (58s (212013 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 07:53
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 07:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 07:54
---
Focus handoff: duplicate_detector

Outcome: No duplicate found. OOMPAH-329 is unique in the task tracker.

Evidence:
- Searched all task state directories (in-progress, open, backlog, done, merged, archived)
- Found no tasks covering cross-forge GitLab acceptance/migration testing
- Closest related tasks: OOMPAH-6 (GitHub intake auth) and OOMPAH-259 (state branch migration) - both unrelated
- The plan reference plans/gitlab-forge-parity.md exists; OOMPAH-329 covers its 'Migration, testing, and acceptance' section specifically
- Blocking tasks OOMPAH-321 through OOMPAH-328 have no task files in the filesystem (likely not yet created or are managed externally)

Relevant files:
- plans/gitlab-forge-parity.md — full spec for the test suite
- tests/ — existing test patterns to follow
- Blockers OOMPAH-321 through OOMPAH-328 reference the GitLab feature implementation tasks this test suite depends on

Remaining work:
- Build network-free GitLab HTTP fixtures
- Provider contract suite shared with GitHub
- Migration fixture for pre-forge GitHub project records
- Gated live GitLab.com and self-managed smoke tests (skipped without credentials)
- Verify make test passes

Recommended next focus: test (implementation of the test suite)
---
author: oompah
created: 2026-07-22 07:55
---
Agent completed successfully in 101s (4218 tokens)
---
author: oompah
created: 2026-07-22 07:55
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 40, Tool calls: 32
- Tokens: 23 in / 4.2K out [4.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 41s
- Log: OOMPAH-329__20260722T075321Z.jsonl
---
author: oompah
created: 2026-07-22 07:55
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 07:55
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 07:55
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 07:55
---
Understanding: I will identify the existing forge/provider interfaces and test conventions, then add network-free shared contract, migration, and credential-gated smoke coverage for GitHub and GitLab. I will verify with the project Makefile test target.
---
<!-- COMMENTS:END -->
