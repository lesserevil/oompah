---
id: OOMPAH-321
type: task
status: In Progress
priority: 1
title: Complete GitLab Merge Request provider parity
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-320
labels: []
assignee: null
created_at: '2026-07-21T20:33:51.110283Z'
updated_at: '2026-07-21T23:23:55.142142Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 104a0df8-ffe4-4374-9593-8d73a7d75081
oompah.task_costs:
  total_input_tokens: 390372
  total_output_tokens: 2376
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 390372
      output_tokens: 2376
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 390372
    output_tokens: 2376
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:23:35.814488+00:00'
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, GitLab implementation.

Implement GitLabProvider against the forge-neutral SCM contract for GitLab.com and configurable GitLab 17+ hosts. Handle nested namespace project IDs, URL encoding, pagination, retries, rate limits, redacted errors, MR list/detail/find/create/rebase/merge/close, labels, notes, changed files, commits, reviewers, approvals, draft/WIP, conflicts, divergence, and mergeability. Preserve history: do not force squash. Implement normal GitLab auto-merge through merge_when_pipeline_succeeds; return actionable policy/approval errors and do not implement merge trains.

Tests:
- HTTP fixtures for GitLab.com and self-managed base URL/nested namespace requests.
- Every SCM contract operation, pagination, auth failure, conflict, unavailable MR, label preservation, history-preserving merge, and auto-merge rejection.

Acceptance criteria:
- GitLab MRs behave equivalently to GitHub PRs for all supported SCM operations.
- No request leaks an access token in logs or errors.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:22
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:23
---
Agent completed successfully in 63s (392748 tokens)
---
author: oompah
created: 2026-07-21 23:23
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 10
- Tokens: 390.4K in / 2.4K out [392.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 3s
- Log: OOMPAH-321__20260721T232234Z.jsonl
---
author: oompah
created: 2026-07-21 23:23
---
Agent completed without closing this issue (63s (392748 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 23:23
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 23:23
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
