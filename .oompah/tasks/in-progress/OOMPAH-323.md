---
id: OOMPAH-323
type: task
status: In Progress
priority: 1
title: Implement GitLab Issues tracker with Oompah status governance
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-319
labels: []
assignee: null
created_at: '2026-07-21T20:34:25.248230Z'
updated_at: '2026-07-21T23:04:43.850502Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b43604be-7377-4fa3-99cc-04c938a90234
oompah.task_costs:
  total_input_tokens: 190106
  total_output_tokens: 1613
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 190106
      output_tokens: 1613
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 190106
    output_tokens: 1613
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:04:27.163693+00:00'
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, GitLab implementation.

Add GitLabIssueTracker implementing every TrackerProtocol operation through GitLab Issues, notes, labels, and issue links. Use oompah:status:* labels for canonical state, preserve priority/type/parent/dependency behavior, enforce authorized status-label actors, audit/revert unauthorized transitions, and support comments, attachments metadata, archive/reopen, and issue detail. Make identifiers globally unambiguous for nested GitLab namespaces.

Do not implement native external intake in this task.

Tests:
- Contract suite for every TrackerProtocol method.
- Label/status lifecycle, parent/dependency links, comment and metadata round trips, authorization rejection, pagination, and GitLab API failures.
- Existing GitHub tracker behavior remains unchanged.

Acceptance criteria:
- A GitLab Issues project can operate the entire Oompah task and epic lifecycle without GitHub code paths.
- Status safety and audit behavior match GitHub-backed tracking.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:04
---
Agent completed successfully in 44s (191719 tokens)
---
author: oompah
created: 2026-07-21 23:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 190.1K in / 1.6K out [191.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 44s
- Log: OOMPAH-323__20260721T230345Z.jsonl
---
author: oompah
created: 2026-07-21 23:04
---
Agent completed without closing this issue (44s (191719 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
