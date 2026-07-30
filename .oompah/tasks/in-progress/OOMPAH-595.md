---
id: OOMPAH-595
type: feature
status: In Progress
priority: 1
title: Expose separate operator and worker task-auth health signals
parent: OOMPAH-586
children: []
blocked_by:
- OOMPAH-593
- OOMPAH-594
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:56.897824Z'
updated_at: '2026-07-30T15:31:06.172681Z'
work_branch: epic-OOMPAH-586--task-OOMPAH-595
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5599144d8549cf413f0b3bfec2f0109e3cca03737c85cfab4397a53213de6eb8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T15:30:33.099442+00:00'
  matched_identifiers: []
  evidence: "I acknowledge the coordination message. The fact that OOMPAH-594 is marked\
    \ as both a \"dependency\" and \"epic-sibling\" of OOMPAH-595 (not a duplicate)\
    \ reinforces my conclusion:\n\n**Dependency Relationship Analysis:**\n- If OOMPAH-595\
    \ were a duplicate of OOMPAH-594, there would be no blocking dependency\u2014\
    the tasks would be consolidated into one.\n- The blocking dependency indicates\
    \ OOMPAH-595 is sequential work that builds on or requires OOMPAH-594's implementation\
    \ first.\n- Epic-sibling status confirms they are distinct tasks within the same\
    \ parent epic (OOMPAH-586).\n\nThis confirms the tasks are related but separate\
    \ pieces of work within the authentication health monitoring epic.\n\n---\n\n\
    **Focus handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** No existing task in open, backlog, merged,\
    \ or archived states covers OOMPAH-595's scope (separate operator Basic-auth and\
    \ worker task-handoff health signals with 401/403 redaction and credential masking).\
    \ OOMPAH-594 is a blocking dependency, not a prior implementation\u2014the dependency\
    \ relationship confirms they are distinct, sequential tasks within epic OOMPAH-586,\
    \ not duplicates."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: 92712307-9fad-499b-a457-4e1550e270bc
oompah.work_branch: epic-OOMPAH-586--task-OOMPAH-595
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-586--task-OOMPAH-595
  base_branch: epic-OOMPAH-586
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:30:44.767650+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 859
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 859
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 859
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:30:33.098859+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-595__20260730T152855Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-586--task-OOMPAH-595
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:30:33.105446+00:00'
---
## Summary

Implementation scope

Add safe health probes and alerts that distinguish operator Basic-auth configuration drift from scoped task-handoff capability failures. Count/redact 401 and 403 outcomes by authentication path, report whether a worker token was minted and accepted without reporting the token, and provide actionable operator guidance. Avoid alerting on intentional unrelated-task denial. Relevant files include task_handoff instrumentation, task CLI/server middleware, service health/alerts APIs, dashboard, and docs troubleshooting.

Tests

Cover healthy operator and worker paths, stale operator credentials, missing/expired worker token, intentional scope denial, alert clear after recovery, restart persistence where appropriate, and redaction. Run focused auth/health/UI tests and make test.

Acceptance criteria

Operators can tell which authentication plane failed and how to recover it; secrets/capabilities never appear in logs, state JSON, alerts, or task comments.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 15:22
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:27
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 23
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 4m 20s
- Log: OOMPAH-595__20260730T152251Z.jsonl
---
author: oompah
created: 2026-07-30 15:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:30
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 50, Tool calls: 21
- Tokens: 10 in / 859 out [869 total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 47s
- Log: OOMPAH-595__20260730T152855Z.jsonl
---
author: oompah
created: 2026-07-30 15:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 15:30
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 15:31
---
Agent completed successfully in 22s (47464 tokens)
---
author: oompah
created: 2026-07-30 15:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 1
- Tokens: 47.0K in / 501 out [47.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 22s
- Log: OOMPAH-595__20260730T153048Z.jsonl
---
<!-- COMMENTS:END -->
