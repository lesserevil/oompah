---
id: OOMPAH-298
type: task
status: In Progress
priority: 1
title: Inject task-relevant repository maps into agent focus startup prompts
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-296
- OOMPAH-297
labels: []
assignee: null
created_at: '2026-07-21T15:14:08.542161Z'
updated_at: '2026-07-21T23:00:51.690151Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 147608ab-c362-470b-b6ac-11da9096b875
oompah.task_costs:
  total_input_tokens: 182988
  total_output_tokens: 1405
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 182988
      output_tokens: 1405
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 182988
    output_tokens: 1405
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:00:32.918132+00:00'
---
## Summary

Integrate repository maps into the agent prompt assembly path. Resolve the agent checkout commit, load only a fresh matching artifact, derive seeds from the task title, description, linked files, PR/commit data, and focus handoff, then render a token-budgeted map with OOMPAH-296. Insert it into every focus startup prompt in a clearly labeled untrusted repository-context block. Preserve the existing prompt when no fresh map is available. Do not expose data from another project, branch, or commit.\n\nTests:\n- Prompt tests verify a fresh matching map is included for each focus type.\n- Verify stale SHA, wrong project, missing artifact, and rendering failure omit the map and retain normal startup.\n- Verify the configured token ceiling is respected and task-specific seeds affect selection.\n- Verify the prompt labels repository text as data, not instructions, and cannot override system/task instructions.\n\nAcceptance criteria:\n- Newly started agents receive a bounded, relevant map without needing extra model round trips.\n- No startup is blocked by map generation or retrieval failure.\n- Prompt provenance and SHA are available in agent diagnostics.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:00
---
Agent completed successfully in 40s (184393 tokens)
---
author: oompah
created: 2026-07-21 23:00
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 4
- Tokens: 183.0K in / 1.4K out [184.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 40s
- Log: OOMPAH-298__20260721T225954Z.jsonl
---
author: oompah
created: 2026-07-21 23:00
---
Agent completed without closing this issue (40s (184393 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 23:00
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 23:00
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
