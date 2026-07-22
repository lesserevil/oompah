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
labels: []
assignee: null
created_at: '2026-07-21T20:34:42.931068Z'
updated_at: '2026-07-22T07:53:05.128336Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9f297a26-1c31-4c84-8b9b-fbeaf915aa55
oompah.task_costs:
  total_input_tokens: 210579
  total_output_tokens: 1434
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 210579
      output_tokens: 1434
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 210579
    output_tokens: 1434
    cost_usd: 0.0
    recorded_at: '2026-07-22T07:53:02.080936+00:00'
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
<!-- COMMENTS:END -->
