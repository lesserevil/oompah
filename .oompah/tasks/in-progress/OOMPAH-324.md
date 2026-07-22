---
id: OOMPAH-324
type: task
status: In Progress
priority: 2
title: Generalize external issue intake and provenance for GitLab
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-323
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T20:34:26.149163Z'
updated_at: '2026-07-22T05:59:48.976413Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 387fd4e0-fad5-4b98-84a8-7a4eb20cb91e
oompah.task_costs:
  total_input_tokens: 1740383
  total_output_tokens: 14183
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1740383
      output_tokens: 14183
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 226948
    output_tokens: 1466
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:46:54.129831+00:00'
  - profile: default
    model: unknown
    input_tokens: 543450
    output_tokens: 5235
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:55:43.007120+00:00'
  - profile: standard
    model: unknown
    input_tokens: 969985
    output_tokens: 7482
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:59:19.039915+00:00'
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, GitLab implementation.

Refactor github_intake_bridge into a forge-neutral external-intake service while keeping compatibility wrappers for existing callers. Add GitLab native-task intake: import issues and comments once, store provider-specific external metadata under oompah.external.gitlab, synchronize terminal task comments/closure back to GitLab, and route GitLab webhook events to the bridge. Extend prompt provenance enums, wrappers, and threat-model documentation so GitLab issue/MR/comment/webhook/CI text is untrusted.

Tests:
- GitHub regression suite remains green through compatibility paths.
- GitLab issue create/update/comment/close/reopen import and idempotency fixtures.
- Terminal mirror behavior and metadata lookup.
- Prompt delimiter/provenance tests proving GitLab content cannot become trusted instructions.

Acceptance criteria:
- Native Markdown projects may enable GitLab issue intake with the same behavior as GitHub intake.
- External IDs and metadata never collide across providers.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:46
---
Understanding: Performing duplicate screening only. I will compare GitLab external-intake, provenance, and terminal-mirroring scope against the GitLab parity siblings and historic GitHub intake work before handing off if this is distinct.
---
author: oompah
created: 2026-07-22 05:46
---
Discovery: No confirmed duplicate. Reviewed OOMPAH-323 (GitLab Issues tracker; explicitly excludes native external intake), OOMPAH-325 (GitLab project-hook lifecycle and generic webhook normalization), OOMPAH-319 (forge configuration/migration), and OOMPAH-329 (final acceptance suite). Historic GitHub intake tasks cover only GitHub-specific lifecycle fixes. None owns forge-neutral native intake, provider-qualified external metadata, GitLab comment/issue idempotency, terminal mirroring, or GitLab provenance boundaries.
---
author: oompah
created: 2026-07-22 05:46
---
Focus handoff: duplicate_detector

1. Outcome: no duplicate confirmed; OOMPAH-324 is the distinct GitLab native external-intake/provenance child.
2. Evidence: searched task records and plans for GitLab, forge parity, external intake, and github_intake_bridge; reviewed OOMPAH-323, OOMPAH-325, OOMPAH-319, and OOMPAH-329 in full. OOMPAH-323 explicitly excludes this scope, and OOMPAH-325 stops at hook lifecycle/event normalization.
3. Remaining work/risks: refactor github_intake_bridge behind compatibility wrappers; implement provider-qualified GitLab import, idempotency, terminal mirroring, webhook routing, and untrusted prompt provenance/docs without cross-provider external-ID collisions.
4. Recommended next focus: feature.
---
author: oompah
created: 2026-07-22 05:46
---
Agent completed successfully in 49s (228414 tokens)
---
author: oompah
created: 2026-07-22 05:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 226.9K in / 1.5K out [228.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 49s
- Log: OOMPAH-324__20260722T054607Z.jsonl
---
author: oompah
created: 2026-07-22 05:47
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 05:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:53
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-22 05:55
---
Agent completed successfully in 122s (548685 tokens)
---
author: oompah
created: 2026-07-22 05:55
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 9
- Tokens: 543.5K in / 5.2K out [548.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 2s
- Log: OOMPAH-324__20260722T055343Z.jsonl
---
author: oompah
created: 2026-07-22 05:55
---
Agent completed without closing this issue (122s (548685 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 05:56
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 05:56
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-22 05:59
---
Agent completed successfully in 189s (977467 tokens)
---
author: oompah
created: 2026-07-22 05:59
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 13
- Tokens: 970.0K in / 7.5K out [977.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 9s
- Log: OOMPAH-324__20260722T055613Z.jsonl
---
author: oompah
created: 2026-07-22 05:59
---
Agent completed without closing this issue (189s (977467 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-22 05:59
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-22 05:59
---
Focus: Technical Writer
---
<!-- COMMENTS:END -->
