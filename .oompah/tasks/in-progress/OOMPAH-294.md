---
id: OOMPAH-294
type: task
status: In Progress
priority: 1
title: Define repository-map artifact and state-branch lifecycle
parent: OOMPAH-293
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T15:13:47.496504Z'
updated_at: '2026-07-21T15:46:25.313150Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2898ad89-dacf-4db5-8e71-22cf17fe3fc7
oompah.task_costs:
  total_input_tokens: 275556
  total_output_tokens: 1584
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 275556
      output_tokens: 1584
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 275556
    output_tokens: 1584
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:46:09.606215+00:00'
---
## Summary

Write the implementation design and add the core model/types for a repository-map artifact. Define a versioned, deterministic JSON schema containing: repository identity, analyzed commit SHA, generator version, indexed files, symbol tags, relationship edges, generation timestamp, and rendering metadata. Define the exact state-branch path, atomic-write procedure, freshness rule (map SHA must equal checkout SHA), retention/pruning policy, and behavior for unavailable or unsupported repositories.\n\nDo not add parsing or prompt injection in this task. The artifact must be data only; it must never be executed or interpreted as instructions.\n\nTests:\n- Unit-test schema serialization/deserialization and schema-version rejection.\n- Unit-test deterministic output for identical input and invalidation when the commit SHA changes.\n- Unit-test all path construction and state-branch writes remain within the project state namespace.\n\nAcceptance criteria:\n- A documented schema and lifecycle exist in plans/.\n- Code exposes a typed artifact contract for later tasks.\n- Artifacts are keyed by repository identity and commit SHA and are safe to read only when fresh.\n- Tests pass through the project Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 15:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 15:46
---
Agent completed successfully in 47s (277140 tokens)
---
author: oompah
created: 2026-07-21 15:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 6
- Tokens: 275.6K in / 1.6K out [277.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 47s
- Log: OOMPAH-294__20260721T154528Z.jsonl
---
author: oompah
created: 2026-07-21 15:46
---
Agent completed without landing — no commits found on origin for branch `epic-OOMPAH-293`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
