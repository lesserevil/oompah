---
id: OOMPAH-289
type: task
status: In Progress
priority: 1
title: Harden focus triage and other model-only decisions against external instructions
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-288
labels: []
assignee: null
created_at: '2026-07-21T14:51:55.684579Z'
updated_at: '2026-07-21T22:30:21.996050Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: eb80d94c-65cb-4381-ad9a-438e3dba1b3e
oompah.task_costs:
  total_input_tokens: 479334
  total_output_tokens: 2697
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 479334
      output_tokens: 2697
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 479334
    output_tokens: 2697
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:26:22.068916+00:00'
---
## Summary

Update focus triage and every model-only decision path found in the threat model. Pass untrusted title/body/comment text only through the shared safe renderer, use structured output validation, and retain deterministic validation/fallbacks. Ensure injections cannot select arbitrary foci, alter priority, bypass approval, or create follow-up work.

Dependency: Render untrusted content in explicit prompt data boundaries.

Tests: mock model calls with injected content and malicious model output; verify invalid outputs are rejected, deterministic fallback is used, and no unauthorized side effect occurs.

Acceptance criteria: triage remains constrained to configured foci and server-side eligibility rules regardless of external text.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 22:26
---
Agent completed successfully in 77s (482031 tokens)
---
author: oompah
created: 2026-07-21 22:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 9
- Tokens: 479.3K in / 2.7K out [482.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 17s
- Log: OOMPAH-289__20260721T222507Z.jsonl
---
author: oompah
created: 2026-07-21 22:26
---
Agent completed without closing this issue (77s (482031 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 22:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:30
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
